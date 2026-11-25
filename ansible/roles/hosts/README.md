# hosts
# Manages /etc/hosts entries and the node resolver for cluster nodes.

## Variables

| Variable | Default | Description |
|---|---|---|
| `hosts_entries` | `[]` | List of host entries (dict with `ip`, `names`, optional `aliases`) |
| `hosts_manage_loopback` | `true` | Ensure standard localhost entries exist |
| `hosts_dns_servers` | `[]` | Ordered resolvers written to the primary NetworkManager connection. Empty disables the task. |

## Resolver fallback

Without `hosts_dns_servers` the nodes resolve only through in-cluster DNS, which
runs inside the cluster. A cluster outage then also blocks image pulls, so the
cluster cannot repair itself. Set an ordered list with the in-cluster resolver
first and a plain upstream last:

```yaml
hosts_dns_servers:
  - 10.43.0.10   # in-cluster DNS — internal names
  - 10.0.0.1     # upstream — only consulted on timeout
```

Order matters: glibc falls through to the next resolver on timeout, not on
`NXDOMAIN`. The change is applied with `nmcli device reapply`, which does not
drop the connection, so an in-flight play keeps its SSH session.

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
        hosts_dns_servers:
          - 10.43.0.10
          - 10.0.0.1
```