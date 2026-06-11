# Homelab

GitOps-managed Kubernetes homelab powered by [ArgoCD](https://argo-cd.readthedocs.io/).

## Quick Start

### Prerequisites

- A Kubernetes cluster (K3s, Kind, or any K8s distro)
- `kubectl` configured with cluster access
- `argocd` CLI (optional, for debugging)

### Bootstrap

```bash
# 1. Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 2. Wait for ArgoCD to be ready
kubectl wait -n argocd --for=condition=Ready pods --all --timeout=5m

# 3. Apply the root app
kubectl apply -f argocd/root-app.yaml

# 4. (Optional) Get the initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

That's it. The root app watches the `argocd/` directory, which deploys three category-level apps (`infra`, `media`, `productivity`), which in turn deploy all individual services. Everything syncs automatically — push to `main` and ArgoCD applies it.

### Access Services

All services are exposed at `{name}.rostor.local` via Traefik. Add `*.rostor.local` to your DNS (Pi-hole, router, or `/etc/hosts` pointing to your cluster's ingress IP).

## Repository Layout

```
argocd/                          # Root app watches here
  root-app.yaml                  # Bootstrap: applied once via kubectl
  infra.yaml                     # Deploys apps/infra/
  media.yaml                     # Deploys apps/media/
  productivity.yaml              # Deploys apps/productivity/
apps/
  infra/                         # Infrastructure: Traefik, cert-manager, etc.
  media/                         # Media: Jellyfin, Immich, *arr stack, etc.
  productivity/                  # Productivity: Nextcloud, Ollama, etc.
scripts/                         # Utility scripts (config backups, etc.)
```

## Active Services

| Category | Service | Hostname | Status |
|---|---|---|---|
| **Infra** | Traefik (ingress) | — | ✅ |
| | cert-manager | — | ✅ |
| | sealed-secrets | — | ✅ |
| | MetalLB | — | ✅ |
| | AdGuard Home | adguard.rostor.local | ✅ |
| | Authentik | authentik.rostor.local | ✅ |
| **Media** | Jellyfin | jellyfin.rostor.local | ✅ |
| | Immich | immich.rostor.local | ✅ |
| | Audiobookshelf | audiobookshelf.rostor.local | ✅ |
| | Navidrome | navidrome.rostor.local | ✅ |
| | Komga | komga.rostor.local | ✅ |
| | Sonarr | sonarr.rostor.local | ✅ |
| | Radarr | radarr.rostor.local | ✅ |
| | Lidarr | lidarr.rostor.local | ✅ |
| | Readarr | readarr.rostor.local | ✅ |
| | Bazarr | bazarr.rostor.local | ✅ |
| | Prowlarr | prowlarr.rostor.local | ✅ |
| | Gluetun (VPN) | — | ✅ |
| **Productivity** | Nextcloud | nextcloud.rostor.local | ✅ |
| | Wiki.js | wikijs.rostor.local | ✅ |
| | Ollama | — | ✅ |
| | Open WebUI | ai.rostor.local | ✅ |

## Storage

- **NFS Media** (`nfs-media` StorageClass): Static NFS PVs backed by a Synology NAS. Each app gets its own PV/PVC pair for the media mount at `/data`.
- **Local Path** (`local-storage` — default): Config PVCs for app state.

## Secrets

Secrets use [sealed-secrets](https://github.com/bitnami-labs/sealed-secrets). Encrypted `SealedSecret` manifests live alongside each app. They're decrypted automatically by the sealed-secrets controller at sync time.

## Notes

- The control node may need taints removed to run workloads: `kubectl taint nodes --all node-role.kubernetes.io/control-plane-`
- NFS-backed configs are ephemeral. Use `scripts/backup-arr-configs.sh` to back up *arr app state before node reboots or PVC teardowns.