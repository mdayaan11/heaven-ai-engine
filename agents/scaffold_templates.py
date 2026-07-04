"""Hardcoded scaffold templates + auto-package detection for Next.js projects."""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from models.schemas import ApiEndpoint

# ─────────────────────────────────────────────────────────────────────────────
# Known package registry — version-pinned, Vercel-compatible
# ─────────────────────────────────────────────────────────────────────────────
KNOWN_PACKAGES: Dict[str, str] = {
    # 3D / Three.js
    "three": "^0.169.0",
    "@react-three/fiber": "^8.17.10",
    "@react-three/drei": "^9.117.3",
    "@react-three/postprocessing": "^2.16.0",
    # Animation
    "framer-motion": "^11.12.0",
    "gsap": "^3.12.5",
    "lottie-react": "^2.4.0",
    # UI Primitives
    "@radix-ui/react-dialog": "^1.1.3",
    "@radix-ui/react-dropdown-menu": "^2.1.3",
    "@radix-ui/react-tabs": "^1.1.2",
    "@radix-ui/react-toast": "^1.2.3",
    "@radix-ui/react-slot": "^1.1.1",
    # Utilities
    "lucide-react": "^0.460.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.4",
    "class-variance-authority": "^0.7.1",
    # Forms / Validation
    "zod": "^3.23.8",
    "react-hook-form": "^7.54.2",
    "@hookform/resolvers": "^3.9.1",
    # Data fetching
    "axios": "^1.7.9",
    "swr": "^2.2.5",
    "@tanstack/react-query": "^5.62.7",
    # Charts
    "recharts": "^2.13.3",
    "chart.js": "^4.4.7",
    "react-chartjs-2": "^5.2.0",
    # Tables
    "@tanstack/react-table": "^8.20.5",
    # Payments
    "stripe": "^17.4.0",
    "@stripe/react-stripe-js": "^3.1.1",
    "@stripe/stripe-js": "^5.3.0",
    # Auth helpers
    "bcryptjs": "^2.4.3",
    "jsonwebtoken": "^9.0.2",
    # Notifications
    "react-hot-toast": "^2.4.1",
    "sonner": "^1.7.1",
    # Dates
    "date-fns": "^4.1.0",
    "dayjs": "^1.11.13",
    # Upload
    "uploadthing": "^7.2.0",
    "@uploadthing/react": "^7.1.0",
    # State
    "zustand": "^5.0.2",
    "jotai": "^2.10.3",
    # Other
    "sharp": "^0.33.5",
    "nodemailer": "^6.9.16",
    "react-dropzone": "^14.3.0",
    "react-select": "^5.8.3",
    "socket.io-client": "^4.8.1",
    "react-markdown": "^9.0.1",
    "react-syntax-highlighter": "^15.6.1",
    "react-icons": "^5.4.0",
    "@heroicons/react": "^2.2.0",
}

DEV_PACKAGES: Dict[str, str] = {
    "@types/three": "^0.169.0",
    "@types/bcryptjs": "^2.4.6",
    "@types/jsonwebtoken": "^9.0.7",
    "@types/nodemailer": "^6.4.17",
    "@types/react-syntax-highlighter": "^15.5.13",
    "tailwindcss": "^3.4.17",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "@tailwindcss/forms": "^0.5.9",
    "@tailwindcss/typography": "^0.5.15",
}

# Packages that need SSR disabled in Next.js (use dynamic import)
SSR_UNSAFE = {"three", "@react-three/fiber", "@react-three/drei"}


def detect_imports(files: list) -> Dict[str, str]:
    """Scan generated files for npm imports and return {package: version} dict."""
    found_deps: Dict[str, str] = {}
    found_dev: Dict[str, str] = {}
    import_pattern = re.compile(
        r"""(?:import|from|require)\s*[\(\s]['"](@?[a-zA-Z0-9][\w\-\.]*(?:/[\w\-\.]+)?)['"]\)?"""
    )
    for f in files:
        content = f.content if hasattr(f, "content") else f.get("content", "")
        path = f.path if hasattr(f, "path") else f.get("path", "")
        if not content or path == "package.json":
            continue
        for match in import_pattern.finditer(content):
            pkg = match.group(1)
            # Normalize scoped packages (@scope/pkg) and plain (pkg)
            parts = pkg.split("/")
            base = "/".join(parts[:2]) if pkg.startswith("@") else parts[0]
            if base in KNOWN_PACKAGES:
                found_deps[base] = KNOWN_PACKAGES[base]
            if base in DEV_PACKAGES:
                found_dev[base] = DEV_PACKAGES[base]
    return found_deps, found_dev


def package_json(project_name: str, extra_deps: Dict[str, str] = None,
                 extra_dev: Dict[str, str] = None) -> str:
    deps = {
        "next": "15.1.0",
        "react": "^19.0.0",
        "react-dom": "^19.0.0",
        "@prisma/client": "^6.0.0",
        "next-auth": "^4.24.0",
        # Always include Tailwind utilities since prompts use them
        "clsx": "^2.1.1",
        "tailwind-merge": "^2.5.4",
        "lucide-react": "^0.460.0",
    }
    dev = {
        "@types/node": "^22.0.0",
        "@types/react": "^19.0.0",
        "@types/react-dom": "^19.0.0",
        "typescript": "^5.7.0",
        "prisma": "^6.0.0",
        "eslint": "^9.0.0",
        "eslint-config-next": "15.1.0",
        "tailwindcss": "^3.4.17",
        "autoprefixer": "^10.4.20",
        "postcss": "^8.4.49",
    }
    if extra_deps:
        deps.update(extra_deps)
    if extra_dev:
        dev.update(extra_dev)
    return json.dumps({
        "name": _slug(project_name),
        "version": "0.1.0",
        "private": True,
        "scripts": {
            "dev": "next dev",
            "build": "next build",
            "start": "next start",
            "lint": "next lint",
        },
        "dependencies": deps,
        "devDependencies": dev,
    }, indent=2) + "\n"


def tailwind_config() -> str:
    return """import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
};

export default config;
"""


def postcss_config() -> str:
    return """module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
"""


def globals_css() -> str:
    return """@tailwind base;
@tailwind components;
@tailwind utilities;

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --foreground: #f8fafc;
  --background: #0f172a;
}

body {
  font-family: 'Inter', sans-serif;
  background: var(--background);
  color: var(--foreground);
  min-height: 100vh;
}
"""


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

const nextConfig: NextConfig = {
  images: { unoptimized: true },
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;
"""


def middleware_ts() -> str:
    return """import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|api/health).*)'],
};
"""


def auth_ts() -> str:
    return """// auth.ts — server-side only, do NOT import in middleware
import NextAuth from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        if (credentials?.email && credentials?.password) {
          return { id: '1', email: credentials.email as string, name: 'User' };
        }
        return null;
      },
    }),
  ],
  pages: { signIn: '/login' },
  session: { strategy: 'jwt' },
});
"""


def route_handler(ep: Optional[ApiEndpoint] = None) -> str:
    path = ep.path if ep else "/api/health"
    method = (ep.method if ep else "GET").upper()
    is_health = "health" in path.lower()
    exports: list[str] = []
    if method == "GET" or is_health:
        exports.append(f"""export async function GET() {{
  return NextResponse.json({{
    status: 'ok',
    endpoint: '{path}',
    timestamp: new Date().toISOString(),
  }});
}}""")
    if method == "POST" and not is_health:
        exports.append("""export async function POST(request: Request) {
  try {
    const body = await request.json();
    return NextResponse.json({ success: true, data: body }, { status: 201 });
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }
}""")
    if method == "PUT":
        exports.append("""export async function PUT(request: Request) {
  try {
    const body = await request.json();
    return NextResponse.json({ success: true, updated: body });
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }
}""")
    if method == "DELETE":
        exports.append("""export async function DELETE() {
  return NextResponse.json({ success: true, deleted: true });
}""")
    if not exports:
        exports.append(f"""export async function GET() {{
  return NextResponse.json({{ message: 'Endpoint {path} ready' }});
}}""")
    body = "\n\n".join(exports)
    return f"""import {{ NextResponse }} from 'next/server';

{body}
"""


def endpoint_to_route_path(ep_path: str) -> str:
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
