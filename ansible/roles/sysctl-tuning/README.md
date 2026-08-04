# sysctl-tuning
# Sets kernel parameters required for Kubernetes, disables swap, and
# tunes inotify/network limits.

## Variables

| Variable | Default | Description |
|---|---|---|
| `sysctl_disable_swap` | `true` | Disable swap |
| `sysctl_enable_ipv4_forwarding` | `true` | Enable IPv4 forwarding |
| `sysctl_enable_bridge_nf` | `true` | bridge-nf-call-iptables for k8s networking |
| `sysctl_inotify_max_user_watches` | `1048576` | Inotify watcher limit |
| `sysctl_vm_swappiness` | `0` | Swappiness (0 = no swap) |
| `sysctl_extra` | `{}` | Extra sysctl params as key/value pairs |

## Example playbook

```yaml
- hosts: k3s-servers:k3s-workers
  roles:
    - role: sysctl-tuning
      vars:
        sysctl_extra:
          net.ipv4.conf.all.rp_filter: 1
```