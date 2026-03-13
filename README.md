# ted-mcp

MCP server for [TED (ted.europa.eu)](https://ted.europa.eu) — the EU public procurement database. Exposes TED notice search to LLMs via the [Model Context Protocol](https://modelcontextprotocol.io).

No API key required. Uses the public TED search API.

> [!TIP]
> Point your favorite AI companion here (e.g. Claude) and ask it to help set this MCP server up for you.

## Installation

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

No further setup needed — `uv run` handles the virtual environment automatically.

## Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ted-procurement": {
      "command": "/Users/your-username/.local/bin/uv",
      "args": ["run", "--directory", "/path/to/ted-mcp", "ted-mcp"]
    }
  }
}
```

Use the full path to `uv` (find it with `which uv`) rather than just `"uv"`, since MCP clients run with a limited PATH that may not include `~/.local/bin`.

## Tools

### `search_notices`

Structured search over contract award notices.

| Parameter | Type | Description |
|-----------|------|-------------|
| `winner_name` | string | Company name, fuzzy match (e.g. `"Deloitte"`) |
| `buyer_country` | string | 3-letter ISO country code. Defaults to `"DEU"` (Germany) |
| `year` | int | Publication year (e.g. `2024`) |
| `cpv_codes` | int[] | CPV codes (e.g. `[72000000]`) |
| `keywords` | string | Full-text search across notice content |
| `notice_type` | string | Defaults to `can-standard` when `winner_name` is set |
| `page` / `page_size` | int | Pagination; max 100 per page |

**Example natural-language queries:**
- "Which contracts did Deloitte win in Germany in 2024?"
- "Which government bodies procured SAP S4 transformations?"
- "What are prominent IT services contracts in France in 2023"

You can query in your local language as well (e.g. in German "Welche Ausschreibungen für Softwareentwicklung laufen gerade?").

### `get_notice`

Returns full detail for a single notice by publication number.

| Parameter | Type | Description |
|-----------|------|-------------|
| `publication_number` | string | Format `NNNNNN-YYYY` (e.g. `"6091-2024"`) |

### `search_notices_raw`

Passes an expert query string directly to the TED API. Intended for precise or complex queries.

| Parameter | Type | Description |
|-----------|------|-------------|
| `expert_query` | string | TED expert query string |
| `fields` | string[] | Fields to return (defaults to standard award fields) |
| `pagination_mode` | string | `PAGE_NUMBER` (default) or `ITERATION` |
| `iteration_token` | string | Continuation token for ITERATION mode |

**Expert query syntax:**

```
buyer-country=DEU
winner-name~"Deloitte"
PD>=20240101 AND PD<=20241231
classification-cpv IN (72000000)
FT~"SAP S4 transformation"
notice-type=can-standard
```

## Reference

**Common CPV codes**

| Code | Category |
|------|----------|
| 72000000 | IT services |
| 48000000 | Software |
| 71000000 | Architecture & engineering |
| 79000000 | Business services |
| 45000000 | Construction |

**Country codes (ISO 3166-1 alpha-3)**

`DEU` Germany · `FRA` France · `GBR` United Kingdom · `ITA` Italy · `ESP` Spain · `POL` Poland · `NLD` Netherlands · `BEL` Belgium · `SWE` Sweden · `AUT` Austria · `PRT` Portugal · `ROU` Romania

## Limitations

- Winner data is only reliably present on `can-standard` notices (contract award notices), and coverage varies by member state prior to 2021.
- Multi-lot contracts can have many winners; summary view truncates at 10.
- Most notices are not in English — the server falls back to the best available language.
- `PAGE_NUMBER` pagination is capped at 15,000 results; use `ITERATION` mode for bulk access.
- Framework agreements frequently report value as `0.00` (not disclosed).

# Notes
The code in this repository is mostly AI generated. Treat it as such.
