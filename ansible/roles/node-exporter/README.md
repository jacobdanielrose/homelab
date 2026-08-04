# node-exporter
# Installs Prometheus node_exporter as a systemd service.

## Variables

| Variable | Default | Description |
|---|---|---|
| `node_exporter_version` | `1.8.2` | Version to install |
| `node_exporter_port` | `9100` | Listen port |
| `node_exporter_collectors` | `[]` | Collectors to enable |
| `node_exporter_disabled_collectors` | `[]` | Collectors to disable |
| `node_exporter_extra_args` | `""` | Extra CLI flags |

## Example playbook

```yaml
- hosts: all
  roles:
    - role: node-exporter
      vars:
        node_exporter_disabled_collectors:
          - mdadm
          - zfs
```