# ntp
# Installs and configures chrony for NTP time synchronization.
# Critical for Kubernetes nodes (certificate validation, etcd).

## Variables

| Variable | Default | Description |
|---|---|---|
| `ntp_timezone` | `UTC` | System timezone |
| `ntp_servers` | pool.ntp.org pool | NTP servers to use |
| `ntp_allow_clients` | `[]` | Clients allowed to query (NTP server mode) |
| `ntp_rtcsync` | `true` | Sync hardware clock with system time |

## Example playbook

```yaml
- hosts: all
  roles:
    - role: ntp
      vars:
        ntp_timezone: America/New_York
```