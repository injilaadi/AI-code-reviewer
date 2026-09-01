from app.receiver.webhook_verify import verify_signature
import hmac
import hashlib


def test_valid_signature_passes():
    secret = "testsecret"
    body = b'{"hello": "world"}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(body, sig, secret) is True


def test_invalid_signature_fails():
    assert verify_signature(b"body", "sha256=deadbeef", "testsecret") is False


def test_missing_signature_fails():
    assert verify_signature(b"body", "", "testsecret") is False
