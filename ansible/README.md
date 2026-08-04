# Ansible — Homelab

Bootstrap bare-metal Linux nodes from zero to a fully running k3s cluster with ArgoCD managing all workloads.

## Quick start

```bash
# 1. Edit inventory.yml with your hosts, SSH key, and k3s token
vim inventory.yml

# 2. Prepare all nodes (tools, security, sysctl, ntp, etc.)
ansible-playbook prepare.yml

# 3. Install k3s + Longhorn + ArgoCD
ansible-playbook k3s.yml

# 4. Fetch kubeconfig to your workstation
ansible-playbook kubeconfig.yml
```

Or run everything in one shot:

```bash
ansible-playbook install-all.yml
```

## Inventory

Two groups in `inventory.yml`:

| Group | Hosts | Role |
|---|---|---|
| `k3s_servers` | k3s-master | Control plane |
| `k3s_workers` | k3s-node1, k3s-node2 | Workers |

## Playbooks

| Playbook | Runs on | What it does |
|---|---|---|
| `prepare.yml` | all | Common tools, /etc/hosts, chrony, sysctl tuning, SSH hardening, fail2ban, UFW, package upgrades, node_exporter |
| `k3s.yml` | k3s_servers, k3s_workers | k3s control plane → workers join → Longhorn disk prep → ArgoCD bootstrap |
| `install-all.yml` | all | prepare.yml + k3s.yml combined |
| `security.yml` | all | Reapply SSH hardening, fail2ban, UFW and show status |
| `update.yml` | all (rolling) | Package upgrades, kernel cleanup, reboot check |
| `kubeconfig.yml` | k3s_servers | Fetch kubeconfig, replace localhost with master IP |

## Roles

| Role | What it does |
|---|---|
| `common-tools` | Install vim, htop, jq, tcpdump, git, etc. |
| `hosts` | Manage /etc/hosts entries for cluster resolution |
| `ntp` | Install chrony, set timezone, wait for sync |
| `sysctl-tuning` | Disable swap, bridge-nf-call, inotify limits, vm.overcommit |
| `linux-hardening` | Lock down SSH (keys only, no root, no passwords), deploy authorized keys |
| `fail2ban` | 3 retries → 24h ban on SSH |
| `ufw` | Firewall: SSH, Cockpit, k3s API, Flannel, monitoring |
| `system-upgrade` | apt dist-upgrade, unattended-upgrades, reboot if needed |
| `node-exporter` | Prometheus node_exporter on port 9100 |
| `k3s-control` | Install k3s control plane with config.yaml |
| `k3s-agent` | Join worker to existing cluster |
| `longhorn-prep` | Detect secondary disk, format ext4, mount to /var/lib/longhorn |
| `k3s-argocd` | Install Helm, bootstrap ArgoCD, apply root Application |

## Ordering (for install-all.yml)

```
 1. common-tools      → packages
 2. hosts             → /etc/hosts
 3. ntp               → chrony + timezone
 4. sysctl-tuning     → kernel params, swap off
 5. linux-hardening   → SSH lockdown
 6. fail2ban          → brute-force protection
 7. ufw               → firewall rules
 8. system-upgrade    → packages + reboot
 9. node-exporter     → monitoring
10. k3s-control       → control plane
11. k3s-agent         → workers join
12. longhorn-prep     → storage disk
13. k3s-argocd        → GitOps bootstrap
```

## Requirements

- Ansible >= 2.15
- Collections: `ansible.posix`, `community.general`

```bash
ansible-galaxy collection install ansible.posix community.general
```