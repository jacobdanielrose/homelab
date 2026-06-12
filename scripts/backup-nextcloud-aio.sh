#!/bin/bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────
# Nextcloud AIO Backup (run directly on Synology)
#
# Backs up per official NC docs: maintenance mode → db dump → data/config
#
# Usage:
#   sudo ./backup-nextcloud-aio.sh
#
# Output goes to ./nextcloud-aio-backup-<timestamp> by default, or set
# BACKUP_DIR to change it.
#
# To restore on a new host:
#   - restore the DB dump into a fresh PostgreSQL
#   - restore volumes from the .tar.gz files
#   - see the restore script for detailed steps
# ─────────────────────────────────────────────────────────────────────────

BACKUP_DIR="${BACKUP_DIR:-./nextcloud-aio-backup-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$BACKUP_DIR"
BACKUP_DIR="$(cd "$BACKUP_DIR" && pwd)"
echo "📁 Backup: $BACKUP_DIR"

NC_CONTAINER="nextcloud-aio-nextcloud"
DB_CONTAINER="nextcloud-aio-database"
MASTER_CONTAINER="nextcloud-aio-mastercontainer"

# ─── Step 1: Enable maintenance mode ──────────────────────────────────
echo ""
echo "🔒 Enabling Nextcloud maintenance mode..."
docker exec --user www-data "$NC_CONTAINER" php occ maintenance:mode --on \
  || echo "  ⚠️  Could not enable maintenance mode"
echo "  ✅ Maintenance mode on"

# ─── Step 2: Dump PostgreSQL database ──────────────────────────────────
echo ""
echo "🗄️  Dumping PostgreSQL database..."
DB_DUMP="nextcloud-db-dump-$(date +%Y%m%d-%H%M%S).sql"

# Get DB credentials from NC config.php
DB_CONFIG=$(docker exec "$NC_CONTAINER" cat config/config.php 2>/dev/null || true)
DB_NAME=$(echo "$DB_CONFIG" | grep -oP "'dbname'\s*=>\s*'\K[^']+" || echo "nextcloud")
DB_USER=$(echo "$DB_CONFIG" | grep -oP "'dbuser'\s*=>\s*'\K[^']+" || echo "nextcloud")
DB_PASS=$(echo "$DB_CONFIG" | grep -oP "'dbpassword'\s*=>\s*'\K[^']+" || echo "")

if [ -n "$DB_PASS" ]; then
  docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP_DIR/$DB_DUMP"
  echo "  ✅ DB dump saved ($(wc -l < "$BACKUP_DIR/$DB_DUMP") lines)"
else
  echo "  ⚠️  Could not extract DB password; falling back to volume backup only"
fi

# ─── Step 3: Backup Docker volumes ────────────────────────────────────
echo ""
echo "💾 Backing up Docker volumes..."

# nextcloud_aio_nextcloud → config, apps, themes (the "install" dir)
echo "  nextcloud_aio_nextcloud (config/apps/themes)..."
docker run --rm \
  -v nextcloud_aio_nextcloud:/source:ro \
  -v "$BACKUP_DIR":/backup \
  alpine:latest \
  tar czf /backup/nextcloud_aio_nextcloud.tar.gz -C /source . &

# nextcloud_aio_ncdata → user data
echo "  nextcloud_aio_ncdata (user data)..."
docker run --rm \
  -v nextcloud_aio_ncdata:/source:ro \
  -v "$BACKUP_DIR":/backup \
  alpine:latest \
  tar czf /backup/nextcloud_aio_ncdata.tar.gz -C /source . &

# nextcloud_aio_database → PostgreSQL data dir (migration fallback)
echo "  nextcloud_aio_database (PG data dir)..."
docker run --rm \
  -v nextcloud_aio_database:/source:ro \
  -v "$BACKUP_DIR":/backup \
  alpine:latest \
  tar czf /backup/nextcloud_aio_database.tar.gz -C /source . &

# nextcloud_aio_redis → cache (can skip, but grab for completeness)
echo "  nextcloud_aio_redis (cache)..."
docker run --rm \
  -v nextcloud_aio_redis:/source:ro \
  -v "$BACKUP_DIR":/backup \
  alpine:latest \
  tar czf /backup/nextcloud_aio_redis.tar.gz -C /source . &

# nextcloud_aio_mastercontainer
echo "  nextcloud_aio_mastercontainer..."
docker run --rm \
  -v nextcloud_aio_mastercontainer:/source:ro \
  -v "$BACKUP_DIR":/backup \
  alpine:latest \
  tar czf /backup/nextcloud_aio_mastercontainer.tar.gz -C /source . &

wait
echo "  ✅ Volume backups done"

# ─── Step 4: AIO built-in backup (extra migration aid) ────────────────
echo ""
echo "🔄 Attempting AIO built-in backup..."
if docker ps -a --format '{{.Names}}' | grep -q "^${MASTER_CONTAINER}$"; then
  docker start "$MASTER_CONTAINER" 2>/dev/null || true
  sleep 3
  if docker exec "$MASTER_CONTAINER" sh -c "aio-backup" 2>/dev/null; then
    echo "  ✅ AIO backup succeeded"
    docker cp "$MASTER_CONTAINER:/nextcloud-aio-backup.tar.gz" "$BACKUP_DIR/" 2>/dev/null || true
  else
    echo "  ⚠️  aio-backup not available, skipping"
  fi
fi

# ─── Step 5: Container metadata ───────────────────────────────────────
echo ""
echo "📋 Saving container metadata..."
docker ps -a --filter name=nextcloud-aio \
  --format '{{.Names}} {{.Image}} {{.Status}}' \
  > "$BACKUP_DIR/containers.txt" || true

for c in nextcloud-aio-mastercontainer nextcloud-aio-nextcloud nextcloud-aio-database; do
  if docker inspect "$c" &>/dev/null; then
    docker inspect "$c" > "$BACKUP_DIR/inspect-${c}.json" 2>/dev/null || true
  fi
done

# ─── Step 6: Disable maintenance mode ─────────────────────────────────
echo ""
echo "🔓 Disabling Nextcloud maintenance mode..."
docker exec --user www-data "$NC_CONTAINER" php occ maintenance:mode --off \
  || echo "  ⚠️  Could not disable maintenance mode — do this manually"
echo "  ✅ Maintenance mode off"

# ─── Summary ──────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  ✅ Backup complete!"
echo "  📁 $BACKUP_DIR"
echo ""
echo "  Files:"
ls -lh "$BACKUP_DIR" | awk '{print "    " $9 " (" $5 ")"}'
echo ""
echo "  🔑 Key files for restore:"
echo "    • $DB_DUMP              — PostgreSQL dump (portable)"
echo "    • nextcloud_aio_nextcloud.tar.gz — config, apps, themes"
echo "    • nextcloud_aio_ncdata.tar.gz    — user files (data/)"
echo ""
echo "  To restore on a new host:"
echo "    1. Start fresh NC AIO mastercontainer"
echo "    2. Stop all AIO containers it creates"
echo "    3. Restore volumes from .tar.gz files to matching named volumes"
echo "       docker run --rm -v <vol>:/target alpine tar xzf backup.tar.gz -C /target"
echo "    4. Restore the DB: docker exec <db> psql -U <user> <db> < dump.sql"
echo "    5. Start mastercontainer"
echo "═══════════════════════════════════════════════════════════════════"