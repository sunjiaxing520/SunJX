import { timingSafeEqual } from 'node:crypto';
import { createServer, IncomingMessage, ServerResponse } from 'node:http';
import { URL } from 'node:url';

import {
  DEFAULT_MODEL,
  hasConfiguredSunoCookie,
  sunoApi
} from './lib/SunoApi';

const host = process.env.COMPAT_HOST || '127.0.0.1';
const port = Number.parseInt(process.env.COMPAT_PORT || '3000', 10);
const internalToken = process.env.INTERNAL_API_TOKEN || '';
const maxBodyBytes = 256 * 1024;
const exposedRoutes = [
  'GET /api/health',
  'GET /api/get',
  'GET /api/get_limit',
  'GET /api/clip',
  'GET /api/get_aligned_lyrics',
  'GET /api/persona',
  'POST /api/generate',
  'POST /api/custom_generate',
  'POST /api/extend_audio',
  'POST /api/generate_lyrics',
  'POST /api/concat',
  'POST /api/generate_stems'
];

if (!internalToken) {
  throw new Error('INTERNAL_API_TOKEN is required.');
}

if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error('COMPAT_PORT must be a valid TCP port.');
}

type JsonRecord = Record<string, unknown>;

class HttpError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details?: JsonRecord
  ) {
    super(message);
  }
}

const server = createServer(async (request, response) => {
  try {
    await handleRequest(request, response);
  } catch (error) {
    sendFailure(response, error);
  }
});

server.requestTimeout = 65_000;
server.headersTimeout = 10_000;
server.keepAliveTimeout = 5_000;

server.listen(port, host, () => {
  console.log(`Blue Music Suno compatibility service listening on http://${host}:${port}`);
});

server.on('error', error => {
  console.error('Compatibility service failed:', error);
  process.exitCode = 1;
});

async function handleRequest(
  request: IncomingMessage,
  response: ServerResponse
): Promise<void> {
  if (request.method === 'OPTIONS') {
    response.writeHead(204, {
      Allow: 'GET, POST, OPTIONS',
      'Cache-Control': 'no-store'
    });
    response.end();
    return;
  }

  requireInternalToken(request);

  if (request.headers.cookie) {
    throw new HttpError(
      400,
      'INBOUND_COOKIE_FORBIDDEN',
      'Cookies must be configured only inside the isolated compatibility service.'
    );
  }

  const url = new URL(request.url || '/', `http://${host}:${port}`);

  if (request.method === 'GET' && url.pathname === '/api/health') {
    const cookieConfigured = hasConfiguredSunoCookie();
    sendJson(response, 200, {
      status: cookieConfigured ? 'ready' : 'waiting_cookie',
      service: 'blue-music-suno-compat',
      upstream: 'gcui-art/suno-api',
      captcha_mode: 'human_verification',
      cookie_configured: cookieConfigured,
      routes: exposedRoutes
    });
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/get_limit') {
    const limit = await (await sunoApi()).get_credits();
    sendJson(response, 200, limit);
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/get') {
    const ids = url.searchParams.get('ids');
    const page = url.searchParams.get('page') || undefined;
    const result = await (await sunoApi()).get(
      ids ? ids.split(',').filter(Boolean) : undefined,
      page
    );
    sendJson(response, 200, result);
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/clip') {
    const clipId = requireQueryString(
      url,
      'id',
      'CLIP_ID_REQUIRED',
      'id is required.'
    );
    const result = await (await sunoApi()).getClip(clipId);
    sendJson(response, 200, result);
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/get_aligned_lyrics') {
    const songId = requireQueryString(
      url,
      'song_id',
      'SONG_ID_REQUIRED',
      'song_id is required.'
    );
    const result = await (await sunoApi()).getLyricAlignment(songId);
    sendJson(response, 200, result);
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/persona') {
    const personaId = requireQueryString(
      url,
      'id',
      'PERSONA_ID_REQUIRED',
      'id is required.'
    );
    const result = await (await sunoApi()).getPersonaPaginated(
      personaId,
      positiveIntegerParam(url.searchParams.get('page'), 1)
    );
    sendJson(response, 200, result);
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/generate') {
    const body = await readJsonBody(request);
    const result = await (await sunoApi()).generate(
      asString(body.prompt),
      Boolean(body.make_instrumental),
      asOptionalString(body.model) || DEFAULT_MODEL,
      Boolean(body.wait_audio)
    );
    sendJson(response, 200, result);
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/custom_generate') {
    const body = await readJsonBody(request);
    const result = await (await sunoApi()).custom_generate(
      asString(body.prompt),
      asString(body.tags),
      asString(body.title),
      Boolean(body.make_instrumental),
      asOptionalString(body.model) || DEFAULT_MODEL,
      Boolean(body.wait_audio),
      asOptionalString(body.negative_tags)
    );
    sendJson(response, 200, result);
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/extend_audio') {
    const body = await readJsonBody(request);
    const audioId = asString(body.audio_id);
    if (!audioId) {
      throw new HttpError(400, 'AUDIO_ID_REQUIRED', 'audio_id is required.');
    }
    const result = await (await sunoApi()).extendAudio(
      audioId,
      asString(body.prompt),
      asFiniteNumber(body.continue_at) ?? 0,
      asString(body.tags),
      asString(body.negative_tags),
      asString(body.title),
      asOptionalString(body.model) || DEFAULT_MODEL,
      Boolean(body.wait_audio)
    );
    sendJson(response, 200, result);
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/generate_lyrics') {
    const body = await readJsonBody(request);
    const prompt = requireBodyString(
      body.prompt,
      'PROMPT_REQUIRED',
      'prompt is required.'
    );
    const result = await (await sunoApi()).generateLyrics(prompt);
    sendJson(response, 200, result);
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/concat') {
    const body = await readJsonBody(request);
    const clipId = requireBodyString(
      body.clip_id,
      'CLIP_ID_REQUIRED',
      'clip_id is required.'
    );
    const result = await (await sunoApi()).concatenate(clipId);
    sendJson(response, 200, result);
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/generate_stems') {
    const body = await readJsonBody(request);
    const audioId = requireBodyString(
      body.audio_id,
      'AUDIO_ID_REQUIRED',
      'audio_id is required.'
    );
    const result = await (await sunoApi()).generateStems(audioId);
    sendJson(response, 200, result);
    return;
  }

  throw new HttpError(404, 'ROUTE_NOT_FOUND', 'Route not found.');
}

function requireInternalToken(request: IncomingMessage): void {
  const authorization = request.headers.authorization || '';
  const supplied = authorization.startsWith('Bearer ')
    ? authorization.slice('Bearer '.length)
    : '';
  const expectedBytes = Buffer.from(internalToken);
  const suppliedBytes = Buffer.from(supplied);
  const valid =
    expectedBytes.length === suppliedBytes.length &&
    timingSafeEqual(expectedBytes, suppliedBytes);

  if (!valid) {
    throw new HttpError(401, 'UNAUTHORIZED', 'A valid internal token is required.');
  }
}

async function readJsonBody(request: IncomingMessage): Promise<JsonRecord> {
  const contentType = request.headers['content-type'] || '';
  if (!contentType.toLowerCase().startsWith('application/json')) {
    throw new HttpError(
      415,
      'JSON_REQUIRED',
      'Content-Type must be application/json.'
    );
  }

  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    size += buffer.length;
    if (size > maxBodyBytes) {
      throw new HttpError(413, 'BODY_TOO_LARGE', 'Request body is too large.');
    }
    chunks.push(buffer);
  }

  try {
    const parsed = JSON.parse(Buffer.concat(chunks).toString('utf8')) as unknown;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('JSON body is not an object.');
    }
    return parsed as JsonRecord;
  } catch {
    throw new HttpError(400, 'INVALID_JSON', 'Request body is not valid JSON.');
  }
}

function sendFailure(response: ServerResponse, error: unknown): void {
  if (response.headersSent) {
    response.end();
    return;
  }

  if (error instanceof HttpError) {
    sendJson(response, error.status, {
      error: error.message,
      code: error.code,
      ...(error.details ? { details: error.details } : {})
    });
    return;
  }

  const upstream = error as {
    message?: string;
    response?: { status?: number; data?: unknown };
    request?: unknown;
  };
  const upstreamData = upstream.response?.data;
  const upstreamMessage =
    extractUpstreamMessage(upstreamData) || upstream.message || 'Unknown upstream error.';
  const normalized = upstreamMessage.toLowerCase();

  if (normalized.includes('hcaptcha') || normalized.includes('human verification')) {
    sendJson(response, 409, {
      error:
        'hCaptcha human verification required; complete it in the normal Suno interface, then retry.',
      code: 'SUNO_HUMAN_VERIFICATION_REQUIRED',
      requires_human: true
    });
    return;
  }

  if (normalized.includes('suno_cookie is not configured')) {
    sendJson(response, 503, {
      error: 'SUNO_COOKIE is not configured in the isolated service.',
      code: 'SUNO_COOKIE_NOT_CONFIGURED'
    });
    return;
  }

  const upstreamStatus = upstream.response?.status;
  const status =
    typeof upstreamStatus === 'number' &&
    upstreamStatus >= 400 &&
    upstreamStatus <= 599
      ? upstreamStatus
      : upstream.request
        ? 503
        : 500;
  sendJson(response, status, {
    error: upstreamMessage,
    code: upstream.request ? 'SUNO_NETWORK_ERROR' : 'SUNO_UPSTREAM_ERROR'
  });
}

function sendJson(response: ServerResponse, status: number, value: unknown): void {
  response.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff'
  });
  response.end(JSON.stringify(value));
}

function extractUpstreamMessage(value: unknown): string | undefined {
  if (typeof value === 'string') {
    return value;
  }
  if (!value || typeof value !== 'object') {
    return undefined;
  }
  const record = value as JsonRecord;
  for (const key of ['detail', 'error', 'message']) {
    if (typeof record[key] === 'string' && record[key]) {
      return record[key] as string;
    }
  }
  return undefined;
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function asOptionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value ? value : undefined;
}

function asFiniteNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function requireBodyString(
  value: unknown,
  code: string,
  message: string
): string {
  const result = asString(value).trim();
  if (!result) {
    throw new HttpError(400, code, message);
  }
  return result;
}

function requireQueryString(
  url: URL,
  name: string,
  code: string,
  message: string
): string {
  const result = (url.searchParams.get(name) || '').trim();
  if (!result) {
    throw new HttpError(400, code, message);
  }
  return result;
}

function positiveIntegerParam(value: string | null, fallback: number): number {
  if (!value) {
    return fallback;
  }
  const result = Number.parseInt(value, 10);
  if (!Number.isInteger(result) || result < 1) {
    throw new HttpError(400, 'PAGE_INVALID', 'page must be a positive integer.');
  }
  return result;
}
