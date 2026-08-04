# system-upgrade
# Manages package updates, unattended-upgrades, kernel cleanup, and
# automatic reboot when needed.

## Variables

| Variable | Default | Description |
|---|---|---|
| `sysupgrade_packages` | `true` | Upgrade all packages |
| `sysupgrade_reboot` | `true` | Reboot if /var/run/reboot-required exists |
| `sysupgrade_unattended` | `true` | Install and configure unattended-upgrades |
| `sysupgrade_remove_unused_dependencies` | `true` | autoremove/autoclean |
| `sysupgrade_reboot_time` | `03:00` | Scheduled reboot window |

## Example playbook

```yaml
- hosts: all
  roles:
    - role: system-upgrade
```