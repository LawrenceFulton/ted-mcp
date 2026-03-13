from __future__ import annotations
from typing import Any
from pydantic import BaseModel

LANGUAGE_PRIORITY = ["eng", "deu", "fra", "nld", "ita", "spa", "por", "pol"]

CURRENCY_SYMBOLS: dict[str, str] = {
    "EUR": "€",
    "GBP": "£",
    "USD": "$",
    "CHF": "CHF",
    "PLN": "PLN",
    "SEK": "SEK",
    "DKK": "DKK",
    "NOK": "NOK",
    "CZK": "CZK",
    "HUF": "HUF",
    "RON": "RON",
    "BGN": "BGN",
    "HRK": "HRK",
}


def pick_best_language(field: Any) -> str | None:
    """Pick best available language from a multilingual field dict."""
    if field is None:
        return None
    if isinstance(field, str):
        return field
    if not isinstance(field, dict):
        return str(field)
    for lang in LANGUAGE_PRIORITY:
        if lang in field:
            values = field[lang]
            if isinstance(values, list) and values:
                return values[0]
            if isinstance(values, str):
                return values
    # Fall back to first available
    for values in field.values():
        if isinstance(values, list) and values:
            return values[0]
        if isinstance(values, str):
            return values
    return None


def pick_all_languages(field: Any) -> list[str]:
    """Get all unique values from a multilingual field dict."""
    if field is None:
        return []
    if isinstance(field, str):
        return [field]
    if not isinstance(field, dict):
        return [str(field)]
    seen: set[str] = set()
    result: list[str] = []
    for lang in LANGUAGE_PRIORITY:
        if lang in field:
            values = field[lang]
            if isinstance(values, list):
                for v in values:
                    if v not in seen:
                        seen.add(v)
                        result.append(v)
            elif isinstance(values, str) and values not in seen:
                seen.add(values)
                result.append(values)
    for lang, values in field.items():
        if lang in LANGUAGE_PRIORITY:
            continue
        if isinstance(values, list):
            for v in values:
                if v not in seen:
                    seen.add(v)
                    result.append(v)
        elif isinstance(values, str) and values not in seen:
            seen.add(values)
            result.append(values)
    return result


def zip_winners(notice: dict[str, Any], max_count: int | None = None) -> list[dict[str, str]]:
    """Zip winner-name and winner-country into list of dicts."""
    raw_names = notice.get("winner-name")
    raw_countries = notice.get("winner-country", [])

    if not raw_names:
        return []

    # winner-name is a multilingual dict: {lang: [name1, name2, ...]}
    # Collect all names in order
    names: list[str] = []
    if isinstance(raw_names, dict):
        # Use language priority to get the names list
        for lang in LANGUAGE_PRIORITY:
            if lang in raw_names:
                vals = raw_names[lang]
                if isinstance(vals, list):
                    names = vals
                    break
                elif isinstance(vals, str):
                    names = [vals]
                    break
        if not names:
            for vals in raw_names.values():
                if isinstance(vals, list) and vals:
                    names = vals
                    break
                elif isinstance(vals, str):
                    names = [vals]
                    break
    elif isinstance(raw_names, list):
        names = raw_names

    if not names:
        return []

    # Normalize countries
    if isinstance(raw_countries, list):
        countries = raw_countries
    else:
        countries = []

    winners = []
    total = len(names)
    limit = min(total, max_count) if max_count else total
    for i in range(limit):
        country = countries[i] if i < len(countries) else ""
        winners.append({"name": names[i], "country": country})

    return winners


def format_value(notice: dict[str, Any]) -> str:
    """Format contract value with currency."""
    value = notice.get("result-value-notice")
    currency = notice.get("result-value-cur-notice", "EUR")

    if value is None:
        return "Not disclosed"
    try:
        fval = float(value)
    except (TypeError, ValueError):
        return "Not disclosed"

    if fval <= 0.01:
        return "Not disclosed"

    symbol = CURRENCY_SYMBOLS.get(str(currency), str(currency))
    if fval >= 1_000_000:
        return f"{symbol}{fval/1_000_000:.2f}M"
    elif fval >= 1_000:
        return f"{symbol}{fval/1_000:.1f}K"
    else:
        return f"{symbol}{fval:.2f}"


def _extract_buyer_country(notice: dict[str, Any]) -> str | None:
    val = notice.get("buyer-country")
    if isinstance(val, str):
        return val
    if isinstance(val, list) and val:
        return val[0]
    return None


class NoticeSearchResult(BaseModel):
    publication_number: str
    notice_type: str | None = None
    publication_date: str | None = None
    buyer_name: str | None = None
    buyer_country: str | None = None
    winners: list[dict[str, str]] = []
    total_winners: int = 0
    contract_value: str = "Not disclosed"
    cpv_codes: list[str] = []
    contract_title: str | None = None
    ted_url: str = ""

    @classmethod
    def from_notice(cls, notice: dict[str, Any], max_winners: int = 10) -> "NoticeSearchResult":
        pub_num = notice.get("publication-number", "")
        all_winners = zip_winners(notice)
        winners = all_winners[:max_winners]

        cpv_raw = notice.get("classification-cpv", [])
        if isinstance(cpv_raw, list):
            cpv_codes = [str(c) for c in cpv_raw]
        else:
            cpv_codes = [str(cpv_raw)] if cpv_raw else []

        return cls(
            publication_number=pub_num,
            notice_type=notice.get("notice-type"),
            publication_date=notice.get("publication-date"),
            buyer_name=pick_best_language(notice.get("buyer-name")),
            buyer_country=_extract_buyer_country(notice),
            winners=winners,
            total_winners=len(all_winners),
            contract_value=format_value(notice),
            cpv_codes=cpv_codes,
            contract_title=pick_best_language(notice.get("contract-title")),
            ted_url=f"https://ted.europa.eu/en/notice/-/detail/{pub_num}" if pub_num else "",
        )
