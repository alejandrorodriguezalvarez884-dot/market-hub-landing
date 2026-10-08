"""The check that whoever makes an account is a person: Cloudflare Turnstile.

Making an account costs nothing to ask for, and each one opens the tools, which spend with the
owner's keys. So a registration carries a token the page got from Turnstile's widget, and the
server asks Cloudflare whether it is good before it does anything else.

Two keys, from the Turnstile page of the Cloudflare dashboard: the site key goes to the browser
(TURNSTILE_SITE_KEY), the secret stays here (TURNSTILE_SECRET_KEY). Both are kept in Secret
Manager and reach the service as its environment; neither is in .env. Without both there is no
check, and then no accounts are made either, unless MARKETHUB_OPEN_REGISTRATION=1 says they may
be made without one (for a developer's machine).

What Cloudflare gets is the token and the address the request came from. A check that cannot be
made (Cloudflare not answering) counts as failed: the door stays shut rather than open.
"""

from __future__ import annotations

import json
import logging
import os

import httpx

log = logging.getLogger("markethub.captcha")

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
ACTION = "register"  # what the widget on the page says it is for
TOKEN_MAX = 2048  # Cloudflare's own limit for a token


class Turnstile:
    def __init__(self, site_key: str, secret: str, client: httpx.Client | None = None):
        self.site_key, self.secret = site_key, secret
        self.client = client or httpx.Client(timeout=8)

    def passes(self, token, address: str = "") -> bool:
        """Whether Cloudflare vouches for ``token``. A token is good once and for a few minutes."""
        token = str(token or "")
        if not token or len(token) > TOKEN_MAX:
            return False
        try:
            answer = self.client.post(VERIFY_URL, data={"secret": self.secret, "response": token, **({"remoteip": address} if address else {})})
            body = answer.json()
        except (httpx.HTTPError, ValueError):
            log.warning("captcha check could not be made")
            return False
        if not body.get("success"):
            # Why it failed, in Cloudflare's own codes; never the token.
            log.info("captcha refused: %s", ",".join(map(str, body.get("error-codes") or [])) or "no reason given")
            return False
        # A token made for another purpose on the same site is not one for this.
        return body.get("action") in (None, "", ACTION)


def app_page(site_key: str) -> str:
    """The widget on a page by itself, for the phone app to show inside its own form (a WebView):
    Turnstile runs only on a page of the domain its key was made for, so the page is ours. It
    hands what the widget says to the app that shows it, and to nobody else: in a browser there
    is nobody to hand it to. {"token": ""} says the one given before no longer counts."""
    key = json.dumps(site_key).replace("<", "\\u003c")
    return ("<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<meta name=robots content=noindex><title>Market Hub</title>"
            "<style>html,body{margin:0;background:#0b0c0d}#check{min-height:65px}</style>"
            "<div id=check></div><script>"
            "function say(m){if(window.ReactNativeWebView)window.ReactNativeWebView.postMessage(JSON.stringify(m))}"
            f"function ready(){{turnstile.render('#check',{{sitekey:{key},theme:'dark',size:'flexible',action:'{ACTION}',"
            "callback:function(t){say({token:t})},'expired-callback':function(){say({token:''})},"
            "'error-callback':function(){say({token:'',error:true})}})}"
            "</script><script src='https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=ready' async defer "
            "onerror='say({token:\"\",error:true})'></script></html>")


def default_captcha() -> Turnstile | None:
    site, secret = os.environ.get("TURNSTILE_SITE_KEY", "").strip(), os.environ.get("TURNSTILE_SECRET_KEY", "").strip()
    return Turnstile(site, secret) if site and secret else None


def open_without() -> bool:
    return os.environ.get("MARKETHUB_OPEN_REGISTRATION", "").strip() == "1"
