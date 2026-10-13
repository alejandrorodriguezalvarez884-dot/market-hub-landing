"""The phone app opens the tools of My Hub inside itself.

The tools (Fundamentals Lab, the Earnings Radar, Peer Map, the Playground) are sites of their
own, and each admits whoever carries the portal's session cookie. The app has no cookie: it has
its token. So the page the app opens inside itself starts here:

    GET /api/app/web/enter?to=<the tool's address>
    Authorization: Bearer <the app's token>

The token is checked as everywhere else, the session cookie is set for whoever it names, and the
page goes on to the tool. It is the one route under ``/api/app/`` that sets a cookie, and it only
does so for a request that carries a good token: a browser cannot be sent here by a foreign page
and come out signed in, because a link or a form cannot add that header. The token travels in
the header of this one request and nowhere else: the page that follows is a new request, so it
never reaches the tool's address, and nothing is put in an address that a log or a history keeps.

The page only goes on to a tool the portal itself names (``ToolPages``): it is not a way to send
a signed-in browser anywhere else.
"""

from __future__ import annotations

import html
import json
from urllib.parse import urlsplit


class ToolPages:
    """The addresses the app's page may go on to: any page of a tool the portal names."""

    def __init__(self, tools: list[str | None]):
        self._origins = {self._origin(t) for t in tools if t}
        self._origins.discard(None)

    @staticmethod
    def _origin(address: str) -> tuple[str, str] | None:
        parts = urlsplit(address)
        # No user, password or odd port tricks: a scheme, a host, and nothing before the host.
        if parts.scheme not in ("https", "http") or not parts.hostname or "@" in parts.netloc or "\\" in address:
            return None
        return parts.scheme, parts.netloc.lower()

    def allowed(self, address: str) -> bool:
        return bool(address) and address.isprintable() and self._origin(address) in self._origins


def entering_page(address: str | None, words: str) -> str:
    """What the app's page shows for a moment on its way to the tool, or when it cannot go."""
    go = f"<script>location.replace({json.dumps(address).replace('<', chr(92) + 'u003c')})</script>" if address else ""
    return ("<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<meta name=robots content=noindex><title>Market Hub</title>"
            "<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0b0c0d;color:#8d8b85;"
            "font:15px/1.5 system-ui,sans-serif;text-align:center}main{padding:24px;max-width:22rem}</style>"
            f"<main><p>{html.escape(words)}</p>{go}</main></html>")
