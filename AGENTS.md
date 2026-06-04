# AGENTS.md — Homelab GitOps Repository

## Overview

This is a **GitOps homelab** managed entirely through **ArgoCD** using the **App-of-Apps pattern**. There is no build system, no tests, and no code — only Kubernetes manifests and Helm `values.yaml` files. Changes pushed to `main` are automatically applied to the cluster.

---

## Architecture: App-of-Apps Pattern

```
argocd/root-app.yaml          ← Bootstrapped manually once; watches argocd/ dir
  ├── argocd/infra.yaml        → deploys everything in apps/infra/
  ├── argocd/media.yaml        → deploys everything in apps/media/
  └── argocd/productivity.yaml → deploys everything in apps/productivity/
```

- `argocd/root-app.yaml` is the single bootstrap resource applied to the cluster once via `kubectl apply`. After that ArgoCD manages itself.
- Each `argocd/*.yaml` is an ArgoCD `Application` pointing at a subdirectory of `apps/`. ArgoCD recursively deploys all manifests found there.
- Apps in `apps/media/` are themselves ArgoCD `Application` manifests — a second layer of app-of-apps — pointing at external Helm chart registries.

---

## Repository Layout

```
argocd/                        # Layer 1: category-level ArgoCD Applications
apps/
  infra/
    adguard/                   # Empty — planned, not yet implemented
    authentik/                 # Empty — planned, not yet implemented
  media/
    namespace-media.yaml       # Creates the `media` namespace
    *-app.yaml                 # ArgoCD Application per media service
    arr-stack/
      *-app.yaml               # ArgoCD Applications for *arr + gluetun
    immich/values.yaml         # Helm overrides for immich
    jellyfin/values.yaml       # Helm overrides for jellyfin
    audiobookshelf/values.yaml # Helm overrides for audiobookshelf
  productivity/
    nextcloud/                 # Empty — planned, not yet implemented
```

---

## Helm Chart Sources

Three different OCI/HTTP Helm registries are used:

| Registry | Used by |
|---|---|
| `oci://ghcr.io/bjw-s-labs/charts` | All *arr apps, gluetun, bazarr |
| `oci://ghcr.io/immich-app/immich-charts/immich` | immich |
| `oci://oci.trueforge.org/truecharts/navidrome` | navidrome |
| `https://jellyfin.github.io/jellyfin-helm` | jellyfin |
| `https://christianhuth.github.io/helm-charts` | audiobookshelf |
| `https://repo.helmforge.dev` | komga |

---

## Two Patterns for Helm Apps

**With custom values** — `helm.valueFiles` points back into this repo:
```yaml
source:
  repoURL: https://jellyfin.github.io/jellyfin-helm
  chart: jellyfin
  targetRevision: 3.2.0
  helm:
    valueFiles:
      - apps/media/jellyfin/values.yaml
```
The `values.yaml` lives at `apps/media/<appname>/values.yaml`.

**Without custom values** — `helm:` block is commented out (most *arr apps):
```yaml
source:
  repoURL: oci://ghcr.io/bjw-s-labs/charts
  chart: sonarr
  targetRevision: 5.0.1
  #helm:
  #  valueFiles:
  #    - apps/media/arr-stack/sonarr/values.yaml
```
The commented-out path shows the *intended* location for values when customization is needed later.

---

## Conventions

- **File naming**: `{appname}-app.yaml` for ArgoCD Application manifests.
- **Namespace**: All deployed apps target namespace `media`, including infra and productivity apps (appears to be a copy-paste default — verify before adding new category apps).
- **Ingress**: Traefik is the ingress controller (`ingressClassName: traefik`).
- **Hostnames follow**: `{service}.home.example.com` (placeholder — real hostnames differ on the actual cluster).
- **PVCs**: Either `existingClaim` (pre-provisioned externally) or dynamic provisioning with `storageClass: standard`.
- **Sync policy**: Always `automated` with `prune: true` and `selfHeal: true` — every push to `main` is immediately applied.

---

## Known Issues / Gotchas

- **`immich-app.yaml` has a YAML bug**: `helm:` appears on its own line without indented children — `valueFiles` is a sibling instead of a child. This means ArgoCD ignores the values file. The correct structure needs `helm:` and `valueFiles:` properly nested (see jellyfin-app.yaml for the correct pattern).

- **`argocd/infra.yaml` and `argocd/productivity.yaml` have `namespace: media`** in their destination — this is likely a copy-paste error and should be `infra` / `productivity` respectively when those categories have real apps.

- **Automated pruning is live**: `prune: true` means deleting a file from this repo removes the resource from the cluster. Be deliberate when removing or renaming manifests.

- **No dry-run or staging**: There is no CI pipeline or linting. Validate YAML locally with `kubectl apply --dry-run=client -f <file>` or `helm template` before pushing.

---

## Adding a New App

1. Create `apps/<category>/<appname>-app.yaml` as an ArgoCD `Application` manifest.
2. If Helm overrides are needed, create `apps/<category>/<appname>/values.yaml` and reference it in `helm.valueFiles`.
3. The category-level ArgoCD app (`argocd/media.yaml` etc.) will automatically pick it up on the next sync.
4. No manual `kubectl apply` needed after the initial bootstrap.

---

## Bootstrap (first-time cluster setup)

```bash
kubectl apply -f argocd/root-app.yaml
```

This installs the root app; ArgoCD then reconciles the rest of the repo automatically.
