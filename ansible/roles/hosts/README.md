# hosts
# Manages /etc/hosts entries for cluster node resolution.

## Variables

| Variable | Default | Description |
|---|---|---|
| `hosts_entries` | `[]` | List of host entries (dict with `ip`, `names`, optional `aliases`) |
| `hosts_manage_loopback` | `true` | Ensure standard localhost entries exist |

## Example playbook

```yaml
- hosts: all
  roles:
    - role: hosts
      vars:
        hosts_entries:
          - ip: 10.0.0.10
            names: k3s-master
          - ip: 10.0.0.11
            names: k3s-node1
          - ip: 10.0.0.12
            names: k3s-node2
```