# Complete Cluster Strip Runbook

Strip the entire k3s cluster — ArgoCD apps, Longhorn, k3s itself — while leaving node hardening (firewalld, fail2ban, Linux hardening, sysctl, NTP, node-exporter, system-upgrade) intact.

---

## 1. Prerequisites

- SSH access to all nodes (core@192.168.3.2, 192.168.3.3, 192.168.3.4)
- A working `kubectl` pointing at the cluster (or SSH to the control node)
- Ansible installed on your workstation

```bash
# Verify connectivity
ansible all -i ansible/inventory.yml -m ping
```

---

## 2. Delete All ArgoCD Applications

Delete ArgoCD Application CRDs so ArgoCD stops managing everything. Delete in reverse dependency order: leaf apps first, then the app-of-apps, then the root app.

### 2a. Delete all ArgoCD Applications via kubectl

```bash
# Delete all ArgoCD Applications (this removes the CRD objects, which triggers
# Helm uninstall for each app, then deletes namespaces)
kubectl delete applications.argoproj.io --all --namespace argocd
```

Wait for all resources to be cleaned up:

```bash
kubectl get applications.argoproj.io --namespace argocd  # should be empty
kubectl get namespaces | grep -E '(longhorn-system|argocd|media|productivity|infra)'
```

### 2b. Uninstall ArgoCD itself

```bash
helm uninstall argocd --namespace argocd
kubectl delete namespace argocd --wait=false
```

### 2c. Clean up ArgoCD CRDs (optional but thorough)

```bash
kubectl get crd | grep argoproj.io | awk '{print $1}' | xargs kubectl delete crd
```

---

## 3. Delete Longhorn Volumes and Data

### 3a. Find and delete all Longhorn volumes

```bash
# Check for PVCs using Longhorn StorageClass
kubectl get pvc --all-namespaces | grep longhorn

# Delete all PVCs (this must happen before Longhorn is removed)
kubectl delete pvc --all --all-namespaces
```

If the Longhorn namespace still exists, directly delete remaining Longhorn volumes:

```bash
# If Longhorn is still running, delete volumes via Longhorn API
LH_NODE=$(kubectl get nodes -o name | head -1)
kubectl exec -n longhorn-system deploy/longhorn-manager-0 -- longhorn-manager volume list
kubectl delete -n longhorn-system --all pods,deploy,svc,ds,cm
```

### 3b. Delete Longhorn namespace

```bash
kubectl delete namespace longhorn-system --wait=false
```

If it hangs, remove finalizers:

```bash
kubectl get namespace longhorn-system -o json | jq 'del(.spec.finalizers[])' | kubectl replace --raw /api/v1/namespaces/longhorn-system/finalize -f -
```

---

## 4. Wipe Longhorn Data Disks on Workers

SSH into each worker node and wipe the Longhorn data device.

### Worker: rostor-worker-node-0 (192.168.3.3)

```bash
ssh core@192.168.3.3

# Unmount Longhorn data directory
sudo umount /var/lib/longhorn

# Wipe the filesystem signature
sudo wipefs -a /dev/nvme0n1

# Remove mount directory
sudo rm -rf /var/lib/longhorn

# Remove iscsi modules config (optional - keep if you want to re-use)
sudo rm -f /etc/modules-load.d/iscsi_tcp.conf

exit
```

### Worker: rostor-worker-node-1 (192.168.3.4)

```bash
ssh core@192.168.3.4

# Unmount Longhorn data directory
sudo umount /var/lib/longhorn

# Wipe the filesystem signature
sudo wipefs -a /dev/nvme0n1

# Remove mount directory
sudo rm -rf /var/lib/longhorn

# Remove iscsi modules config (optional - keep if you want to re-use)
sudo rm -f /etc/modules-load.d/iscsi_tcp.conf

exit
```

---

## 5. Uninstall k3s from All Nodes

### 5a. Drain each worker node (optional, speeds things up)

```bash
kubectl cordon rostor-worker-node-0
kubectl drain rostor-worker-node-0 --ignore-daemonsets --delete-emptydir-data
kubectl cordon rostor-worker-node-1
kubectl drain rostor-worker-node-1 --ignore-daemonsets --delete-emptydir-data
```

### 5b. Uninstall k3s-agent from workers

```bash
# Worker 0
ssh core@192.168.3.3 '
  sudo systemctl stop k3s-agent
  sudo systemctl disable k3s-agent
  sudo /usr/local/bin/k3s-agent-uninstall.sh
  sudo rm -rf /var/lib/rancher/k3s /etc/rancher/k3s /etc/systemd/system/k3s-agent.service
'

# Worker 1
ssh core@192.168.3.4 '
  sudo systemctl stop k3s-agent
  sudo systemctl disable k3s-agent
  sudo /usr/local/bin/k3s-agent-uninstall.sh
  sudo rm -rf /var/lib/rancher/k3s /etc/rancher/k3s /etc/systemd/system/k3s-agent.service
'
```

### 5c. Uninstall k3s server from control node

```bash
ssh core@192.168.3.2 '
  sudo systemctl stop k3s
  sudo systemctl disable k3s
  sudo /usr/local/bin/k3s-uninstall.sh
  sudo rm -rf /var/lib/rancher/k3s /etc/rancher/k3s /etc/systemd/system/k3s.service
'
```

### 5d. Remove local kubeconfig

```bash
rm -f ansible/kubeconfig
```

---

## 6. Verify Nodes Are Stripped

```bash
# These should all fail (no k3s cluster)
kubectl get nodes 2>&1
kubectl get pods --all-namespaces 2>&1

# Verify services are gone on each node
for host in 192.168.3.2 192.168.3.3 192.168.3.4; do
  echo "=== $host ==="
  ssh core@$host "systemctl is-active k3s k3s-agent 2>&1 || true"
  ssh core@$host "ls /usr/local/bin/k3s 2>&1 || echo 'k3s binary removed'"
  ssh core@$host "ls /var/lib/rancher/k3s 2>&1 || echo 'k3s data dir removed'"
done
```

---

## 7. Verify Hardening Is Still in Place

```bash
for host in 192.168.3.2 192.168.3.3 192.168.3.4; do
  echo "=== $host ==="
  ssh core@$host "sudo firewall-cmd --list-all 2>&1 | head -5"
  ssh core@$host "sudo fail2ban-client status 2>&1 | head -3"
  ssh core@$host "systemctl is-active node_exporter 2>&1"
  ssh core@$host "chronyc tracking 2>&1 | head -2"
  ssh core@$host "sysctl net.ipv4.tcp_syncookies 2>&1"
done
```

---

## 8. Clean Up Ansible Inventory (Optional)

If you plan to reinstall later, blank out the `k3s_token` in `ansible/inventory.yml`:

```yaml
k3s_token: ""
```

To fully remove k3s from the inventory, delete the `k3s_servers` and `k3s_workers` host groups and their vars, but keep the `all.vars` for SSH keys and `/etc/hosts`.

---

## Summary of What's Left vs. Removed

| Component | Status |
|-----------|--------|
| ArgoCD + all apps | **Removed** |
| Longhorn + data disks | **Removed** |
| k3s control plane | **Removed** |
| k3s agents | **Removed** |
| firewalld | **Kept** |
| fail2ban | **Kept** |
| Linux hardening (SSH, kernel) | **Kept** |
| sysctl tuning | **Kept** |
| NTP / chrony | **Kept** |
| node-exporter | **Kept** |
| system-upgrade | **Kept** |
| /etc/hosts entries | **Kept** |

## Recovery

To reinstall from scratch:

```bash
ansible-playbook -i ansible/inventory.yml ansible/install-all.yml
```