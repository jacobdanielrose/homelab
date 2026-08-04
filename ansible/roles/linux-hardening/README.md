---
# linux-hardening
# Hardens SSH configuration and deploys authorized SSH keys.

## Dependencies
None outside of Ansible Core + `ansible.posix` collection (for `authorized_key` module).

Install the collection:
```bash
ansible-galaxy collection install ansible.posix
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `ssh_port` | `22` | SSH listen port |
| `ssh_permit_root_login` | `"no"` | PermitRootLogin setting |
| `ssh_password_authentication` | `"no"` | PasswordAuthentication setting |
| `ssh_pubkey_authentication` | `"yes"` | PubkeyAuthentication setting |
| `ssh_challenge_response_authentication` | `"no"` | ChallengeResponseAuthentication |
| `ssh_authentication_methods` | `"publickey"` | AuthenticationMethods |
| `ssh_authorized_keys` | `[]` | List of public keys to deploy (strings or dicts with `key`, `comment`) |
| `ssh_authorized_users` | `[]` | List of Linux users to deploy keys to |

## Example playbook

```yaml
- hosts: all
  roles:
    - role: linux-hardening
      vars:
        ssh_authorized_keys:
          - "ssh-ed25519 AAAAC3... user@laptop"
          - key: "ssh-rsa AAAAB3..."
            comment: "backup-key"
        ssh_authorized_users:
          - jacob
```
