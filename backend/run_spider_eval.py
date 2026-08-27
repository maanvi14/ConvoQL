import os
import json
import asyncio
import argparse
import subprocess
import sqlite3
from typing import Dict, Any, List

# Setup sys path so we can import from agent and db
import sys
current_file = os.path.abspath(__file__)
backend_dir = os.path.dirname(current_file)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from db.connection import db_manager
from cache.schema_rag import schema_rag
from agent.graph import agent_graph

SPIDER_DIR = os.path.join(backend_dir, "spider_data", "spider")
dev_json_path = os.path.join(SPIDER_DIR, "dev.json")
tables_json_path = os.path.join(SPIDER_DIR, "tables.json")
db_dir_path = os.path.join(SPIDER_DIR, "database")

# Target databases for subset evaluation
TARGET_DBS = ["concert_singer", "pets_1", "car_1"]

def build_initial_state(question: str, dialect: str = "sqlite") -> Dict[str, Any]:
    return {
        "question": question,
        "dialect": dialect,
        "messages": [{"role": "user", "content": question}],
        "intent": None,
        "decomposition": None,
        "schema_context": "",
        "structured_plan": None,
        "few_shot_examples": "",
        "entity_links": None,
        "generated_sql": "",
        "valid": None,
        "error": None,
        "error_classification": None,
        "retry_count": 0,
        "retry_hint": None,
        "result_set_valid": None,
        "result_set_issue": None,
        "sql_result": None,
        "result": None,
        "answer": "",
        "explanation": "",
        "has_chart": False,
        "chart_type": None,
        "chart_title": None,
        "has_table": False,
        "insight": None,
        "follow_ups": [],
        "anomaly": None,
        "trend_analysis": None,
        "narrative": None,
        "execution_time_ms": 0,
        "row_count": 0,
    }

async def run_eval(mode: str):
    if not os.path.exists(dev_json_path):
        print(f"Error: {dev_json_path} not found. Run setup_spider.py/download_spider_gdrive.py first.")
        return

    with open(dev_json_path, "r", encoding="utf-8") as f:
        dev_data = json.load(f)

    if mode == "quick":
        # Filter and group queries by db_id (target DBs only)
        queries_by_db = {}
        for row in dev_data:
            db_id = row["db_id"]
            if db_id in TARGET_DBS:
                if db_id not in queries_by_db:
                    queries_by_db[db_id] = []
                queries_by_db[db_id].append(row)

        eval_queries = []
        for db_id in TARGET_DBS:
            db_queries = queries_by_db.get(db_id, [])
            eval_queries.extend(db_queries[:10])
    elif mode == "sample":
        import random
        random.seed(42)
        eval_queries = random.sample(dev_data, min(100, len(dev_data)))
    else:
        eval_queries = dev_data

    print(f"Running evaluation on {len(eval_queries)} Spider dev-set queries...")

    gold_lines = []
    pred_lines = []
    exec_success = 0
    exec_total = 0

    for idx, item in enumerate(eval_queries, 1):
        db_id = item["db_id"]
        question = item["question"]
        gold_sql = item["query"]

        db_path = os.path.join(db_dir_path, db_id, f"{db_id}.sqlite")
        print(f"[{idx}/{len(eval_queries)}] DB: {db_id} | Question: {question}")

        # 1. Connect to specific SQLite database
        conn_str = f"sqlite+aiosqlite:///{db_path}"
        await db_manager.initialize(conn_str)
        
        # 2. Embed schema in SchemaRAG for linking
        schema = await db_manager.get_schema()
        schema_rag.embed_schema(schema)

        # 3. Build initial state and run graph with 429 rate limit retries
        state = build_initial_state(question, "sqlite")
        
        max_attempts = 5
        base_backoff = 15
        final_state = None
        pred_sql = ""
        
        for attempt in range(max_attempts):
            try:
                # Pace requests to prevent hitting Token limits (sleep 5 seconds between queries)
                if attempt == 0 and idx > 1:
                    await asyncio.sleep(5)
                    
                final_state = await agent_graph.ainvoke(state, config={"recursion_limit": 50})
                pred_sql = final_state.get("generated_sql", "").strip()
                break # Success
            except Exception as e:
                err_str = str(e)
                # Check for rate limit indicators (429, rate_limit, TPM, RPM)
                if any(ind in err_str or ind in repr(e) for ind in ["429", "rate_limit", "Rate limit", "TPM", "RPM"]):
                    backoff = base_backoff * (2 ** attempt)
                    print(f"  Rate limit (429) hit. Retrying in {backoff}s... (Attempt {attempt+1}/{max_attempts})")
                    await asyncio.sleep(backoff)
                else:
                    print(f"  Graph failed with non-rate-limit error: {e}")
                    pred_sql = "SELECT * FROM error_fallback"
                    break
        else:
            print("  Graph failed: Max 429 retry attempts reached.")
            pred_sql = "SELECT * FROM error_fallback"

        if not pred_sql:
            pred_sql = "SELECT * FROM empty_fallback"

        # Replace newlines for evaluation.py compatibility
        pred_sql_single_line = pred_sql.replace("\n", " ").strip()
        gold_sql_single_line = gold_sql.replace("\n", " ").strip()

        print(f"  Gold: {gold_sql_single_line}")
        print(f"  Pred: {pred_sql_single_line}")

        gold_lines.append(f"{gold_sql_single_line}\t{db_id}\n")
        pred_lines.append(f"{pred_sql_single_line}\n")

        # 4. Measure Execution Accuracy
        exec_total += 1
        # Compare prediction vs gold execution on the database
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute(gold_sql)
            gold_res = sorted(cursor.fetchall())
            
            cursor.execute(pred_sql)
            pred_res = sorted(cursor.fetchall())
            
            if gold_res == pred_res:
                exec_success += 1
                print("  Status: EXEC PASS")
            else:
                print("  Status: EXEC FAIL (mismatched result sets)")
            conn.close()
        except Exception as e:
            print(f"  Status: EXEC FAIL (exception: {e})")

    # Write temporary files for evaluation.py
    gold_path = os.path.join(backend_dir, "gold_temp.txt")
    pred_path = os.path.join(backend_dir, "pred_temp.txt")

    with open(gold_path, "w", encoding="utf-8") as f:
        f.writelines(gold_lines)
    with open(pred_path, "w", encoding="utf-8") as f:
        f.writelines(pred_lines)

    print("\n" + "="*50)
    print("Running Official Exact Set Match Evaluation...")
    print("="*50)

    # Call official evaluation.py script
    eval_script_path = os.path.join(SPIDER_DIR, "evaluation.py")
    cmd = [
        "venv\\Scripts\\python.exe",
        eval_script_path,
        "--gold", gold_path,
        "--pred", pred_path,
        "--db", db_dir_path,
        "--table", tables_json_path,
        "--etype", "match"
    ]

    try:
        # Run process
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("Failed to run evaluation.py:")
        print(e.stdout)
        print(e.stderr)

    exec_acc = (exec_success / exec_total) * 100 if exec_total > 0 else 0
    print(f"Execution Accuracy: {exec_success}/{exec_total} ({exec_acc:.2f}%)")

    # Cleanup temp files
    try:
        os.remove(gold_path)
        os.remove(pred_path)
    except:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Run 10 queries per DB (30 total)")
    parser.add_argument("--sample", action="store_true", help="Run a random fixed-seed sample of 100 queries")
    parser.add_argument("--full", action="store_true", help="Run the complete dev set (1034 total)")
    args = parser.parse_args()

    mode = "quick"
    if args.sample:
        mode = "sample"
    elif args.full:
        mode = "full"
        
    asyncio.run(run_eval(mode))
