#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KUBESEAL_OPTS="--controller-name=sealed-secrets --controller-namespace=sealed-secrets"

echo "=== Fetching sealed-secrets cert ==="
kubeseal $KUBESEAL_OPTS --fetch-cert > /tmp/sealed-secrets-cert.pem

echo ""
echo "=== OIDC Secrets Resealer ==="
echo "Enter the client-id and client-secret from Authentik for each app."
echo "Press Enter to skip an app."
echo ""

# --- komga ---
read -rp "komga client-id (default: komga): " KOMGA_ID
KOMGA_ID="${KOMGA_ID:-komga}"
read -rsp "komga client-secret (leave empty to skip): " KOMGA_SECRET
echo ""
if [ -n "$KOMGA_SECRET" ]; then
  kubectl create secret generic komga-oidc --namespace komga \
    --from-literal=client-id="$KOMGA_ID" \
    --from-literal=client-secret="$KOMGA_SECRET" \
    --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
    > "$REPO_ROOT/apps/media/komga/sealed-secrets.yaml"
  echo "  -> komga done"
else
  echo "  -> komga skipped"
fi

# --- forgejo ---
read -rp "forgejo OAuth key (default: forgejo): " FORGEJO_KEY
FORGEJO_KEY="${FORGEJO_KEY:-forgejo}"
read -rsp "forgejo OAuth secret (leave empty to skip): " FORGEJO_SECRET
echo ""
if [ -n "$FORGEJO_SECRET" ]; then
  kubectl create secret generic forgejo-oauth-secret --namespace forgejo \
    --from-literal=key="$FORGEJO_KEY" \
    --from-literal=secret="$FORGEJO_SECRET" \
    --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
    > "$REPO_ROOT/apps/productivity/forgejo/sealed-secrets.yaml"
  echo "  -> forgejo done"
else
  echo "  -> forgejo skipped"
fi

# --- homarr ---
read -rp "homarr OIDC client-id (default: homarr): " HOMARR_ID
HOMARR_ID="${HOMARR_ID:-homarr}"
read -rsp "homarr OIDC client-secret (leave empty to skip): " HOMARR_SECRET
echo ""
if [ -n "$HOMARR_SECRET" ]; then
  kubectl create secret generic homarr-secrets --namespace homarr \
    --from-literal=db-encryption-key=$(openssl rand -hex 32) \
    --from-literal=oidc-client-id="$HOMARR_ID" \
    --from-literal=oidc-client-secret="$HOMARR_SECRET" \
    --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
    > "$REPO_ROOT/apps/productivity/homarr/sealed-secrets.yaml"
  echo "  -> homarr done (db-encryption-key regenerated)"
else
  echo "  -> homarr skipped"
fi

# --- open-webui ---
read -rp "open-webui OIDC client-id (default: open-webui): " OWUI_ID
OWUI_ID="${OWUI_ID:-open-webui}"
read -rsp "open-webui OIDC client-secret (leave empty to skip): " OWUI_SECRET
echo ""
if [ -n "$OWUI_SECRET" ]; then
  kubectl create secret generic open-webui-secrets --namespace open-webui \
    --from-literal=WEBUI_ADMIN_PASSWORD=$(openssl rand -base64 32) \
    --from-literal=WEBUI_SECRET_KEY=$(openssl rand -hex 64) \
    --from-literal=oidc-client-id="$OWUI_ID" \
    --from-literal=oidc-client-secret="$OWUI_SECRET" \
    --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
    > "$REPO_ROOT/apps/productivity/open-webui/sealed-secrets.yaml"
  echo "  -> open-webui done (WEBUI_ADMIN_PASSWORD and WEBUI_SECRET_KEY regenerated)"
else
  echo "  -> open-webui skipped"
fi

# --- outline ---
read -rsp "outline OIDC_CLIENT_SECRET (leave empty to skip): " OUTLINE_SECRET
echo ""
if [ -n "$OUTLINE_SECRET" ]; then
  kubectl create secret generic outline-oidc-secrets --namespace outline \
    --from-literal=OIDC_CLIENT_SECRET="$OUTLINE_SECRET" \
    --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
    > "$REPO_ROOT/apps/productivity/outline/sealed-secrets.yaml"
  echo "  -> outline done"
else
  echo "  -> outline skipped"
fi

# --- sure ---
read -rsp "sure OIDC_CLIENT_SECRET (leave empty to skip): " SURE_SECRET
echo ""
if [ -n "$SURE_SECRET" ]; then
  kubectl create secret generic sure-oidc-secrets --namespace sure \
    --from-literal=OIDC_CLIENT_SECRET="$SURE_SECRET" \
    --dry-run=client -o yaml | kubeseal $KUBESEAL_OPTS --cert=/tmp/sealed-secrets-cert.pem -o yaml \
    > "$REPO_ROOT/apps/productivity/sure/sealed-secrets.yaml"
  echo "  -> sure done"
else
  echo "  -> sure skipped"
fi

echo ""
echo "=== Done ==="