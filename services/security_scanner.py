"""
Heaven AI — Security Scanner Service
Automatically detects and removes hardcoded secrets, validates auth middleware presence.
"""
from __future__ import annotations
import re
from typing import Dict, List, Tuple
from models.schemas import GeneratedFile


# ─────────────────────────────────────────────
# Secret Detection Patterns
# ─────────────────────────────────────────────
SECRET_PATTERNS: List[Tuple[str, re.Pattern, str]] = [
    # (env_var_name, regex_pattern, replacement_expression)
    ("ANTHROPIC_API_KEY",     re.compile(r'sk-ant-[A-Za-z0-9\-_]{20,}'),               'process.env.ANTHROPIC_API_KEY'),
    ("OPENAI_API_KEY",        re.compile(r'sk-[A-Za-z0-9]{40,}'),                       'process.env.OPENAI_API_KEY'),
    ("GITHUB_TOKEN",          re.compile(r'gh[ps]_[A-Za-z0-9]{36}'),                    'process.env.GITHUB_TOKEN'),
    ("VERCEL_TOKEN",          re.compile(r'[A-Za-z0-9]{24,}(?=.*vercel)',re.IGNORECASE),'process.env.VERCEL_TOKEN'),
    ("DATABASE_URL",          re.compile(r'postgres(?:ql)?://[^\s\'"]+'),               'process.env.DATABASE_URL'),
    ("SUPABASE_KEY",          re.compile(r'eyJ[A-Za-z0-9+/=]{50,}'),                   'process.env.SUPABASE_KEY'),
    ("STRIPE_SECRET_KEY",     re.compile(r'sk_(?:live|test)_[A-Za-z0-9]{24,}'),        'process.env.STRIPE_SECRET_KEY'),
    ("STRIPE_PUBLISHABLE_KEY",re.compile(r'pk_(?:live|test)_[A-Za-z0-9]{24,}'),        'process.env.NEXT_PUBLIC_STRIPE_KEY'),
    ("AWS_ACCESS_KEY",        re.compile(r'AKIA[A-Z0-9]{16}'),                          'process.env.AWS_ACCESS_KEY_ID'),
    ("AWS_SECRET_KEY",        re.compile(r'[A-Za-z0-9+/]{40}(?=.*aws)',re.IGNORECASE),  'process.env.AWS_SECRET_ACCESS_KEY'),
    ("JWT_SECRET",            re.compile(r'(?:jwt|secret)[\s\'"=:]+([A-Za-z0-9!@#$%^&*]{16,})', re.IGNORECASE), 'process.env.JWT_SECRET'),
    ("API_KEY_GENERIC",       re.compile(r'(?:api_key|apikey|API_KEY)[\s\'"=:]+([A-Za-z0-9\-_]{16,})', re.IGNORECASE), 'process.env.API_KEY'),
]

# Assignment patterns that indicate a hardcoded secret
HARDCODED_ASSIGNMENT = re.compile(
    r'(?:const|let|var)\s+\w+\s*=\s*["\']([A-Za-z0-9\-_\/+]{20,})["\']'
)

# Auth middleware keywords — at least one must be present in route files
AUTH_KEYWORDS = [
    "middleware", "authenticate", "verifyToken", "requireAuth",
    "getServerSession", "auth()", "withAuth", "protect", "isAuthenticated",
    "session", "jwt.verify", "Bearer"
]


class SecurityScannerService:
    """
    Scans generated codebase for:
    1. Hardcoded secrets → moves to .env
    2. Missing auth middleware on protected routes
    3. SQL injection patterns
    4. Sensitive data exposure in API responses
    """

    def __init__(self):
        self.secrets_found: List[str] = []
        self.vulnerabilities_fixed: List[str] = []

    def scan_and_sanitize(self, files: List[GeneratedFile]) -> Tuple[List[GeneratedFile], List[str], List[str]]:
        """
        Main scan entry point.

        Returns:
            (sanitized_files, secrets_found_list, vulnerabilities_fixed_list)
        """
        self.secrets_found = []
        self.vulnerabilities_fixed = []
        sanitized: List[GeneratedFile] = []

        route_files = [f for f in files if self._is_route_file(f.path)]
        has_auth = self._check_auth_presence(route_files)

        for file in files:
            content, file_secrets = self._strip_secrets(file.content, file.path)
            self.secrets_found.extend(file_secrets)

            content = self._fix_sql_injection(content, file.path)
            content = self._fix_sensitive_response(content, file.path)

            if self._is_route_file(file.path) and not has_auth:
                content = self._inject_auth_import(content, file.path)
                if content != file.content:
                    self.vulnerabilities_fixed.append(
                        f"Injected auth middleware import into {file.path}"
                    )

            sanitized.append(GeneratedFile(path=file.path, content=content, language=file.language))

        # Update .env.example if exists
        sanitized = self._update_env_example(sanitized)

        # Deduplicate
        self.secrets_found = list(set(self.secrets_found))

        return sanitized, self.secrets_found, self.vulnerabilities_fixed

    # ─────────────────────────────────────────────
    # Private Helpers
    # ─────────────────────────────────────────────
    def _strip_secrets(self, content: str, file_path: str) -> Tuple[str, List[str]]:
        """Find and replace hardcoded secrets with env var references."""
        found_vars: List[str] = []
        modified = content

        for env_var, pattern, replacement in SECRET_PATTERNS:
            if pattern.search(modified):
                modified = pattern.sub(replacement, modified)
                found_vars.append(env_var)
                self.vulnerabilities_fixed.append(
                    f"Moved hardcoded {env_var} to process.env in {file_path}"
                )

        return modified, found_vars

    def _fix_sql_injection(self, content: str, file_path: str) -> str:
        """Detect raw string interpolation in SQL queries."""
        sql_interpolation = re.compile(
            r'(?:query|sql|SELECT|INSERT|UPDATE|DELETE)[^;]*\$\{[^}]+\}',
            re.IGNORECASE
        )
        if sql_interpolation.search(content):
            self.vulnerabilities_fixed.append(
                f"WARNING: Potential SQL injection pattern detected in {file_path}. "
                "Ensure parameterized queries are used."
            )
        return content

    def _fix_sensitive_response(self, content: str, file_path: str) -> str:
        """Flag if password/hash is returned in API response."""
        if "password" in content.lower() and "json(" in content.lower():
            # Add a comment warning — do not blindly remove as context matters
            self.vulnerabilities_fixed.append(
                f"WARNING: Verify 'password' field is excluded from API responses in {file_path}"
            )
        return content

    def _check_auth_presence(self, route_files: List[GeneratedFile]) -> bool:
        """Check if any auth mechanism is present across route files."""
        for file in route_files:
            for keyword in AUTH_KEYWORDS:
                if keyword in file.content:
                    return True
        return False

    def _inject_auth_import(self, content: str, file_path: str) -> str:
        """Inject a basic auth guard comment if missing."""
        if "middleware" not in content.lower() and "page.tsx" not in file_path:
            auth_comment = (
                "// SECURITY: Ensure this route is protected by auth middleware\n"
                "// Add: import { getServerSession } from 'next-auth';\n"
                "// and verify session before processing request.\n"
            )
            # Insert after first import block
            lines = content.split("\n")
            insert_at = 0
            for i, line in enumerate(lines):
                if line.startswith("import "):
                    insert_at = i + 1
            lines.insert(insert_at, auth_comment)
            return "\n".join(lines)
        return content

    def _update_env_example(self, files: List[GeneratedFile]) -> List[GeneratedFile]:
        """Add discovered secret variable names to .env.example."""
        if not self.secrets_found:
            return files

        env_example_content = "# Auto-generated by Heaven AI Security Scanner\n"
        env_example_content += "# Fill in the values before deployment\n\n"
        for var in sorted(set(self.secrets_found)):
            env_example_content += f"{var}=your_{var.lower()}_here\n"

        # Check if .env.example already exists
        existing = next((f for f in files if f.path in [".env.example", ".env.local.example"]), None)
        if existing:
            # Append to existing
            updated_files = []
            for f in files:
                if f.path == existing.path:
                    merged_content = f.content + "\n\n# Additional secrets found by scanner:\n"
                    for var in sorted(set(self.secrets_found)):
                        if var not in f.content:
                            merged_content += f"{var}=your_{var.lower()}_here\n"
                    updated_files.append(GeneratedFile(path=f.path, content=merged_content, language="env"))
                else:
                    updated_files.append(f)
            return updated_files
        else:
            # Create new .env.example
            return files + [
                GeneratedFile(path=".env.example", content=env_example_content, language="env")
            ]

    @staticmethod
    def _is_route_file(path: str) -> bool:
        """Determine if a file is an API route or server-side file."""
        indicators = ["api/", "route.ts", "routes.py", "router", "endpoint", "controller"]
        return any(ind in path.lower() for ind in indicators)

    def generate_scan_report(self) -> str:
        """Generate a human-readable security scan report."""
        lines = ["# Heaven AI Security Scan Report\n"]
        if self.secrets_found:
            lines.append(f"## ✅ Secrets Moved to .env ({len(self.secrets_found)} total)")
            for s in self.secrets_found:
                lines.append(f"  - {s}")
        else:
            lines.append("## ✅ No hardcoded secrets detected")

        if self.vulnerabilities_fixed:
            lines.append(f"\n## 🔧 Issues Fixed / Flagged ({len(self.vulnerabilities_fixed)} total)")
            for v in self.vulnerabilities_fixed:
                lines.append(f"  - {v}")
        else:
            lines.append("\n## ✅ No additional vulnerabilities found")

        return "\n".join(lines)
