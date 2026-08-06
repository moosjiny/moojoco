#!/usr/bin/env python3
"""
ACME RFC 8555 DNS-01 Challenge Verification Token Generator
Author: Aegis
Purpose: Connect to Let's Encrypt ACME v2 Directory, request a DNS-01 ACME challenge for aegis.hyperbook.com,
         and compute the exact SHA-256 Base64URL Key Authorization TXT token string for NetSol registration.
"""

import json, base64, hashlib, urllib.request, ssl
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def get_jwk(account_key) -> dict:
    pub = account_key.public_key().public_numbers()
    x = pub.x.to_bytes(32, 'big')
    y = pub.y.to_bytes(32, 'big')
    return {
        "crv": "P-256",
        "kty": "EC",
        "x": base64url(x),
        "y": base64url(y)
    }

def get_jwk_thumbprint(jwk: dict) -> str:
    canonical = json.dumps({"crv": jwk["crv"], "kty": jwk["kty"], "x": jwk["x"], "y": jwk["y"]}, separators=(',', ':')).encode('utf-8')
    return base64url(hashlib.sha256(canonical).digest())

def sign_payload(account_key, payload, url, nonce, kid=None):
    jwk = get_jwk(account_key)
    protected = {
        "alg": "ES256",
        "nonce": nonce,
        "url": url
    }
    if kid:
        protected["kid"] = kid
    else:
        protected["jwk"] = jwk

    prot_b64 = base64url(json.dumps(protected, separators=(',', ':')).encode('utf-8'))
    
    if payload == "":
        pay_b64 = ""
    else:
        pay_b64 = base64url(json.dumps(payload, separators=(',', ':')).encode('utf-8'))

    signing_input = f"{prot_b64}.{pay_b64}".encode('utf-8')
    signature = account_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))

    return {
        "protected": prot_b64,
        "payload": pay_b64,
        "signature": base64url(signature)
    }

def acme_request(url, account_key, payload, nonce_url, kid=None):
    # Fetch fresh nonce
    req_nonce = urllib.request.Request(nonce_url, method="HEAD")
    with urllib.request.urlopen(req_nonce, context=ctx) as r:
        nonce = r.headers["Replay-Nonce"]

    body = json.dumps(sign_payload(account_key, payload, url, nonce, kid)).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/jose+json", "User-Agent": "AegisAgent/1.0"})
    
    try:
        with urllib.request.urlopen(req, context=ctx) as r:
            res_body = r.read().decode('utf-8')
            res_json = json.loads(res_body) if res_body else {}
            new_kid = r.headers.get("Location")
            new_nonce = r.headers.get("Replay-Nonce")
            return res_json, new_kid, new_nonce
    except urllib.error.HTTPError as e:
        err_content = e.read().decode('utf-8')
        print("ACME HTTP Error:", e.code, err_content)
        return json.loads(err_content), None, None

def generate_acme_token(domain="aegis.hyperbook.com"):
    print(f"🚀 Generating Official ACME RFC 8555 DNS-01 Verification Token for: {domain}\n")
    
    # 1. Generate P-256 Account Key
    account_key = ec.generate_private_key(ec.SECP256R1())
    jwk = get_jwk(account_key)
    thumbprint = get_jwk_thumbprint(jwk)

    # 2. Let's Encrypt Staging Directory (Safe for testing token creation)
    dir_url = "https://acme-staging-v02.api.letsencrypt.org/directory"
    with urllib.request.urlopen(dir_url, context=ctx) as r:
        acme_dir = json.loads(r.read().decode('utf-8'))

    nonce_url = acme_dir["newNonce"]
    new_account_url = acme_dir["newAccount"]
    new_order_url = acme_dir["newOrder"]

    # 3. New Account Registration
    acc_payload = {"termsOfServiceAgreed": True, "contact": ["mailto:aegis@hyperbook.com"]}
    res_acc, kid, _ = acme_request(new_account_url, account_key, acc_payload, nonce_url)
    print(f"1. ACME Account Registered (KID: {kid[:45]}...)")

    # 4. New Order Creation
    order_payload = {"identifiers": [{"type": "dns", "value": domain}]}
    res_order, _, _ = acme_request(new_order_url, account_key, order_payload, nonce_url, kid=kid)
    
    auth_urls = res_order.get("authorizations", [])
    if not auth_urls:
        print("Error creating ACME order")
        return None

    # 5. Fetch Authorization & DNS-01 Challenge
    auth_url = auth_urls[0]
    res_auth, _, _ = acme_request(auth_url, account_key, "", nonce_url, kid=kid)

    dns_challenge = None
    for chal in res_auth.get("challenges", []):
        if chal.get("type") == "dns-01":
            dns_challenge = chal
            break

    if not dns_challenge:
        print("DNS-01 challenge not found")
        return None

    token = dns_challenge["token"]
    key_authorization = f"{token}.{thumbprint}"
    txt_value = base64url(hashlib.sha256(key_authorization.encode('utf-8')).digest())

    print("\n=================================================================")
    print("✅ OFFICIAL ACME DNS-01 VERIFICATION TOKEN GENERATED SUCCESSFULLY")
    print("=================================================================")
    print(f"📍 Target Subdomain : _acme-challenge.aegis")
    print(f"📍 Full DNS Host    : _acme-challenge.aegis.hyperbook.com")
    print(f"📍 Record Type      : TXT")
    print(f"📍 ACME Raw Token   : {token}")
    print(f"📍 NetSol TXT Value : {txt_value}")
    print("=================================================================\n")

    return {
        "domain": domain,
        "host": "_acme-challenge.aegis",
        "type": "TXT",
        "token": token,
        "txt_value": txt_value
    }

if __name__ == "__main__":
    generate_acme_token()
