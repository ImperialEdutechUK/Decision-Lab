"""Email-fallback identity: validation, stable keying by email, unverified marking, OTP scaffold."""
import pytest

from auth import email_identity as E
from config import config


def test_rejects_bad_email():
    with pytest.raises(ValueError):
        E.claim_identity("not-an-email")


def test_same_email_maps_to_same_learner():
    a = E.claim_identity("Learner@Example.com")
    b = E.claim_identity("learner@example.com")   # case-insensitive
    assert a["id"] == b["id"]
    assert a["email"] == "learner@example.com"


def test_fallback_is_marked_unverified():
    lr = E.claim_identity("someone@example.com")
    assert lr["issuer"] == config.EMAIL_IDENTITY_ISSUER
    assert E.is_unverified_identity(lr) is True


def test_verified_identity_uses_distinct_issuer():
    lr = E.claim_identity("verified@example.com", verified=True)
    assert lr["issuer"] == config.EMAIL_VERIFIED_ISSUER
    assert E.is_unverified_identity(lr) is False


def test_otp_roundtrip():
    code = E.send_login_code("otp@example.com")   # DEV_MODE returns the code
    assert code and len(code) == 6
    assert E.verify_login_code("otp@example.com", code) is True
    # a used/again-wrong code fails
    assert E.verify_login_code("otp@example.com", "000000") is False
