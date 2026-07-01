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

All services are exposed at `{name}.rostor.internal` via Traefik. Add `*.rostor.internal` to your DNS (Pi-hole, router, or `/etc/hosts` pointing to your cluster's ingress IP).

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
| | AdGuard Home | adguard.rostor.internal | ✅ |
| | Authentik | authentik.rostor.internal | ✅ |
| **Media** | Jellyfin | jellyfin.rostor.internal | ✅ |
| | Immich | immich.rostor.internal | ✅ |
| | Audiobookshelf | audiobookshelf.rostor.internal | ✅ |
| | Navidrome | navidrome.rostor.internal | ✅ |
| | Komga | komga.rostor.internal | ✅ |
| | Sonarr | sonarr.rostor.internal | ✅ |
| | Radarr | radarr.rostor.internal | ✅ |
| | Lidarr | lidarr.rostor.internal | ✅ |
| | Readarr | readarr.rostor.internal | ✅ |
| | Bazarr | bazarr.rostor.internal | ✅ |
| | Prowlarr | prowlarr.rostor.internal | ✅ |
| | Gluetun (VPN) | — | ✅ |
| **Productivity** | Nextcloud | nextcloud.rostor.internal | ✅ |
| | Wiki.js | wikijs.rostor.internal | ✅ |
| | Ollama | — | ✅ |
| | Open WebUI | ai.rostor.internal | ✅ |

## Storage

- **NFS Media** (`nfs-media` StorageClass): Static NFS PVs backed by a Synology NAS. Each app gets its own PV/PVC pair for the media mount at `/data`.
- **Synology CSI** (`synology-*-*` StorageClasses): ISCSI and SMB volumes provisioned on demand from the Synology NAS, with `Retain` reclaim policy.
- **Longhorn** (`longhorn` — default for config PVCs): Replicated block storage across both nodes (2 replicas). All app config/data PVCs use this class — survives pod reschedules and ArgoCD redeploys.

## Secrets

Secrets use [sealed-secrets](https://github.com/bitnami-labs/sealed-secrets). Encrypted `SealedSecret` manifests live alongside each app. They're decrypted automatically by the sealed-secrets controller at sync time.

## Notes

- The control node may need taints removed to run workloads: `kubectl taint nodes --all node-role.kubernetes.io/control-plane-`
- Config PVCs use Longhorn with 2 replicas, so data persists across redeploys. For migration-level backups, see `scripts/backup-*-configs.sh` or `scripts/authentik-migrate.py`.
- NFS-backed media mounts are stateless from the cluster's perspective — the Synology owns the data.