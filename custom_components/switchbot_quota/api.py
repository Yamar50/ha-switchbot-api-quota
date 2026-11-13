"""One read-only request; credentials and device-list bodies are never recorded."""

import asyncio
import base64
import hashlib
import hmac
import time
import uuid

from aiohttp import ClientError, ClientTimeout

from .const import URL
from .model import parse_remaining


async def fetch_quota(session, token: str, secret: str) -> tuple[int, int, str]:
    timestamp = str(int(time.time() * 1000))
    nonce = str(uuid.uuid4())
    signature = base64.b64encode(hmac.new(
        secret.encode(), (token + timestamp + nonce).encode(), hashlib.sha256
    ).digest()).decode()
    headers = {"Authorization": token, "sign": signature, "t": timestamp,
               "nonce": nonce, "Accept": "application/json"}
    try:
        async with session.get(URL, headers=headers, allow_redirects=False,
                               timeout=ClientTimeout(total=25), raise_for_status=False) as response:
            # Deliberately do not deserialize, log or persist the device list.
            return (parse_remaining(response.status, response.headers),
                    response.status, response.headers.get("Date", ""))
    except (ClientError, asyncio.TimeoutError):
        # Never forward HTTP exceptions containing request headers or response data.
        raise ValueError("API request failed (network or timeout)") from None
