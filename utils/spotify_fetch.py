"""Driverless Spotify playlist fetcher.

Gets an anonymous web-player access token (no browser, no API key) via the
TOTP flow against open.spotify.com/api/token, then paginates the private
GraphQL endpoint api-partner.spotify.com/pathfinder/v2/query (fetchPlaylist)
to return the full track list of a public playlist.

Returns a list of "Artist Trackname" strings, just like the spotipy code.
"""

import base64
import hashlib
import hmac
import re
import struct
import time
import uuid

from curl_cffi import requests

IMPRESONATE = "chrome131"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
PATHFINDER_URL = "https://api-partner.spotify.com/pathfinder/v2/query"
TOKEN_URL = "https://open.spotify.com/api/token"

# Known-good persisted-query hash. When Spotify rolls the web-player build
# this is re-scraped live; kept as fallback if scraping fails.
FALLBACK_FETCHPLAYLIST_HASH = (
    "346811f856fb0b7e4f6c59f8ebea78dd081c6e2fb01b77c954b26259d5fc6763"
)

# Community-hosted map of TOTP secret version -> cipher bytes (kept fresh).
SECRET_SOURCES = [
    "https://code.thetadev.de/ThetaDev/spotify-secrets/raw/branch/main/secrets/secretDict.json",
    "https://raw.githubusercontent.com/afkarxyz/secretBytes/refs/heads/main/secrets/secretBytes.json",
]
# Version 18 fallback (SpotAPI's hardcoded secret).  Upstream secrets rotate
# frequently; if this stops working, refresh from SECRET_SOURCES or capture.
FALLBACK_SECRETS = {
    "18": [
        44,
        55,
        47,
        42,
        70,
        40,
        34,
        114,
        76,
        74,
        50,
        111,
        120,
        97,
        75,
        76,
        94,
        102,
        43,
        69,
        49,
        120,
        118,
        80,
        64,
        78,
    ],
}


# --------------------------------------------------------------------------
# TOTP helpers (no pyotp dependency needed)
# --------------------------------------------------------------------------


def _b32_encode(raw: bytes) -> str:
    return base64.b32encode(raw).decode().rstrip("=")


def _hotp(b32_secret: str, counter: int) -> str:
    msg = struct.pack(">Q", counter)
    digest = hmac.new(base64.b32decode(b32_secret), msg, hashlib.sha1).digest()
    off = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[off : off + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def _totp_at(b32_secret: str, ts: int) -> str:
    return _hotp(b32_secret, ts // 30)


def _fetch_secret_dict() -> dict:
    for url in SECRET_SOURCES:
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            if isinstance(data, dict) and data:
                return data
        except Exception:
            continue
    return FALLBACK_SECRETS


def _generate_totp(secret_dict: dict) -> tuple[str, str]:
    version = max(secret_dict, key=int)
    cipher = secret_dict[version]
    transformed = [e ^ ((t % 33) + 9) for t, e in enumerate(cipher)]
    joined = "".join(str(n) for n in transformed)
    raw = bytes.fromhex(joined.encode().hex())
    return str(version), _b32_encode(raw)


# --------------------------------------------------------------------------
# Token acquisition
# --------------------------------------------------------------------------


def _access_token(session) -> dict:
    """Anonymous web-player access token via the TOTP flow."""
    server_time = session.get(
        "https://open.spotify.com/api/server-time", impersonate=IMPRESONATE
    ).json()["serverTime"]

    version, b32_secret = _generate_totp(_fetch_secret_dict())
    otp = _totp_at(b32_secret, server_time)

    params = {
        "reason": "init",
        "productType": "web-player",
        "totp": otp,
        "totpServer": otp,
        "totpVer": version,
    }
    if int(version) < 10:
        client_time = int(time.time() * 1000)
        build_date = time.strftime("%Y-%m-%d", time.gmtime(server_time))
        params.update(
            {
                "sTime": server_time,
                "cTime": client_time,
                "buildDate": build_date,
                "buildVer": f"web-player_{build_date}_{server_time * 1000}_{uuid.uuid4().hex[:8]}",
            }
        )

    headers = {
        "User-Agent": UA,
        "Accept": "application/json",
        "Referer": "https://open.spotify.com/",
        "App-Platform": "WebPlayer",
    }
    r = session.get(TOKEN_URL, params=params, headers=headers, impersonate=IMPRESONATE)
    if r.status_code != 200:
        raise RuntimeError(f"Token request failed: {r.status_code} {r.text[:200]}")
    return r.json()


def _client_token(session, client_id: str, device_id: str) -> str:
    payload = {
        "client_data": {
            "client_version": "1.2.87.28.g9713df8f",
            "client_id": client_id,
            "js_sdk_data": {
                "device_brand": "unknown",
                "device_model": "unknown",
                "os": "windows",
                "os_version": "NT 10.0",
                "device_id": device_id,
                "device_type": "computer",
            },
        }
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "origin": "https://open.spotify.com",
        "referer": "https://open.spotify.com/",
        "user-agent": UA,
    }
    r = session.post(
        "https://clienttoken.spotify.com/v1/clienttoken",
        json=payload,
        headers=headers,
        impersonate=IMPRESONATE,
    )
    return r.json()["granted_token"]["token"]


def _fetchplaylist_hash(session) -> str:
    """Scrape the current fetchPlaylist persisted-query hash from the live bundle."""
    html = session.get("https://open.spotify.com/").text
    bundles = list(
        dict.fromkeys(
            re.findall(
                r"https://open\.spotifycdn\.com/cdn/build/web-player/[^\"\\']+\.js",
                html,
            )
        )
    )
    for url in bundles:
        bundle = session.get(url, impersonate=IMPRESONATE).text
        m = re.search(r'"fetchPlaylist","query","([0-9a-f]{64})"', bundle)
        if m:
            return m.group(1)
    raise RuntimeError("Could not find fetchPlaylist hash in web-player bundle")


def _headers(playlist_id: str) -> dict:
    session = requests.Session(impersonate=IMPRESONATE)
    session.get(f"https://open.spotify.com/playlist/{playlist_id}")

    token = _access_token(session)
    client_token = _client_token(
        session, token["clientId"], session.cookies.get("sp_t") or ""
    )
    session.close()
    return {
        "accept": "application/json",
        "app-platform": "WebPlayer",
        "authorization": f"Bearer {token['accessToken']}",
        "client-token": client_token,
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://open.spotify.com",
        "referer": f"https://open.spotify.com/playlist/{playlist_id}",
        "user-agent": UA,
    }


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def playlist_tracks(playlist_id: str, limit: int = 100) -> list[str]:
    """Return every track of a public playlist as ["Artist Trackname", ...]."""
    match = re.search(r"playlist/([A-Za-z0-9]+)", playlist_id)
    if match:
        playlist_id = match.group(1)

    headers = _headers(playlist_id)
    session = requests.Session(impersonate=IMPRESONATE)

    try:
        fetch_hash = _fetchplaylist_hash(session)
    except Exception:
        fetch_hash = FALLBACK_FETCHPLAYLIST_HASH

    tracks: list[str] = []
    offset = 0
    while True:
        payload = {
            "variables": {
                "uri": f"spotify:playlist:{playlist_id}",
                "offset": offset,
                "limit": limit,
                "enableWatchFeedEntrypoint": False,
            },
            "operationName": "fetchPlaylist",
            "extensions": {"persistedQuery": {"version": 1, "sha256Hash": fetch_hash}},
        }
        r = session.post(
            PATHFINDER_URL, json=payload, headers=headers, impersonate=IMPRESONATE
        )
        if r.status_code != 200:
            # Hash might have rotated between scrape and request; retry once.
            if fetch_hash != FALLBACK_FETCHPLAYLIST_HASH:
                payload["extensions"]["persistedQuery"][
                    "sha256Hash"
                ] = FALLBACK_FETCHPLAYLIST_HASH
                r = session.post(
                    PATHFINDER_URL,
                    json=payload,
                    headers=headers,
                    impersonate=IMPRESONATE,
                )
        if r.status_code != 200:
            raise RuntimeError(f"Pathfinder error {r.status_code}: {r.text[:300]}")

        body = r.json()
        if "playlistV2" not in body.get("data", {}) or not body["data"][
            "playlistV2"
        ].get("content"):
            raise RuntimeError(
                f"Unexpected response (offset={offset}): {str(body)[:400]}"
            )
        content = body["data"]["playlistV2"]["content"]
        total_count = content["totalCount"]

        for item in content["items"]:
            data = item.get("itemV2", {}).get("data") or {}
            if not data or data.get("__typename") != "Track":
                continue
            artist = data["artists"]["items"][0]["profile"]["name"]
            tracks.append(f"{artist} {data['name']}")

        offset += limit
        if len(tracks) >= total_count or not content["items"]:
            break

    session.close()
    return tracks


if __name__ == "__main__":
    all_tracks = playlist_tracks("3rT9xc86BIZWNAT42nGI8T")
    print(f"\nTotal: {len(all_tracks)} tracks")
    print("\nFirst 5:")
    for t in all_tracks[:5]:
        print("  ", t)
    print("\nLast 5:")
    for t in all_tracks[-5:]:
        print("  ", t)
