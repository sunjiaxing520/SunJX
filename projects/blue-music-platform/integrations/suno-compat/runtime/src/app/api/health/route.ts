import { NextResponse } from 'next/server';
import { hasConfiguredSunoCookie } from '@/lib/SunoApi';

export const dynamic = 'force-dynamic';

export async function GET() {
  return NextResponse.json({
    status: hasConfiguredSunoCookie() ? 'ready' : 'waiting_cookie',
    service: 'blue-music-suno-compat',
    captcha_mode: 'human_verification'
  });
}
