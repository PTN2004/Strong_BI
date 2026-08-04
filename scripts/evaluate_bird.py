import sys
import os
import argparse
import json
import time
import sqlite3
import logging
import asyncio
from typing import List, Dict, Any, Tuple

# Add root folder to sys.path to resolve api imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("BIRD_Evaluator")

from api.loaders.sqlite_loader import SQLiteLoader
from api.agents import AnalysisAgent
from api.agents.healer_agent import HealerAgent
from api.core.schema_loader import load_database_sync
from api.core.text2sql import run_query, ChatRequest
from api.graph_db import GraphDatabaseFactory
from api.retriever import Retriever

def get_sqlite_schema_as_tables(db_path: str) -> List[List[Any]]:
    """Đọc trực tiếp SQLite schema và chuyển đổi thành cấu trúc TableInfo mà AnalysisAgent mong đợi."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Sử dụng các hàm trích xuất thông tin có sẵn trong SQLiteLoader
    entities = SQLiteLoader.extract_tables_info(cursor)
    relationships = SQLiteLoader.extract_relationships(cursor)
    
    cursor.close()
    conn.close()
    
    tables = []
    for table_name, table_info in entities.items():
        cols = []
        for col_name, col_info in table_info["columns"].items():
            cols.append({
                "columnName": col_name,
                "description": col_info.get("description", ""),
                "dataType": col_info.get("type", "unknown"),
                "keyType": col_info.get("key", ""),
                "nullable": col_info.get("null", True)
            })
            
        # Tìm các khoá ngoại liên quan đến bảng này
        fks = []
        for rel_name, rels in relationships.items():
            for rel in rels:
                if rel["from"] == table_name:
                    fks.append(f"{rel['source_column']} -> {rel['to']}.{rel['target_column']}")
                    
        fks_str = "Foreign keys: " + ", ".join(fks) if fks else "Foreign keys: None"
        
        tables.append([
            table_name,
            table_info.get("description", ""),
            fks_str,
            cols
        ])
        
    return tables

def execute_sql(db_path: str, sql: str) -> Tuple[bool, Any, Any]:
    """Thực thi câu lệnh SQL trên tệp SQLite và trả về kết quả đã chuẩn hoá."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        # Set timeout 5s để tránh câu lệnh bị treo hoặc quá chậm
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.execute(sql)
        results = cursor.fetchall()
        
        # Chuẩn hoá dữ liệu kết quả để so sánh (convert tất cả về string và sort)
        normalized = []
        for row in results:
            normalized.append(tuple(str(val) for val in row))
        normalized.sort()
        
        return True, normalized, None
    except Exception as e:
        return False, None, str(e)
    finally:
        cursor.close()
        conn.close()

def evaluate_sql_match(db_path: str, gold_sql: str, gen_sql: str) -> Tuple[bool, str]:
    """So sánh kết quả thực thi của Gold SQL và Generated SQL."""
    # 1. Chạy câu Gold SQL trước làm chuẩn
    gold_ok, gold_res, gold_err = execute_sql(db_path, gold_sql)
    if not gold_ok:
        return False, f"Gold SQL execution failed: {gold_err}"
        
    # 2. Chạy câu Generated SQL của AI
    gen_ok, gen_res, gen_err = execute_sql(db_path, gen_sql)
    if not gen_ok:
        return False, f"Generated SQL execution failed: {gen_err}"
        
    # 3. So sánh
    if gold_res == gen_res:
        return True, "Match"
    else:
        return False, f"Mismatch. Gold count: {len(gold_res)}, Gen count: {len(gen_res)}"

async def execute_and_heal_sql(db_path: str, db_description: str, question: str, initial_sql: str) -> str:
    """Kiểm tra và tự động sửa lỗi SQL bằng HealerAgent nếu SQL ban đầu thực thi thất bại."""
    ok, _, err = execute_sql(db_path, initial_sql)
    if ok:
        return initial_sql
        
    logger.info(f"SQL execution failed. Attempting to heal: {err}")
    healer = HealerAgent(max_healing_attempts=3)
    
    def _run_sql(sql: str):
        ok_heal, res_heal, err_heal = execute_sql(db_path, sql)
        if not ok_heal:
            raise Exception(err_heal)
        return res_heal
        
    loop = asyncio.get_running_loop()
    healing_result = await loop.run_in_executor(
        None,
        lambda: healer.heal_and_execute(
            initial_sql=initial_sql,
            initial_error=str(err),
            execute_sql_func=_run_sql,
            db_description=db_description,
            question=question,
            database_type="sqlite",
        )
    )
    
    if healing_result.get("success"):
        logger.info(f"Healed successfully after {healing_result.get('attempts')} attempts.")
        return healing_result["sql_query"]
    else:
        logger.warning(f"Failed to heal SQL. Final error: {healing_result.get('final_error')}")
        return healing_result["sql_query"]

async def evaluate_schema_only(db_path: str, question: str) -> str:
    """Tạo SQL bằng cách nạp trực tiếp toàn bộ schema vào AnalysisAgent (Bỏ qua Graph DB)."""
    tables = get_sqlite_schema_as_tables(db_path)
    
    agent_an = AnalysisAgent(
        queries_history=[question],
        result_history=[],
    )
    
    # Thực hiện gọi LLM để phân tích & sinh SQL
    loop = asyncio.get_event_loop()
    answer_an = await loop.run_in_executor(
        None,
        lambda: agent_an.get_analysis(
            user_query=question,
            tables=tables,
            db_description="BIRD SQLite Evaluation",
            instructions="",
            memory_context=None,
            db_type="sqlite",
            user_rules_spec=None
        )
    )
    
    generated_sql = answer_an.get("sql_query", "")
    if generated_sql:
        generated_sql = await execute_and_heal_sql(db_path, "BIRD SQLite Evaluation", question, generated_sql)
        
    return generated_sql

async def evaluate_e2e(db_path: str, db_id: str, question: str, existing_graphs: set) -> str:
    """Đăng ký CSDL vào Graph DB (FalkorDB/Neo4j) sau đó chạy qua Pipeline tìm kiếm thực tế."""
    user_id = "bird_eval"
    sqlite_url = f"sqlite:///{os.path.abspath(db_path)}"
    graph_name = f"{user_id}_{db_id}"
    
    # 1. Nạp cơ sở dữ liệu đồng bộ (chỉ nạp nếu chưa tồn tại trong GraphDB)
    if graph_name not in existing_graphs:
        logger.info(f"Syncing DB {db_id} to GraphDB (Graph ID: {graph_name})...")
        db_conn = await load_database_sync(sqlite_url, user_id)
        if not db_conn or not db_conn.success:
            logger.error(f"Failed to sync DB {db_id} to GraphDB")
            return ""
        existing_graphs.add(graph_name)
    else:
        logger.info(f"Graph '{graph_name}' already exists in GraphDB. Skipping import.")
        
    # 2. Sử dụng Retriever và AnalysisAgent trực tiếp để bỏ qua Chart, Relevancy
    retriever = Retriever(graph_id=graph_name, db=None)
    db_description, _ = await retriever.get_db_description()
    
    tables = await retriever.find([question], db_description)
    
    agent_an = AnalysisAgent(
        queries_history=[question],
        result_history=[],
    )
    
    loop = asyncio.get_running_loop()
    answer_an = await loop.run_in_executor(
        None,
        lambda: agent_an.get_analysis(
            user_query=question,
            tables=tables,
            db_description=db_description,
            instructions="",
            memory_context=None,
            db_type="sqlite",
            user_rules_spec=None
        )
    )
    
    generated_sql = answer_an.get("sql_query", "")
    if generated_sql:
        generated_sql = await execute_and_heal_sql(db_path, db_description, question, generated_sql)
        
    return generated_sql

async def main():
    parser = argparse.ArgumentParser(description="BIRD Benchmark Evaluator for StrongBI")
    parser.add_argument("--db-dir", type=str, required=True, help="Directory containing BIRD databases folder (db_id/db_id.sqlite)")
    parser.add_argument("--eval-json", type=str, required=True, help="Path to dev.json / train.json BIRD dataset")
    parser.add_argument("--mode", type=str, choices=["e2e", "schema-only"], default="e2e", help="e2e (with GraphDB) or schema-only (without GraphDB)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of queries to evaluate")
    parser.add_argument("--output", type=str, default="bird_results.json", help="Path to save output results")
    args = parser.parse_args()

    # Đọc dataset BIRD
    with open(args.eval_json, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
        
    if args.limit:
        dataset = dataset[:args.limit]
        
    logger.info(f"Loaded {len(dataset)} queries for evaluation in mode: {args.mode}")
    
    # Lấy danh sách các Graph đã tồn tại trong GraphDB để tránh nạp lại
    existing_graphs = set()
    try:
        db_factory = GraphDatabaseFactory.create()
        await db_factory.connect()
        existing_graphs = set(await db_factory.list_graph())
        logger.info(f"Found {len(existing_graphs)} existing graphs in GraphDB.")
    except Exception as e:
        logger.warning(f"Could not connect to GraphDB to fetch existing graphs: {e}")
    finally:
        try:
            await db_factory.disconnect()
        except Exception:
            pass
            
    results = []
    correct_count = 0
    start_time = time.time()
    
    for idx, item in enumerate(dataset):
        db_id = item["db_id"]
        question = item["question"]
        gold_sql = item["SQL"]
        
        # Đường dẫn tới file SQLite thực tế
        db_path = os.path.join(args.db_dir, db_id, f"{db_id}.sqlite")
        if not os.path.exists(db_path):
            logger.error(f"SQLite file not found at: {db_path}")
            continue
            
        logger.info(f"[{idx+1}/{len(dataset)}] Evaluating query for DB: {db_id}")
        logger.info(f"Question: {question}")
        
        query_start = time.time()
        generated_sql = ""
        error_msg = None
        
        try:
            if args.mode == "schema-only":
                generated_sql = await evaluate_schema_only(db_path, question)
            else:
                generated_sql = await evaluate_e2e(db_path, db_id, question, existing_graphs)
        except Exception as e:
            logger.exception("Error during SQL generation")
            error_msg = f"Generation Error: {str(e)}"
            
        latency = time.time() - query_start
        
        # Đánh giá kết quả thực thi
        is_match = False
        match_msg = ""
        if generated_sql and not error_msg:
            is_match, match_msg = evaluate_sql_match(db_path, gold_sql, generated_sql)
        else:
            match_msg = error_msg or "No SQL generated"
            
        if is_match:
            correct_count += 1
            logger.info("-> RESULT: SUCCESS")
        else:
            logger.warning(f"-> RESULT: FAILED ({match_msg})")
            
        results.append({
            "question_id": item.get("question_id", idx),
            "db_id": db_id,
            "question": question,
            "gold_sql": gold_sql,
            "generated_sql": generated_sql,
            "is_correct": is_match,
            "message": match_msg,
            "latency": latency
        })
        
    total_time = time.time() - start_time
    accuracy = (correct_count / len(dataset)) * 100 if dataset else 0
    
    summary = {
        "evaluation_mode": args.mode,
        "total_queries": len(dataset),
        "correct_queries": correct_count,
        "accuracy_percentage": accuracy,
        "total_time_seconds": total_time,
        "avg_latency_seconds": total_time / len(dataset) if dataset else 0
    }
    
    logger.info("=== EVALUATION SUMMARY ===")
    logger.info(f"Total: {summary['total_queries']}")
    logger.info(f"Correct: {summary['correct_queries']}")
    logger.info(f"Accuracy: {summary['accuracy_percentage']:.2f}%")
    logger.info(f"Avg Latency: {summary['avg_latency_seconds']:.2f}s")
    
    # Ghi file kết quả
    output_data = {
        "summary": summary,
        "results": results
    }
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Detailed report saved to: {args.output}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
