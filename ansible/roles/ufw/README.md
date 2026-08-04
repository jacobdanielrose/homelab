# ufw
# Configures UFW firewall with sane defaults for a k3s node.
# Opens SSH, k3s API, Flannel VXLAN/WireGuard, kubelet, and node_exporter.

## Requirements

Requires the `community.general` collection:

```bash
ansible-galaxy collection install community.general
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `ufw_enabled` | `true` | Enable UFW |
| `ufw_default_deny_incoming` | `true` | Default deny incoming |
| `ufw_default_allow_outgoing` | `true` | Default allow outgoing |
| `ufw_logging` | `low` | Log level (off, low, medium, high) |
| `ufw_rules` | (see below) | Base rules for k3s + monitoring |
| `ufw_extra_rules` | `[]` | Additional rules to append |

### Default rules opened

| Port | Proto | Purpose |
|---|---|---|
| 22 | TCP | SSH |
| 6443 | TCP | k3s API server |
| 8472 | UDP | Flannel VXLAN |
| 51820-51821 | UDP | Flannel WireGuard |
| 10250 | TCP | kubelet metrics |
| 10256 | TCP | kube-proxy |
| 9100 | TCP | node_exporter |

## Example playbook

```yaml
- hosts: all
  roles:
    - role: ufw
      vars:
        ufw_extra_rules:
          - { port: "8080", proto: "tcp", rule: "allow", comment: "custom app" }
```