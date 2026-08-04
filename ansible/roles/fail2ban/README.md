# fail2ban
# Installs and configures fail2ban to protect SSH and other services.

## Variables

| Variable | Default | Description |
|---|---|---|
| `fail2ban_maxretry` | `3` | Max retries before ban |
| `fail2ban_bantime` | `24h` | Ban duration |
| `fail2ban_findtime` | `10m` | Window for counting retries |
| `fail2ban_ignoreip` | `127.0.0.1/8 ::1` | IPs to never ban |
| `fail2ban_jails` | (sshd, sshd-ddos) | List of jails to enable |

## Example playbook

```yaml
- hosts: all
  roles:
    - role: fail2ban
```