#!/usr/bin/env python3
"""
Authentik Migration Backup Tool

Designed for Authentik installed via community-scripts Proxmox VE LXC
(https://community-scripts.org/scripts/authentik), but works on any host
where the `ak` CLI is available.

How it works (5 steps):
  1. Global blueprint export   — `ak export_blueprint`
     Dumps ALL objects (providers, apps, flows, policies, stages, sources,
     property mappings, outposts, tenants, etc.) into a single YAML file
     that can be re-imported on the new instance via the Admin UI or API.

  2. Individual flow exports   — `ak list_flows` + `ak export_flow`
     Exports each flow separately into flows/flow-<slug>.yaml for
     granular import if you don't want everything at once.

  3. PostgreSQL dump           — `pg_dump`
     SQL dump of the authentik database. This is the most critical piece
     per official docs — without it, nothing can be restored.

  4. Static directories        — tar.gz archives
     media/     (/var/lib/authentik)       — icons, flow backgrounds, uploads
     certs/     (/etc/authentik/certs)     — TLS certificates on disk
     templates/ (/etc/authentik/templates) — custom UI overrides
     blueprints (/etc/authentik/blueprints) — blueprint files on disk

  5. Instance metadata         — `ak version`
     Saved to metadata.json and manifest.json.

Output structure:
  authentik-migrate-<timestamp>/
    ├── manifest.json                   — counts & file listing
    ├── metadata.json                   — backup time, ak version
    ├── authentik-blueprint-export.yaml — global blueprint (step 1)
    ├── authentik-database.sql          — PostgreSQL dump (step 3)
    ├── flows/
    │   ├── flow-<slug-1>.yaml          — individual flow exports (step 2)
    │   └── flow-<slug-2>.yaml
    └── volumes/
        ├── media.tar.gz                — static directories (step 4)
        ├── certs.tar.gz
        ├── custom-templates.tar.gz
        └── blueprints.tar.gz

To migrate to a new host:
  1. Copy the output directory to the new machine
  2. Restore the database:   psql -U authentik authentik < authentik-database.sql
  3. Import the blueprint via Admin UI → Blueprints → Import
     (or: ak import_blueprint authentik-blueprint-export.yaml)
  4. Restore static directories from volumes/*.tar.gz
  5. Restart authentik services

Usage:
  sudo ./authentik-migrate.py                              # full backup
  ./authentik-migrate.py --no-db                            # skip DB dump
  ./authentik-migrate.py --no-dirs                          # skip static dirs
  ./authentik-migrate.py --data /custom/path                # custom data dir
"""

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path


# ─── Default paths for a typical Authentik install ────────────────────────
DEFAULT_AK_BIN = "ak"
DEFAULT_DATA_DIR = "/var/lib/authentik"
DEFAULT_CERTS_DIR = "/etc/authentik/certs"
DEFAULT_TEMPLATES_DIR = "/etc/authentik/templates"
DEFAULT_BLUEPRINTS_DIR = "/etc/authentik/blueprints"
DEFAULT_DB_USER = "authentik"
DEFAULT_DB_NAME = "authentik"


def fmt_size(bytes_: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if bytes_ < 1024:
            return f"{bytes_:.1f} {unit}"
        bytes_ /= 1024
    return f"{bytes_:.1f} TB"


def run(cmd: list[str], timeout: int = 120,
        capture: bool = True) -> subprocess.CompletedProcess:
    """Run a command, return CompletedProcess."""
    try:
        return subprocess.run(
            cmd, capture_output=capture, text=True, timeout=timeout,
        )
    except FileNotFoundError:
        print(f"  ❌ Command not found: {cmd[0]}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("  ❌ Timed out")
        sys.exit(1)


def check_ak(ak_bin: str) -> bool:
    """Verify `ak` CLI is available."""
    r = run([ak_bin, "--help"], timeout=10)
    return r.returncode == 0


def backup_global_blueprint(ak_bin: str, output_dir: Path) -> str | None:
    """Run `ak export_blueprint` and save the YAML."""
    print("  Running `ak export_blueprint` ...", end=" ", flush=True)
    r = run([ak_bin, "export_blueprint"], timeout=300)
    if r.returncode == 0 and r.stdout:
        fname = "authentik-blueprint-export.yaml"
        (output_dir / fname).write_text(r.stdout)
        lines = r.stdout.strip().count("\n")
        print(f"✅ {lines} entries")
        return fname
    else:
        if r.stderr:
            print(f"⚠️  {r.stderr[:120]}")
        else:
            print("⚠️  No output (empty instance?)")
        return None


def backup_flows(ak_bin: str, output_dir: Path) -> int:
    """Export each flow via `ak export_flow <slug>`."""
    flow_dir = output_dir / "flows"
    flow_dir.mkdir(exist_ok=True)

    print("  Listing flows via `ak list_flows` ...", end=" ", flush=True)
    r = run([ak_bin, "list_flows"], timeout=30)
    if r.returncode != 0 or not r.stdout.strip():
        print("⚠️")
        return 0

    slugs = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
    print(f"{len(slugs)} found")

    exported = 0
    for slug in slugs:
        print(f"    {slug} ...", end=" ", flush=True)
        r2 = run([ak_bin, "export_flow", slug], timeout=60)
        if r2.returncode == 0 and r2.stdout:
            (flow_dir / f"flow-{slug}.yaml").write_text(r2.stdout)
            exported += 1
            print("✅")
        else:
            print(f"⚠️  ({r2.stderr[:50]})")

    return exported


def backup_database(output_dir: Path,
                    db_user: str, db_name: str) -> str | None:
    """Dump PostgreSQL database."""
    print("  Dumping PostgreSQL with pg_dump ...", end=" ", flush=True)
    db_file = output_dir / "authentik-database.sql"

    # Use pg_dump from the system, connecting via local socket (no password)
    cmd = [
        "pg_dump",
        "-U", db_user,
        "-d", db_name,
        "--no-owner",
        "--no-acl",
        # Use Unix socket — no password prompt on localhost
    ]

    r = run(cmd, timeout=300)
    if r.returncode == 0 and r.stdout:
        db_file.write_text(r.stdout)
        size = fmt_size(db_file.stat().st_size)
        print(f"✅ {size}")
        return db_file.name
    else:
        # Try with host option
        print(f"⚠️  ({r.stderr[:80]})")
        print("    Retrying with -h localhost ...", end=" ", flush=True)
        cmd.extend(["-h", "localhost"])
        r = run(cmd, timeout=300)
        if r.returncode == 0 and r.stdout:
            db_file.write_text(r.stdout)
            size = fmt_size(db_file.stat().st_size)
            print(f"✅ {size}")
            return db_file.name
        else:
            print(f"⚠️  ({r.stderr[:80]})")
            return None


def backup_directory(name: str, src: str, output_dir: Path) -> str | None:
    """Tar a directory and save to output_dir/volumes/."""
    vol_dir = output_dir / "volumes"
    vol_dir.mkdir(exist_ok=True)

    if not os.path.isdir(src):
        print(f"    {name} ({src}) ... not found, skipping")
        return None

    tar_path = vol_dir / f"{name}.tar.gz"
    print(f"    {name} ({src}) ...", end=" ", flush=True)

    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(src, arcname=".")

    size = fmt_size(tar_path.stat().st_size)
    print(f"✅ {size}")
    return tar_path.name


def main():
    parser = argparse.ArgumentParser(
        description="Authentik migration backup tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full backup (run on the LXC / VM directly):
  sudo ./authentik-migrate.py

  # Custom paths:
  ./authentik-migrate.py \\
      --ak /opt/authentik/venv/bin/ak \\
      --data /mnt/storage/authentik/media \\
      --db-user authentik --db-name authentik
        """,
    )

    parser.add_argument("--ak", default=DEFAULT_AK_BIN,
                        help="Path to `ak` CLI binary")
    parser.add_argument("--data", default=DEFAULT_DATA_DIR,
                        help="Authentik data directory (media files)")
    parser.add_argument("--certs-dir", default=DEFAULT_CERTS_DIR,
                        help="Custom certs directory")
    parser.add_argument("--templates-dir", default=DEFAULT_TEMPLATES_DIR,
                        help="Custom templates directory")
    parser.add_argument("--blueprints-dir", default=DEFAULT_BLUEPRINTS_DIR,
                        help="Custom blueprints directory")
    parser.add_argument("--db-user", default=DEFAULT_DB_USER,
                        help="PostgreSQL user")
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME,
                        help="PostgreSQL database name")
    parser.add_argument("--output", "-o",
                        default=f"./authentik-migrate-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                        help="Output directory")
    parser.add_argument("--no-db", action="store_true",
                        help="Skip database dump")
    parser.add_argument("--no-dirs", action="store_true",
                        help="Skip static directory backups")
    parser.add_argument("--no-flows", action="store_true",
                        help="Skip individual flow exports")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress progress output")

    args = parser.parse_args()

    # Validate
    if not check_ak(args.ak):
        print(f"❌ `{args.ak}` not available or not working")
        sys.exit(1)

    # Prepare output
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not args.quiet:
        print(f"📁 Output: {output_dir.resolve()}")
        print()

    info = {}

    # ── Step 1: Global blueprint export ──────────────────────────────
    print("📦 Global blueprint export")
    bp = backup_global_blueprint(args.ak, output_dir)
    if bp:
        info["blueprint_export"] = bp

    # ── Step 2: Individual flow exports ──────────────────────────────
    if not args.no_flows:
        print("\n🌊 Individual flow exports")
        count = backup_flows(args.ak, output_dir)
        info["flows_exported"] = count

    # ── Step 3: PostgreSQL dump ──────────────────────────────────────
    if not args.no_db:
        print("\n🗄️  Database dump")
        db = backup_database(output_dir, args.db_user, args.db_name)
        if db:
            info["db_dump"] = db

    # ── Step 4: Static directories ───────────────────────────────────
    if not args.no_dirs:
        print("\n💾 Static directories")
        dirs = [
            ("media", args.data),
            ("certs", args.certs_dir),
            ("custom-templates", args.templates_dir),
            ("blueprints", args.blueprints_dir),
        ]
        dir_info = {}
        for name, path in dirs:
            f = backup_directory(name, path, output_dir)
            if f:
                dir_info[name] = f
        if dir_info:
            info["directories"] = dir_info

    # ── Step 5: Instance metadata ────────────────────────────────────
    print("\nℹ️  Instance metadata")
    print("  Saving `ak version` and system info ...", end=" ", flush=True)
    r = run([args.ak, "version"], timeout=10)
    metadata = {
        "backup_time": datetime.now(timezone.utc).isoformat(),
        "ak_version": r.stdout.strip() if r.returncode == 0 else "unknown",
    }
    with open(output_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print("✅")

    # ── Manifest ─────────────────────────────────────────────────────
    manifest = {
        "backup_tool": "authentik-migrate.py",
        "backup_time": datetime.now(timezone.utc).isoformat(),
        "info": info,
    }
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # ── Summary ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  ✅ Migration backup complete!")
    print(f"  📁 {output_dir.resolve()}")
    print()

    for item in sorted(output_dir.iterdir()):
        if item.is_dir():
            sub = list(item.iterdir())
            size = sum(f.stat().st_size for f in sub if f.is_file())
            print(f"    📂 {item.name}/  ({len(sub)} files, {fmt_size(size)})")
        elif item.is_file():
            size = fmt_size(item.stat().st_size)
            print(f"    📄 {item.name} ({size})")

    print()
    print("  ── To migrate ──")
    print(f"  1. Copy this directory to the new host")
    print(f"  2. Restore the PostgreSQL dump: psql -U {args.db_user} {args.db_name} < {info.get('db_dump', '...')}")
    print(f"  3. Import the global blueprint via the Admin UI")
    if info.get("flows_exported", 0) > 0:
        print(f"  4. {info['flows_exported']} flow exports available in flows/")
    if "directories" in info:
        dirs = ", ".join(info["directories"].keys())
        print(f"  5. Restore static directories: {dirs}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()