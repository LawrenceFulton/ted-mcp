"""NUTS (Nomenclature of Territorial Units for Statistics) code lookup.

Covers NUTS levels 0–2 for EU member states plus EFTA/UK. NUTS-3 is omitted
(too many to bundle); pass NUTS-3 codes directly if needed.

Source: Eurostat NUTS 2021 classification.
"""

from __future__ import annotations
import difflib
import unicodedata


# Curated name -> NUTS code. Names are normalized (lowercased, accents stripped)
# at lookup time, so entries here can use natural casing.
NUTS: dict[str, str] = {
    # ---- NUTS-0 (countries) ----
    "austria": "AT",
    "belgium": "BE",
    "bulgaria": "BG",
    "croatia": "HR",
    "cyprus": "CY",
    "czechia": "CZ",
    "czech republic": "CZ",
    "denmark": "DK",
    "estonia": "EE",
    "finland": "FI",
    "france": "FR",
    "germany": "DE",
    "greece": "EL",
    "hellas": "EL",
    "hungary": "HU",
    "ireland": "IE",
    "italy": "IT",
    "latvia": "LV",
    "lithuania": "LT",
    "luxembourg": "LU",
    "malta": "MT",
    "netherlands": "NL",
    "poland": "PL",
    "portugal": "PT",
    "romania": "RO",
    "slovakia": "SK",
    "slovenia": "SI",
    "spain": "ES",
    "sweden": "SE",
    "iceland": "IS",
    "liechtenstein": "LI",
    "norway": "NO",
    "switzerland": "CH",
    "united kingdom": "UK",
    "uk": "UK",
    # ---- Germany (DE) ----
    "baden-wurttemberg": "DE1",
    "baden württemberg": "DE1",
    "bayern": "DE2",
    "bavaria": "DE2",
    "berlin": "DE3",
    "brandenburg": "DE4",
    "bremen": "DE5",
    "hamburg": "DE6",
    "hessen": "DE7",
    "hesse": "DE7",
    "mecklenburg-vorpommern": "DE8",
    "niedersachsen": "DE9",
    "lower saxony": "DE9",
    "nordrhein-westfalen": "DEA",
    "north rhine-westphalia": "DEA",
    "nrw": "DEA",
    "rheinland-pfalz": "DEB",
    "rhineland-palatinate": "DEB",
    "saarland": "DEC",
    "sachsen": "DED",
    "saxony": "DED",
    "sachsen-anhalt": "DEE",
    "saxony-anhalt": "DEE",
    "schleswig-holstein": "DEF",
    "thuringen": "DEG",
    "thüringen": "DEG",
    "thuringia": "DEG",
    # DE NUTS-2 highlights
    "stuttgart": "DE11",
    "karlsruhe": "DE12",
    "freiburg": "DE13",
    "tubingen": "DE14",
    "oberbayern": "DE21",
    "upper bavaria": "DE21",
    "niederbayern": "DE22",
    "lower bavaria": "DE22",
    "oberpfalz": "DE23",
    "upper palatinate": "DE23",
    "oberfranken": "DE24",
    "upper franconia": "DE24",
    "mittelfranken": "DE25",
    "middle franconia": "DE25",
    "unterfranken": "DE26",
    "lower franconia": "DE26",
    "schwaben": "DE27",
    "swabia": "DE27",
    "darmstadt": "DE71",
    "giessen": "DE72",
    "kassel": "DE73",
    "dusseldorf": "DEA1",
    "düsseldorf": "DEA1",
    "koln": "DEA2",
    "köln": "DEA2",
    "cologne": "DEA2",
    "munster": "DEA3",
    "münster": "DEA3",
    "detmold": "DEA4",
    "arnsberg": "DEA5",
    "leipzig": "DED5",
    "dresden": "DED2",
    "chemnitz": "DED4",
    # ---- France (FR) ----
    "ile-de-france": "FR10",
    "île-de-france": "FR10",
    "paris region": "FR10",
    "centre-val de loire": "FRB0",
    "centre val de loire": "FRB0",
    "bourgogne-franche-comte": "FRC0",
    "bourgogne franche comté": "FRC0",
    "normandie": "FRD0",
    "normandy": "FRD0",
    "hauts-de-france": "FRE0",
    "grand est": "FRF0",
    "alsace champagne ardenne lorraine": "FRF0",
    "pays de la loire": "FRG0",
    "bretagne": "FRH0",
    "brittany": "FRH0",
    "nouvelle-aquitaine": "FRI0",
    "occitanie": "FRJ0",
    "auvergne-rhone-alpes": "FRK0",
    "auvergne rhône alpes": "FRK0",
    "provence-alpes-cote d'azur": "FRL0",
    "paca": "FRL0",
    "corse": "FRM0",
    "corsica": "FRM0",
    # ---- Italy (IT) ----
    "piemonte": "ITC1",
    "piedmont": "ITC1",
    "valle d'aosta": "ITC2",
    "aosta valley": "ITC2",
    "liguria": "ITC3",
    "lombardia": "ITC4",
    "lombardy": "ITC4",
    "trentino-alto adige": "ITH1",
    "südtirol": "ITH1",
    "south tyrol": "ITH1",
    "veneto": "ITH3",
    "friuli-venezia giulia": "ITH4",
    "emilia-romagna": "ITH5",
    "toscana": "ITI1",
    "tuscany": "ITI1",
    "umbria": "ITI2",
    "marche": "ITI3",
    "lazio": "ITI4",
    "abruzzo": "ITF1",
    "molise": "ITF2",
    "campania": "ITF3",
    "puglia": "ITF4",
    "apulia": "ITF4",
    "basilicata": "ITF5",
    "calabria": "ITF6",
    "sicilia": "ITG1",
    "sicily": "ITG1",
    "sardegna": "ITG2",
    "sardinia": "ITG2",
    # ---- Spain (ES) ----
    "galicia": "ES11",
    "asturias": "ES12",
    "principado de asturias": "ES12",
    "cantabria": "ES13",
    "pais vasco": "ES21",
    "país vasco": "ES21",
    "basque country": "ES21",
    "navarra": "ES22",
    "navarre": "ES22",
    "la rioja": "ES23",
    "aragon": "ES24",
    "aragón": "ES24",
    "comunidad de madrid": "ES30",
    "madrid": "ES30",
    "castilla y leon": "ES41",
    "castilla y león": "ES41",
    "castilla-la mancha": "ES42",
    "extremadura": "ES43",
    "cataluna": "ES51",
    "cataluña": "ES51",
    "catalonia": "ES51",
    "catalunya": "ES51",
    "comunidad valenciana": "ES52",
    "valencia": "ES52",
    "valencian community": "ES52",
    "illes balears": "ES53",
    "balearic islands": "ES53",
    "baleares": "ES53",
    "andalucia": "ES61",
    "andalucía": "ES61",
    "andalusia": "ES61",
    "region de murcia": "ES62",
    "murcia": "ES62",
    "ceuta": "ES63",
    "melilla": "ES64",
    "canarias": "ES70",
    "canary islands": "ES70",
    # ---- Netherlands (NL) ----
    "groningen": "NL11",
    "friesland": "NL12",
    "fryslan": "NL12",
    "drenthe": "NL13",
    "overijssel": "NL21",
    "gelderland": "NL22",
    "flevoland": "NL23",
    "utrecht": "NL31",
    "noord-holland": "NL32",
    "north holland": "NL32",
    "zuid-holland": "NL33",
    "south holland": "NL33",
    "zeeland": "NL34",
    "noord-brabant": "NL41",
    "north brabant": "NL41",
    "limburg (nl)": "NL42",
    # ---- Belgium (BE) ----
    "brussels": "BE10",
    "bruxelles": "BE10",
    "brussel": "BE10",
    "vlaams gewest": "BE2",
    "flanders": "BE2",
    "vlaanderen": "BE2",
    "antwerpen": "BE21",
    "antwerp": "BE21",
    "limburg (be)": "BE22",
    "oost-vlaanderen": "BE23",
    "east flanders": "BE23",
    "vlaams-brabant": "BE24",
    "flemish brabant": "BE24",
    "west-vlaanderen": "BE25",
    "west flanders": "BE25",
    "region wallonne": "BE3",
    "wallonia": "BE3",
    "wallonie": "BE3",
    # ---- Austria (AT) ----
    "burgenland": "AT11",
    "niederosterreich": "AT12",
    "niederösterreich": "AT12",
    "lower austria": "AT12",
    "wien": "AT13",
    "vienna": "AT13",
    "karnten": "AT21",
    "kärnten": "AT21",
    "carinthia": "AT21",
    "steiermark": "AT22",
    "styria": "AT22",
    "oberosterreich": "AT31",
    "oberösterreich": "AT31",
    "upper austria": "AT31",
    "salzburg": "AT32",
    "tirol": "AT33",
    "tyrol": "AT33",
    "vorarlberg": "AT34",
    # ---- Poland (PL) ----
    "lodzkie": "PL71",
    "łódzkie": "PL71",
    "mazowieckie": "PL9",
    "masovia": "PL9",
    "warsaw": "PL91",
    "malopolskie": "PL21",
    "małopolskie": "PL21",
    "lesser poland": "PL21",
    "slaskie": "PL22",
    "śląskie": "PL22",
    "silesia": "PL22",
    "lubelskie": "PL81",
    "podkarpackie": "PL82",
    "swietokrzyskie": "PL72",
    "świętokrzyskie": "PL72",
    "podlaskie": "PL84",
    "wielkopolskie": "PL41",
    "greater poland": "PL41",
    "zachodniopomorskie": "PL42",
    "west pomerania": "PL42",
    "lubuskie": "PL43",
    "dolnoslaskie": "PL51",
    "dolnośląskie": "PL51",
    "lower silesia": "PL51",
    "opolskie": "PL52",
    "kujawsko-pomorskie": "PL61",
    "warminsko-mazurskie": "PL62",
    "warmińsko-mazurskie": "PL62",
    "pomorskie": "PL63",
    "pomerania": "PL63",
    # ---- Sweden (SE) ----
    "stockholm": "SE11",
    "ostra mellansverige": "SE12",
    "östra mellansverige": "SE12",
    "smaland med oarna": "SE21",
    "småland med öarna": "SE21",
    "sydsverige": "SE22",
    "skane": "SE224",
    "skåne": "SE224",
    "vastsverige": "SE23",
    "västsverige": "SE23",
    "norra mellansverige": "SE31",
    "mellersta norrland": "SE32",
    "ovre norrland": "SE33",
    "övre norrland": "SE33",
}


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


# Pre-normalized index built once at import time.
_INDEX: dict[str, str] = {_normalize(k): v for k, v in NUTS.items()}


def resolve_nuts(value: str, fuzzy: bool = True) -> str | None:
    """Resolve a region name or NUTS code to a canonical NUTS code.

    Already-valid-looking codes (e.g. "DE21", "FR10", "ITC4") pass through
    uppercased. Names are matched case/accent-insensitively, with optional
    fuzzy fallback for typos.
    """
    if not value:
        return None
    v = value.strip()
    # Pass through anything that looks like a NUTS code: 2-5 chars, starts with
    # 2 letters, rest alphanumeric.
    if 2 <= len(v) <= 5 and v[:2].isalpha() and v[2:].isalnum():
        upper = v.upper()
        if upper[2:].isdigit() or len(upper) == 2 or upper[2:].isalnum():
            return upper
    key = _normalize(v)
    if key in _INDEX:
        return _INDEX[key]
    if fuzzy:
        match = difflib.get_close_matches(key, _INDEX.keys(), n=1, cutoff=0.85)
        if match:
            return _INDEX[match[0]]
    return None


def resolve_nuts_list(
    values: list[str], fuzzy: bool = True
) -> tuple[list[str], list[str]]:
    """Resolve a list of names/codes. Returns (resolved_codes, unresolved_inputs)."""
    resolved: list[str] = []
    unresolved: list[str] = []
    for v in values:
        code = resolve_nuts(v, fuzzy=fuzzy)
        if code:
            resolved.append(code)
        else:
            unresolved.append(v)
    return resolved, unresolved
