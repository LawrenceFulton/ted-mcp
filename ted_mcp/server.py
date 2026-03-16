from __future__ import annotations
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP, Context
from .ted_client import TEDClient, TEDTimeoutError, TEDBadRequestError, TEDAPIError, AWARD_FIELDS
from .models import NoticeSearchResult, zip_winners, pick_best_language, pick_all_languages, format_value


@dataclass
class AppContext:
    ted_client: TEDClient


def build_expert_query(
    winner_name: str | None = None,
    buyer_country: str | None = None,
    year: int | None = None,
    cpv_codes: list[int] | None = None,
    keywords: str | None = None,
    notice_type: str | None = None,
) -> str:
    parts: list[str] = []
    if winner_name:
        effective_type = notice_type or "can-standard"
        parts.append(f"notice-type={effective_type}")
        parts.append(f'winner-name~"{winner_name}"')
    elif notice_type:
        parts.append(f"notice-type={notice_type}")
    if buyer_country:
        parts.append(f"buyer-country={buyer_country.upper()}")
    if year:
        parts.append(f"PD>={year}0101 AND PD<={year}1231")
    if cpv_codes:
        codes_str = ", ".join(str(c) for c in cpv_codes)
        parts.append(f"classification-cpv IN ({codes_str})")
    if keywords:
        parts.append(f'FT~"{keywords}"')
    return " AND ".join(parts) or "PD>=20200101"


@asynccontextmanager
async def lifespan(server: FastMCP):
    async with httpx.AsyncClient() as client:
        yield AppContext(ted_client=TEDClient(client))


mcp = FastMCP("TED EU Procurement", lifespan=lifespan)


def _format_notices_markdown(results: list[NoticeSearchResult], total: int, query: str) -> str:
    lines = [f"**Found {total} notices** for query: `{query}`\n"]
    if not results:
        lines.append("No results returned.")
        return "\n".join(lines)

    for r in results:
        lines.append(f"### [{r.publication_number}]({r.ted_url})")
        lines.append(f"- **Date:** {r.publication_date or 'N/A'}")
        lines.append(f"- **Type:** {r.notice_type or 'N/A'}")
        if r.contract_title:
            lines.append(f"- **Title:** {r.contract_title}")
        lines.append(f"- **Buyer:** {r.buyer_name or 'N/A'} ({r.buyer_country or 'N/A'})")
        if r.winners:
            winner_strs = [f"{w['name']} ({w['country']})" if w['country'] else w['name'] for w in r.winners]
            shown = ", ".join(winner_strs)
            if r.total_winners > len(r.winners):
                shown += f" ... (+{r.total_winners - len(r.winners)} more)"
            lines.append(f"- **Winner(s):** {shown}")
        else:
            lines.append("- **Winner(s):** N/A")
        lines.append(f"- **Value:** {r.contract_value}")
        if r.cpv_codes:
            lines.append(f"- **CPV:** {', '.join(r.cpv_codes[:5])}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def search_notices(
    ctx: Context,
    winner_name: str | None = None,
    buyer_country: str = "DEU",
    year: int | None = None,
    cpv_codes: list[int] | None = None,
    keywords: str | None = None,
    notice_type: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> str:
    """Search EU public procurement notices on TED (ted.europa.eu).

    Use this to find contract award notices, filter by winner company name,
    buyer country, year, CPV codes, or keywords.

    Args:
        winner_name: Company/entity name to search as winner (fuzzy match). E.g. "Deloitte", "Accenture"
        buyer_country: 3-letter ISO country code of the buying authority. Defaults to "DEU" (Germany). E.g. "FRA", "GBR", "ITA"
        year: Publication year filter. E.g. 2024
        cpv_codes: List of CPV (Common Procurement Vocabulary) codes. E.g. [72000000] for IT services
        keywords: Full-text search across notice content. E.g. "SAP S4 transformation"
        notice_type: Notice type filter. Defaults to "can-standard" when winner_name is set. E.g. "can-standard", "cn-standard"
        page: Page number (1-based)
        page_size: Results per page (1-100, default 10)
    """
    page_size = max(1, min(100, page_size))
    query = build_expert_query(
        winner_name=winner_name,
        buyer_country=buyer_country,
        year=year,
        cpv_codes=cpv_codes,
        keywords=keywords,
        notice_type=notice_type,
    )

    ted: TEDClient = ctx.request_context.lifespan_context.ted_client
    try:
        data = await ted.search(query, page=page, limit=page_size)
    except TEDTimeoutError:
        return "Error: TED API timed out. Try narrowing your query (add a year, country, or more specific terms)."
    except TEDBadRequestError as e:
        return f"Error: {e}\n\nTip: Check that buyer_country uses 3-letter ISO code (e.g. DEU not DE) and year is a 4-digit integer."
    except TEDAPIError as e:
        return f"Error: {e}"

    notices_raw = data.get("notices", [])
    total = data.get("totalNoticeCount", 0)
    timed_out = data.get("timedOut", False)

    results = [NoticeSearchResult.from_notice(n) for n in notices_raw]
    output = _format_notices_markdown(results, total, query)

    if timed_out:
        output += "\n\n> **Warning:** TED API query timed out — results may be incomplete. Try narrowing your query."

    if total == 0:
        output += "\n\n**Tips:**\n- Use 3-letter ISO country codes (DEU, FRA, GBR, ITA, ESP, POL, NLD)\n- Try partial company names\n- Winner data is most reliable for `can-standard` notices from 2021 onwards"

    return output


@mcp.tool()
async def get_notice(ctx: Context, publication_number: str) -> str:
    """Retrieve full details of a single TED procurement notice.

    Args:
        publication_number: TED publication number in format NNNNNN-YYYY. E.g. "6091-2024", "123456-2023"
    """
    ted: TEDClient = ctx.request_context.lifespan_context.ted_client

    # Fetch extra fields for detail view
    detail_fields = list(dict.fromkeys(AWARD_FIELDS + ["procedure-type"]))

    try:
        data = await ted.search(
            query=f'publication-number={publication_number}',
            fields=detail_fields,
            page=1,
            limit=1,
        )
    except TEDTimeoutError:
        return "Error: TED API timed out."
    except TEDBadRequestError as e:
        return f"Error: {e}"
    except TEDAPIError as e:
        return f"Error: {e}"

    notices = data.get("notices", [])
    if not notices:
        return f"No notice found with publication number `{publication_number}`.\n\nCheck the format is NNNNNN-YYYY (e.g. 6091-2024)."

    n = notices[0]
    pub_num = n.get("publication-number", publication_number)
    ted_url = f"https://ted.europa.eu/en/notice/-/detail/{pub_num}"

    lines = [f"## Notice {pub_num}", f"**URL:** {ted_url}\n"]

    lines.append(f"**Type:** {n.get('notice-type', 'N/A')}")
    lines.append(f"**Publication Date:** {n.get('publication-date', 'N/A')}")
    if n.get("procedure-type"):
        lines.append(f"**Procedure Type:** {n.get('procedure-type')}")

    # Contract title
    title = pick_best_language(n.get("contract-title"))
    if title:
        lines.append(f"**Contract Title:** {title}")

    lines.append("")
    lines.append("### Buyer")
    buyer_names = pick_all_languages(n.get("buyer-name"))
    if buyer_names:
        lines.append(f"**Name:** {' / '.join(buyer_names)}")
    buyer_country = n.get("buyer-country")
    if isinstance(buyer_country, list):
        buyer_country = buyer_country[0] if buyer_country else None
    if buyer_country:
        lines.append(f"**Country:** {buyer_country}")

    lines.append("")
    lines.append("### Contract Value")
    lines.append(format_value(n))

    # CPV
    cpv_raw = n.get("classification-cpv", [])
    if isinstance(cpv_raw, list) and cpv_raw:
        lines.append(f"\n**CPV Codes:** {', '.join(str(c) for c in cpv_raw)}")

    # Winners
    all_winners = zip_winners(n)
    decision_date = n.get("winner-decision-date")
    lines.append(f"\n### Winners ({len(all_winners)} total)")
    if decision_date:
        lines.append(f"**Award Decision Date:** {decision_date}")

    if all_winners:
        for i, w in enumerate(all_winners, 1):
            country_str = f" ({w['country']})" if w['country'] else ""
            lines.append(f"{i}. {w['name']}{country_str}")
    else:
        lines.append("No winner data available (may not be a contract award notice).")

    return "\n".join(lines)


@mcp.tool()
async def search_notices_raw(
    ctx: Context,
    expert_query: str,
    fields: list[str] | None = None,
    page: int = 1,
    page_size: int = 10,
    pagination_mode: str = "PAGE_NUMBER",
    iteration_token: str | None = None,
) -> str:
    """Search TED notices using a raw expert query string.

    For power users who need precise control over the TED expert query syntax.
    Supports ITERATION pagination mode for large result sets.

    Expert query examples:
    - `buyer-country=DEU AND winner-name~"Deloitte" AND PD>=20240101 AND PD<=20241231`
    - `notice-type=can-standard AND classification-cpv IN (72000000) AND buyer-country=FRA`
    - `FT~"SAP S4 transformation" AND notice-type=can-standard`

    Args:
        expert_query: TED expert query string
        fields: List of fields to return. Defaults to standard award fields.
        page: Page number for PAGE_NUMBER mode
        page_size: Results per page (1-100)
        pagination_mode: "PAGE_NUMBER" (default) or "ITERATION" (for >15000 results)
        iteration_token: Token from previous ITERATION response for next page
    """
    page_size = max(1, min(100, page_size))
    ted: TEDClient = ctx.request_context.lifespan_context.ted_client

    try:
        data = await ted.search(
            query=expert_query,
            fields=fields,
            page=page,
            limit=page_size,
            pagination_mode=pagination_mode,
            iteration_token=iteration_token,
        )
    except TEDTimeoutError:
        return "Error: TED API timed out. Try narrowing your query."
    except TEDBadRequestError as e:
        return f"Error: {e}"
    except TEDAPIError as e:
        return f"Error: {e}"

    notices_raw = data.get("notices", [])
    total = data.get("totalNoticeCount", 0)
    timed_out = data.get("timedOut", False)
    next_token = data.get("iterationNextToken")

    results = [NoticeSearchResult.from_notice(n) for n in notices_raw]
    output = _format_notices_markdown(results, total, expert_query)

    if next_token:
        output += f"\n\n**Next page token (ITERATION):** `{next_token}`\n(Pass as `iteration_token` in next call)"

    if timed_out:
        output += "\n\n> **Warning:** TED API query timed out — results may be incomplete."

    return output


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
