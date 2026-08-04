# k3s-argocd
# Bootstraps ArgoCD on a k3s cluster using Helm.
# After ArgoCD is up, it applies the root Application from `argocd/`
# which cascades into all app-of-apps (infra, media, productivity).

## Variables

| Variable | Default | Description |
|---|---|---|
| `argocd_namespace` | `argocd` | Namespace to install into |
| `argocd_chart_version` | (latest) | Pin ArgoCD Helm chart version |
| `argocd_values` | `{}` | Inline Helm values (dict) |
| `argocd_values_file` | `""` | Path to a values.yaml file |
| `argocd_apply_root_app` | `true` | Apply the root Application from `argocd/` dir |
| `argocd_admin_password` | `""` | Set admin password (plaintext) |
| `argocd_admin_password_hash` | `""` | Set admin password (bcrypt hash) |

## Example playbook

```yaml
- hosts: k3s-servers
  roles:
    - role: k3s-argocd
      vars:
        argocd_chart_version: "7.7.0"
        argocd_values:
          server:
            ingress:
              enabled: true
              ingressClassName: traefik
              hostname: argocd.home.lab
```

## What it does

1. Installs Helm (if missing)
2. Adds the ArgoCD Helm repo and installs the chart
3. Waits for the argocd-server pod to be ready
4. Applies the root Application from the `argocd/` directory via `kubectl apply -k`
5. Prints the initial admin password