"""SchemaRAG: Semantic retrieval of relevant tables/columns for a query."""
from typing import Dict, Any, List
import re

class SchemaRAG:
    """Simple keyword + heuristic based schema retrieval."""

    def __init__(self):
        self.tables = []
        self.columns = []
        self._table_index = {}

    def embed_schema(self, schema: Dict[str, Any]):
        """Index schema for retrieval."""
        self.tables = schema.get("tables", [])
        self.columns = []
        self._table_index = {}

        for table in self.tables:
            table_name = table["name"]
            self._table_index[table_name.lower()] = table

            for col in table.get("columns", []):
                self.columns.append({
                    "table": table_name,
                    "column": col["name"],
                    "type": col.get("type", "TEXT"),
                })

    def retrieve_relevant(self, question: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """Retrieve relevant tables based on question keywords."""
        question_lower = question.lower()
        words = set(re.findall(r'[a-z]+', question_lower))

        # DETECTION SIGNALS
        needs_budget = any(w in question_lower for w in [
            "budget", "budgets", "allocated", "over budget", "under budget",
            "budget vs", "budget vs actual", "actual vs budget",
            "compare budget", "compare my budget", "compare the budget",
            "compare spending to budget", "compare with budget",
            "remaining budget", "budget utilization", "budget comparison",
            "budget limit", "budgeted", "overspent", "underspent"
        ])

        needs_accounts = any(w in question_lower for w in [
            "account", "accounts", "balance", "balances", "bank", "bank balance",
            "total balance", "highest balance", "account metadata", "all accounts",
            "hdfc", "icici", "paytm"
        ])

        needs_categories = any(w in question_lower for w in [
            "category color", "category icon", "category description",
            "category metadata", "category info", "category type"
        ])

        simple_transaction = any(w in question_lower for w in [
            "highest", "expense", "spent", "spend", "purchase", "how much",
            "show me", "list", "find", "transactions", "transaction",
            "merchant", "tag", "category", "payment", "date", "amount"
        ])

        scored_tables = []

        for table in self.tables:
            name_lower = table["name"].lower()
            similarity = 0.0
            reason = ""

            # BUDGET QUERIES: Massively boost budgets table
            if needs_budget:
                if "budget" in name_lower:
                    similarity += 2.0
                    reason = "budget keyword match (+2.0)"
                elif "transaction" in name_lower:
                    similarity += 0.3
                    reason = "transaction table for budget join (+0.3)"
                else:
                    similarity = -999
                    reason = "excluded for budget query"

            # ACCOUNT QUERIES: Boost accounts table
            elif needs_accounts:
                if "account" in name_lower:
                    similarity += 1.5
                    reason = "account keyword match (+1.5)"
                elif "transaction" in name_lower:
                    similarity += 0.3
                    reason = "transaction table for account join (+0.3)"
                else:
                    similarity = -999
                    reason = "excluded for account query"

            # CATEGORY METADATA: Boost categories table
            elif needs_categories:
                if "categor" in name_lower:
                    similarity += 1.5
                    reason = "category keyword match (+1.5)"
                elif "transaction" in name_lower:
                    similarity += 0.3
                    reason = "transaction table for category join (+0.3)"
                else:
                    similarity = -999
                    reason = "excluded for category metadata query"

            # SIMPLE TRANSACTION QUERIES
            elif simple_transaction and not needs_budget and not needs_accounts:
                if "transaction" in name_lower:
                    similarity += 0.5
                    reason = "transaction keyword match (+0.5)"
                elif "budget" in name_lower or "account" in name_lower or "categor" in name_lower:
                    similarity = -999
                    reason = "excluded for simple transaction query"

            # Default scoring for unmatched cases
            if similarity == 0.0:
                for col in table.get("columns", []):
                    col_name = col["name"].lower()
                    if col_name in question_lower:
                        similarity += 0.3
                        reason = f"column '{col_name}' match"

            scored_tables.append({
                "name": table["name"],
                "score": similarity,
                "reason": reason,
                "table": table,
            })

        # Sort by score descending
        scored_tables.sort(key=lambda x: x["score"], reverse=True)

        # For budget queries, ensure budgets is ALWAYS included
        if needs_budget:
            budget_in_results = any(t["name"].lower() == "budgets" for t in scored_tables[:top_k])
            if not budget_in_results:
                for t in scored_tables:
                    if t["name"].lower() == "budgets":
                        scored_tables.remove(t)
                        scored_tables.insert(0, t)
                        print(f"[SchemaRAG] FORCED budgets table into top results")
                        break

        return scored_tables[:top_k]

    def build_context(self, full_schema: Dict[str, Any], relevant: List[Dict[str, Any]]) -> str:
        """Build schema context string from relevant tables."""
        lines = []
        for rel in relevant:
            table = rel["table"]
            lines.append(f"Table: {table['name']}")
            for col in table.get("columns", []):
                lines.append(f"  - {col['name']}: {col.get('type', 'TEXT')}")
            lines.append("")
        return "\n".join(lines)

    def get_stats(self) -> Dict[str, int]:
        return {
            "tables_indexed": len(self.tables),
            "columns_indexed": len(self.columns),
        }

# Global instance
schema_rag = SchemaRAG()
