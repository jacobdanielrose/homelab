#!/usr/bin/env python3
"""
Create an app password for a Stalwart user via the JMAP management API.

Uses kubectl exec to reach the recovery admin on the local mgmt port (8080).

Usage:
    # List users (omit --password to see available accounts)
    python3 scripts/create-app-password.py --list

    # Create an app password for a user
    python3 scripts/create-app-password.py jacobdanielrose@rostor.cloud \
        --description "Thunderbird on laptop"

    # Specify a different namespace/pod
    python3 scripts/create-app-password.py jacobdanielrose@rostor.cloud \
        --namespace stalwart-mail \
        --pod stalwart-mail-stalwart-0 \
        --description "My device"
"""

import argparse
import json
import subprocess
import sys
import base64


def get_admin_creds(namespace):
    """Pull recovery admin credentials from the Kubernetes secret."""
    cmd = [
        "kubectl", "get", "secret",
        "-n", namespace,
        "stalwart-mail-stalwart-env",
        "-o", "jsonpath={.data.STALWART_RECOVERY_ADMIN}"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        print(f"Error: failed to read recovery admin secret: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    decoded = base64.b64decode(result.stdout.strip()).decode()
    # Format is "username:password"
    if ":" not in decoded:
        print(f"Error: unexpected secret format: {decoded}", file=sys.stderr)
        sys.exit(1)
    return decoded


def kubectl_exec(pod, namespace, payload, creds=None):
    """Run a JMAP API call inside the Stalwart pod via kubectl exec."""
    if creds is None:
        creds = get_admin_creds(namespace)
    cmd = [
        "kubectl", "exec",
        "-n", namespace,
        pod, "--",
        "sh", "-c",
        f'curl -s http://localhost:8080/jmap/ '
        f'-u "{creds}" '
        f'-H "Content-Type: application/json" '
        f'-d \'{json.dumps(payload)}\''
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"Error: kubectl exec failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"Error: failed to parse response: {e}", file=sys.stderr)
        print(f"Raw output: {result.stdout[:500]}", file=sys.stderr)
        sys.exit(1)


def query_accounts(pod, namespace, creds=None):
    """Get all accounts from the server."""
    payload = {
        "using": ["urn:ietf:params:jmap:core", "urn:stalwart:jmap"],
        "methodCalls": [
            ["x:Account/query", {}, "0"]
        ]
    }
    resp = kubectl_exec(pod, namespace, payload, creds)
    try:
        ids = resp["methodResponses"][0][1]["ids"]
    except (KeyError, IndexError, TypeError) as e:
        print(f"Error: unexpected response format: {json.dumps(resp, indent=2)[:500]}", file=sys.stderr)
        sys.exit(1)
    if not ids:
        return []
    # Get full account details
    payload = {
        "using": ["urn:ietf:params:jmap:core", "urn:stalwart:jmap"],
        "methodCalls": [
            ["x:Account/get", {"ids": ids}, "0"]
        ]
    }
    resp = kubectl_exec(pod, namespace, payload, creds)
    return resp.get("methodResponses", [])[0][1].get("list", [])


def find_account_by_email(accounts, email):
    """Find an account by email address."""
    for acct in accounts:
        if acct.get("emailAddress", "").lower() == email.lower():
            return acct
    return None


def create_app_password(pod, namespace, account_id, description, creds=None):
    """Create an app password for a given account."""
    payload = {
        "using": ["urn:ietf:params:jmap:core", "urn:stalwart:jmap"],
        "methodCalls": [
            ["x:AppPassword/set", {
                "accountId": account_id,
                "create": {
                    "p1": {
                        "description": description,
                        "permissions": {"@type": "Inherit"}
                    }
                }
            }, "0"]
        ]
    }
    resp = kubectl_exec(pod, namespace, payload, creds)
    try:
        created = resp["methodResponses"][0][1].get("created", {})
        if "p1" in created:
            return created["p1"]
        # Check for errors
        not_created = resp["methodResponses"][0][1].get("notCreated", {})
        if "p1" in not_created:
            err = not_created["p1"]
            print(f"Error: {err.get('type', 'unknown')} - {err.get('description', '')}", file=sys.stderr)
            return None
        return None
    except (KeyError, IndexError, TypeError) as e:
        print(f"Error: unexpected response: {json.dumps(resp, indent=2)[:500]}", file=sys.stderr)
        return None


def list_accounts(pod, namespace, creds=None):
    """Pretty-print all accounts with their credentials."""
    accounts = query_accounts(pod, namespace, creds)
    if not accounts:
        print("No accounts found.")
        return
    print(f"{'ID':4s} | {'Type':6s} | {'Email':35s} | {'Credentials'}")
    print("-" * 90)
    for acct in accounts:
        aid = acct.get("id", "?")
        atype = acct.get("@type", "?")
        email = acct.get("emailAddress", "?")
        creds = acct.get("credentials", {})
        cred_strs = []
        for k, v in creds.items():
            ct = v.get("@type", "?")
            desc = v.get("description", "")
            cred_strs.append(f"{ct}: {desc}"[:40])
        cred_display = ", ".join(cred_strs) if cred_strs else "(none)"
        print(f"{aid:4s} | {atype:6s} | {email:35s} | {cred_display}")


def main():
    parser = argparse.ArgumentParser(
        description="Create app passwords for Stalwart users via recovery admin."
    )
    parser.add_argument("email", nargs="?", help="User email address")
    parser.add_argument("--description", "-d", default="App Password",
                        help="Description for the app password")
    parser.add_argument("--list", "-l", action="store_true",
                        help="List all accounts instead of creating a password")
    parser.add_argument("--creds",
                        help="Recovery admin credentials as user:pass (default: read from K8s secret)")
    parser.add_argument("--namespace", "-n", default="stalwart-mail",
                        help="Kubernetes namespace (default: stalwart-mail)")
    parser.add_argument("--pod", "-p", default="stalwart-mail-stalwart-0",
                        help="Pod name (default: stalwart-mail-stalwart-0)")

    args = parser.parse_args()

    creds = args.creds

    if args.list:
        list_accounts(args.pod, args.namespace, creds)
        return

    if not args.email:
        parser.print_help()
        print("\nError: email address is required (or use --list)", file=sys.stderr)
        sys.exit(1)

    # Find the user
    accounts = query_accounts(args.pod, args.namespace, creds)
    user = find_account_by_email(accounts, args.email)

    if not user:
        print(f"Error: no account found for '{args.email}'", file=sys.stderr)
        print("\nAvailable accounts:")
        for acct in accounts:
            print(f"  {acct.get('emailAddress', '?')}  (id={acct.get('id', '?')})")
        sys.exit(1)

    aid = user["id"]
    email = user["emailAddress"]

    print(f"Creating app password for {email} (id={aid})...")
    result = create_app_password(args.pod, args.namespace, aid, args.description, creds)

    if result:
        secret = result.get("secret", "unknown")
        print(f"\n✅  App password created!")
        print(f"   Description: {args.description}")
        print(f"   Secret:      {secret}")
        print(f"\nUse this secret as the password in your mail client.")
    else:
        print(f"\n❌  Failed to create app password.")
        sys.exit(1)


if __name__ == "__main__":
    main()
