"""Hardcoded scaffold templates for files that must never be LLM placeholders."""
from __future__ import annotations

import json
import re
from typing import Optional

from models.schemas import ApiEndpoint


def endpoint_to_route_path(ep_path: str) -> str:
    """Map /api/health -> src/app/api/health/route.ts (Next.js App Router)."""
    segments = ep_path.strip("/").split("/")
    if segments and segments[0] == "api":
        segments = segments[1:]
    rel = "/".join(segments)
    return f"src/app/api/{rel}/route.ts" if rel else "src/app/api/route.ts"


def is_valid_route_module(content: str) -> bool:
    stripped = content.strip()
    if not stripped:
        return False
    if re.search(r"//\s*TODO|TODO:\s*implement", stripped, re.IGNORECASE):
        return False
    if "export" not in stripped:
        return False
    return True


def is_valid_package_json(content: str) -> bool:
    try:
        data = json.loads(content)
        return isinstance(data, dict) and "dependencies" in data and "scripts" in data
    except (json.JSONDecodeError, TypeError):
        return False


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "heaven-app"


def package_json(project_name: str) -> str:
    return json.dumps(
        {
            "name": _slug(project_name),
            "version": "0.1.0",
            "private": True,
            "scripts": {
                "dev": "next dev",
                "build": "next build",
                "start": "next start",
                "lint": "next lint",
            },
            "dependencies": {
                "next": "15.1.0",
                "react": "^19.0.0",
                "react-dom": "^19.0.0",
                "@prisma/client": "^6.0.0",
                "next-auth": "^4.24.0",
            },
            "devDependencies": {
                "@types/node": "^22.0.0",
                "@types/react": "^19.0.0",
                "@types/react-dom": "^19.0.0",
                "typescript": "^5.7.0",
                "prisma": "^6.0.0",
                "eslint": "^9.0.0",
                "eslint-config-next": "15.1.0",
            },
        },
        indent=2,
    ) + "\n"


def tsconfig_json() -> str:
    return """{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
"""


def next_config_ts() -> str:
    return """import type { NextConfig } from 'next';

const nextConfig: NextConfig = {};

export default nextConfig;
"""


def route_handler(ep: Optional[ApiEndpoint] = None) -> str:
    path = ep.path if ep else "/api/health"
    method = (ep.method if ep else "GET").upper()
    is_health = "health" in path.lower()

    exports: list[str] = []
    if method == "GET" or is_health:
        exports.append(
            f"""export async function GET() {{
  return NextResponse.json({{
    status: 'ok',
    endpoint: '{path}',
    timestamp: new Date().toISOString(),
  }});
}}"""
        )
    if method == "POST" and not is_health:
        exports.append(
            """export async function POST(request: Request) {
  try {
    const body = await request.json();
    return NextResponse.json({ success: true, data: body }, { status: 201 });
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }
}"""
        )
    if method == "PUT":
        exports.append(
            """export async function PUT(request: Request) {
  try {
    const body = await request.json();
    return NextResponse.json({ success: true, updated: body });
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }
}"""
        )
    if method == "DELETE":
        exports.append(
            """export async function DELETE() {
  return NextResponse.json({ success: true, deleted: true });
}"""
        )
    if not exports:
        exports.append(
            f"""export async function GET() {{
  return NextResponse.json({{ message: 'Endpoint {path} ready' }});
}}"""
        )

    body = "\n\n".join(exports)
    return f"""import {{ NextResponse }} from 'next/server';

{body}
"""


# ─────────────────────────────────────────────
# Auth scaffolding (only used when needs_auth() is True)
# ─────────────────────────────────────────────

AUTH_KEYWORDS = (
    "login", "log in", "sign in", "signin", "sign up", "signup",
    "auth", "authentication", "account", "user account",
    "register", "registration", "session", "password",
)


def needs_auth(features: list[str]) -> bool:
    """Decide whether the project actually needs login/auth scaffolding."""
    joined = " ".join(features).lower()
    return any(keyword in joined for keyword in AUTH_KEYWORDS)


def auth_config_ts() -> str:
    """Edge-safe config: NO providers, NO bcrypt/db imports.
    Safe to import from middleware.ts (runs in Edge Runtime)."""
    return """import type { NextAuthOptions } from 'next-auth';

// Edge-safe config only. Do NOT import providers or database
// clients here — this file is imported by middleware.ts, which
// runs in the Edge Runtime and cannot use Node.js APIs or
// dynamic code evaluation (which next-auth providers rely on).
export const authConfig: Partial<NextAuthOptions> = {
  pages: {
    signIn: '/login',
  },
  session: {
    strategy: 'jwt',
  },
};
"""


def auth_ts() -> str:
    """Full NextAuth setup with providers. Only imported from
    Node.js runtime routes (e.g. app/api/auth/[...nextauth]/route.ts),
    never from middleware.ts."""
    return """import NextAuth from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import { authConfig } from './auth.config';

export const authOptions = {
  ...authConfig,
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        // TODO: replace with real lookup against your database.
        if (!credentials?.email || !credentials?.password) {
          return null;
        }
        return { id: '1', email: credentials.email };
      },
    }),
  ],
};

export default NextAuth(authOptions);
"""


def auth_nextauth_route_ts() -> str:
    """app/api/auth/[...nextauth]/route.ts — Node runtime, safe to use full next-auth."""
    return """import NextAuth from 'next-auth';
import { authOptions } from '@/lib/auth';

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
"""


def middleware_ts() -> str:
    """Edge-safe middleware. Imports ONLY auth.config.ts (no providers,
    no next-auth core eval-based code) to avoid the Edge Runtime
    'Dynamic Code Evaluation' build error."""
    return """import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Lightweight cookie-presence check only. Full session
// verification happens in the Node runtime (API routes / pages),
// not here, since middleware runs in the Edge Runtime and cannot
// use next-auth's full provider stack.
export function middleware(request: NextRequest) {
  const sessionToken =
    request.cookies.get('next-auth.session-token') ||
    request.cookies.get('__Secure-next-auth.session-token');

  const isProtectedRoute = request.nextUrl.pathname.startsWith('/dashboard');

  if (isProtectedRoute && !sessionToken) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*'],
};
"""
