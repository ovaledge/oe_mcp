from server.auth.cache_keys import opaque_cache_key
from server.auth.credentials_cache import credential_cache_key


def test_opaque_cache_key_stable_and_distinct() -> None:
    a = opaque_cache_key("oauth-exchange", "tok-a")
    b = opaque_cache_key("oauth-exchange", "tok-a")
    c = opaque_cache_key("oauth-exchange", "tok-b")
    assert a == b
    assert a != c
    assert len(a) == 64


def test_credential_cache_key_uses_opaque_helper() -> None:
    assert credential_cache_key("u", "s") == opaque_cache_key("u", "s")
    assert credential_cache_key("u", "s") != credential_cache_key("u", "other")
