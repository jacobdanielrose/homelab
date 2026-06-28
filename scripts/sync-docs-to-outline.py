#!/usr/bin/env python3
"""
Upload docs/ to Outline wiki via its REST API.
Zero external dependencies — uses only stdlib.

Usage:
  python3 scripts/sync-docs-to-outline.py --api-key <key> [--url https://wiki.rostor.cloud]

The script:
  1. Creates "Homelab" collection with _index.md as the collection description
  2. Creates "Rostor Cloud" collection with services/_index.md as the description
  3. Uploads all section pages as documents within each collection, grouped
     under category parent docs for Rostor Cloud
  4. Sets default permission to read, grants admin to configured users
"""

import argparse
import json
import os
import re
import sys
import urllib.request


# ── Configuration ──────────────────────────────────────────────────────────

ADMIN_USERS = ["admin@rostor.cloud", "jacobdanielrose@rostor.cloud"]

# Collection definitions
# doc_files: list of paths relative to docs_dir
# groups: dict of group_title -> list of doc_files INSIDE that group
# Docs listed directly under doc_files sit at root; those in groups nest under a parent doc.

COLLECTIONS = {
    "Homelab": {
        "description_file": "_index.md",
        "doc_files": [
            "network.md",
            "gitops.md",
            "kubernetes.md",
            "storage.md",
            "security.md",
            "monitoring.md",
            "scripts.md",
        ],
    },
    "Rostor Cloud": {
        "description_file": "services/_index.md",
        "doc_files": [
            "services/adguard.md",
            "services/authentik.md",
            "services/traefik.md",
            "services/hass.md",
        ],
        "groups": {
            "🎬 Media & Entertainment": [
                "services/jellyfin.md",
                "services/immich.md",
                "services/audiobookshelf.md",
                "services/navidrome.md",
                "services/komga.md",
            ],
            "📦 Arr-stack": [
                "services/sonarr.md",
                "services/radarr.md",
                "services/lidarr.md",
                "services/readarr.md",
                "services/prowlarr.md",
                "services/bazarr.md",
                "services/qbittorrent.md",
            ],
            "📋 Productivity": [
                "services/nextcloud.md",
                "services/outline.md",
                "services/homarr.md",
                "services/sure.md",
            ],
        },
    },
}


# ── API helpers ────────────────────────────────────────────────────────────

def api(url, api_key, endpoint, data=None, method="POST"):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        f"{url}/api/{endpoint}",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method=method,
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode())


def resolve_users(url, api_key, emails):
    result = api(url, api_key, "users.list", {"offset": 0, "limit": 100})
    users = {}
    for u in result.get("data", []):
        uemail = u.get("email", "")
        for email in emails:
            if email.lower() in uemail.lower():
                users[u["name"]] = u["id"]
    return users


def find_or_create_collection(url, api_key, name, description_text):
    result = api(url, api_key, "collections.list", {"offset": 0, "limit": 100})
    for c in result.get("data", []):
        if c["name"] == name:
            print(f"  Found collection: {name}")
            return c["id"]
    result = api(
        url, api_key, "collections.create",
        {"name": name, "description": description_text, "permission": "read", "sharing": True},
    )
    coll_id = result["data"]["id"]
    print(f"  Created collection: {name}")
    return coll_id


def grant_admin_access(url, api_key, collection_id, user_id):
    try:
        api(
            url, api_key, "collections.add_user",
            {"id": collection_id, "userId": user_id, "permission": "admin"},
        )
        print(f"  Granted admin to user: {user_id}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if "already a member" in body.lower():
            pass
        else:
            print(f"  WARN: could not grant admin to {user_id}: {e.code} {body}")


def find_existing_doc(url, api_key, collection_id, title):
    result = api(
        url, api_key, "documents.list",
        {"collectionId": collection_id, "limit": 100},
    )
    for d in result.get("data", []):
        if d["title"] == title:
            return d["id"]
    return None


def upload_doc(url, api_key, collection_id, md_path, parent_document_id=None):
    """Upload a markdown file as a document. Skips files starting with _ ."""
    basename = os.path.basename(md_path)
    if basename.startswith("_"):
        return

    with open(md_path, "r") as f:
        content = f.read()

    title_match = re.match(r"^# (.+)", content, re.MULTILINE)
    if not title_match:
        print(f"  SKIP (no # title): {md_path}")
        return
    title = title_match.group(1).strip()

    text = re.sub(r"^# .+(\r?\n|$)", "", content, count=1).strip()
    if not text:
        text = " "

    existing_id = find_existing_doc(url, api_key, collection_id, title)
    is_new = existing_id is None
    endpoint = "documents.create" if is_new else "documents.update"
    data = {
        "title": title,
        "text": text,
        "collectionId": collection_id,
        "publish": True,
    }
    if parent_document_id:
        data["parentDocumentId"] = parent_document_id
    if not is_new:
        data["id"] = existing_id

    api(url, api_key, endpoint, data)
    print(f"  {'CREATE' if is_new else 'UPDATE'}: {title}")


def extract_overview(md_path):
    """Extract title and 'What is it?' paragraph from a markdown doc."""
    with open(md_path, "r") as f:
        content = f.read()
    title_match = re.match(r"^# (.+)", content, re.MULTILINE)
    if not title_match:
        return None, None
    title = title_match.group(1).strip()
    # Grab the paragraph right after the first ## heading or the URL line
    match = re.search(r"## What is it\?\s*\n+(.*?)\n+(?=##|\Z)", content, re.DOTALL)
    blurb = match.group(1).strip() if match else ""
    return title, blurb


def build_group_text(group_title, docs_dir, file_list):
    """Build a friendly overview page for a group of services."""
    lines = [f"### {group_title}", "", "Here are the services in this category:"]
    for rel_path in file_list:
        full_path = os.path.join(docs_dir, rel_path)
        if not os.path.isfile(full_path):
            continue
        title, blurb = extract_overview(full_path)
        if title:
            url_match = re.search(r"\*\*URL:\*\*\s*\[([^\]]+)\]\(([^)]+)\)", blurb)
            if url_match:
                blurb = blurb.split("**URL:**")[0].strip()
                lines.append(f"- **[{title}]({url_match.group(2)})** — {blurb} [{url_match.group(1)}]({url_match.group(2)})")
            else:
                lines.append(f"- **{title}** — {blurb}")
    return "\n".join(lines)


def upsert_group_parent(url, api_key, collection_id, group_title, docs_dir, file_list):
    """Create or update the parent document for a group of services."""
    group_text = build_group_text(group_title, docs_dir, file_list)
    existing_id = find_existing_doc(url, api_key, collection_id, group_title)
    if existing_id:
        api(
            url, api_key, "documents.update",
            {"id": existing_id, "title": group_title, "text": group_text, "publish": True},
        )
        print(f"  UPDATE group parent: {group_title}")
        return existing_id

    result = api(
        url, api_key, "documents.create",
        {
            "title": group_title,
            "text": group_text,
            "collectionId": collection_id,
            "publish": True,
        },
    )
    parent_id = result["data"]["id"]
    print(f"  CREATE group parent: {group_title}")
    return parent_id


def read_file(docs_dir, rel_path):
    full_path = os.path.join(docs_dir, rel_path)
    if not os.path.isfile(full_path):
        return None
    with open(full_path, "r") as f:
        content = f.read()
    text = re.sub(r"^# .+(\r?\n|$)", "", content, count=1).strip()
    return text


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync docs/ to Outline wiki")
    parser.add_argument("--api-key", required=True, help="Outline API key")
    parser.add_argument("--url", default="https://wiki.rostor.cloud", help="Outline URL")
    parser.add_argument("--docs-dir", default="docs", help="Path to docs/ directory")
    args = parser.parse_args()

    docs_dir = os.path.abspath(args.docs_dir)
    if not os.path.isdir(docs_dir):
        print(f"Error: {docs_dir} not found")
        sys.exit(1)

    admin_users = {}
    try:
        admin_users = resolve_users(args.url, args.api_key, ADMIN_USERS)
        if admin_users:
            print(f"Found admin users: {list(admin_users.keys())}")
        else:
            print(f"WARN: Could not find users matching {ADMIN_USERS}")
    except Exception as e:
        print(f"WARN: Could not list users: {e}")

    for coll_name, config in COLLECTIONS.items():
        print(f"\n── {coll_name} ─{'─' * 40}")

        desc_text = read_file(docs_dir, config["description_file"])
        if desc_text is None:
            print(f"  ERROR: Description file not found: {config['description_file']}")
            continue

        coll_id = find_or_create_collection(
            args.url, args.api_key, coll_name, desc_text
        )

        # Upload root-level doc_files (ungrouped)
        for rel_path in config.get("doc_files", []):
            full_path = os.path.join(docs_dir, rel_path)
            if not os.path.isfile(full_path):
                print(f"  SKIP (not found): {rel_path}")
                continue
            upload_doc(args.url, args.api_key, coll_id, full_path)

        # Upload grouped docs under parent documents
        for group_title, file_list in config.get("groups", {}).items():
            parent_id = upsert_group_parent(args.url, args.api_key, coll_id, group_title, docs_dir, file_list)
            for rel_path in file_list:
                full_path = os.path.join(docs_dir, rel_path)
                if not os.path.isfile(full_path):
                    print(f"  SKIP (not found): {rel_path}")
                    continue
                upload_doc(args.url, args.api_key, coll_id, full_path, parent_document_id=parent_id)

        # Grant admin access
        for name, uid in admin_users.items():
            grant_admin_access(args.url, args.api_key, coll_id, uid)

    print("\nDone!")


if __name__ == "__main__":
    main()
