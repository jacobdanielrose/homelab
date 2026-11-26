# AGENTS.md

Context file for AI coding agents working in this repo. Read this first instead of
re-exploring the tree. Keep it updated when conventions change.

> **Sanitization note:** this file intentionally uses placeholder domains
> (`example.lab`, `example.cloud`), generic node names, and no IPs, usernames, or
> email addresses. Real values live in the gitignored `docs/` folder and
> `ansible/inventory.yml`. Do not copy real hostnames/IPs/secrets into tracked files.

---

## 1. What this repo is

A **GitOps-managed Kubernetes homelab**. Everything is declarative YAML in Git;
ArgoCD reconciles the cluster to match `main`. There is no imperative workflow —
no `kubectl apply` for app changes, no SSH-and-edit.

| Layer | Tool | Location |
|---|---|---|
| Bare-metal provisioning | Ansible | `ansible/` |
| Cluster | K3s (3 nodes: 1 control-plane, 2 workers) | provisioned by Ansible |
| GitOps controller | ArgoCD (app-of-apps) | `argocd/` |
| Workloads | Helm charts + Kustomize overlays | `apps/{infra,media,productivity}/` |
| Ingress | Traefik | `apps/infra/traefik/` |
| TLS | cert-manager (Let's Encrypt DNS-01 + selfsigned) | `apps/infra/cert-manager/` |
| Secrets | Sealed Secrets (encrypted in Git) | `*/sealed-secrets.yaml` |
| Storage | Longhorn (default) + static NFS PVs | `apps/infra/longhorn/`, `apps/media/nfs-storage-class.yaml` |
| Auth | Authentik (OIDC per app) | `apps/infra/authentik/` |
| Observability | Prometheus, Loki, Grafana, Promtail, Uptime Kuma | `apps/infra/*` |
| Docs | Markdown, **gitignored**, synced to Outline wiki | `docs/` |

---

## 2. Golden rules

1. **Change the repo, not the cluster.** Edit YAML → commit → push to `main` →
   ArgoCD syncs (auto-sync, `prune: true`, `selfHeal: true`). Manual `kubectl edit`
   will be reverted.
2. **Never commit plaintext secrets.** Use `kubeseal` to produce a
   `SealedSecret` and commit only the encrypted manifest.
3. **`docs/` is gitignored** (`.gitignore`: "Private docs (not committed - copy to
   wiki)"). It contains real hostnames/IPs. Read it for context, but never copy
   its literal values into tracked files, and never `git add -f docs/`.
4. **`ansible/inventory.yml` and `ansible/kubeconfig` are gitignored.** Only
   `inventory.yml.example` is tracked. Never commit real inventory.
5. **Every new app must be registered in its category `kustomization.yaml`** or
   ArgoCD will never see it (see §9 for existing drift).
6. **Match existing conventions** — copy a neighbouring app rather than inventing
   a new layout. Consistency is the whole point of this repo.
7. **Never commit or push to `main`.** `main` is the deploy branch — ArgoCD
   auto-syncs it, so a push is a production deploy. Agents must either:
   - leave changes uncommitted and hand the user the exact `git` commands to run
     themselves, or
   - commit to a new feature branch (e.g. `feat/<short-description>`) and give the
     user the commands to merge into `main` when they're ready to deploy.

   Never run `git push origin main`, `git merge` into `main`, or `git commit` on
   `main` without explicit instruction.

---

## 3. Repository layout

```
argocd/                     # Root app watches this dir
  root-app.yaml             # Bootstrap, applied once by hand
  infra.yaml                # → apps/infra
  media.yaml                # → apps/media
  productivity.yaml         # → apps/productivity
  kustomization.yaml        # lists the 4 files above
apps/
  infra/                    # Traefik, cert-manager, MetalLB, Longhorn, Authentik,
                            # Technitium, Prometheus/Loki/Grafana/Promtail,
                            # RustFS, Home Assistant, ArgoCD ingress, Uptime Kuma,
                            # Homepage, sealed-secrets
  media/                    # Jellyfin, Immich, Audiobookshelf, Navidrome, Komga,
                            # Seerr, arr-stack/ (sonarr, radarr, lidarr, readarr,
                            # prowlarr, bazarr, bookbounty, gluetun)
  productivity/             # Nextcloud, Outline, Homarr, Sure, Ollama, Open WebUI,
                            # Forgejo, n8n, Synapse, SearXNG, Karakeep, Paperless,
                            # Paperless-GPT, Stirling PDF, AirVault, Stalwart,
                            # Bulwark, Vaultwarden, Ghost
ansible/                    # Playbooks + roles for bare-metal → K3s → ArgoCD
runbooks/                   # Operational runbooks (e.g. complete-strip.md)
scripts/                    # Manual utility scripts (see §8)
docs/                       # GITIGNORED. Human docs: architecture, per-service pages
```

---

## 4. App-of-apps hierarchy

```
homelab-root (argocd/root-app.yaml)
  └── watches argocd/  →  homelab-infra, homelab-media, homelab-productivity
        └── each watches apps/{category}/  →  one Application per service
              └── each Application points at a Helm chart + apps/{category}/{svc}/values.yaml
```

- Root app: `path: argocd`, namespace `argocd`.
- Category apps: `path: apps/{category}`, namespace `default` (they only create
  `Application` CRs in `argocd`).
- Leaf apps: `path: apps/{category}/{service}`, destination namespace = the
  service's own namespace, created via `CreateNamespace=true`.

---

## 5. Adding a new service (checklist)

1. Create `apps/{category}/{service}/` with:
   - `values.yaml` — Helm values (image, ingress, persistence, resources, env)
   - `certificates.yaml` — `cert-manager.io/v1` `Certificate` (only if exposed)
   - `sealed-secrets.yaml` — `SealedSecret`(s) (only if it needs secrets)
   - `kustomization.yaml` — lists the above as `resources:`
   - optional `resources.yaml` (extra K8s objects), `middleware.yaml`,
     `ingressroute.yaml`
2. Create `apps/{category}/{service}-app.yaml` — the ArgoCD `Application`.
3. Add `{service}-app.yaml` to `apps/{category}/kustomization.yaml`.
4. Commit + push. ArgoCD picks it up within ~3 min.

### ArgoCD Application template (multi-source Helm — the dominant pattern)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: <service>
  namespace: argocd
spec:
  project: default
  sources:
    - repoURL: <helm-chart-repo>
      chart: <chart>
      targetRevision: <pinned-version>
      helm:
        valueFiles:
          - $values/apps/<category>/<service>/values.yaml
    - repoURL: <this-repo-url>      # copy verbatim from a sibling manifest
      targetRevision: HEAD
      ref: values
    - repoURL: <this-repo-url>
      targetRevision: HEAD
      path: apps/<category>/<service>
  destination:
    server: https://kubernetes.default.svc
    namespace: <service>
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
      - PruneLast=true            # optional
  ignoreDifferences:              # optional, common for PVCs
    - group: ""
      kind: PersistentVolumeClaim
      jqPathExpressions:
        - .spec.finalizers
```

Variants seen in the repo:
- **Single-source Helm** (no local values file): `apps/infra/sealed-secrets-app.yaml`
  (OCI chart, no `values.yaml`).
- **Plain Kustomize** (no Helm): `apps/infra/argocd-ingress-app.yaml`,
  `apps/infra/hass-app.yaml`.
- **`argocd.argoproj.io/sync-wave`** annotation for ordering (e.g. Traefik `"0"`).
- **`managedNamespaceMetadata.labels`** to label the created namespace.
- **`ignoreDifferences`** on PVC `volumeName` / `finalizers` — needed for static
  NFS PVs and Longhorn.

> The repo URL is hardcoded in every Application manifest. When adding an app,
> copy the `repoURL` from an existing manifest in the same category — do not
> guess it.

---

## 6. Conventions

### Hostnames
- `{service}.example.lab` — internal only, resolved by in-cluster DNS (Technitium)
  to the Traefik MetalLB IP.
- `{service}.example.cloud` — public, proxied through Cloudflare.
- Some services are exposed on **both** (see `apps/infra/hass/ingressroute.yaml`).
- Naming is not always the app name: `photos` = Immich, `music` = Navidrome,
  `books` = Komga, `wiki` = Outline, `ai` = Open WebUI, `git` = Forgejo,
  `finance` = Sure, `search` = SearXNG, `element` = Synapse, `mail` = Stalwart,
  `webmail` = Bulwark, `downloads` = qBittorrent, `storage` = Longhorn,
  `ha` = Home Assistant.

### TLS
- `letsencrypt-prod` — default for anything with a real hostname (DNS-01 via
  Cloudflare, works for `.lab` too).
- `letsencrypt-staging` — pre-flight testing only.
- `selfsigned` — internal-only UIs (Longhorn, ArgoCD).
- Each exposed service has a `Certificate` in its own namespace; the TLS secret
  name convention is `{service}-{lab|cloud}-tls`.

### Ingress
- Prefer the chart's `ingress:` block with `className: traefik` and
  `cert-manager.io/cluster-issuer: letsencrypt-prod`.
- Use raw `IngressRoute` (`traefik.io/v1alpha1`) only when the chart can't express
  it (e.g. Home Assistant, ArgoCD ingress).
- Traefik runs 2 replicas, `allowCrossNamespace=true`, metrics on 9100.

### Storage
- **`longhorn`** (default SC) — all config/database PVCs. 2 replicas.
- **`nfs-media`** — `kubernetes.io/no-provisioner`, `WaitForFirstConsumer`;
  static PV/PVC pairs backed by the NAS, mounted at `/data` for media apps.
- **Synology CSI classes** — on-demand iSCSI/SMB volumes, `Retain` policy.
- Always set `storageClass` explicitly in values; don't rely on the default.

### Resources
- **Requests** only on core apps (immich, jellyfin, nextcloud, ollama, authentik,
  stalwart, karakeep, stirlingpdf, airvault, synapse).
- **Limits** on everything, typically 2–4× expected usage.
- No CPU limits on Immich pods (CPU is compressible; bursting is desirable).
- The control-plane node is small (~8 GB / 4c) — avoid memory-heavy pods there.
- Full table: `docs/resource-limits.md`.

### GPU
- Exactly one GPU in the cluster: **Intel Arc Pro B50 (Battlemage G21)** on
  `rostor-worker-node-1`, bound to the **`xe` KMD** (not `i915`).
- Exposed by the Intel GPU device plugin (`apps/infra/intel-gpu/`, plain
  Kustomize, pinned `intel/intel-gpu-plugin:0.37.1`) as **`gpu.intel.com/xe`**,
  time-sliced 2 ways (`-shared-dev-num=2`) so two pods can share the card.
- A `hostPath: /dev/dri` mount alone does **not** work: the pod's device cgroup
  denies the render node, `open()` returns EPERM and Vulkan/Level-Zero report
  zero devices. Always request the extended resource instead.
- Ollama drives the card through **Vulkan** (`OLLAMA_VULKAN=1`) and is pinned to
  `rostor-worker-node-1`. The otwld chart's `ollama.gpu` block only understands
  `nvidia`/`amd`, so the GPU is requested in `resources.limits` directly.
- There is **no NVIDIA stack** (no device plugin, no container toolkit); the
  `nvidia` / `nvidia-experimental` RuntimeClasses come from k3s and are unused.

### Enabling / disabling an app
- An app is deployed **only** if its `{service}-app.yaml` is listed under
  `resources:` in the category `kustomization.yaml`.
- **Commented-out entries are intentional.** A commented-out resource means the
  app is staged and may or may not be deployed later — it is not drift and not a
  bug. Leave commented entries alone unless asked to enable them.
- To enable: uncomment the line. To disable: comment it out (ArgoCD `prune: true`
  will remove the app on next sync).

### Secrets
```bash
kubeseal --format=yaml < secret.yaml > sealed-secrets.yaml
```
Sealed secrets are scoped to namespace + name; renaming either requires re-sealing.

### Auth
- Authentik is the IdP. Most apps integrate via **native OIDC** configured in
  `values.yaml` (grep `authentik` in `apps/` for examples).
- A few apps use Traefik `Middleware` (see `apps/media/immich/middleware.yaml`,
  `apps/productivity/nextcloud/middleware.yaml`,
  `apps/media/navidrome/middleware.yaml`, `apps/infra/argocd-ingress/resources.yaml`).
- `docs/security.md` describes a global forward-auth middleware; in practice
  per-app OIDC is what's deployed. Verify before assuming.

---

## 7. Ansible layer

`ansible/` bootstraps bare metal → hardened nodes → K3s → Longhorn → ArgoCD.
Once ArgoCD is up, Ansible is only used for node-level work (hardening, upgrades,
reboots). It does **not** manage workloads.

| Playbook | Purpose |
|---|---|
| `install-all.yml` | `prepare.yml` + `k3s.yml` |
| `prepare.yml` | tools, /etc/hosts, chrony, sysctl, SSH hardening, fail2ban, firewalld, upgrades, node_exporter |
| `k3s.yml` | control plane → workers join → Longhorn disk prep → ArgoCD bootstrap |
| `security.yml` | re-apply hardening, show status |
| `update.yml` | rolling package upgrades + cordon/drain/reboot/uncordon |
| `kubeconfig.yml` | fetch kubeconfig, rewrite server address |
| `info.yml` | read-only cluster info dump |
| `strip-cluster.yml` | tear down ArgoCD apps, Longhorn data, k3s (keeps hardening) |

Roles (in order): `common-tools`, `hosts`, `ntp`, `sysctl-tuning`,
`linux-hardening`, `fail2ban`, `firewalld`, `system-upgrade`, `node-exporter`,
`k3s-control`, `k3s-agent`, `longhorn-prep`, `k3s-argocd`.
Each role has its own `README.md` — read those for role-specific detail.

Requirements: Ansible ≥ 2.15, collections `ansible.posix`, `community.general`.

---

## 8. Scripts

`scripts/` holds **manual** utilities (not run by the cluster). Currently just one:

| Script | Purpose |
|---|---|
| `create-app-password.py` | Create a Stalwart (mail) app password via the JMAP admin API, reached through `kubectl exec` into the Stalwart pod. Reads the recovery-admin credential from the `stalwart-mail-stalwart-env` Secret at runtime — no credentials are stored in the script. |

Usage:

```bash
python3 scripts/create-app-password.py --list                 # list accounts
python3 scripts/create-app-password.py user@example.com \
    --description "Thunderbird on laptop"                     # create a password
```

`scripts/config-backups/` and `scripts/__pycache__/` are gitignored.

> Older backup/restore scripts (`backup-arr-configs`, `restore-arr-configs`,
> `backup-nextcloud-aio`, `authentik-backup`, `authentik-migrate`,
> `sync-docs-to-outline`) have been removed from the repo. `docs/scripts.md` still
> references them — treat that doc as stale.

---

## 9. Known drift / gotchas (verify before trusting)

- `apps/productivity/ghost/` exists with manifests but is **not active** — Ghost
  is staged for a possible future rollout. Don't "fix" this by wiring it into
  `apps/productivity/kustomization.yaml` unless explicitly asked to deploy it.
- `apps/infra/stirling-pdf/` is an **empty directory**; the real Stirling PDF app
  lives at `apps/productivity/stirlingpdf/`.
- `docs/` mentions services (e.g. qBittorrent, Gluetun) that are sub-apps of
  `apps/media/arr-stack/`, not top-level apps.
- `docs/` is gitignored, so it can lag behind the manifests. **Manifests are the
  source of truth**; docs are commentary.
- `docs/kubernetes.md` and `docs/issues.md` are stale on `rostor-worker-node-1`:
  it now *does* have a Longhorn disk (replicas split 96/96 with worker-node-0)
  and it holds the cluster's only GPU (Intel Arc Pro B50).
- `docs/scripts.md` lists backup/restore scripts that have been **removed** from
  `scripts/`. Only `create-app-password.py` remains.

---

## 10. Known operational issues (from `docs/issues.md`)

1. **THP-induced node flapping** — Transparent HugePages `always` on workload
   nodes causes `NotReady` flips under I/O load. Runtime fix:
   `echo never > /sys/kernel/mm/transparent_hugepage/{enabled,defrag}`.
   **Not persistent** across reboots (immutable OS) — a systemd tmpfiles unit is
   still TODO.
2. **Multi-Attach errors on RWO Longhorn volumes** — symptom of pod reschedules,
   not a root cause; resolves in ~30 s.
3. **Longhorn snapshot data loss** — no backup target configured, no recurring
   jobs, no Velero. `snapshotRevert` requires a detached volume; force-detaching
   can purge the snapshot chain. **Backups are the biggest open gap.**
4. **Redis split-brain** (Sure) — manual `SLAVEOF` + label fix.
5. **Host DNS single point of failure** — nodes resolve only via CoreDNS ClusterIP;
   no external fallback. Managed by systemd-resolved, so `/etc/resolv.conf` edits
   don't stick.
6. **`InvalidDiskCapacity 0`** — benign containerd 2.x + immutable-OS bug. Ignore.
7. **Journal corruption after hard crash** — previous-boot logs are lost.
8. **Longhorn replica imbalance** — one worker has no Longhorn disk; all replicas
   sit on the other two nodes. Fix: label the node
   `node.longhorn.io/create-default-disk=true`, then rebalance.

---

## 11. Validation before committing

```bash
# Render a kustomize overlay locally
kubectl kustomize apps/<category>
kubectl kustomize apps/<category>/<service>

# Lint YAML
yamllint apps/ argocd/            # if installed

# Check what ArgoCD would change (needs cluster access)
argocd app diff <app-name>
argocd app list

# Ansible syntax check
ansible-playbook --syntax-check ansible/install-all.yml
```

There is **no CI, no test suite, and no linter config** in this repo. Validation is
`kubectl kustomize` + ArgoCD diff + review.

---

## 12. Git workflow (agents: read this)

`main` is the deploy branch. Pushing to it triggers an ArgoCD sync within ~3
minutes. **Agents must not commit or push to `main`.**

Preferred: leave the working tree dirty and print the commands for the user.

```bash
git add <files>
git commit -m "<message>"
git push origin main
```

Alternative: commit to a feature branch, then hand over the merge commands.

```bash
# agent does this
git checkout -b feat/<short-description>
git add <files>
git commit -m "<message>"
git push -u origin feat/<short-description>

# user runs this when ready to deploy
git checkout main
git pull
git merge --no-ff feat/<short-description>
git push origin main
git branch -d feat/<short-description>
```

Commit message style: imperative subject, ≤72 chars, optional body explaining
*why*. One logical change per commit.

---

## 13. Where to look for more context

| Question | File |
|---|---|
| Architecture, domains, node roles | `docs/_index.md`, `docs/kubernetes.md` |
| Network, DNS, traffic flow | `docs/network.md` |
| Storage tiers, NAS exports | `docs/storage.md` |
| Auth, TLS, secrets, firewall | `docs/security.md` |
| Prometheus/Loki/Grafana setup | `docs/monitoring.md` |
| CPU/memory limits per app | `docs/resource-limits.md` |
| GitOps flow, app structure | `docs/gitops.md` |
| Backup scripts | `docs/scripts.md` |
| Known issues | `docs/issues.md` |
| Per-service human docs (43 pages) | `docs/services/*.md`, index at `docs/services/_index.md` |
| Full teardown procedure | `runbooks/complete-strip.md` |
| Ansible detail | `ansible/README.md` + `ansible/roles/*/README.md` |

---

## 14. Style

- YAML: 2-space indent, `---` document separators in multi-doc files.
- Pin Helm chart versions in `targetRevision` — never `*` or floating tags.
- One service per directory; one `Application` per service.
- Keep `values.yaml` minimal — only override chart defaults that matter.
- Prefer `ServerSideApply=true` for charts with large CRDs.
- Comments in values files explain *why* a value differs from the default.
