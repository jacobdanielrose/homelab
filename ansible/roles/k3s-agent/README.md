# k3s-agent
# Joins a worker node to an existing k3s cluster.

## Requirements

- `k3s_server_url` — the control plane URL (e.g. `https://10.0.0.10:6443`)
- `k3s_token` — the node-token from the server (`/var/lib/rancher/k3s/server/node-token`)

## Variables

| Variable | Default | Description |
|---|---|---|
| `k3s_version` | `v1.30` | k3s version to install |
| `k3s_server_url` | `""` | **Required.** Control plane URL |
| `k3s_token` | `""` | **Required.** Cluster join token |
| `k3s_node_ip` | `""` | Node IP to advertise |
| `k3s_node_labels` | `{}` | Labels to apply to the node |
| `k3s_node_taints` | `[]` | Taints to apply to the node |
| `k3s_flannel_iface` | `""` | Flannel interface to use |

## Example playbook

```yaml
- hosts: k3s-workers
  roles:
    - role: k3s-agent
      vars:
        k3s_server_url: "https://k3s-master:6443"
        k3s_token: "{{ lookup('file', '/path/to/node-token') }}"
        k3s_node_labels:
          node-role.kubernetes.io/worker: "true"
```