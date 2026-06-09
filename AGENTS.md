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
    grafana/values.yaml        # Helm overrides for Grafana
    loki/values.yaml           # Helm overrides for Loki
    prometheus/values.yaml     # Helm overrides for kube-prometheus-stack
    rustfs/                    # RustFS S3 object store for Loki
    traefik-app.yaml           # Traefik ingress controller (deployed via Helm)
    traefik/values.yaml        # Helm overrides for Traefik
  media/
    namespaces.yaml            # Creates one namespace per active media app
    storage/pvcs.yaml          # PVCs colocated in each app namespace
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
| `oci://ghcr.io/bjw-s-labs/helm/app-template` | *arr apps and gluetun via `app-template` |
| `oci://ghcr.io/immich-app/immich-charts/immich` | immich |
| `oci://oci.trueforge.org/truecharts/navidrome` | navidrome |
| `https://jellyfin.github.io/jellyfin-helm` | jellyfin |
| `https://christianhuth.github.io/helm-charts` | audiobookshelf |
| `https://repo.helmforge.dev` | komga |
| `oci://registry-1.docker.io/bitnamicharts` | authentik PostgreSQL |
| `https://grafana.github.io/helm-charts` | loki, grafana |
| `https://prometheus-community.github.io/helm-charts` | kube-prometheus-stack |
| `https://helm.traefik.io/traefik` | traefik |
| `https://nextcloud.github.io/helm/` | nextcloud |
| `https://charts.js.wiki` | wikijs |

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
The `values.yaml` lives at `apps/media/<appname>/values.yaml`. Active apps use ArgoCD multi-source Applications: one Helm chart source, one `$values` repo source, and one app resource path (`apps/media/<appname>`) for PVCs/support manifests.

**Arr-stack apps** — use bjw-s `app-template`; there are no individual bjw-s charts named `sonarr`, `radarr`, etc.:
```yaml
sources:
  - repoURL: oci://ghcr.io/bjw-s-labs/helm/app-template
    chart: app-template
    targetRevision: 5.0.1
    helm:
      valueFiles:
        - $values/apps/media/arr-stack/sonarr/values.yaml
  - repoURL: https://github.com/jacobdanielrose/homelab.git
    targetRevision: HEAD
    ref: values
```
Each app defines its image, service port, and persistence in `apps/media/arr-stack/<app>/values.yaml`.

---

## Conventions

- **File naming**: `{appname}-app.yaml` for ArgoCD Application manifests.
- **Namespace**: Media apps deploy into per-app namespaces (`jellyfin`, `immich`, `audiobookshelf`, `navidrome`, `komga`). Each app gets `syncOptions: CreateNamespace=true`.
- **Ingress**: Traefik is deployed by this repo as an ArgoCD Application (`apps/infra/traefik-app.yaml`). It uses `ingressClassName: traefik`.
- **Hostnames follow**: `{app}.home` — every app with an active ingress is exposed at `{name}.home` (e.g. `grafana.home`, `jellyfin.home`, `sonarr.home`). This is a local DNS domain handled by your router or Pi-hole — no public DNS or TLS is configured.
- **Traefik proxy**: Traefik v3 deployed via Helm chart `traefik` from `https://helm.traefik.io/traefik`. Both Kubernetes Ingress and CRD providers are enabled. Dashboard is off by default.
- **Metrics**: Prometheus metrics are enabled on Traefik (`addRoutersLabels`, `addServicesLabels`), scraped by kube-prometheus-stack.
- **PVCs and app-owned resources**: Each active app has `apps/media/<app>/resources.yaml` plus `kustomization.yaml`; the app `Application` includes that path as an additional ArgoCD source so PVCs and support resources appear inside the same Argo dashboard as the Helm release. Kubernetes PVCs are namespace-scoped, so shared claim names such as `media-nfs-pvc` are repeated in each app namespace that mounts them.
- **Sync policy**: Always `automated` with `prune: true` and `selfHeal: true` — every push to `main` is immediately applied.

---

## Known Issues / Gotchas

- **`argocd/infra.yaml` and `argocd/productivity.yaml` have `namespace: media`** in their destination — this is likely a copy-paste error and should be `infra` / `productivity` respectively when those categories have real apps.

- **Automated pruning is live**: `prune: true` means deleting a file from this repo removes the resource from the cluster. Be deliberate when removing or renaming manifests.

- **No dry-run or staging**: There is no CI pipeline or linting. Validate YAML locally with `kubectl apply --dry-run=client -f <file>` or `helm template` before pushing.

---

## Secrets Management (SOPS + Age)

Secrets are encrypted with [SOPS](https://github.com/getsops/sops) using [age](https://age-encryption.org/). Each app's secrets live in `apps/<category>/<app>/secrets.yaml` as a standard K8s Secret manifest, whole-file encrypted. ArgoCD decrypts them automatically at sync time.

### Key management

- **Private key** (backup this): `$HOME/.config/sops/age/keys.txt`
- **Public key**: `age1rrmavzfl5aarr7hs9y5yzvxn80szfjhs4xk63d6wsz8v88fcudaqsrpnnj`
- **Config**: `/.sops.yaml`

### Encrypted files

| File | What it contains |
|---|---|
| `apps/media/immich/secrets.yaml` | Immich Postgres credentials |
| `apps/infra/authentik/secrets.yaml` | Authentik secret key, bootstrap creds, postgres password |
| `apps/infra/loki/secrets.yaml` | Loki S3 access/secret key |
| `apps/infra/grafana/secrets.yaml` | Grafana admin password |
| `apps/infra/rustfs/values.yaml` | RustFS S3 access/secret key (field-level, chart inline) |
| `apps/productivity/nextcloud/secrets.yaml` | Nextcloud admin, postgres, redis passwords |
| `apps/productivity/open-webui/secrets.yaml` | Open WebUI secret key, admin password |

### Workflow

**View/edit an encrypted file:**
```bash
sops apps/infra/authentik/secrets.yaml
```
Opens in `$EDITOR` with decrypted content; re-encrypts on save.

**Encrypt a new secrets.yaml:**
```bash
sops --encrypt apps/myapp/secrets.yaml > apps/myapp/secrets.yaml.tmp
mv apps/myapp/secrets.yaml.tmp apps/myapp/secrets.yaml
```

**Add a new app with secrets:**
1. Create `apps/<category>/<app>/secrets.yaml` (plaintext K8s Secret)
2. Encrypt it: `sops --encrypt apps/.../secrets.yaml > tmp && mv tmp apps/.../secrets.yaml`
3. Add it to the app's `kustomization.yaml`
4. If no kustomization dir exists yet, add a 3rd ArgoCD source `path:` to the app manifest

### Cluster bootstrap (one-time)

```bash
# 1. Create the age key Secret
kubectl -n argocd create secret generic sops-age-key \
  --from-file=keys.txt=$HOME/.config/sops/age/keys.txt

# 2. Enable SOPS in ArgoCD
kubectl -n argocd patch configmap argocd-cm --type merge -p \
  '{"data": {"sops.enabled": "true"}}'

# 3. Restart repo-server
kubectl -n argocd rollout restart deployment argocd-repo-server
kubectl -n argocd rollout status deployment argocd-repo-server
```

### Key rotation

1. `age-keygen -o ~/.config/sops/age/keys-new.txt`
2. Add new public key to `/.sops.yaml` under `creation_rules[0].key_groups[0].age`
3. `sops updatekeys apps/media/immich/secrets.yaml` (repeat per file)
4. Update cluster Secret with new `keys.txt`
5. Remove old key from `/.sops.yaml` and `keys.txt`

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
