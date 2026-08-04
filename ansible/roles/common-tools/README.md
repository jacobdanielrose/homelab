# common-tools
# Installs useful CLI tools for debugging and system administration.

## Default packages

vim, htop, iotop, lsof, tcpdump, git, curl, wget, jq, unzip, netcat-openbsd, dnsutils, traceroute, mtr, rsync

## Variables

| Variable | Default | Description |
|---|---|---|
| `common_tools_extra_packages` | `[]` | Additional packages to install |

## Example playbook

```yaml
- hosts: all
  roles:
    - role: common-tools
      vars:
        common_tools_extra_packages:
          - ethtool
          - strace
```