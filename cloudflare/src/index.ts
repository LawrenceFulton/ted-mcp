import { McpAgent } from "agents/mcp";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

// ============ TED Client ============

const TED_SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search";

const AWARD_FIELDS = [
  "publication-number",
  "notice-type",
  "publication-date",
  "buyer-name",
  "buyer-country",
  "winner-name",
  "winner-country",
  "winner-decision-date",
  "result-value-notice",
  "result-value-cur-notice",
  "classification-cpv",
  "contract-title",
];

class TEDAPIError extends Error {}
class TEDTimeoutError extends TEDAPIError {}
class TEDConnectionError extends TEDAPIError {}
class TEDBadRequestError extends TEDAPIError {}

async function tedSearch(
  query: string,
  fields?: string[],
  page = 1,
  limit = 10,
  paginationMode = "PAGE_NUMBER",
  iterationToken?: string,
): Promise<Record<string, unknown>> {
  const body: Record<string, unknown> = {
    query,
    fields: fields ?? AWARD_FIELDS,
    page,
    limit,
    paginationMode,
  };
  if (iterationToken) {
    body["iterationNextToken"] = iterationToken;
  }

  let response: Response;
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30_000);
    try {
      response = await fetch(TED_SEARCH_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeoutId);
    }
  } catch (e: unknown) {
    if (e instanceof Error && e.name === "AbortError") {
      throw new TEDTimeoutError("TED API timed out. Try narrowing your query.");
    }
    throw new TEDConnectionError(`Failed to connect to TED API: ${e}`);
  }

  if (response.status === 400) {
    let msg: string;
    try {
      const data = (await response.json()) as Record<string, unknown>;
      msg = String(data["message"] ?? data["error"] ?? response.statusText);
    } catch {
      msg = await response.text();
    }
    throw new TEDBadRequestError(`TED API bad request: ${msg}`);
  }

  if (response.status !== 200) {
    const text = await response.text();
    throw new TEDAPIError(`TED API returned HTTP ${response.status}: ${text.slice(0, 200)}`);
  }

  return (await response.json()) as Record<string, unknown>;
}

// ============ Models ============

const LANGUAGE_PRIORITY = ["eng", "deu", "fra", "nld", "ita", "spa", "por", "pol"];

const CURRENCY_SYMBOLS: Record<string, string> = {
  EUR: "€", GBP: "£", USD: "$", CHF: "CHF", PLN: "PLN",
  SEK: "SEK", DKK: "DKK", NOK: "NOK", CZK: "CZK",
  HUF: "HUF", RON: "RON", BGN: "BGN", HRK: "HRK",
};

function pickBestLanguage(field: unknown): string | null {
  if (field == null) return null;
  if (typeof field === "string") return field;
  if (typeof field !== "object" || Array.isArray(field)) return String(field);
  const f = field as Record<string, unknown>;
  for (const lang of LANGUAGE_PRIORITY) {
    if (lang in f) {
      const values = f[lang];
      if (Array.isArray(values) && values.length > 0) return String(values[0]);
      if (typeof values === "string") return values;
    }
  }
  for (const values of Object.values(f)) {
    if (Array.isArray(values) && values.length > 0) return String(values[0]);
    if (typeof values === "string") return values;
  }
  return null;
}

function pickAllLanguages(field: unknown): string[] {
  if (field == null) return [];
  if (typeof field === "string") return [field];
  if (typeof field !== "object" || Array.isArray(field)) return [String(field)];
  const f = field as Record<string, unknown>;
  const seen = new Set<string>();
  const result: string[] = [];
  const addValue = (v: unknown) => {
    const s = String(v);
    if (!seen.has(s)) { seen.add(s); result.push(s); }
  };
  for (const lang of LANGUAGE_PRIORITY) {
    if (!(lang in f)) continue;
    const values = f[lang];
    if (Array.isArray(values)) values.forEach(addValue);
    else if (typeof values === "string") addValue(values);
  }
  for (const [lang, values] of Object.entries(f)) {
    if (LANGUAGE_PRIORITY.includes(lang)) continue;
    if (Array.isArray(values)) values.forEach(addValue);
    else if (typeof values === "string") addValue(values);
  }
  return result;
}

function zipWinners(
  notice: Record<string, unknown>,
  maxCount?: number,
): Array<{ name: string; country: string }> {
  const rawNames = notice["winner-name"];
  const rawCountries = notice["winner-country"] ?? [];

  if (!rawNames) return [];

  let names: string[] = [];
  if (typeof rawNames === "object" && !Array.isArray(rawNames)) {
    const f = rawNames as Record<string, unknown>;
    for (const lang of LANGUAGE_PRIORITY) {
      if (lang in f) {
        const vals = f[lang];
        if (Array.isArray(vals) && vals.length > 0) { names = vals.map(String); break; }
        if (typeof vals === "string") { names = [vals]; break; }
      }
    }
    if (names.length === 0) {
      for (const vals of Object.values(f)) {
        if (Array.isArray(vals) && vals.length > 0) { names = vals.map(String); break; }
        if (typeof vals === "string") { names = [vals]; break; }
      }
    }
  } else if (Array.isArray(rawNames)) {
    names = rawNames.map(String);
  }

  if (names.length === 0) return [];

  const countries: string[] = Array.isArray(rawCountries) ? rawCountries.map(String) : [];
  const limit = maxCount != null ? Math.min(names.length, maxCount) : names.length;
  return Array.from({ length: limit }, (_, i) => ({
    name: names[i],
    country: countries[i] ?? "",
  }));
}

function formatValue(notice: Record<string, unknown>): string {
  const value = notice["result-value-notice"];
  const currency = String(notice["result-value-cur-notice"] ?? "EUR");
  if (value == null) return "Not disclosed";
  const fval = parseFloat(String(value));
  if (isNaN(fval) || fval <= 0.01) return "Not disclosed";
  const symbol = CURRENCY_SYMBOLS[currency] ?? currency;
  if (fval >= 1_000_000) return `${symbol}${(fval / 1_000_000).toFixed(2)}M`;
  if (fval >= 1_000) return `${symbol}${(fval / 1_000).toFixed(1)}K`;
  return `${symbol}${fval.toFixed(2)}`;
}

function extractBuyerCountry(notice: Record<string, unknown>): string | null {
  const val = notice["buyer-country"];
  if (typeof val === "string") return val;
  if (Array.isArray(val) && val.length > 0) return String(val[0]);
  return null;
}

interface NoticeSearchResult {
  publication_number: string;
  notice_type: string | null;
  publication_date: string | null;
  buyer_name: string | null;
  buyer_country: string | null;
  winners: Array<{ name: string; country: string }>;
  total_winners: number;
  contract_value: string;
  cpv_codes: string[];
  contract_title: string | null;
  ted_url: string;
}

function noticeFromRaw(notice: Record<string, unknown>, maxWinners = 10): NoticeSearchResult {
  const pubNum = String(notice["publication-number"] ?? "");
  const allWinners = zipWinners(notice);
  const cpvRaw = notice["classification-cpv"];
  const cpvCodes = Array.isArray(cpvRaw) ? cpvRaw.map(String) : cpvRaw != null ? [String(cpvRaw)] : [];
  return {
    publication_number: pubNum,
    notice_type: notice["notice-type"] != null ? String(notice["notice-type"]) : null,
    publication_date: notice["publication-date"] != null ? String(notice["publication-date"]) : null,
    buyer_name: pickBestLanguage(notice["buyer-name"]),
    buyer_country: extractBuyerCountry(notice),
    winners: allWinners.slice(0, maxWinners),
    total_winners: allWinners.length,
    contract_value: formatValue(notice),
    cpv_codes: cpvCodes,
    contract_title: pickBestLanguage(notice["contract-title"]),
    ted_url: pubNum ? `https://ted.europa.eu/en/notice/-/detail/${pubNum}` : "",
  };
}

// ============ Query Builder ============

function buildExpertQuery(params: {
  winner_name?: string;
  buyer_country?: string;
  year?: number;
  cpv_codes?: number[];
  keywords?: string;
  notice_type?: string;
}): string {
  const parts: string[] = [];
  if (params.winner_name) {
    const effectiveType = params.notice_type ?? "can-standard";
    parts.push(`notice-type=${effectiveType}`);
    parts.push(`winner-name~"${params.winner_name}"`);
  } else if (params.notice_type) {
    parts.push(`notice-type=${params.notice_type}`);
  }
  if (params.buyer_country) {
    parts.push(`buyer-country=${params.buyer_country.toUpperCase()}`);
  }
  if (params.year) {
    parts.push(`PD>=${params.year}0101 AND PD<=${params.year}1231`);
  }
  if (params.cpv_codes && params.cpv_codes.length > 0) {
    parts.push(`classification-cpv IN (${params.cpv_codes.join(", ")})`);
  }
  if (params.keywords) {
    parts.push(`FT~"${params.keywords}"`);
  }
  return parts.join(" AND ") || "PD>=20200101";
}

// ============ Markdown Formatter ============

function formatNoticesMarkdown(results: NoticeSearchResult[], total: number, query: string): string {
  const lines: string[] = [`**Found ${total} notices** for query: \`${query}\`\n`];
  if (results.length === 0) {
    lines.push("No results returned.");
    return lines.join("\n");
  }
  for (const r of results) {
    lines.push(`### [${r.publication_number}](${r.ted_url})`);
    lines.push(`- **Date:** ${r.publication_date ?? "N/A"}`);
    lines.push(`- **Type:** ${r.notice_type ?? "N/A"}`);
    if (r.contract_title) lines.push(`- **Title:** ${r.contract_title}`);
    lines.push(`- **Buyer:** ${r.buyer_name ?? "N/A"} (${r.buyer_country ?? "N/A"})`);
    if (r.winners.length > 0) {
      const winnerStrs = r.winners.map((w) => (w.country ? `${w.name} (${w.country})` : w.name));
      let shown = winnerStrs.join(", ");
      if (r.total_winners > r.winners.length) shown += ` ... (+${r.total_winners - r.winners.length} more)`;
      lines.push(`- **Winner(s):** ${shown}`);
    } else {
      lines.push("- **Winner(s):** N/A");
    }
    lines.push(`- **Value:** ${r.contract_value}`);
    if (r.cpv_codes.length > 0) lines.push(`- **CPV:** ${r.cpv_codes.slice(0, 5).join(", ")}`);
    lines.push("");
  }
  return lines.join("\n");
}

// ============ MCP Agent ============

export interface Env {}

export class TedMCP extends McpAgent<Env> {
  server = new McpServer({
    name: "TED EU Procurement",
    version: "1.0.0",
  });

  async init() {
    this.server.tool(
      "search_notices",
      "Search EU public procurement notices on TED (ted.europa.eu). Use this to find contract award notices, filter by winner company name, buyer country, year, CPV codes, or keywords.",
      {
        winner_name: z.string().optional().describe('Company/entity name to search as winner (fuzzy match). E.g. "Deloitte", "Accenture"'),
        buyer_country: z.string().default("DEU").describe('3-letter ISO country code of the buying authority. E.g. "FRA", "GBR", "ITA"'),
        year: z.number().int().optional().describe("Publication year filter. E.g. 2024"),
        cpv_codes: z.array(z.number().int()).optional().describe("List of CPV (Common Procurement Vocabulary) codes. E.g. [72000000] for IT services"),
        keywords: z.string().optional().describe('Full-text search across notice content. E.g. "SAP S4 transformation"'),
        notice_type: z.string().optional().describe('Notice type filter. Defaults to "can-standard" when winner_name is set.'),
        page: z.number().int().default(1).describe("Page number (1-based)"),
        page_size: z.number().int().default(10).describe("Results per page (1-100)"),
      },
      async ({ winner_name, buyer_country, year, cpv_codes, keywords, notice_type, page, page_size }) => {
        const limitedPageSize = Math.max(1, Math.min(100, page_size));
        const query = buildExpertQuery({ winner_name, buyer_country, year, cpv_codes, keywords, notice_type });

        let data: Record<string, unknown>;
        try {
          data = await tedSearch(query, undefined, page, limitedPageSize);
        } catch (e) {
          if (e instanceof TEDTimeoutError) {
            return { content: [{ type: "text" as const, text: "Error: TED API timed out. Try narrowing your query (add a year, country, or more specific terms)." }] };
          }
          if (e instanceof TEDBadRequestError) {
            return { content: [{ type: "text" as const, text: `Error: ${(e as Error).message}\n\nTip: Check that buyer_country uses 3-letter ISO code (e.g. DEU not DE) and year is a 4-digit integer.` }] };
          }
          return { content: [{ type: "text" as const, text: `Error: ${(e as Error).message}` }] };
        }

        const noticesRaw = (data["notices"] as unknown[] | undefined) ?? [];
        const total = (data["totalNoticeCount"] as number | undefined) ?? 0;
        const timedOut = Boolean(data["timedOut"]);

        const results = noticesRaw.map((n) => noticeFromRaw(n as Record<string, unknown>));
        let output = formatNoticesMarkdown(results, total, query);

        if (timedOut) {
          output += "\n\n> **Warning:** TED API query timed out — results may be incomplete. Try narrowing your query.";
        }
        if (total === 0) {
          output += "\n\n**Tips:**\n- Use 3-letter ISO country codes (DEU, FRA, GBR, ITA, ESP, POL, NLD)\n- Try partial company names\n- Winner data is most reliable for `can-standard` notices from 2021 onwards";
        }

        return { content: [{ type: "text" as const, text: output }] };
      },
    );

    this.server.tool(
      "get_notice",
      "Retrieve full details of a single TED procurement notice.",
      {
        publication_number: z.string().describe('TED publication number in format NNNNNN-YYYY. E.g. "6091-2024", "123456-2023"'),
      },
      async ({ publication_number }) => {
        const detailFields = [...new Set([...AWARD_FIELDS, "procedure-type"])];

        let data: Record<string, unknown>;
        try {
          data = await tedSearch(`publication-number=${publication_number}`, detailFields, 1, 1);
        } catch (e) {
          if (e instanceof TEDTimeoutError) {
            return { content: [{ type: "text" as const, text: "Error: TED API timed out." }] };
          }
          if (e instanceof TEDBadRequestError) {
            return { content: [{ type: "text" as const, text: `Error: ${(e as Error).message}` }] };
          }
          return { content: [{ type: "text" as const, text: `Error: ${(e as Error).message}` }] };
        }

        const notices = (data["notices"] as unknown[] | undefined) ?? [];
        if (notices.length === 0) {
          return { content: [{ type: "text" as const, text: `No notice found with publication number \`${publication_number}\`.\n\nCheck the format is NNNNNN-YYYY (e.g. 6091-2024).` }] };
        }

        const n = notices[0] as Record<string, unknown>;
        const pubNum = String(n["publication-number"] ?? publication_number);
        const tedUrl = `https://ted.europa.eu/en/notice/-/detail/${pubNum}`;

        const lines: string[] = [`## Notice ${pubNum}`, `**URL:** ${tedUrl}\n`];
        lines.push(`**Type:** ${n["notice-type"] ?? "N/A"}`);
        lines.push(`**Publication Date:** ${n["publication-date"] ?? "N/A"}`);
        if (n["procedure-type"]) lines.push(`**Procedure Type:** ${n["procedure-type"]}`);

        const title = pickBestLanguage(n["contract-title"]);
        if (title) lines.push(`**Contract Title:** ${title}`);

        lines.push("", "### Buyer");
        const buyerNames = pickAllLanguages(n["buyer-name"]);
        if (buyerNames.length > 0) lines.push(`**Name:** ${buyerNames.join(" / ")}`);
        const buyerCountry = extractBuyerCountry(n);
        if (buyerCountry) lines.push(`**Country:** ${buyerCountry}`);

        lines.push("", "### Contract Value");
        lines.push(formatValue(n));

        const cpvRaw = n["classification-cpv"];
        if (Array.isArray(cpvRaw) && cpvRaw.length > 0) {
          lines.push(`\n**CPV Codes:** ${cpvRaw.join(", ")}`);
        }

        const allWinners = zipWinners(n);
        const decisionDate = n["winner-decision-date"];
        lines.push(`\n### Winners (${allWinners.length} total)`);
        if (decisionDate) lines.push(`**Award Decision Date:** ${decisionDate}`);

        if (allWinners.length > 0) {
          allWinners.forEach((w, i) => {
            const countryStr = w.country ? ` (${w.country})` : "";
            lines.push(`${i + 1}. ${w.name}${countryStr}`);
          });
        } else {
          lines.push("No winner data available (may not be a contract award notice).");
        }

        return { content: [{ type: "text" as const, text: lines.join("\n") }] };
      },
    );

    this.server.tool(
      "search_notices_raw",
      'Search TED notices using a raw expert query string. For power users who need precise control over the TED expert query syntax. Supports ITERATION pagination mode for large result sets. Examples: `buyer-country=DEU AND winner-name~"Deloitte"`, `notice-type=can-standard AND classification-cpv IN (72000000)`',
      {
        expert_query: z.string().describe('TED expert query string. E.g. `buyer-country=DEU AND winner-name~"Deloitte" AND PD>=20240101`'),
        fields: z.array(z.string()).optional().describe("List of fields to return. Defaults to standard award fields."),
        page: z.number().int().default(1).describe("Page number for PAGE_NUMBER mode"),
        page_size: z.number().int().default(10).describe("Results per page (1-100)"),
        pagination_mode: z.enum(["PAGE_NUMBER", "ITERATION"]).default("PAGE_NUMBER").describe("Pagination mode"),
        iteration_token: z.string().optional().describe("Token from previous ITERATION response for next page"),
      },
      async ({ expert_query, fields, page, page_size, pagination_mode, iteration_token }) => {
        const limitedPageSize = Math.max(1, Math.min(100, page_size));

        let data: Record<string, unknown>;
        try {
          data = await tedSearch(expert_query, fields, page, limitedPageSize, pagination_mode, iteration_token);
        } catch (e) {
          if (e instanceof TEDTimeoutError) {
            return { content: [{ type: "text" as const, text: "Error: TED API timed out. Try narrowing your query." }] };
          }
          if (e instanceof TEDBadRequestError) {
            return { content: [{ type: "text" as const, text: `Error: ${(e as Error).message}` }] };
          }
          return { content: [{ type: "text" as const, text: `Error: ${(e as Error).message}` }] };
        }

        const noticesRaw = (data["notices"] as unknown[] | undefined) ?? [];
        const total = (data["totalNoticeCount"] as number | undefined) ?? 0;
        const timedOut = Boolean(data["timedOut"]);
        const nextToken = data["iterationNextToken"] as string | undefined;

        const results = noticesRaw.map((n) => noticeFromRaw(n as Record<string, unknown>));
        let output = formatNoticesMarkdown(results, total, expert_query);

        if (nextToken) {
          output += `\n\n**Next page token (ITERATION):** \`${nextToken}\`\n(Pass as \`iteration_token\` in next call)`;
        }
        if (timedOut) {
          output += "\n\n> **Warning:** TED API query timed out — results may be incomplete.";
        }

        return { content: [{ type: "text" as const, text: output }] };
      },
    );
  }
}

// ============ Worker Entry Point ============

export default {
  fetch(request: Request, env: Env, ctx: ExecutionContext): Response | Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/sse" || url.pathname === "/sse/message") {
      return TedMCP.serveSSE("/sse").fetch(request, env, ctx);
    }

    if (url.pathname === "/mcp") {
      return TedMCP.serve("/mcp").fetch(request, env, ctx);
    }

    return new Response(
      "TED EU Procurement MCP Server\n\nEndpoints:\n- POST /mcp  (HTTP Streamable)\n- GET  /sse  (Server-Sent Events)",
      { status: 200, headers: { "Content-Type": "text/plain" } },
    );
  },
} satisfies ExportedHandler<Env>;
