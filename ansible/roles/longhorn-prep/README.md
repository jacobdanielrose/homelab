# longhorn-prep
# Prepares a worker node for Longhorn distributed storage.
# Detects the secondary data disk, formats it (if needed), mounts it to
# /var/lib/longhorn, and installs required dependencies.

## How it works

1. Installs prerequisites (open-iscsi, nfs-common, curl)
2. Auto-detects the non-root block device, or uses `longhorn_data_device` if set explicitly
3. Formats the device as ext4 (skips if already formatted for Longhorn, unless `longhorn_force_format=true`)
4. Mounts the device to `/var/lib/longhorn` with `noatime`
5. Adds an entry to `/etc/fstab`
6. Pre-creates Longhorn data directories

## Variables

| Variable | Default | Description |
|---|---|---|
| `longhorn_data_device` | `""` | Explicit data device (e.g. `/dev/sdb`). If empty and `longhorn_auto_detect=true`, will find the non-root disk. |
| `longhorn_mount_path` | `/var/lib/longhorn` | Mount point for Longhorn data |
| `longhorn_filesystem` | `ext4` | Filesystem to use |
| `longhorn_auto_detect` | `true` | Auto-detect the non-root disk |
| `longhorn_disk_label` | `longhorn` | Filesystem label |
| `longhorn_force_format` | `false` | Reformat even if a filesystem already exists (destroys data) |

## Example playbook

```yaml
- hosts: k3s-workers
  roles:
    - role: longhorn-prep
      vars:
        longhorn_data_device: /dev/sdb
```

Or with auto-detection:

```yaml
- hosts: k3s-workers
  roles:
    - role: longhorn-prep
      # longhorn_data_device is left empty — auto-detection will find the
      # non-root disk automatically
```

## After this role

Once the nodes are prepared, install Longhorn itself via Helm:

```bash
helm repo add longhorn https://charts.longhorn.io
helm repo update
helm install longhorn longhorn/longhorn --namespace longhorn-system --create-namespace
```

Longhorn will automatically discover the `/var/lib/longhorn` mount as a filesystem-backed disk.