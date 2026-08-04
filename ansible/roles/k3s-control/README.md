# k3s-control
# Installs and configures a single-node k3s control plane.

## Variables

| Variable | Default | Description |
|---|---|---|
| `k3s_version` | `v1.30` | k3s version to install |
| `k3s_disable_traefik` | `true` | Disable built-in Traefik ingress |
| `k3s_disable_servicelb` | `false` | Disable built-in ServiceLB |
| `k3s_disable_metrics_server` | `false` | Disable metrics-server |
| `k3s_disable_local_storage` | `false` | Disable local-path-provisioner |
| `k3s_cluster_cidr` | `10.42.0.0/16` | Pod network CIDR |
| `k3s_service_cidr` | `10.43.0.0/16` | Service network CIDR |
| `k3s_cluster_dns` | `10.43.0.10` | Cluster DNS IP |
| `k3s_tls_san` | `[]` | Additional TLS SANs (e.g. hostname, domain) |
| `k3s_token` | `""` | Token for agents to join; auto-generated if empty |
| `k3s_node_labels` | `{}` | Labels to apply to the node |
| `k3s_node_taints` | `[]` | Taints to apply to the node |
| `k3s_flannel_backend` | `vxlan` | Flannel backend (vxlan, wireguard, host-gw) |
| `k3s_containerd_registries` | `{}` | Containerd registry mirrors |

## Example playbook

```yaml
- hosts: k3s-servers
  roles:
    - role: k3s-control
      vars:
        k3s_disable_traefik: true
        k3s_tls_san:
          - k3s.home.lab
        k3s_node_labels:
          node-role.kubernetes.io/control-plane: "true"
```

## Accessing the cluster

After the playbook runs:

```bash
# On the node
k3s kubectl get nodes

# From your workstation
scp user@node:/etc/rancher/k3s/k3s.yaml ~/.kube/config
# Then edit ~/.kube/config to replace 127.0.0.1 with the node's IP
```
