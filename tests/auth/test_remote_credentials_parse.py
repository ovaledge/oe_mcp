"""remote_credentials header parsing."""

from server.auth.remote_credentials_parse import parse_remote_user_credentials
from server.constants import CREDENTIALS_COMBINED_SEPARATOR, CREDENTIALS_HEADER_MAX_LEN


def test_combined_header() -> None:
    assert parse_remote_user_credentials(combined_hdr="tok::sec") == ("tok", "sec")


def test_combined_secret_may_contain_colons() -> None:
    assert parse_remote_user_credentials(combined_hdr="tok::sec:ret:extra") == (
        "tok",
        "sec:ret:extra",
    )


def test_dual_headers() -> None:
    assert parse_remote_user_credentials(token_hdr="tok", secret_hdr="sec") == ("tok", "sec")


def test_combined_wins_over_dual() -> None:
    assert parse_remote_user_credentials(
        combined_hdr="c_tok::c_sec",
        token_hdr="legacy_t",
        secret_hdr="legacy_s",
    ) == ("c_tok", "c_sec")


def test_empty_combined_falls_back_to_dual() -> None:
    assert parse_remote_user_credentials(
        combined_hdr="   ",
        token_hdr="tok",
        secret_hdr="sec",
    ) == ("tok", "sec")


def test_missing_secret_in_combined() -> None:
    assert parse_remote_user_credentials(combined_hdr="tok::") is None
    assert parse_remote_user_credentials(combined_hdr="::sec") is None
    assert parse_remote_user_credentials(combined_hdr="nodelimiter") is None


def test_whitespace_in_token_401() -> None:
    assert parse_remote_user_credentials(combined_hdr="tok en::sec") is None


def test_oversized_part() -> None:
    big = "a" * (CREDENTIALS_HEADER_MAX_LEN + 1)
    assert parse_remote_user_credentials(combined_hdr=f"{big}::sec") is None


def test_oversized_combined_value() -> None:
    half = "a" * CREDENTIALS_HEADER_MAX_LEN
    combined = f"{half}{CREDENTIALS_COMBINED_SEPARATOR}{half}x"
    assert parse_remote_user_credentials(combined_hdr=combined) is None
