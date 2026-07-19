"""Column linker: Resolves entities in question to actual schema columns.

SCHEMA/DATA-DRIVEN REWRITE
---------------------------
The previous version hardcoded per-dataset value lists: specific bank names
("hdfc", "icici", "paytm"), specific merchants ("zomato", "swiggy", ...),
specific categories, and a static ENTITY_SYNONYMS dict mapping phrases like
"hdfc account" -> "HDFC". None of that generalizes beyond the one dataset it
was written against — a new deployment with different banks/merchants/
categories would silently link nothing.

This version instead asks the *live database* what values actually exist in
account/category/merchant/payment_method-shaped columns (found dynamically
from the schema, not by hardcoded table/column name guesses beyond the role
mapping below) and matches the question against those real values. Table
references are still detected from schema table names, plus a fuzzy fallback
via schema_rag for phrasing that doesn't literally contain the table name.
"""
from typing import Dict, Any, List
import re
import time

from db.connection import db_manager
from cache.schema_rag import schema_rag

# Column *roles* we know how to link against real data. This maps a semantic
# role to the column name(s) that typically hold it — NOT to any specific
# value. The actual values (bank names, merchants, categories, etc.) are
# always read live from the database, never hardcoded here.
ENTITY_COLUMN_ROLES = {
    "account": ["account", "account_name"],
    "category": ["category"],
    "merchant": ["merchant"],
    "payment_method": ["payment_method"],
}

# Generic phrase suffixes used to detect "<value> account/bank/wallet/card"
# style mentions so we can strip the suffix and match the bare value against
# real account values, without hardcoding which accounts exist.
ACCOUNT_PHRASE_SUFFIXES = ["account", "bank", "wallet", "card"]

# Generic phrase suffixes used to detect "<value> table" style mentions,
# e.g. "budget limit" / "account balance" -> used only as a fuzzy-match hint,
# not a fixed table mapping.
TABLE_PHRASE_HINTS = ["balance", "balances", "limit", "vs actual", "utilization"]

# Words to strip from entity mentions before matching
STRIP_WORDS = ["account", "transactions", "spending", "expenses", "income", "payment"]

# In-memory cache of distinct column values, refreshed periodically so we
# aren't hitting the DB on every single question.
_VALUE_CACHE: Dict[str, Dict[str, Any]] = {}
_VALUE_CACHE_TTL_SECONDS = 300
_MAX_DISTINCT_VALUES = 500


async def _get_distinct_values(table: str, column: str) -> List[str]:
    """Fetch (and cache) the distinct string values actually present in a
    column. This is what makes entity linking schema/data-driven: whatever
    accounts, categories, merchants, or payment methods actually exist in
    THIS deployment's data are what gets linked — not a fixed guess list."""
    cache_key = f"{table}.{column}".lower()
    cached = _VALUE_CACHE.get(cache_key)
    now = time.monotonic()
    if cached and (now - cached["ts"]) < _VALUE_CACHE_TTL_SECONDS:
        return cached["values"]

    values: List[str] = cached["values"] if cached else []
    try:
        result = await db_manager.execute_readonly(
            f"SELECT DISTINCT {column} FROM {table} "
            f"WHERE {column} IS NOT NULL LIMIT {_MAX_DISTINCT_VALUES}"
        )
        fetched = []
        for row in result.get("rows", []):
            v = row.get(column)
            if isinstance(v, str) and v.strip():
                fetched.append(v.strip())
        values = fetched
    except Exception as e:
        print(f"[ColumnLinker] Could not fetch distinct values for {cache_key}: {e}")

    _VALUE_CACHE[cache_key] = {"values": values, "ts": now}
    return values


def _find_value_matches(question: str, values: List[str]) -> List[str]:
    """Return distinct values actually mentioned in the question, matched
    case-insensitively on word boundaries. Longest values are checked first
    so e.g. 'Apollo Pharmacy' matches whole rather than partially."""
    matches = []
    for value in sorted(set(values), key=len, reverse=True):
        pattern = r'\b' + re.escape(value.lower()) + r'\b'
        if re.search(pattern, question):
            matches.append(value)
    return matches


def _extract_account_phrase_candidates(question: str) -> List[str]:
    """Find '<word(s)> account/bank/wallet/card' style mentions and return the
    bare candidate strings (e.g. 'hdfc' from 'hdfc account') so they can be
    matched against real account values instead of a hardcoded mapping."""
    candidates = []
    for suffix in ACCOUNT_PHRASE_SUFFIXES:
        for m in re.finditer(rf'\b([a-zA-Z][a-zA-Z ]{{1,20}}?)\s+{suffix}s?\b', question):
            candidate = m.group(1).strip()
            if candidate and candidate not in STRIP_WORDS:
                candidates.append(candidate)
    return candidates


async def column_linker_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Link entities from the question to actual database columns and values."""
    question = state["question"].lower()
    schema = await db_manager.get_schema()

    # Build column registry
    column_registry = {}
    table_registry = {}

    for table in schema.get("tables", []):
        table_name = table["name"].lower()
        table_registry[table_name] = table["name"]

        for col in table.get("columns", []):
            col_name = col["name"].lower()
            if col_name not in column_registry:
                column_registry[col_name] = []
            column_registry[col_name].append({
                "table": table["name"],
                "column": col["name"],
                "type": col.get("type", "TEXT"),
            })

    entities = {
        "columns": [],
        "tables": [],
        "values": [],
        "date_references": [],
    }

    # === TABLE DETECTION (schema-driven, with fuzzy fallback) ===
    for table_name, actual_name in table_registry.items():
        if table_name in question:
            entities["tables"].append(actual_name)

    # Fuzzy fallback: phrases like "budget limit" or "account balance" don't
    # literally contain a table name. Use schema_rag's relevance ranking
    # (already schema-driven) instead of a hardcoded phrase->table dict.
    if not entities["tables"] and any(hint in question for hint in TABLE_PHRASE_HINTS):
        try:
            relevant = schema_rag.retrieve_relevant(state["question"], top_k=1)
            if relevant and relevant[0].get("score", 0) > 0.3:
                entities["tables"].append(relevant[0]["name"])
        except Exception as e:
            print(f"[ColumnLinker] schema_rag fallback failed: {e}")

    # === COLUMN DETECTION ===
    for col_name, refs in column_registry.items():
        if col_name in question:
            entities["columns"].extend(refs)

    # === DATA-DRIVEN VALUE EXTRACTION ===
    # Instead of hardcoded value lists per role, walk the live schema for
    # columns matching a known role and match the question against whatever
    # values actually exist in the database for that column.
    for table in schema.get("tables", []):
        table_name = table["name"]
        for col in table.get("columns", []):
            col_name_lower = col["name"].lower()
            role = None
            for r, names in ENTITY_COLUMN_ROLES.items():
                if col_name_lower in names:
                    role = r
                    break
            if role is None:
                continue

            values = await _get_distinct_values(table_name, col["name"])
            if not values:
                continue

            matched = _find_value_matches(question, values)

            # For accounts specifically, also try "<x> account/bank/wallet"
            # style phrasing against the same real value list, in case the
            # exact stored value differs slightly in case/spacing from what
            # the user typed (e.g. user says "hdfc", stored value is "HDFC").
            if role == "account" and not matched:
                for candidate in _extract_account_phrase_candidates(question):
                    for v in values:
                        if candidate.lower() == v.lower() or candidate.lower() in v.lower():
                            matched.append(v)

            for v in matched:
                entities["values"].append({
                    "type": role,
                    "value": v,
                    "column": col["name"],
                })

    # ============================================================================
    # Tag value extraction from questions like "tagged with 'subscription'"
    # Structural parsing, not dataset-specific — kept as-is.
    # ============================================================================
    tag_patterns = [
        r"tagged\s+(?:with\s+)?['\"]([^'\"]+)['\"]",
        r"tag\s+(?:is\s+)?['\"]([^'\"]+)['\"]",
        r"tags?\s+(?:like|containing|with)\s+['\"]([^'\"]+)['\"]",
        r"['\"]([^'\"]+)['\"]\s+tag",
    ]
    for pattern in tag_patterns:
        matches = re.findall(pattern, question, re.IGNORECASE)
        for match in matches:
            entities["values"].append({
                "type": "tag",
                "value": match.strip(),
                "column": "tags",
                "operator": "LIKE",
            })

    # Also catch "tagged with subscription" (no quotes)
    tag_bare_pattern = r"tagged\s+with\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    bare_tag_matches = re.findall(tag_bare_pattern, question, re.IGNORECASE)
    for match in bare_tag_matches:
        if match.lower() not in {"the", "a", "an", "my", "your", "all", "any", "some", "with"}:
            entities["values"].append({
                "type": "tag",
                "value": match.strip(),
                "column": "tags",
                "operator": "LIKE",
            })

    # Date extraction — structural, not dataset-specific
    month_names = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }

    date_patterns = [
        (r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})\b', 'month_year'),
        (r'\b(\d{4})-(\d{2})\b', 'year_month'),
        (r'\bthis month\b', 'this_month'),
        (r'\blast month\b', 'last_month'),
        (r'\bthis year\b', 'this_year'),
        (r'\blast year\b', 'last_year'),
    ]

    for pattern, dtype in date_patterns:
        matches = re.findall(pattern, question, re.IGNORECASE)
        for match in matches:
            if dtype == 'month_year':
                month_name, year = match
                month_num = month_names.get(month_name.lower(), '01')
                formatted_date = f"{year}-{month_num}"
                entities["date_references"].append({
                    "type": dtype,
                    "match": match if isinstance(match, str) else " ".join(match),
                    "formatted": formatted_date,
                    "sql_filter": f"strftime('%Y-%m', date) = '{formatted_date}'"
                })
            elif dtype == 'year_month':
                year, month = match
                formatted_date = f"{year}-{month}"
                entities["date_references"].append({
                    "type": dtype,
                    "match": match if isinstance(match, str) else " ".join(match),
                    "formatted": formatted_date,
                    "sql_filter": f"strftime('%Y-%m', date) = '{formatted_date}'"
                })
            else:
                entities["date_references"].append({
                    "type": dtype,
                    "match": match if isinstance(match, str) else " ".join(match),
                })

    # Amount extraction — structural, not dataset-specific
    amount_pattern = r'\b((?:rs\.?\s*|₹\s*|inr\s*)?\d+(?:,\d{3})*(?:\.\d{2})?)\b'
    for full_match in re.finditer(amount_pattern, question, re.IGNORECASE):
        full_token = full_match.group(1)
        has_currency_prefix = bool(re.match(r'^(?:rs\.?\s*|₹\s*|inr\s*)', full_token, re.IGNORECASE))
        digits_only = re.sub(r'^(?:rs\.?\s*|₹\s*|inr\s*)', '', full_token, flags=re.IGNORECASE).strip()
        clean = digits_only.replace(",", "")
        try:
            val = float(clean)
            if not has_currency_prefix and re.fullmatch(r'(19|20)\d{2}', clean):
                print(f"[ColumnLinker] Skipping year-like number '{clean}' (not a currency amount)")
                continue
            if '.' in digits_only or val >= 100 or val <= 0:
                entities["values"].append({"type": "amount", "value": clean, "column": "amount"})
            else:
                print(f"[ColumnLinker] Skipping small number '{clean}' (likely LIMIT value, not amount)")
        except ValueError:
            pass

    # Resolve ambiguities
    resolved = {
        "linked_columns": entities["columns"],
        "linked_tables": list(set(entities["tables"])),
        "linked_values": entities["values"],
        "linked_dates": entities["date_references"],
        "ambiguous": [],
    }

    seen_cols = {}
    for col_ref in entities["columns"]:
        col_name = col_ref["column"].lower()
        if col_name in seen_cols:
            if seen_cols[col_name]["table"] != col_ref["table"]:
                resolved["ambiguous"].append({
                    "column": col_ref["column"],
                    "tables": [seen_cols[col_name]["table"], col_ref["table"]],
                })
        else:
            seen_cols[col_name] = col_ref

    return {
        **state,
        "entity_links": resolved,
    }
