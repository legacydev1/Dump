"""
search_engine.py - FTS5-powered full-text search.

Log formats handled by parse_log_record():

  PRIMARY FORMAT (new standard):
        url:login:pass
        https://login.live.com:user@gmail.com:password123
        https://site.com/path:login:pass

  ALSO SUPPORTED:
        url|login|pass         (pipe-delimited)
        url login pass         (space-delimited)
        URL:  / Login: / Pass: (key-value multi-line)

IMPORTANT: Only records where URL, Login AND Pass are ALL non-empty
are included in the output file. Incomplete records are silently dropped.

OUTPUT FORMAT:
    url:login:pass   (one line per record — the new standard format)
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

from database.connection import db

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# LOG RECORD PARSER
# ══════════════════════════════════════════════════════════════════════════════

_URL_RE   = re.compile(r'^(?:url|host|site|link)\s*[:\|]\s*(.+)', re.IGNORECASE)
_LOGIN_RE = re.compile(r'^(?:login|email|user(?:name)?|mail)\s*[:\|]\s*(.+)', re.IGNORECASE)
_PASS_RE  = re.compile(r'^(?:pass(?:word)?|pwd|secret)\s*[:\|]\s*(.+)', re.IGNORECASE)


def _is_complete(rec: Dict[str, str]) -> bool:
    url   = rec.get("url", "").strip()
    login = rec.get("login", "").strip()
    pwd   = rec.get("pass", "").strip()
    return bool(url) and bool(login) and bool(pwd)


def _split_colon_format(raw: str) -> Optional[Dict[str, str]]:
    """
    Parse the primary format: url:login:pass
    Handles:
      https://site.com:login@email.com:password
      https://site.com/path/page:login:password
      phone:password:https://site.com  (URL-last format)
    """
    # URL-first format: https://site.com:login:password
    if re.match(r'https?://', raw, re.IGNORECASE):
        scheme_end = raw.index("//") + 2
        rest = raw[scheme_end:]
        colon_pos = rest.find(":")
        if colon_pos == -1:
            return None
        url   = raw[:scheme_end + colon_pos]
        after = rest[colon_pos + 1:]
        last_colon = after.rfind(":")
        if last_colon == -1:
            return {"url": url, "login": after, "pass": ""}
        return {
            "url":   url,
            "login": after[:last_colon],
            "pass":  after[last_colon + 1:],
        }

    # URL-last format: phone:password:https://site.com
    if raw.count(":") >= 2:
        url_match = re.search(r'https?://', raw, re.IGNORECASE)
        if url_match:
            url_start  = url_match.start()
            login_part = raw[:url_start].rstrip(":")
            url_part   = raw[url_start:]
            parts      = login_part.split(":")
            login      = parts[0]
            password   = ":".join(parts[1:]) if len(parts) > 1 else ""
            return {"url": url_part, "login": login, "pass": password}

    return None


def _split_pipe_format(raw: str) -> Optional[Dict[str, str]]:
    parts = raw.split("|")
    if len(parts) >= 3 and re.match(r'https?://', parts[0], re.IGNORECASE):
        return {
            "url":   parts[0].strip(),
            "login": parts[1].strip(),
            "pass":  parts[2].strip(),
        }
    return None


def _split_space_format(raw: str) -> Optional[Dict[str, str]]:
    parts = raw.split()
    if len(parts) >= 3 and re.match(r'https?://', parts[0], re.IGNORECASE):
        return {"url": parts[0], "login": parts[1], "pass": parts[2]}
    return None


def _split_multiline(raw: str) -> Optional[Dict[str, str]]:
    lines = re.split(r'\\n|\n|\r', raw)
    result: Dict[str, str] = {"url": "", "login": "", "pass": ""}
    matched = False
    for line in lines:
        line = line.strip()
        m = _URL_RE.match(line)
        if m and not result["url"]:
            result["url"] = m.group(1).strip()
            matched = True
            continue
        m = _LOGIN_RE.match(line)
        if m and not result["login"]:
            result["login"] = m.group(1).strip()
            matched = True
            continue
        m = _PASS_RE.match(line)
        if m and not result["pass"]:
            result["pass"] = m.group(1).strip()
            matched = True
            continue
    return result if matched else None


def parse_log_record(raw: str) -> Dict[str, str]:
    """
    Parse a raw log line into {'url': ..., 'login': ..., 'pass': ...}.
    Primary format: url:login:pass
    """
    raw = raw.strip()

    # 1. Multi-line labelled (URL: / Login: / Pass:)
    if re.search(r'(?:url|login|pass)\s*:', raw, re.IGNORECASE):
        r = _split_multiline(raw)
        if r and any(r.values()):
            return r

    # 2. Colon-delimited (primary format: url:login:pass)
    if raw.count(":") >= 2:
        r = _split_colon_format(raw)
        if r:
            return r

    # 3. Pipe-delimited
    if "|" in raw:
        r = _split_pipe_format(raw)
        if r:
            return r

    # 4. Space-delimited
    r = _split_space_format(raw)
    if r:
        return r

    # 5. Fallback — incomplete
    return {"url": raw[:500], "login": "", "pass": ""}


# ══════════════════════════════════════════════════════════════════════════════
# OUTPUT BUILDER — New format: url:login:pass (one line per record)
# ══════════════════════════════════════════════════════════════════════════════

def build_txt_output(
    records: List[Dict[str, str]],
    query: str,
    total_in_db: int,
    mode: str = "all",
) -> str:
    """
    Serialise complete records into the new standard format:
        url:login:pass
    One record per line. Preceded by a stats header.
    """
    from keyboards.user_kb import SEARCH_MODES
    mode_label = SEARCH_MODES.get(mode, {}).get("label", mode)

    complete = [r for r in records if _is_complete(r)]
    dropped  = len(records) - len(complete)

    sep = "=" * 40
    header_lines = [
        sep,
        f"  LOGSBOT SEARCH RESULTS",
        sep,
        f"  Mode    : {mode_label}",
        f"  Query   : {query}",
        f"  Total   : {total_in_db}",
        f"  Found   : {len(complete)}",
    ]
    if dropped:
        header_lines.append(f"  Skipped : {dropped} (incomplete records)")
    header_lines += [sep, ""]

    body_lines: List[str] = []
    for rec in complete:
        # New standard format: url:login:pass
        body_lines.append(f"{rec['url']}:{rec['login']}:{rec['pass']}")

    return "\n".join(header_lines + body_lines)


def build_detailed_txt_output(
    records: List[Dict[str, str]],
    query: str,
    total_in_db: int,
    mode: str = "all",
) -> str:
    """
    Alternative detailed format for reading system display:
        URL   : https://...
        Login : user@email.com
        Pass  : password123
        ========================================
    """
    from keyboards.user_kb import SEARCH_MODES
    mode_label = SEARCH_MODES.get(mode, {}).get("label", mode)

    complete = [r for r in records if _is_complete(r)]
    sep = "=" * 40
    header_lines = [
        sep,
        f"  LOGSBOT — DETAILED RESULTS",
        sep,
        f"  Mode  : {mode_label}",
        f"  Query : {query}",
        f"  Found : {len(complete)} complete records",
        sep, "",
    ]

    body_lines: List[str] = []
    for i, rec in enumerate(complete, 1):
        body_lines.append(f"[{i}]")
        body_lines.append(f"URL   : {rec['url']}")
        body_lines.append(f"Login : {rec['login']}")
        body_lines.append(f"Pass  : {rec['pass']}")
        body_lines.append(sep)

    return "\n".join(header_lines + body_lines)


# ══════════════════════════════════════════════════════════════════════════════
# QUERY NORMALISER
# ══════════════════════════════════════════════════════════════════════════════

def _normalise_query(raw: str) -> str:
    raw = raw.strip()[:500]
    tokens: List[str] = []
    pattern = re.compile(r'"[^"]*"|-?\w+|AND|OR|NOT', re.IGNORECASE)
    for match in pattern.finditer(raw):
        token = match.group()
        upper = token.upper()
        if upper in ("AND", "OR", "NOT"):
            tokens.append(upper)
        elif token.startswith('"') and token.endswith('"'):
            tokens.append(token)
        elif token.startswith("-"):
            word = token[1:]
            if word:
                tokens.append("NOT")
                tokens.append(f"{word}*")
        else:
            tokens.append(f"{token}*")
    return " ".join(tokens) if tokens else '""'


# ══════════════════════════════════════════════════════════════════════════════
# CORE SEARCH FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

async def search_logs(
    query: str,
    page: int = 0,
    per_page: int = 10,
) -> Tuple[List[Dict], int]:
    """Paginated FTS5 search. Returns (raw_db_rows, total_count)."""
    fts_query = _normalise_query(query)
    offset = page * per_page
    try:
        count_row = await db.fetchone(
            "SELECT COUNT(*) FROM logs "
            "WHERE id IN (SELECT rowid FROM logs_fts WHERE logs_fts MATCH ?)",
            (fts_query,),
        )
        total_count: int = count_row[0] if count_row else 0
        if total_count == 0:
            return [], 0
        rows = await db.fetchall(
            """
            SELECT l.id, l.record_text, l.source_file, l.created_at
            FROM logs l
            JOIN logs_fts f ON l.id = f.rowid
            WHERE f.logs_fts MATCH ?
            ORDER BY rank
            LIMIT ? OFFSET ?
            """,
            (fts_query, per_page, offset),
        )
        return [dict(r) for r in rows], total_count
    except Exception as e:
        logger.warning("FTS5 failed (%s), fallback LIKE. Query: %s", e, fts_query)
        return await _fallback_search(query, per_page, offset)


async def search_logs_all(
    query: str,
    limit: Optional[int] = None,
    mode: str = "all",
) -> Tuple[List[Dict[str, str]], int]:
    """
    Fetch matching records, parse url:login:pass, keep only COMPLETE ones.

    Modes:
      "all"     — FTS5 search across full record_text (smart search)
      "domain"  — LIKE search, post-filter: url field contains query domain
      "ip"      — LIKE search, post-filter: url contains IP pattern
      "email"   — LIKE search, post-filter: login field contains query
      "pass"    — LIKE search, post-filter: pass field contains query
      "url"     — LIKE search, post-filter: url field contains full query
      "keyword" — FTS5 search (same as "all")

    Returns:
        (complete_parsed_records, total_raw_matches_in_db)
    """
    if mode in ("domain", "ip", "email", "pass", "url"):
        return await _field_search(query, mode, limit)

    # "all" and "keyword" → FTS5
    fts_query = _normalise_query(query)
    try:
        count_row = await db.fetchone(
            "SELECT COUNT(*) FROM logs "
            "WHERE id IN (SELECT rowid FROM logs_fts WHERE logs_fts MATCH ?)",
            (fts_query,),
        )
        total_count: int = count_row[0] if count_row else 0
        if total_count == 0:
            return [], 0

        fetch_limit = (limit * 3) if limit is not None else -1
        rows = await db.fetchall(
            """
            SELECT l.record_text
            FROM logs l
            JOIN logs_fts f ON l.id = f.rowid
            WHERE f.logs_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, fetch_limit),
        )
    except Exception as e:
        logger.warning("FTS5 all-fetch failed (%s), fallback LIKE. Query: %s", e, fts_query)
        rows, total_count = await _fallback_search_all(query, limit)
        raw_texts = [r["record_text"] if isinstance(r, dict) else r[0] for r in rows]
        complete = _filter_complete([parse_log_record(t) for t in raw_texts], limit)
        return complete, total_count

    parsed   = [parse_log_record(row[0]) for row in rows]
    complete = _filter_complete(parsed, limit)
    return complete, total_count


async def _field_search(
    query: str,
    mode: str,
    limit: Optional[int],
) -> Tuple[List[Dict[str, str]], int]:
    """LIKE-based full-table scan + post-parse field filter."""
    search_term = query.strip()
    host_only   = _extract_host(search_term)
    like_term   = f"%{host_only}%" if host_only else f"%{search_term}%"
    fetch_limit = (limit * 6) if limit is not None else -1

    try:
        count_row = await db.fetchone(
            "SELECT COUNT(*) FROM logs WHERE record_text LIKE ?", (like_term,)
        )
        total_count: int = count_row[0] if count_row else 0
        if total_count == 0:
            return [], 0

        rows = await db.fetchall(
            "SELECT record_text FROM logs WHERE record_text LIKE ? LIMIT ?",
            (like_term, fetch_limit),
        )
    except Exception as e:
        logger.error("Field search DB error: %s", e)
        return [], 0

    q_lower  = (host_only or search_term).lower()
    q_full   = search_term.lower()
    results: List[Dict[str, str]] = []

    for row in rows:
        rec = parse_log_record(row[0])
        if not _is_complete(rec):
            continue

        url_lower   = rec["url"].lower()
        login_lower = rec["login"].lower()
        pass_lower  = rec["pass"].lower()
        parsed_host = _extract_host(url_lower) or url_lower

        if mode == "domain":
            if q_lower not in parsed_host:
                continue
        elif mode == "ip":
            if q_lower not in url_lower:
                continue
        elif mode == "email":
            if q_lower not in login_lower:
                continue
        elif mode == "pass":
            if q_lower not in pass_lower:
                continue
        elif mode == "url":
            if q_full not in url_lower:
                path_query = re.sub(r'^https?://', '', q_full)
                if path_query not in url_lower:
                    continue

        results.append(rec)
        if limit is not None and len(results) >= limit:
            break

    return results, total_count


def _extract_host(url: str) -> Optional[str]:
    url = url.strip().lower()
    m = re.match(r'https?://([^/:\s?#]+)', url)
    if m:
        return m.group(1)
    return None


def _filter_complete(
    records: List[Dict[str, str]],
    limit: Optional[int],
) -> List[Dict[str, str]]:
    complete = [r for r in records if _is_complete(r)]
    if limit is not None:
        complete = complete[:limit]
    return complete


async def _fallback_search(
    query: str, per_page: int, offset: int
) -> Tuple[List[Dict], int]:
    keywords = re.sub(r'["\-]', " ", query).split()
    if not keywords:
        return [], 0
    term = f"%{keywords[0]}%"
    try:
        count_row = await db.fetchone(
            "SELECT COUNT(*) FROM logs WHERE record_text LIKE ?", (term,)
        )
        total: int = count_row[0] if count_row else 0
        rows = await db.fetchall(
            "SELECT id, record_text, source_file, created_at FROM logs "
            "WHERE record_text LIKE ? LIMIT ? OFFSET ?",
            (term, per_page, offset),
        )
        return [dict(r) for r in rows], total
    except Exception as e2:
        logger.error("Fallback search failed: %s", e2)
        return [], 0


async def _fallback_search_all(
    query: str, limit: Optional[int]
) -> Tuple[List, int]:
    keywords = re.sub(r'["\-]', " ", query).split()
    if not keywords:
        return [], 0
    term = f"%{keywords[0]}%"
    try:
        count_row = await db.fetchone(
            "SELECT COUNT(*) FROM logs WHERE record_text LIKE ?", (term,)
        )
        total: int = count_row[0] if count_row else 0
        fetch_limit = (limit * 3) if limit is not None else -1
        rows = await db.fetchall(
            "SELECT record_text FROM logs WHERE record_text LIKE ? LIMIT ?",
            (term, fetch_limit),
        )
        return list(rows), total
    except Exception as e:
        logger.error("Fallback all-search failed: %s", e)
        return [], 0
