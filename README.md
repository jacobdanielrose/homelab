# Homelab

GitOps-managed Kubernetes homelab powered by [ArgoCD](https://argo-cd.readthedocs.io/), provisioned with [Ansible](https://docs.ansible.com/).

## Quick Start

### From bare metal

```bash
# One-command bootstrap: prepare nodes, install k3s, deploy ArgoCD
ansible-playbook ansible/install-all.yml
```

See [ansible/README.md](ansible/README.md) for full details on playbooks, roles, and ordering.

### From an existing cluster

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

All services are exposed at `{name}.example.lab` (internal) or `{name}.example.cloud` (external via Cloudflare) via Traefik. Add `*.example.lab` to your DNS (Pi-hole, router, or `/etc/hosts` pointing to your cluster's ingress IP).

## Repository Layout

```
argocd/                          # Root app watches here
  root-app.yaml                  # Bootstrap: applied once via kubectl
  infra.yaml                     # Deploys apps/infra/
  media.yaml                     # Deploys apps/media/
  productivity.yaml              # Deploys apps/productivity/
apps/
  infra/                         # Infrastructure: Traefik, cert-manager, Technitium, etc.
  media/                         # Media: Jellyfin, Immich, *arr stack, etc.
  productivity/                  # Productivity: Nextcloud, Forgejo, n8n, Synapse, etc.
scripts/                         # Utility scripts (config backups, etc.)
```

## Active Services

| Category | Service | Hostname | Status |
|---|---|---|---|
| **Infra** | Traefik (ingress) | — | :white_check_mark: |
| | cert-manager | — | :white_check_mark: |
| | sealed-secrets | — | :white_check_mark: |
| | MetalLB | — | :white_check_mark: |
| | Technitium DNS | technitium.example.lab | :white_check_mark: |
| | Authentik | authentik.example.cloud | :white_check_mark: |
| | Prometheus | — | :white_check_mark: |
| | Loki | — | :white_check_mark: |
| | Grafana | grafana.example.internal | :white_check_mark: |
| | Longhorn | storage.example.internal | :white_check_mark: |
| | RustFS (S3) | — | :white_check_mark: |
| | Home Assistant | ha.example.cloud | :white_check_mark: |
| | ArgoCD | argocd.example.internal | :white_check_mark: |
| **Media** | Jellyfin | jellyfin.example.cloud | :white_check_mark: |
| | Immich | photos.example.cloud | :white_check_mark: |
| | Audiobookshelf | audiobooks.example.cloud | :white_check_mark: |
| | Navidrome | music.example.cloud | :white_check_mark: |
| | Komga | books.example.cloud | :white_check_mark: |
| | Seerr | seerr.example.cloud | :white_check_mark: |
| | Sonarr | sonarr.example.lab | :white_check_mark: |
| | Radarr | radarr.example.lab | :white_check_mark: |
| | Lidarr | lidarr.example.lab | :white_check_mark: |
| | Readarr | readarr.example.lab | :white_check_mark: |
| | Bazarr | bazarr.example.lab | :white_check_mark: |
| | Prowlarr | prowlarr.example.lab | :white_check_mark: |
| | Gluetun (VPN) | — | :white_check_mark: |
| | BookBounty | bookbounty.example.lab | :white_check_mark: |
| **Productivity** | Nextcloud | nextcloud.example.cloud | :white_check_mark: |
| | Ollama | ollama.example.cloud | :white_check_mark: |
| | Open WebUI | ai.example.cloud | :white_check_mark: |
| | Outline wiki | wiki.example.cloud | :white_check_mark: |
| | Homarr dashboard | homarr.example.cloud | :white_check_mark: |
| | Sure (finance) | finance.example.cloud | :white_check_mark: |
| | Forgejo (Git) | git.example.cloud | :white_check_mark: |
| | n8n automation | n8n.example.lab | :white_check_mark: |
| | Synapse (Matrix) | element.example.cloud | :white_check_mark: |
| | SearXNG search | search.example.cloud | :white_check_mark: |

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