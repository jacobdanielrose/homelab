#!/usr/bin/env python3
"""
Authentik Configuration Backup Tool

Dumps all Authentik resources via the REST API, plus optionally backs up
the PostgreSQL database and static Docker volumes.

Usage:
    # API dump only (portable, human-readable JSON)
    ./authentik-backup.py --url https://auth.example.com --token "ak-api-token"

    # Full backup with DB + volumes (if running locally on Docker host)
    ./authentik-backup.py --url https://auth.example.com --token "..." \
        --db-dump --db-user authentik --volumes

    # If token isn't provided, you'll be prompted; or use --username/--password
    # for a one-time token exchange.
"""

import argparse
import json
import os
import sys
import time
import shutil
import subprocess
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlencode, urlparse
from urllib.request import Request, urlopen


# ─── API endpoint catalog ───────────────────────────────────────────────────
# Each entry: (label, api_path, paginated?)
# Paginated endpoints use ?page=1&page_size=100 (Authentik DRF default).
ENDPOINTS = [
    # Core
    ("core/brands",              "/api/v3/brands/brands/"),
    ("core/applications",        "/api/v3/core/applications/"),
    ("core/groups",              "/api/v3/core/groups/"),
    ("core/users",               "/api/v3/core/users/"),
    ("core/user-consent",        "/api/v3/core/user-consent/"),
    ("core/transactional-applications", "/api/v3/core/transactional-applications/"),

    # Flows
    ("flows/instances",          "/api/v3/flows/instances/"),
    ("flows/bindings",           "/api/v3/flows/bindings/"),

    # Stages
    ("stages/all",               "/api/v3/stages/all/"),
    ("stages/identification",    "/api/v3/stages/identification/"),
    ("stages/prompt",            "/api/v3/stages/prompt/"),
    ("stages/user_login",        "/api/v3/stages/user_login/"),
    ("stages/consent",           "/api/v3/stages/consent/"),
    ("stages/deny",              "/api/v3/stages/deny/"),
    ("stages/dummy",             "/api/v3/stages/dummy/"),
    ("stages/password",          "/api/v3/stages/password/"),
    ("stages/email",             "/api/v3/stages/email/"),
    ("stages/authenticator_validate", "/api/v3/stages/authenticator/validate/"),
    ("stages/authenticator_totp",     "/api/v3/stages/authenticator/totp/"),
    ("stages/authenticator_duo",      "/api/v3/stages/authenticator/duo/"),
    ("stages/authenticator_sms",      "/api/v3/stages/authenticator/sms/"),
    ("stages/authenticator_webauthn", "/api/v3/stages/authenticator/webauthn/"),
    ("stages/captcha",           "/api/v3/stages/captcha/"),

    # Policies
    ("policies/all",             "/api/v3/policies/all/"),
    ("policies/binding",         "/api/v3/policies/binding/"),
    ("policies/event_matcher",   "/api/v3/policies/event_matcher/"),
    ("policies/expression",      "/api/v3/policies/expression/"),
    ("policies/password",        "/api/v3/policies/password/"),
    ("policies/reputation",      "/api/v3/policies/reputation/"),
    ("policies/geoip",           "/api/v3/policies/geoip/"),

    # Providers
    ("providers/all",            "/api/v3/providers/all/"),
    ("providers/ldap",           "/api/v3/providers/ldap/"),
    ("providers/oauth2",         "/api/v3/providers/oauth2/"),
    ("providers/proxy",          "/api/v3/providers/proxy/"),
    ("providers/radius",         "/api/v3/providers/radius/"),
    ("providers/saml",           "/api/v3/providers/saml/"),
    ("providers/scim",           "/api/v3/providers/scim/"),

    # Sources
    ("sources/all",              "/api/v3/sources/all/"),
    ("sources/ldap",             "/api/v3/sources/ldap/"),
    ("sources/oauth",            "/api/v3/sources/oauth/"),
    ("sources/saml",             "/api/v3/sources/saml/"),
    ("sources/plex",             "/api/v3/sources/plex/"),

    # Property Mappings
    ("propertymappings/all",     "/api/v3/propertymappings/all/"),
    ("propertymappings/ldap",    "/api/v3/propertymappings/ldap/"),
    ("propertymappings/notification", "/api/v3/propertymappings/notification/"),
    ("propertymappings/saml",    "/api/v3/propertymappings/saml/"),
    ("propertymappings/scim",    "/api/v3/propertymappings/scim/"),

    # Outposts
    ("outposts/instances",       "/api/v3/outposts/instances/"),
    ("outposts/service-connections", "/api/v3/outposts/service-connections/all/"),

    # Tenants
    ("tenants/tenants",          "/api/v3/tenants/tenants/"),

    # Blueprints
    ("blueprints/blueprints",    "/api/v3/blueprints/blueprints/"),

    # Authenticators
    ("authenticators/all",       "/api/v3/authenticators/all/"),
    ("authenticators/totp",      "/api/v3/authenticators/totp/"),
    ("authenticators/duo",       "/api/v3/authenticators/duo/"),
    ("authenticators/sms",       "/api/v3/authenticators/sms/"),
    ("authenticators/webauthn",  "/api/v3/authenticators/webauthn/"),

    # Event / Notification
    ("events/events",            "/api/v3/events/events/"),
    ("events/notifications",     "/api/v3/events/notifications/"),
    ("events/transports",        "/api/v3/events/notification_transports/"),
    ("events/rules",             "/api/v3/events/notification_rules/"),
    ("events/webhook-mappings",  "/api/v3/events/notification_webhook_mappings/"),

    # Crypto / Certificates
    ("crypto/certificate-pairs", "/api/v3/crypto/certificatepairs/"),

    # RBAC
    ("rbac/roles",               "/api/v3/rbac/roles/"),
    ("rbac/permissions",         "/api/v3/rbac/permissions/"),

    # Admin
    ("admin/system-info",        "/api/v3/admin/system/", False),
    ("admin/version",            "/api/v3/admin/version/", False),
]


# ─── Docker volumes used by Authentik (for --volumes) ──────────────────────
AUTHENTIK_VOLUMES = {
    "authentik-media":      "/data",
    "authentik-certs":      "/certs",
    "authentik-templates":  "/custom-templates",
    "authentik-blueprints": "/blueprints",
}


class AuthentikBackup:
    """Fetches all resources from an Authentik instance via the REST API."""

    def __init__(self, base_url: str, token: str, verify_ssl: bool = True,
                 timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.verify_ssl = verify_ssl
        self.timeout = timeout

    def _request(self, path: str, params: dict | None = None,
                 method: str = "GET") -> dict:
        """Make an Authentik API request, return parsed JSON."""
        url = urljoin(self.base_url, path)
        if params:
            url += "?" + urlencode(params, doseq=True)

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        req = Request(url, headers=headers, method=method)

        try:
            resp = urlopen(req, timeout=self.timeout)
            return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(
                f"HTTP {e.code} on {path}: {body}"
            ) from e
        except URLError as e:
            raise RuntimeError(f"Connection error on {path}: {e.reason}") from e

    def _paginate(self, path: str) -> list[dict]:
        """Fetch all pages of a paginated endpoint."""
        results = []
        page = 1
        params = {"page_size": 100}

        while True:
            params["page"] = page
            data = self._request(path, params=params)
            results.extend(data.get("results", []))

            if data.get("next"):
                page += 1
            else:
                break

        return results

    def fetch_endpoint(self, label: str, path: str,
                       paginated: bool = True) -> tuple[str, object]:
        """Fetch a single endpoint and return (label, data)."""
        print(f"  {label} ...", end=" ", flush=True)
        try:
            if paginated:
                data = self._paginate(path)
            else:
                data = self._request(path)
            count = len(data) if isinstance(data, list) else 1
            print(f"{count} objects" if isinstance(data, list) else "ok")
            return (label, data)
        except Exception as e:
            print(f"FAILED: {e}")
            return (label, None)

    def fetch_all(self) -> dict[str, object]:
        """Fetch all configured endpoints."""
        results = {}
        for label, path, *opts in ENDPOINTS:
            paginated = opts[0] if opts else True
            key, data = self.fetch_endpoint(label, path, paginated=paginated)
            results[key] = data
        return results


def get_api_token(url: str, username: str, password: str,
                  verify_ssl: bool = True) -> str:
    """Exchange username/password for a short-lived API token."""
    import json as _json
    from urllib.request import Request as _Request, urlopen as _urlopen
    from urllib.error import HTTPError as _HTTPError

    auth_url = url.rstrip("/") + "/api/v3/authenticator/admin/tokens/"
    payload = _json.dumps({
        "username": username,
        "password": password,
    }).encode("utf-8")

    req = _Request(
        auth_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        resp = _urlopen(req, timeout=30)
        data = _json.loads(resp.read().decode("utf-8"))
        return data.get("key", data.get("token", ""))
    except _HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(
            f"Token exchange failed (HTTP {e.code}): {body}"
        ) from None
    except Exception as e:
        raise RuntimeError(f"Token exchange failed: {e}") from None


def backup_database(output_dir: Path, db_user: str = "authentik",
                    db_name: str = "authentik", container: str = "",
                    host: str = "") -> None:
    """Dump the Authentik database using pg_dump."""
    print("\n🗄️  Backing up PostgreSQL database...")

    db_file = output_dir / "authentik-database.sql"

    if container:
        # Dump from within a Docker container
        cmd = [
            "docker", "exec", container,
            "pg_dump", "-U", db_user, "-d", db_name,
            "--no-owner", "--no-acl",
        ]
        print(f"  Using Docker container: {container}")
    else:
        cmd = [
            "pg_dump", "-U", db_user, "-d", db_name,
            "--no-owner", "--no-acl",
        ]
        if host:
            cmd.extend(["-h", host])
        print(f"  Using pg_dump directly")

    try:
        with open(db_file, "w") as f:
            subprocess.run(cmd, check=True, stdout=f,
                           stderr=subprocess.PIPE, text=True)
        size = db_file.stat().st_size
        print(f"  ✅ DB dump: {db_file.name} ({_fmt_size(size)})")
    except FileNotFoundError:
        print("  ⚠️  pg_dump not found, skipping DB backup")
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️  DB dump failed: {e.stderr[:200]}")


def backup_volumes(output_dir: Path) -> None:
    """Backup Authentik Docker volumes as tarballs."""
    print("\n💾 Backing up Docker volumes...")

    vol_dir = output_dir / "volumes"
    vol_dir.mkdir(parents=True, exist_ok=True)

    for vol_name, mount_path in AUTHENTIK_VOLUMES.items():
        tar_file = vol_dir / f"{vol_name}.tar.gz"
        print(f"  {vol_name} -> {mount_path} ...", end=" ", flush=True)

        if not _volume_exists(vol_name):
            print("not found, skipping")
            continue

        cmd = [
            "docker", "run", "--rm",
            "-v", f"{vol_name}:/source:ro",
            "-v", f"{vol_dir}:/backup",
            "alpine:latest",
            "tar", "czf", f"/backup/{vol_name}.tar.gz",
            "-C", "/source", ".",
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            size = tar_file.stat().st_size
            print(f"✅ {_fmt_size(size)}")
        except Exception as e:
            print(f"FAILED: {e}")


def _volume_exists(name: str) -> bool:
    try:
        r = subprocess.run(
            ["docker", "volume", "inspect", name],
            capture_output=True, text=True,
        )
        return r.returncode == 0
    except FileNotFoundError:
        return False


def _fmt_size(bytes_: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if bytes_ < 1024:
            return f"{bytes_:.1f} {unit}"
        bytes_ /= 1024
    return f"{bytes_:.1f} TB"


def write_manifest(output_dir: Path, results: dict[str, object],
                   args: argparse.Namespace) -> None:
    """Write a backup manifest file."""
    manifest = {
        "backup_tool": "authentik-backup.py",
        "backup_time": datetime.now(timezone.utc).isoformat(),
        "source_url": args.url,
        "resources": {},
    }
    for label, data in results.items():
        if data is not None:
            count = len(data) if isinstance(data, list) else 1
            manifest["resources"][label] = count
        else:
            manifest["resources"][label] = "FAILED"

    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Backup Authentik configuration via the REST API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # API dump only (portable)
  %(prog)s --url https://auth.example.com --token "ak-..."

  # API dump + PostgreSQL + Docker volumes
  %(prog)s --url https://auth.example.com --token "..." \\
      --db-dump --db-container authentik-server --volumes
        """,
    )
    parser.add_argument("--url", required=True,
                        help="Authentik instance URL (e.g. https://auth.example.com)")
    parser.add_argument("--token",
                        help="API token (create at Admin > API Tokens)")
    parser.add_argument("--username",
                        help="Admin username (for one-time token exchange)")
    parser.add_argument("--password",
                        help="Admin password (for one-time token exchange)")
    parser.add_argument("--output", "-o",
                        default=f"./authentik-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                        help="Output directory")
    parser.add_argument("--insecure", action="store_true",
                        help="Disable SSL verification")
    parser.add_argument("--timeout", type=int, default=30,
                        help="HTTP timeout in seconds (default 30)")

    # Optional extras
    parser.add_argument("--db-dump", action="store_true",
                        help="Also dump the PostgreSQL database")
    parser.add_argument("--db-user", default="authentik",
                        help="PostgreSQL user (default: authentik)")
    parser.add_argument("--db-name", default="authentik",
                        help="PostgreSQL database name (default: authentik)")
    parser.add_argument("--db-host", default="",
                        help="PostgreSQL host (omit if using Docker or local)")
    parser.add_argument("--db-container", default="",
                        help="Docker container name to run pg_dump from")
    parser.add_argument("--volumes", action="store_true",
                        help="Also backup Docker volumes as tarballs")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress progress output")

    args = parser.parse_args()

    # ── Resolve authentication ──────────────────────────────────────────
    token = args.token
    if not token:
        if args.username and args.password:
            print("🔑 Exchanging credentials for API token...")
            token = get_api_token(args.url, args.username, args.password,
                                  verify_ssl=not args.insecure)
            print(f"  Got token (first 10 chars): {token[:10]}...")
        else:
            print("⚠️  No --token or --username/--password provided.")
            sys.exit(1)

    # ── Prepare output directory ────────────────────────────────────────
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    api_dir = output_dir / "api"
    api_dir.mkdir(parents=True, exist_ok=True)

    if not args.quiet:
        print(f"📁 Output: {output_dir.resolve()}")
        print(f"🔗 Target: {args.url}")

    # ── API dump ────────────────────────────────────────────────────────
    print("\n📦 Fetching Authentik resources...")
    backup = AuthentikBackup(
        args.url, token,
        verify_ssl=not args.insecure,
        timeout=args.timeout,
    )
    results = backup.fetch_all()

    # Write each resource to its own JSON file
    for label, data in results.items():
        file_path = api_dir / f"{label.replace('/', '-')}.json"
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    # Write combined single-file export
    combined = {k: v for k, v in results.items() if v is not None}
    with open(output_dir / "authentik-export.json", "w") as f:
        json.dump(combined, f, indent=2, default=str, ensure_ascii=False)

    # Write manifest
    write_manifest(output_dir, results, args)

    # ── Optional extras ─────────────────────────────────────────────────
    if args.db_dump:
        backup_database(
            output_dir, args.db_user, args.db_name,
            container=args.db_container, host=args.db_host,
        )

    if args.volumes:
        backup_volumes(output_dir)

    # ── Summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  ✅ Backup complete!")
    print(f"  📁 {output_dir.resolve()}")
    print(f"  📊 {len([v for v in results.values() if v is not None])} endpoints exported")
    total_objects = sum(
        len(v) if isinstance(v, list) else 1
        for v in results.values()
        if v is not None
    )
    print(f"  📦 {total_objects} total objects")

    # List key files
    print(f"\n  Files:")
    for f in sorted(output_dir.iterdir()):
        if f.is_file():
            size = _fmt_size(f.stat().st_size)
            print(f"    {f.name} ({size})")

    api_files = list(api_dir.iterdir())
    if api_files:
        print(f"    api/  ({len(api_files)} resource files)")

    print()
    print(f"  To restore, restore the PostgreSQL database and volumes.")
    print(f"  The API JSON dumps serve as a human-readable reference.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()