from unittest.mock import patch

from server.config import _iana_from_etc_localtime, resolve_client_timezone


def test_resolve_client_timezone_uses_configured_value() -> None:
    with patch("server.config.settings.ovaledge_client_timezone", "Asia/Kolkata"):
        assert resolve_client_timezone() == "Asia/Kolkata"


def test_resolve_client_timezone_auto_detects_iana_zone() -> None:
    with patch("server.config.settings.ovaledge_client_timezone", ""):
        tz = resolve_client_timezone()
    assert tz
    assert "/" in tz or tz == "UTC"


def test_resolve_client_timezone_uses_etc_localtime_when_tzinfo_has_no_key() -> None:
    with (
        patch("server.config.settings.ovaledge_client_timezone", ""),
        patch("server.config._iana_from_etc_localtime", return_value="Asia/Kolkata"),
        patch("datetime.datetime") as mock_datetime,
    ):
        mock_datetime.now.return_value.astimezone.return_value.tzinfo = object()
        assert resolve_client_timezone() == "Asia/Kolkata"


def test_iana_from_etc_localtime_parses_zoneinfo_symlink() -> None:
    zone_path = "/var/db/timezone/zoneinfo/Asia/Kolkata"
    with patch("server.config.os.path.realpath", return_value=zone_path):
        assert _iana_from_etc_localtime() == "Asia/Kolkata"
