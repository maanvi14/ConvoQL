# ConvoQL Pipeline Architecture Report & Upgrade Proposal

This document provides a detailed architectural audit of the current ConvoQL LangGraph pipeline, highlights the structural limitations causing accuracy bottlenecks, and outlines the proposed target architecture to upgrade the system to a state-of-the-art NL-to-SQL platform.

---

## 1. Node-by-Node Pipeline Audit

The active ConvoQL pipeline consists of **12 nodes** wired sequentially in a LangGraph workflow (with a retry loop). Below is the analysis of each node:

### Layer 1: Query Understanding

#### 1. `intent_classifier`
* **What it does**: Classifies the user's natural language question into a primary intent (e.g., aggregation, ranking, trend) and extracts query filters (type, time, entities). Uses a LLM call followed by a deterministic post-processing function `_enforce_type_filter`.
* **What it assumes**: Assumes a fixed financial domain schema with tables `budgets`, `accounts`, `categories`, `transactions` and columns like `amount` and `type`.
* **Where it's brittle**: 
  * The `_enforce_type_filter` relies on hardcoded keyword lists (`DEBIT_SIGNALS`, `CREDIT_SIGNALS`, `JOIN_SIGNALS`).
  * Domain lock-in: If the query is run against a general database (e.g., Spider), these rules will incorrectly trigger or suppress filters (e.g., filtering out columns containing "budget" or "account" on non-financial tables).

#### 2. `query_decomposer`
* **What it does**: LLM call to classify if the question is compound (e.g., containing "and", "vs", "compare") and splits it into independent sub-queries.
* **What it assumes**: Assumes compound queries can be split cleanly.
* **Where it's brittle**:
  * **Dead Code**: While it writes the sub-queries to the state, **they are completely ignored**. The graph control flow is linear and proceeds directly to generate a single SQL query for the main question. It is non-functional.

---

### Layer 2: Schema Retrieval

#### 3. `structured_planner`
* **What it does**: LLM call that outputs a structured JSON plan (tables, joins, select columns, filters, group by, order by, limit) based on SchemaRAG and sample data.
* **What it assumes**: Assumes the LLM can generate a correct JSON query plan that matches the database dialect.
* **Where it's brittle**:
  * The planner is forced to output a complex JSON structure instead of raw SQL, which is harder for the LLM to write correctly.
  * Massive hardcoded sanitizations are applied after the LLM call (e.g., forcing empty `group_by` for listings, removing categories joins, adding type filters). These are tightly coupled to the `finance.db` schema and will break on generic schemas.
  * It forces the LLM to write dialect-specific expressions (like date calculations) inside the JSON plan, which defeats the abstraction of a "plan."

#### 4. `dynamic_few_shot`
* **What it does**: Selects few-shot examples from a hardcoded bank (`EXAMPLE_BANK`) matching the detected intent.
* **What it assumes**: Assumes that showing examples helps query construction.
* **Where it's brittle**:
  * **Dead Code**: The selected examples are saved to the state under `few_shot_examples` but **never injected** into the structured planner's LLM prompt. It has zero effect on generation.

---

### Layer 3: Generation

#### 5. `column_linker`
* **What it does**: Fuzzy matches words in the query against synonyms to resolve them to specific columns and values (accounts, merchants, categories, payment methods, tags, dates, amounts).
* **What it assumes**: Assumes the values in the query belong to a predefined list.
* **Where it's brittle**:
  * **Extremely Hardcoded**: It uses a static list of names (e.g., "hdfc", "apollo pharmacy", "groceries"). Any value or entity not in this list is ignored, meaning no filter will be generated for it. This makes it completely incompatible with new databases (like the Spider dev set).

#### 6. `sql_skeleton`
* **What it does**: A deterministic python builder that joins the `structured_plan` and `entity_links` into a SQL string, running post-processing regex fixes.
* **What it assumes**: Assumes the structured plan and linked entities are aligned.
* **Where it's brittle**:
  * Prone to syntax errors due to string formatting.
  * **Fragile Regex Patching**: Heuristics like `_enforce_abs_for_debits` rely on exact SQL substrings (like `SUM(amount)`). If the LLM uses a column alias (e.g., `amount AS abs_amount` and `ORDER BY abs_amount DESC`), the regex fails, producing incorrect queries that fail to apply `ABS()` to negative debits.

---

### Layer 4: Validation & Retry

#### 7. `validator`
* **What it does**: Validates SQL for forbidden keywords, schema correctness (checking if tables/columns exist), syntax (`EXPLAIN`), and does a dry-run execution.
* **What it assumes**: Assumes a connection to the database.
* **Where it's brittle**:
  * Good deterministic checks, but errors are routed to a broken retry loop.

#### 8. `typed_error_classifier`
* **What it does**: Classifies database errors and sets a `retry_hint`.
* **What it assumes**: Assumes the generator will use this hint to correct the query.
* **Where it's brittle**:
  * **Dummy Retry Loop**: The retry edge in `graph.py` loops back to `sql_skeleton` (the deterministic python compiler), **bypassing the LLM planner**. Since `sql_skeleton` is deterministic and receives the identical inputs, it rebuilds the exact same failing query, causing an infinite loop (or hitting the max retry limit of 3).

#### 9. `result_set_validator`
* **What it does**: Checks the query results for semantic anomalies (e.g. 0-row results, wrong row counts).
* **What it assumes**: Assumes the query has already executed and populated the results.
* **Where it's brittle**:
  * **Execution Order Bug**: It is placed *before* the SQL is executed! The SQL is executed in `enhanced_synthesizer`, which runs *after* this node. Consequently, `sql_result` is always `None` when this node runs, making it a complete no-op that always returns `result_set_valid = True`.

---

### Layer 5: Output

#### 10. `enhanced_synthesizer`
* **What it does**: Executes the SQL query, runs anomaly detection, and calls the LLM to generate a plain-English narrative response.
* **What it assumes**: Assumes the query is valid (handles exceptions with a simple fallback answer).
* **Where it's brittle**:
  * Running execution here is too late for the retry loop. If execution fails here, the agent has no way to correct it.

#### 11. `trend_analyzer`
* **What it does**: Computes simple period-over-period statistics for time-series.
* **Where it's brittle**: Relies on brittle column name keyword matching.

#### 12. `narrative_generator`
* **What it does**: Generates a summary narrative.
* **Where it's brittle**: Similar column name keyword matches.

---

## 2. Core Architectural Limitations (Why Accuracy is Bottlenecked)

1. **No-op Self-Correction**: The retry loop bypasses the LLM. Syntax/schema errors are never fed back to the planner, meaning the agent cannot learn from database errors.
2. **Hardcoded Entity Recognition**: The platform cannot generalise to other databases because it relies on regex matching for a hardcoded list of merchants, categories, and banks.
3. **Execution Order Defect**: Semantic validation of the result set runs before the query is even executed, completely disabling semantic feedback.
4. **Dead Code**: Query decomposition and dynamic few-shot selection are defined in the graph but never used, increasing context overhead with no benefit.
5. **Fragile Regex Patches**: Enforcing domain rules (like `ABS(amount)`) with regex on raw SQL strings is easily bypassed by aliasing, leading to invalid query logic.

---

## 3. Proposed Target Architecture

We propose a full upgrade towards a grounded, execution-guided, self-correcting NL-to-SQL architecture that is database-agnostic:

```
[User Question]
       │
       ▼
1. Query Understanding ──► [Decomposition (Functional)]
       │
       ▼
2. Schema Linking (Grounded & Dynamic RAG)
       │
       ▼
3. Candidate Generation (Generate K SQL queries via LLM)
       │
       ▼
4. Execution-Guided Selection (Execute against Sandboxed DB & filter)
       │
       ▼
5. Self-Correction Loop (Feed SQL/Semantic errors back to LLM Generator)
       │
       ▼
6. Validation Layer (Deterministic security & syntax check)
       │
       ▼
7. Output Synthesis (Narrative + Charts)
```

### Core Design Principles
* **LLM-Driven SQL Generation**: Replace the structured JSON plan + deterministic string builder with direct, LLM-driven SQL generation grounded by schema-linking.
* **Database Agnostic Schema Linking**: Implement similarity-based matching (using fuzzy matching and vector embeddings if needed) to map query terms to table/column names, regardless of the database schema.
* **Execution Guidance**: Run generated queries against the target DB during selection, discarding error-prone candidates and selecting the best match.
* **True Self-Correction**: Loop execution/semantic errors directly back to the LLM query generator with explicit error contexts for targeted correction.
