# Trusting the Internal CA on Client Devices

The cluster issues internal (`*.example.lab`) TLS certificates from a single
private root CA, `rostor-internal`, defined in
`apps/infra/cert-manager/local-ca.yaml`. Import that root once into a device's
trust store and every internal service is trusted — current and future,
including across renewals.

Before this change the cluster used cert-manager's bare `selfSigned: {}`
issuer, which made **each** certificate its own root. There was nothing shared
to import, so every internal UI threw a warning and re-warned on each renewal.
`selfsigned` still exists, but only to bootstrap the root CA itself.

---

## 1. What is affected

Anything served by Traefik on `*.example.lab` whose `Certificate` or ingress
annotation references `issuerRef.name: rostor-internal` — Grafana, ArgoCD,
Longhorn, Technitium, Traefik dashboard, Uptime Kuma, Home Assistant, n8n,
AirVault, Paperless-AI/-GPT, and the arr-stack.

Public (`*.example.cloud`) services use `letsencrypt-prod` and are unaffected.

---

## 2. Extract the root certificate

Only the **public certificate** is needed — never distribute the private key.

```bash
kubectl get secret -n cert-manager rostor-internal-ca-keypair \
  -o jsonpath='{.data.tls\.crt}' | base64 -d > rostor-internal-ca.crt

# sanity check
openssl x509 -in rostor-internal-ca.crt -noout -subject -issuer -dates \
  -ext basicConstraints
```

Expect `subject=CN = rostor-internal-ca`, `issuer=` the same, `CA:TRUE`, and an
expiry ~10 years out.

Keep this `.crt` somewhere safe outside the cluster (e.g. alongside your
dotfiles or password manager). It is not a secret, but losing it — or losing
the `rostor-internal-ca-keypair` Secret, which nothing currently backs up —
means regenerating the CA and re-importing on every device.

---

## 3. macOS (Safari, Chrome, Edge, curl, kubectl, python, node)

```bash
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain rostor-internal-ca.crt
```

- `-d` targets the admin (system) domain so it applies to all users.
- Chrome/Edge on macOS defer to the system keychain, so this covers them too.
- Verify: `security find-certificate -c rostor-internal-ca -a /Library/Keychains/System.keychain`
- Remove: `sudo security delete-certificate -c rostor-internal-ca /Library/Keychains/System.keychain`

GUI alternative: Keychain Access → System keychain → drag the `.crt` in →
double-click it → Trust → **When using this certificate: Always Trust**.

### Firefox (its own store — done separately)

Settings → Privacy & Security → Certificates → **View Certificates** →
Authorities → Import → select `rostor-internal-ca.crt` → tick
**"Trust this CA to identify websites"**.

Or, non-interactively via an enterprise policy
(`/Applications/Firefox.app/Contents/Resources/distribution/policies.json`):

```json
{
  "policies": {
    "Certificates": {
      "ImportEnterpriseRoots": true,
      "Install": ["/absolute/path/to/rostor-internal-ca.crt"]
    }
  }
}
```

---

## 4. Linux

Debian / Ubuntu / Mint:

```bash
sudo cp rostor-internal-ca.crt /usr/local/share/ca-certificates/rostor-internal-ca.crt
sudo update-ca-certificates
```

Fedora / RHEL / Rocky:

```bash
sudo cp rostor-internal-ca.crt /etc/pki/ca-trust/source/anchors/
sudo update-ca-trust
```

Arch:

```bash
sudo trust anchor --store rostor-internal-ca.crt
```

Firefox and Snap/Flatpak browsers keep their own stores — import there too.

---

## 5. iOS / iPadOS

AirDrop or email the `.crt` to the device → Settings → **Profile Downloaded** →
Install. Then Settings → General → About → **Certificate Trust Settings** →
enable full trust for `rostor-internal-ca`.

## 6. Android

Settings → Security → Encryption & credentials → Install a certificate →
**CA certificate** → select the file. Android 11+ also needs
Settings → Security → More security settings → Encryption & credentials →
Trusted credentials → **User** → verify it appears.

---

## 7. Verify

```bash
# Trust chain resolves through the imported root
openssl s_client -connect grafana.example.lab:443 -servername grafana.example.lab \
  </dev/null 2>/dev/null | openssl verify -CAfile rostor-internal-ca.crt

# curl should no longer need -k
curl -sSI https://grafana.example.lab | head -1

# inspect what the cluster is actually serving
echo | openssl s_client -connect argocd.example.lab:443 2>/dev/null \
  | openssl x509 -noout -issuer -dates
```

`issuer=CN = rostor-internal-ca` confirms the leaf is signed by the CA (not
self-signed) and the device chain should now be valid.

---

## 8. Operations

**Rotating / rebuilding the CA.** If `rostor-internal-ca-keypair` is lost, the
CA is regenerated with a new key on the next sync, every leaf is reissued from
it, and every client must re-import a fresh `rostor-internal-ca.crt`. There is
no name-constraint support in cert-manager, so treat the CA private key as an
in-cluster secret worth backing up if you want to avoid the re-import dance.

**Rollout order.** After merging, cert-manager issues the root first, then
reissues each leaf against `rostor-internal`. Leaves briefly fail with
`Issuer ... not ready` until the root Secret exists, then recover on retry — no
manual intervention. Traefik picks up the updated TLS secrets and reloads.

**Security note.** A trusted root can sign for *any* hostname, public ones
included, so whatever holds the CA key could intercept this device's TLS.
Acceptable for a homelab you control; do not import this root on a work laptop
or any device that handles third-party credentials.
