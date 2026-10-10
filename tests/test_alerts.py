import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cogs.alerts import parse_birthday, twitch_username, youtube_channel_ref


def test_parse_birthday_valid():
    assert parse_birthday("25/12") == date(2000, 12, 25)
    assert parse_birthday("25-12") == date(2000, 12, 25)
    assert parse_birthday("29/02") == date(2000, 2, 29)
    assert parse_birthday("25/12/1990") == date(1990, 12, 25)


def test_parse_birthday_invalid():
    assert parse_birthday("") is None
    assert parse_birthday(None) is None
    assert parse_birthday("32/01") is None
    assert parse_birthday("13/13") is None
    assert parse_birthday("abc") is None
    assert parse_birthday("25/12/1990/extra") is None


def test_twitch_username():
    assert twitch_username("https://www.twitch.tv/HawkLord_42") == "hawklord_42"
    assert twitch_username("https://www.twitch.tv/foo/") == "foo"
    assert twitch_username(None) is None
    assert twitch_username("") is None


def test_youtube_channel_ref():
    assert youtube_channel_ref(
        "https://www.youtube.com/channel/UCzQsyUEmdiY3nMM6iPbXQig"
    ) == ("channel", "UCzQsyUEmdiY3nMM6iPbXQig")
    assert youtube_channel_ref("https://www.youtube.com/user/XxLeobsxX") == (
        "user",
        "XxLeobsxX",
    )
    assert youtube_channel_ref("https://www.youtube.com/@handle") == ("handle", "@handle")
    assert youtube_channel_ref("https://www.youtube.com/watch?v=abc") is None
    assert youtube_channel_ref(None) is None
