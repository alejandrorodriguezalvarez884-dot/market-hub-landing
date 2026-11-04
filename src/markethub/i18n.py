"""The service's own words in Spanish, for the site's Spanish pages (docs/i18n.md).

A page under /es/ sends ``X-MH-Lang: es`` with every call, and only then does the service answer
in Spanish: never from Accept-Language, which browsers and phones send by themselves. The phone
app (its routes under /api/app/ and any request with its token) always gets English, as before.

Only words change: the data, the status codes and the shapes of the answers are the same in both.
The English stays where it is written (the routes and the modules that refuse something); its
Spanish is here, found by the English sentence itself, so a module never needs to know who asks.
What a model wrote and what a source wrote (news, opinion articles) stay as they are.
"""

from __future__ import annotations

import re
from typing import Literal

from .holdings import COUNTRY_NAMES
from .tokens import bearer

Lang = Literal["en", "es"]
HEADER = "x-mh-lang"


def lang_of(request) -> Lang:
    """The language the asking page is in: Spanish only when it says ``X-MH-Lang: es`` and it
    is not the phone app."""
    if request.url.path.startswith("/api/app/") or bearer(request.headers.get("authorization")):
        return "en"
    return "es" if request.headers.get(HEADER, "").strip().lower() == "es" else "en"


# --- What the service says when it refuses ------------------------------------------------------

# Sentences said as they are, by their English.
MESSAGES = {
    # Signing in and accounts (api.py, accounts.py).
    "Sign in first.": "Entra primero.",
    "Google sign-in could not be verified.": "No se ha podido comprobar el acceso con Google.",
    "That email and password do not match an account.": "Ese email y esa contraseña no corresponden a ninguna cuenta.",
    "Too many wrong passwords for that email. Wait a few minutes and try again.":
        "Demasiadas contraseñas incorrectas para ese email. Espera unos minutos y vuelve a intentarlo.",
    "Signing in with a password is not on.": "Entrar con contraseña no está activado.",
    "New accounts cannot be made here right now.": "Ahora mismo no se pueden crear cuentas aquí.",
    "Too many accounts were made from this address. Try again later.":
        "Se han creado demasiadas cuentas desde esta dirección. Vuelve a intentarlo más tarde.",
    "We could not check that you are a person. Try the check again.":
        "No hemos podido comprobar que eres una persona. Repite la comprobación.",
    "Too many attempts from this address. Try again later.": "Demasiados intentos desde esta dirección. Vuelve a intentarlo más tarde.",
    "This account signs in with Google or with Apple: it has no password here.":
        "Esta cuenta entra con Google o con Apple: aquí no tiene contraseña.",
    "That is not your current password.": "Esa no es tu contraseña actual.",
    "Too many wrong passwords. Wait a few minutes and try again.": "Demasiadas contraseñas incorrectas. Espera unos minutos y vuelve a intentarlo.",
    "That does not look like an email address.": "Eso no parece una dirección de email.",
    "That password is one of the first anyone would try. Pick another.": "Esa contraseña es de las primeras que probaría cualquiera. Elige otra.",
    "The password cannot be your email address.": "La contraseña no puede ser tu dirección de email.",
    "There is already an account with that email. Sign in instead.": "Ya hay una cuenta con ese email. Entra con ella.",
    "That is the password you already have.": "Esa es la contraseña que ya tienes.",
    # Limits and requests.
    "Too many requests from this address. Try again later.": "Demasiadas peticiones desde esta dirección. Vuelve a intentarlo más tarde.",
    "Cross-site request refused.": "Petición rechazada: no viene de este sitio.",
    "Not a ticker.": "No es un ticker.",
    # The portfolio and the watchlist (users.py, api.py).
    "Positions and watchlist must be lists.": "Las posiciones y la lista de seguimiento tienen que ser listas.",
    "Each position needs a ticker, shares and an average cost.": "Cada posición necesita un ticker, un número de acciones y un coste medio.",
    "No such stock.": "No existe esa acción.",
    "No prices for that stock right now.": "Ahora mismo no hay precios de esa acción.",
    # Prices, quotes and news.
    "Prices for this range are not available right now.": "Los precios de este periodo no están disponibles ahora mismo.",
    "No quote for that ticker right now.": "Ahora mismo no hay cotización de ese ticker.",
    "No such news item.": "No existe esa noticia.",
    "The market data quota is used up for now.": "Por ahora se ha agotado la cuota de datos de mercado.",
    "The market data provider did not answer.": "El proveedor de datos de mercado no ha contestado.",
    "The market data provider is not answering for now.": "El proveedor de datos de mercado no contesta por ahora.",
    "The data plan does not include this.": "El plan de datos no incluye esto.",
    "The SEC company list is not available right now.": "La lista de empresas de la SEC no está disponible ahora mismo.",
    "The Treasury's yields are not available right now.": "Las rentabilidades del Tesoro no están disponibles ahora mismo.",
    # Sharing the portfolio (community.py) and the monthly competition (competitions.py).
    "Pick a name of 3 to 20 letters, digits, spaces, hyphens or underscores.":
        "Elige un nombre de 3 a 20 letras, cifras, espacios, guiones o guiones bajos.",
    "That name is not available.": "Ese nombre no está disponible.",
    "Add a position first: there is nothing to share yet.": "Añade antes una posición: todavía no hay nada que compartir.",
    "Someone already shares under that name.": "Alguien ya comparte con ese nombre.",
    "Each pick is a ticker and its weight.": "Cada elección es un ticker con su peso.",
    "The weights must add up to 100%.": "Los pesos tienen que sumar el 100 %.",
    "Someone else already plays under that name.": "Otra persona ya juega con ese nombre.",
    "This month's competition is full.": "La competición de este mes está completa.",
    "No such month.": "No existe ese mes.",
    # Opinion: articles, comments, reports and blocks (opinion.py, api.py).
    "No such article.": "No existe ese artículo.",
    "No such picture.": "No existe esa imagen.",
    "There is no such article.": "No existe ese artículo.",
    "There is no such thread.": "No existe esa conversación.",
    "Write something first.": "Escribe algo primero.",
    "That has language we do not publish. Say it another way.": "Eso lleva palabras que no publicamos. Dilo de otra manera.",
    "The comment you are answering is no longer there.": "El comentario al que contestas ya no está.",
    "This thread is too deep to answer here. Answer further up.":
        "Esta conversación es demasiado profunda para contestar aquí. Contesta más arriba.",
    "This thread has reached its limit of comments.": "Esta conversación ha llegado a su límite de comentarios.",
    "That comment is no longer there.": "Ese comentario ya no está.",
    "That is your own comment: you can delete it.": "Es tu propio comentario: puedes borrarlo.",
    "That is your own comment.": "Es tu propio comentario.",
    "That comment is not yours.": "Ese comentario no es tuyo.",
    "That is a lot of comments in an hour. Try again later.": "Son muchos comentarios en una hora. Vuelve a intentarlo más tarde.",
    "That is a lot in an hour. Try again later.": "Es mucho en una hora. Vuelve a intentarlo más tarde.",
    "Only the owner reviews reports.": "Solo el propietario revisa las denuncias.",
    # Articles sent in for review (submissions.py, api.py).
    "Articles cannot be sent in right now.": "Ahora mismo no se pueden enviar artículos.",
    "That is the most articles one account can send in a day. Try again tomorrow.":
        "Es el máximo de artículos que una cuenta puede enviar en un día. Vuelve a intentarlo mañana.",
    "The article could not be kept right now. Nothing was sent: try again in a moment.":
        "Ahora mismo no se ha podido guardar el artículo. No se ha enviado nada: vuelve a intentarlo en un momento.",
    "Tick the box to say the article is yours and may be published.":
        "Marca la casilla para decir que el artículo es tuyo y que se puede publicar.",
    "Write the text plainly, without HTML: paragraphs, ## headings, **bold**, *emphasis* and [links](address).":
        "Escribe el texto sin HTML: párrafos, ## títulos, **negrita**, *cursiva* y [enlaces](dirección).",
    "The sources are a list of web addresses.": "Las fuentes son una lista de direcciones web.",
    "The tickers are a short list.": "Los tickers son una lista corta.",
    "This account cannot send articles.": "Esta cuenta no puede enviar artículos.",
}

# Sentences with values in them. In the English, {n…} stands for a number, written with a comma
# for thousands ("1,500"), and anything else for a piece of text (a ticker, an address).
_SAID_WITH_VALUES = [
    ("Tell us a name to call you by, of up to {n} characters.", "Dinos un nombre con el que llamarte, de hasta {n} caracteres."),
    ("The password needs at least {n} characters.", "La contraseña necesita al menos {n} caracteres."),
    ("The password can have up to {n} characters.", "La contraseña puede tener hasta {n} caracteres."),
    ("Not a ticker: {x}", "No es un ticker: {x}"),
    ("Up to {n1} positions and {n2} favourites.", "Hasta {n1} posiciones y {n2} valores en seguimiento."),
    ("{t}: shares and average cost must be numbers.", "{t}: las acciones y el coste medio tienen que ser números."),
    ("{t}: shares must be positive.", "{t}: el número de acciones tiene que ser positivo."),
    ("{t}: the average cost must be zero or positive.", "{t}: el coste medio tiene que ser cero o positivo."),
    ("{t} is not a US-listed ticker.", "{t} no es un ticker de la bolsa de EE. UU."),
    ("Pick {n1} to {n2} stocks.", "Elige de {n1} a {n2} acciones."),
    ("{t}: the weight is a whole number of percent.", "{t}: el peso tiene que ser un porcentaje entero."),
    ("{t} is in the portfolio twice.", "{t} está dos veces en la cartera."),
    ("{t} is a fund: the competition takes single stocks only.", "{t} es un fondo: en la competición solo entran acciones."),
    ("Each stock takes between {n1}% and {n2}% of the portfolio.", "Cada acción ocupa entre el {n1} % y el {n2} % de la cartera."),
    ("A comment can have up to {n} characters.", "Un comentario puede tener hasta {n} caracteres."),
    ("You can block up to {n} members. Unblock one first, on your account page.",
     "Puedes bloquear hasta {n} miembros. Desbloquea antes a uno, en la página de tu cuenta."),
    ("The title needs {n1} to {n2} characters; it has {n3}.", "El título necesita de {n1} a {n2} caracteres; tiene {n3}."),
    ("The summary needs {n1} to {n2} characters; it has {n3}.", "El resumen necesita de {n1} a {n2} caracteres; tiene {n3}."),
    ("The name to sign it with needs {n1} to {n2} characters; it has {n3}.",
     "El nombre con el que lo firmas necesita de {n1} a {n2} caracteres; tiene {n3}."),
    ("A source must be a web address starting with https://. This one is not: {x}",
     "Una fuente tiene que ser una dirección web que empiece por https://. Esta no lo es: {x}"),
    ("The text can have up to {n} characters.", "El texto puede tener hasta {n} caracteres."),
    ("The text needs {n1} to {n2} words; it has {n3}.", "El texto necesita de {n1} a {n2} palabras; tiene {n3}."),
    ('An article argues; it does not tell readers what to do with their money ("{x}").',
     "Un artículo argumenta; no le dice al lector qué hacer con su dinero («{x}»)."),
    ("Name {n1} to {n2} sources: where the figures and the facts come from.",
     "Indica de {n1} a {n2} fuentes: de dónde salen las cifras y los hechos."),
    ("Up to {n} tickers, written like AAPL.", "Hasta {n} tickers, escritos como AAPL."),
    ("You have {n} articles with us already. Take one back before sending another.",
     "Ya tienes {n} artículos con nosotros. Retira uno antes de enviar otro."),
    ("The market data provider answered {n}.", "El proveedor de datos de mercado ha contestado {n}."),
    ("No price for {t} right now.", "Ahora mismo no hay precio de {t}."),
]


def _pattern(english: str) -> re.Pattern:
    out, at = [], 0
    for m in re.finditer(r"\{(\w+)\}", english):
        out.append(re.escape(english[at:m.start()]))
        out.append(rf"(?P<{m[1]}>\d[\d,]*)" if m[1].startswith("n") else rf"(?P<{m[1]}>.+?)")
        at = m.end()
    out.append(re.escape(english[at:]))
    return re.compile("".join(out), re.S)


PATTERNS = [(_pattern(en), es) for en, es in _SAID_WITH_VALUES]


def number(said: str) -> str:
    """A whole number as the English writes it ("1,500"), as Spanish does: "1500", "40.000"."""
    n = int(said.replace(",", ""))
    return f"{n:,}".replace(",", ".") if n >= 10_000 else str(n)


def message(text, lang: Lang):
    """What the service says, in ``lang``. A sentence it has no Spanish for stays in English, and
    anything that is not a sentence (a list of a form's errors) as it is."""
    if lang != "es" or not isinstance(text, str):
        return text
    if text in MESSAGES:
        return MESSAGES[text]
    for pattern, spanish in PATTERNS:
        m = pattern.fullmatch(text)
        if m:
            return spanish.format(**{k: number(v) if k.startswith("n") else v for k, v in m.groupdict().items()})
    return text


# --- Names the service gives figures ---------------------------------------------------------------

# The sectors as the providers name them (Yahoo, FMP), and the names the code gives groups.
SECTORS = {
    "Technology": "Tecnología", "Healthcare": "Salud", "Financial Services": "Servicios financieros",
    "Consumer Cyclical": "Consumo cíclico", "Consumer Defensive": "Consumo defensivo", "Industrials": "Industria",
    "Communication Services": "Comunicaciones", "Energy": "Energía", "Utilities": "Servicios públicos",
    "Real Estate": "Inmobiliario", "Basic Materials": "Materiales básicos",
    "ETF / fund": "ETF / fondo", "Other": "Otros", "Unknown": "Sin datos",
}
_COUNTRIES_BY_CODE = {
    "US": "Estados Unidos", "GB": "Reino Unido", "CA": "Canadá", "CN": "China", "JP": "Japón", "DE": "Alemania", "FR": "Francia",
    "NL": "Países Bajos", "CH": "Suiza", "IE": "Irlanda", "TW": "Taiwán", "DK": "Dinamarca", "ES": "España", "IT": "Italia",
    "IN": "India", "BR": "Brasil", "AU": "Australia", "SG": "Singapur", "KR": "Corea del Sur", "IL": "Israel", "SE": "Suecia",
    "FI": "Finlandia", "LU": "Luxemburgo", "UY": "Uruguay", "MX": "México", "AR": "Argentina", "HK": "Hong Kong", "BM": "Bermudas",
    "KY": "Islas Caimán", "ZA": "Sudáfrica", "NO": "Noruega", "BE": "Bélgica", "CL": "Chile", "CO": "Colombia", "GR": "Grecia",
}
COUNTRIES = {COUNTRY_NAMES[code]: name for code, name in _COUNTRIES_BY_CODE.items()} | {"Funds": "Fondos", "Unknown": "Sin datos"}
VOLATILITY = {"Low": "Baja", "Medium": "Media", "High": "Alta", "Unknown": "Sin datos"}
SIZES = {"Mega cap": "Muy grande", "Large cap": "Grande", "Mid cap": "Mediana", "Small cap": "Pequeña", "ETF / fund": "ETF / fondo",
         "Unknown": "Sin datos"}
ASSETS = {"Stocks": "Acciones", "Bonds": "Bonos", "Cash": "Liquidez", "Preferred": "Preferentes", "Convertible": "Convertibles", "Other": "Otros"}
# The periods My Hub and Community measure (dashboard.PERIODS) and Bot League's (bots.PERIODS), by key.
PERIODS = {"1d": "Hoy", "1m": "1 mes", "3m": "3 meses", "ytd": "Este año", "1y": "1 año"}
BOT_PERIODS = {"1d": "Día", "1w": "Semana", "1m": "Mes", "1y": "Año"}
# How My Hub takes the portfolio apart (dashboard.build's "groups"), by key.
GROUPS = {
    "sector": ("Sector", None),
    "country": ("País", "Dónde tiene su sede cada empresa."),
    "volatility": ("Volatilidad", "Cuánto se ha movido el precio de cada posición en el último año, en cifra anual: "
                                  "por debajo del 20 % es baja; del 35 % en adelante, alta."),
    "size": ("Tamaño", "Por valor en bolsa: muy grande desde 200.000 M$, grande desde 10.000 M$, mediana desde 2.000 M$."),
}
_GROUP_ITEMS = {"sector": SECTORS, "country": COUNTRIES, "volatility": VOLATILITY, "size": SIZES}
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _named(names: dict[str, str], value):
    return names.get(value, value) if isinstance(value, str) else value


def sector(value):
    return _named(SECTORS, value)


def month(key: str) -> str:
    """A month of the competition, "2026-11", as Spanish says it: "noviembre de 2026"."""
    year, m = key.split("-")
    return f"{MONTHS[int(m) - 1]} de {year}"


# --- The answers of the routes whose words are the code's ---------------------------------------------
# Each takes the answer as the route builds it and gives a new one: what was built (and may be
# kept, cached or shared) is never changed.


def dashboard(d: dict, lang: Lang) -> dict:
    """My Hub's figures (dashboard.build): the names of periods, groups, sectors, countries and
    the code's notes. The sentences in "insights" are left as they are (insights.py)."""
    if lang != "es":
        return d
    out = dict(d)
    out["positions"] = [{**r, "sector": sector(r.get("sector")), "country": _named(COUNTRIES, r.get("country")),
                         "volatility_group": _named(VOLATILITY, r.get("volatility_group")), "size": _named(SIZES, r.get("size"))}
                        for r in d.get("positions", [])]
    out["sectors"] = [{**s, "sector": sector(s.get("sector"))} for s in d.get("sectors", [])]
    groups = []
    for g in d.get("groups", []):
        label, note = GROUPS.get(g.get("key"), (g.get("label"), g.get("note")))
        names = _GROUP_ITEMS.get(g.get("key"), {})
        group = {**g, "label": label, "items": [{**i, "label": _named(names, i.get("label"))} for i in g.get("items", [])]}
        if "note" in g:
            group["note"] = note or g["note"]
        groups.append(group)
    out["groups"] = groups
    if "performance" in d:
        out["performance"] = {**d["performance"], "periods": periods(d["performance"].get("periods", []), lang)}
    out["notes"] = [message(n, lang) for n in d.get("notes", [])]
    return out


def periods(items: list[dict], lang: Lang, names: dict[str, str] = PERIODS) -> list[dict]:
    if lang != "es":
        return items
    return [{**p, "label": names.get(p.get("key"), p.get("label"))} for p in items]


def community(board: dict, lang: Lang) -> dict:
    """The shared portfolios: their periods, and the sectors of what they hold."""
    if lang != "es":
        return board
    members = [{**m, **({"top_sector": sector(m["top_sector"])} if m.get("top_sector") else {}),
                **({"positions": [{**p, "sector": sector(p.get("sector"))} for p in m["positions"]]} if m.get("positions") else {})}
               for m in board.get("members", [])]
    return {**board, "members": members, "periods": periods(board.get("periods", []), lang)}


def competitions(overview: dict, lang: Lang) -> dict:
    """The monthly competition: the names of its months."""
    if lang != "es":
        return overview
    out = dict(overview)
    for part in ("running", "open"):
        if isinstance(overview.get(part), dict) and overview[part].get("month"):
            out[part] = {**overview[part], "label": month(overview[part]["month"])}
    if isinstance(overview.get("history"), dict):
        out["history"] = {**overview["history"], "months": [{**m, "label": month(m["month"])} if m.get("month") else m
                                                          for m in overview["history"].get("months", [])]}
    return out


def bots(overview: dict, lang: Lang) -> dict:
    """Bot League's board, as the portal reads it: the names of its periods."""
    if lang != "es" or "periods" not in overview:
        return overview
    return {**overview, "periods": periods(overview["periods"], lang, BOT_PERIODS)}


def quote_more(more: dict, lang: Lang) -> dict:
    """The rest of a quote page: a company's sector, a fund's sectors and what it is made of."""
    if lang != "es":
        return more
    out = dict(more)
    if isinstance(more.get("company"), dict):
        out["company"] = {**more["company"], "sector": sector(more["company"].get("sector"))}
    if isinstance(more.get("fund"), dict):
        f = more["fund"]
        out["fund"] = {**f, "sectors": [{**s, "name": sector(s.get("name"))} for s in f.get("sectors", [])],
                       "asset_mix": [{**a, "name": _named(ASSETS, a.get("name"))} for a in f.get("asset_mix", [])]}
    return out


def watch_item(item: dict, lang: Lang) -> dict:
    """A stock of the watchlist page: its sector's name. Its reading is left as it is."""
    if lang != "es" or not isinstance(item, dict):
        return item
    out = {**item, "sector": sector(item.get("sector"))}
    if isinstance(item.get("sector_strength"), dict):
        out["sector_strength"] = {**item["sector_strength"], "name": sector(item["sector_strength"].get("name"))}
    return out


def watchlist(board: dict, lang: Lang) -> dict:
    if lang != "es":
        return board
    return {**board, "items": [watch_item(i, lang) for i in board.get("items", [])]}
