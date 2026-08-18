import { NextRequest, NextResponse } from 'next/server';

export function middleware(request: NextRequest) {
  if (request.method === 'OPTIONS') {
    return NextResponse.next();
  }

  const expectedToken = process.env.INTERNAL_API_TOKEN;
  if (!expectedToken) {
    return NextResponse.json(
      { error: 'INTERNAL_API_TOKEN is not configured' },
      { status: 503 }
    );
  }

  if (request.headers.get('authorization') !== `Bearer ${expectedToken}`) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  if (request.headers.has('cookie')) {
    return NextResponse.json(
      { error: 'Request Cookie headers are not accepted' },
      { status: 400 }
    );
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/api/:path*']
};
