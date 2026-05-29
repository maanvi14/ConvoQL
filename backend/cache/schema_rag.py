"""Schema-Aware RAG: Embeds schema and retrieves relevant tables for each query."""
import numpy as np
from typing import List, Dict, Any

# Try to use sentence-transformers, fallback to simple approach
try:
    from sentence_transformers import SentenceTransformer
    HAS_SBERT = True
except ImportError:
    HAS_SBERT = False

class SchemaRAG:
    def __init__(self):
        self.embeddings = {}
        self.schema_chunks = {}
        self.column_index = {}
        self.model = None

        if HAS_SBERT:
            try:
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
                print("SchemaRAG: Using sentence-transformers")
            except Exception as e:
                print(f"SchemaRAG: Could not load model: {e}")
                self.model = None
        else:
            print("SchemaRAG: sentence-transformers not installed, using keyword fallback")

    def embed_schema(self, schema: Dict[str, Any]):
        self.embeddings = {}
        self.schema_chunks = {}
        self.column_index = {}

        for table in schema.get("tables", []):
            table_desc = f"Table {table['name']} with {table.get('row_count', 0)} rows. "
            col_descriptions = []
            for col in table.get("columns", []):
                col_text = f"{col['name']} ({col['type']})"
                if col.get('example'):
                    col_text += f" example: {col['example']}"
                col_descriptions.append(col_text)
                self.column_index[col['name'].lower()] = table['name']

            table_desc += ", ".join(col_descriptions)

            name_lower = table['name'].lower()
            if "transaction" in name_lower:
                table_desc += ". PRIMARY DATA TABLE. Contains all individual financial transactions with: date, description, amount (negative=debit/expense, positive=credit/income), type ('debit'/'credit'), category, account, merchant, payment_method, tags. This table ALREADY contains category names and account names — no JOIN needed for simple queries."
            elif "budget" in name_lower:
                table_desc += ". SECONDARY TABLE. Only needed for budget-vs-actual comparisons. Contains monthly budget allocations per category with allocated and spent amounts."
            elif "category" in name_lower:
                table_desc += ". REFERENCE TABLE. Only needed if asking about category metadata (type, color, icon, budget_limit). NOT needed for spending by category — that info is already in transactions table."
            elif "account" in name_lower:
                table_desc += ". REFERENCE TABLE. Only needed if asking about account metadata (bank_name, balance, currency, is_primary). NOT needed for transactions from an account — that info is already in transactions table."

            self.schema_chunks[table['name']] = table_desc

            if self.model:
                self.embeddings[table['name']] = self.model.encode(table_desc)
            else:
                self.embeddings[table['name']] = table_desc.lower()

    def retrieve_relevant(self, question: str, top_k: int = 3) -> List[Dict[str, Any]]:
        question_lower = question.lower()

        mentioned_tables = set()
        for col_name, table_name in self.column_index.items():
            if col_name in question_lower:
                mentioned_tables.add(table_name)

        # Detect query intent
        needs_budget = any(w in question_lower for w in ["budget", "allocated", "over budget", "under budget", "budget vs", "remaining budget"])
        needs_account_meta = any(w in question_lower for w in ["bank name", "account balance", "total balance", "primary account", "currency", "all accounts"])
        needs_category_meta = any(w in question_lower for w in ["category type", "category color", "category icon", "all categories", "category metadata"])

        # Simple transaction keywords — these should ONLY use transactions table
        simple_transaction = any(w in question_lower for w in [
            "highest", "lowest", "most", "biggest", "largest", "top", "maximum", "minimum",
            "expense", "spent", "spend", "purchase", "bought", "transaction",
            "how much", "what did", "show me", "list", "average", "total", "sum",
            "last month", "this month", "january", "february", "march", "april", "may", "june",
            "ever", "all time", "daily", "weekly", "yearly"
        ])

        if self.model and self.embeddings:
            question_vec = self.model.encode(question)

            scores = {}
            for table_name, emb in self.embeddings.items():
                similarity = np.dot(question_vec, emb) / (
                    np.linalg.norm(question_vec) * np.linalg.norm(emb)
                )

                if table_name in mentioned_tables:
                    similarity += 0.4

                name_lower = table_name.lower()

                # HARD EXCLUSION RULES
                if simple_transaction and not needs_budget and not needs_account_meta and not needs_category_meta:
                    # For simple transaction questions, ONLY transactions table matters
                    if "transaction" in name_lower:
                        similarity += 0.5  # Boost transactions
                    else:
                        similarity = -999  # HARD EXCLUDE non-transaction tables

                if needs_budget:
                    if "budget" in name_lower:
                        similarity += 0.4
                    if "transaction" in name_lower:
                        similarity += 0.2

                if needs_account_meta:
                    if "account" in name_lower:
                        similarity += 0.4

                if needs_category_meta:
                    if "category" in name_lower:
                        similarity += 0.4

                scores[table_name] = similarity

            sorted_tables = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            # Filter out excluded tables
            sorted_tables = [(name, score) for name, score in sorted_tables if score > -100]

            return [
                {"name": name, "score": float(score), "reason": self._get_reason(name, question)}
                for name, score in sorted_tables[:top_k]
            ]
        else:
            scores = {}
            for table_name, desc in self.schema_chunks.items():
                score = sum(1 for word in question_lower.split() if word in desc)
                if table_name in mentioned_tables:
                    score += 5

                name_lower = table_name.lower()
                if simple_transaction and not needs_budget:
                    if "transaction" not in name_lower:
                        score = -999

                scores[table_name] = score

            sorted_tables = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            sorted_tables = [(name, score) for name, score in sorted_tables if score > -100]

            return [
                {"name": name, "score": score, "reason": self._get_reason(name, question)}
                for name, score in sorted_tables[:top_k]
            ]

    def _get_reason(self, table_name: str, question: str) -> str:
        question_lower = question.lower()
        reasons = []
        name_lower = table_name.lower()

        if "transaction" in name_lower:
            reasons.append("primary data table for transactions")
        if "budget" in name_lower and "budget" in question_lower:
            reasons.append("contains budget allocations")
        if "account" in name_lower and any(w in question_lower for w in ["account", "balance", "bank"]):
            reasons.append("contains account metadata")
        if "category" in name_lower and any(w in question_lower for w in ["category type", "category color", "category icon"]):
            reasons.append("contains category metadata")

        return ", ".join(reasons) if reasons else "schema match"

    def build_context(self, schema: Dict[str, Any], relevant_tables: List[Dict]) -> str:
        full_tables = {t['name']: t for t in schema.get("tables", [])}

        context_parts = []
        for rel in relevant_tables:
            table = full_tables.get(rel['name'])
            if not table:
                continue

            lines = [f"Table: {table['name']} ({table.get('row_count', 0)} rows)"]
            for col in table.get('columns', []):
                col_line = f"  - {col['name']} ({col['type']})"
                if col.get('example'):
                    col_line += f" e.g. '{col['example']}'"
                lines.append(col_line)

            context_parts.append("\n".join(lines))

        other_tables = [t for t in schema.get("tables", []) 
                       if t['name'] not in [r['name'] for r in relevant_tables]]
        if other_tables:
            other_names = ", ".join([t['name'] for t in other_tables])
            context_parts.append(f"\nOther available tables if needed: {other_names}")

        return "\n\n".join(context_parts)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "tables_indexed": len(self.embeddings),
            "columns_indexed": len(self.column_index),
            "model_loaded": self.model is not None,
        }

schema_rag = SchemaRAG()
