#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KUBESEAL_OPTS="--controller-name=sealed-secrets --controller-namespace=sealed-secrets"

echo "=== Fetching sealed-secrets cert from cluster ==="
kubeseal $KUBESEAL_OPTS --fetch-cert > /tmp/sealed-secrets-cert.pem

# Shared S3 credentials for loki/rustfs
S3_ACCESS_KEY=$(openssl rand -hex 16)
S3_SECRET_KEY=$(openssl rand -base64 32)

echo "=== Infra ==="

# authentik
kubectl create secret generic authentik-secrets --namespace authentik \
  --from-literal=password=$(openssl rand -base64 32) \
  --from-literal=postgres-password=$(openssl rand -base64 32) \
  --from-literal=secret-key=$(openssl rand -hex 64) \
  --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
  > "$REPO_ROOT/apps/infra/authentik/sealed-secrets.yaml"
echo "  -> authentik"

# loki (uses shared S3 creds)
kubectl create secret generic loki-s3-credentials --namespace loki \
  --from-literal=RUSTFS_ACCESS_KEY="$S3_ACCESS_KEY" \
  --from-literal=RUSTFS_SECRET_KEY="$S3_SECRET_KEY" \
  --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
  > "$REPO_ROOT/apps/infra/loki/sealed-secrets.yaml"
echo "  -> loki"

# rustfs (uses shared S3 creds)
kubectl create secret generic rustfs-secrets --namespace rustfs \
  --from-literal=access_key="$S3_ACCESS_KEY" \
  --from-literal=secret-key="$S3_SECRET_KEY" \
  --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
  > "$REPO_ROOT/apps/infra/rustfs/sealed-secrets.yaml"
echo "  -> rustfs"

echo "=== Media ==="

# immich
kubectl create secret generic immich-postgres-secret --namespace immich \
  --from-literal=POSTGRES_DB=immich \
  --from-literal=POSTGRES_PASSWORD=$(openssl rand -base64 32) \
  --from-literal=POSTGRES_USER=immich \
  --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
  > "$REPO_ROOT/apps/media/immich/sealed-secrets.yaml"
echo "  -> immich"

# komga (OIDC — skipped)
echo "  -> komga (SKIPPED — OIDC)"

# arr-stack
for app in sonarr radarr lidarr readarr prowlarr bookbounty; do
  kubectl create secret generic arr-api-key --namespace $app \
    --from-literal=API_KEY=$(openssl rand -hex 32) \
    --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
    > "$REPO_ROOT/apps/media/arr-stack/$app/sealed-secrets.yaml"
  echo "  -> $app"
done

# gluetun
kubectl create secret generic gluetun-secrets --namespace gluetun \
  --from-literal=WIREGUARD_PRIVATE_KEY=CHANGE_ME \
  --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
  > "$REPO_ROOT/apps/media/arr-stack/gluetun/sealed-secrets.yaml"
echo "  -> gluetun  (WIREGUARD_PRIVATE_KEY set to CHANGE_ME)"

echo "=== Productivity ==="

# forgejo (OIDC — skipped)
echo "  -> forgejo (SKIPPED — OIDC)"

# nextcloud (2 secrets)
kubectl create secret generic nextcloud-secrets --namespace nextcloud \
  --from-literal=db-username=nextcloud \
  --from-literal=password=$(openssl rand -base64 32) \
  --from-literal=postgres-password=$(openssl rand -base64 32) \
  --from-literal=redis-password=$(openssl rand -base64 32) \
  --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
  > "$REPO_ROOT/apps/productivity/nextcloud/sealed-secrets.yaml"
echo "  -> nextcloud-secrets"

kubectl create secret generic nextcloud-user --namespace nextcloud \
  --from-literal=password=$(openssl rand -base64 32) \
  --from-literal=username=admin \
  --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
  >> "$REPO_ROOT/apps/productivity/nextcloud/sealed-secrets.yaml"
echo "  -> nextcloud-user"

# outline (OIDC skipped, auto-gen and postgres resealed)
echo "  -> outline-oidc-secrets (SKIPPED — OIDC)"

kubectl create secret generic outline-auto-generated-secret --namespace outline \
  --from-literal=secret-key=$(openssl rand -hex 32) \
  --from-literal=utils-secret=$(openssl rand -hex 32) \
  --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
  > "$REPO_ROOT/apps/productivity/outline/sealed-secrets.yaml"
echo "  -> outline-auto-generated-secret"

kubectl create secret generic outline-postgres-secrets --namespace outline \
  --from-literal=password=$(openssl rand -base64 32) \
  --from-literal=postgres-password=$(openssl rand -base64 32) \
  --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
  >> "$REPO_ROOT/apps/productivity/outline/sealed-secrets.yaml"
echo "  -> outline-postgres-secrets"

# sure (OIDC skipped, everything else resealed)
echo "  -> sure-oidc-secrets (SKIPPED — OIDC)"

kubectl create secret generic sure-secrets --namespace sure \
  --from-literal=ACTIVE_RECORD_ENCRYPTION_DETERMINISTIC_KEY=$(openssl rand -hex 64) \
  --from-literal=ACTIVE_RECORD_ENCRYPTION_KEY_DERIVATION_SALT=$(openssl rand -hex 64) \
  --from-literal=ACTIVE_RECORD_ENCRYPTION_PRIMARY_KEY=$(openssl rand -hex 64) \
  --from-literal=SECRET_KEY_BASE=$(openssl rand -hex 64) \
  --from-literal=password=$(openssl rand -base64 32) \
  --from-literal=redis-password=$(openssl rand -hex 32) \
  --from-literal=username=sure \
  --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
  > "$REPO_ROOT/apps/productivity/sure/sealed-secrets.yaml"
echo "  -> sure-secrets"

# ghost
kubectl create secret generic ghost-user-secret --namespace ghost \
  --from-literal=ghost-password=$(openssl rand -base64 32) \
  --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
  > "$REPO_ROOT/apps/productivity/ghost/sealed-secrets.yaml"
echo "  -> ghost"

# homarr (OIDC — skipped)
echo "  -> homarr (SKIPPED — OIDC)"

# open-webui (OIDC — skipped)
echo "  -> open-webui (SKIPPED — OIDC)"

# stalwart-mail
kubectl create secret generic stalwart-mail --namespace stalwart-mail \
  --from-literal=FALLBACK_ADMIN_SECRET=$(openssl rand -base64 32) \
  --from-literal=METRICS_SECRET=$(openssl rand -base64 32) \
  --from-literal=METRICS_USERNAME=metrics \
  --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
  > "$REPO_ROOT/apps/productivity/stalwart-mail/sealed-secrets.yaml"
echo "  -> stalwart-mail"

# technitium
kubectl create secret generic technitium-secrets --namespace technitium \
  --from-literal=DNS_SERVER_ADMIN_PASSWORD=$(openssl rand -base64 32) \
  --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
  > "$REPO_ROOT/apps/infra/technitium/sealed-secrets.yaml"
echo "  -> technitium"

echo ""
echo "=== Done ==="
echo "S3_ACCESS_KEY=$S3_ACCESS_KEY"
echo "S3_SECRET_KEY=$S3_SECRET_KEY"
echo "Both loki and rustfs sealed-secrets have been updated with these S3 credentials."
echo "If you're using an external S3 provider (not rustfs), configure it there with these values."
echo ""
echo "WIREGUARD_PRIVATE_KEY was set to CHANGE_ME — edit apps/media/arr-stack/gluetun/sealed-secrets.yaml manually."
echo ""
echo "OIDC secrets were SKIPPED: komga, forgejo, homarr, open-webui, outline-oidc-secrets, sure-oidc-secrets"
echo "Reseal those separately after configuring Authentik."