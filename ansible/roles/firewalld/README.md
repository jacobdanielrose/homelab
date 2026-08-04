# firewalld
# Configures firewalld with sane defaults for a k3s node.
# Opens SSH, k3s API, Flannel VXLAN/WireGuard, kubelet, Cockpit, and node_exporter.

## Requirements

Requires the `ansible.posix` collection:

```bash
ansible-galaxy collection install ansible.posix
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `firewalld_enabled` | `true` | Enable firewalld |
| `firewalld_default_zone` | `public` | Default zone |
| `firewalld_rules` | (see below) | Base rules for k3s + monitoring |
| `firewalld_extra_rules` | `[]` | Additional rules to append |
| `firewalld_remove_ufw` | `true` | Remove UFW package if present |

### Default ports opened

| Port | Proto | Purpose |
|---|---|---|
| 22 | TCP | SSH |
| 6443 | TCP | k3s API server |
| 8472 | UDP | Flannel VXLAN |
| 51820-51821 | UDP | Flannel WireGuard |
| 10250 | TCP | kubelet metrics |
| 10256 | TCP | kube-proxy |
| 9090 | TCP | Cockpit |
| 9100 | TCP | node_exporter |

## Example playbook

```yaml
- hosts: all
  roles:
    - role: firewalld
      vars:
        firewalld_extra_rules:
          - { port: "8080/tcp", zone: "public", state: "enabled", comment: "custom app" }
```