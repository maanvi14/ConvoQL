"""Column linker: Resolves entities in question to actual schema columns."""
from typing import Dict, Any, List
import re

from db.connection import db_manager
from cache.schema_rag import schema_rag

# Entity synonyms for fuzzy matching
ENTITY_SYNONYMS = {
    # Account names
    "hdfc account": "HDFC",
    "hdfc bank": "HDFC",
    "icici account": "ICICI",
    "icici bank": "ICICI",
    "paytm account": "Paytm",
    "paytm wallet": "Paytm",

    # Category names
    "investment returns": "Investment",
    "returns": "Investment",
    "salary": "Income",
    "freelance": "Side Income",

    # Payment methods
    "upi transactions": "UPI",
    "cash payment": "Cash",
    "card payment": "Card",

    # Table aliases
    "account balance": "accounts",
    "account balances": "accounts",
    "budget limit": "budgets",
    "budget vs actual": "budgets",
}

# Words to strip from entity mentions before matching
STRIP_WORDS = ["account", "transactions", "spending", "expenses", "income", "payment"]

async def column_linker_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Link entities from the question to actual database columns and values."""
    question = state["question"].lower()
    schema = await db_manager.get_schema()

    # Build column registry
    column_registry = {}
    table_registry = {}

    # Also track actual values in tables for better entity linking
    value_registry = {}

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

    # Extract potential entities
    entities = {
        "columns": [],
        "tables": [],
        "values": [],
        "date_references": [],
    }

    # === IMPROVED TABLE DETECTION ===
    # Check for table mentions (exact + synonyms)
    for table_name, actual_name in table_registry.items():
        if table_name in question:
            entities["tables"].append(actual_name)

    # Check synonym mappings
    for synonym, target in ENTITY_SYNONYMS.items():
        if synonym in question:
            if target.lower() in table_registry:
                entities["tables"].append(table_registry[target.lower()])
            else:
                # It's a value, not a table name
                entities["values"].append({
                    "type": "exact_match",
                    "value": target,
                    "column": "account",  # Default column for account names
                })

    # === IMPROVED COLUMN DETECTION ===
    for col_name, refs in column_registry.items():
        if col_name in question:
            entities["columns"].extend(refs)

    # === SMART VALUE EXTRACTION ===
    # Extract account names mentioned in question
    account_names = ["hdfc", "icici", "paytm"]
    for acc in account_names:
        # Match "HDFC" but not "HDFC Bank" (that's the bank_name column)
        pattern = rf'\b{acc}\b'
        if re.search(pattern, question, re.IGNORECASE):
            # Check if it's followed by "account" or "transactions"
            if re.search(rf'\b{acc}\s+(account|transactions|balance)\b', question, re.IGNORECASE):
                entities["values"].append({
                    "type": "account",
                    "value": acc.upper(),
                    "column": "account",
                })

    # Extract merchant names
    merchant_names = ["amazon", "netflix", "uber", "zomato", "swiggy", "flipkart", 
                      "apollo pharmacy", "big bazaar", "dmart", "reliance fresh",
                      "make my trip", "makemytrip", "booking.com", "croma",
                      "apple store", "indian oil", "bharat petroleum", "gold gym",
                      "pvr cinemas", "taj restaurant", "social restaurant"]
    for merchant in merchant_names:
        if merchant in question:
            # Normalize merchant name
            normalized = merchant.title()
            if merchant == "apollo pharmacy":
                normalized = "Apollo Pharmacy"
            elif merchant == "big bazaar":
                normalized = "Big Bazaar"
            elif merchant == "reliance fresh":
                normalized = "Reliance Fresh"
            elif merchant in ["make my trip", "makemytrip"]:
                normalized = "MakeMyTrip"
            elif merchant == "booking.com":
                normalized = "Booking.com"
            elif merchant == "apple store":
                normalized = "Apple Store"
            elif merchant == "indian oil":
                normalized = "Indian Oil"
            elif merchant == "bharat petroleum":
                normalized = "Bharat Petroleum"
            elif merchant == "gold gym":
                normalized = "Gold Gym"
            elif merchant == "pvr cinemas":
                normalized = "PVR Cinemas"
            elif merchant == "taj restaurant":
                normalized = "Taj Restaurant"
            elif merchant == "social restaurant":
                normalized = "Social Restaurant"

            entities["values"].append({
                "type": "merchant",
                "value": normalized,
                "column": "merchant",
            })

    # Extract category names
    category_names = ["groceries", "shopping", "entertainment", "transport", 
                      "food", "health", "fitness", "travel", "utilities",
                      "housing", "income", "side income", "investment", "cash"]
    for cat in category_names:
        # Use word boundary to avoid partial matches
        pattern = rf'\b{re.escape(cat)}\b'
        if re.search(pattern, question, re.IGNORECASE):
            # Don't add if it's part of a larger phrase like "shopping transactions"
            # where we already captured it as a table
            entities["values"].append({
                "type": "category",
                "value": cat.title(),
                "column": "category",
            })

    # ============================================================================
    # FIX: Extract tag values from questions like "tagged with 'subscription'"
    # ============================================================================
    tag_patterns = [
        r'tagged\s+(?:with\s+)?[\'"]([^\'"]+)[\'"]',  # FIXED: single-quoted raw string
        r'tag\s+(?:is\s+)?[\'"]([^\'"]+)[\'"]',       # FIXED: single-quoted raw string
        r'tags?\s+(?:like|containing|with)\s+[\'"]([^\'"]+)[\'"]',  # FIXED
        r'[\'"]([^\'"]+)[\'"]\s+tag',                 # FIXED: single-quoted raw string
    ]
    for pattern in tag_patterns:
        matches = re.findall(pattern, question, re.IGNORECASE)
        for match in matches:
            entities["values"].append({
                "type": "tag",
                "value": match.strip(),
                "column": "tags",
                "operator": "LIKE",  # Signal to generator that this needs LIKE %value%
            })

    # Also catch "tagged with subscription" (no quotes)
    tag_bare_pattern = r'tagged\s+(?:with\s+)?([a-zA-Z_][a-zA-Z0-9_]*)'
    bare_tag_matches = re.findall(tag_bare_pattern, question, re.IGNORECASE)
    for match in bare_tag_matches:
        # Avoid false positives on common words
        if match.lower() not in {"the", "a", "an", "my", "your", "all", "any", "some"}:
            entities["values"].append({
                "type": "tag",
                "value": match.strip(),
                "column": "tags",
                "operator": "LIKE",
            })

    # Date extraction
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
            entities["date_references"].append({
                "type": dtype,
                "match": match if isinstance(match, str) else " ".join(match),
            })

    # Value extraction (amounts)
    amount_pattern = r'\b(?:rs\.?\s*|₹\s*|inr\s*)?(\d+(?:,\d{3})*(?:\.\d{2})?)\b'
    amounts = re.findall(amount_pattern, question, re.IGNORECASE)
    entities["values"].extend([{"type": "amount", "value": a.replace(",", ""), "column": "amount"} for a in amounts])

    # Resolve ambiguities
    resolved = {
        "linked_columns": entities["columns"],
        "linked_tables": list(set(entities["tables"])),
        "linked_values": entities["values"],
        "linked_dates": entities["date_references"],
        "ambiguous": [],
    }

    # Flag ambiguous column references
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
