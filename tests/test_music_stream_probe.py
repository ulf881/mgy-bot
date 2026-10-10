"""Testes para helpers de stream/cookies do cog de musica."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("SPOTIPY_CLIENT_ID", "test-id")
os.environ.setdefault("SPOTIPY_CLIENT_SECRET", "test-secret")
os.environ.setdefault("YOUTUBE_API_KEY", "test-key")

from cogs import music


def test_extract_cookie_header_filters_and_dedupes(tmp_path):
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text(
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t0\tSID\tabc\n"
        ".youtube.com\tTRUE\t/\tTRUE\t0\tSID\tabc\n"
        ".example.com\tTRUE\t/\tTRUE\t0\tFOO\tbar\n"
        ".google.com\tTRUE\t/\tTRUE\t0\tHSID\tdef\n",
        encoding="utf-8",
    )

    header = music._extract_cookie_header(str(cookie_file))

    assert "SID=abc" in header
    assert header.count("SID=abc") == 1
    assert "HSID=def" in header
    assert "FOO=bar" not in header


def test_extract_cookie_header_missing_file():
    assert music._extract_cookie_header("does-not-exist.txt") == ""
