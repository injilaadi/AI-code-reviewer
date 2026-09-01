"""Verify GitHub webhook signatures (HMAC-SHA256) before trusting any payload.

GitHub signs each webhook delivery with your app's webhook secret. Reject
anything that doesn't match -- this is the difference between "my bot reviews
PRs" and "anyone on the internet can post fake PR payloads at my endpoint".
"""
import hmac
import hashlib


def verify_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """Return True if signature_header (the 'X-Hub-Signature-256' header) matches
    the HMAC-SHA256 of payload_body using secret."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), payload_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
