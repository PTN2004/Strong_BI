import os
import argparse
import json
import time
import logging
import asyncio
from typing import Set

from api.graph_db import GraphDatabaseFactory
from benchmark.sqlite_helper import evaluate_sql_match
from benchmark.evaluator import evaluate_schema_only, evaluate_e2e

logger = logging.getLogger("BIRD_Evaluator.CLI")

async def run_evaluation(args):
    # Đọc dataset BIRD
    with open(args.eval_json, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
        
    if args.limit:
        dataset = dataset[:args.limit]
        
    logger.info(f"Loaded {len(dataset)} queries for evaluation in mode: {args.mode}")
    
    existing_graphs = set()
    if args.mode == "e2e":
        try:
            db_factory = await GraphDatabaseFactory.get_instance()
            # Fetch existing graphs by querying Database nodes in Neo4j Community
            res = await db_factory.query("MATCH (d:Database) RETURN d.name AS name")
            loaded_dbs = [row["name"] for row in res.result_set if "name" in row]
            existing_graphs = {f"bird_eval_{db}" for db in loaded_dbs}
            logger.info(f"Found {len(existing_graphs)} existing graphs in GraphDB.")
        except Exception as e:
            logger.warning(f"Could not connect to GraphDB to fetch existing graphs: {e}")
            
    results = []
    correct_count = 0
    start_time = time.time()
    
    for idx, item in enumerate(dataset):
        db_id = item["db_id"]
        question = item["question"]
        gold_sql = item["SQL"]
        
        # Đường dẫn tới file SQLite thực tế của BIRD
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
    
    if args.mode == "e2e":
        try:
            await GraphDatabaseFactory.close_instance()
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(description="BIRD Benchmark Evaluator for StrongBI")
    parser.add_argument("--db-dir", type=str, required=True, help="Directory containing BIRD databases folder (db_id/db_id.sqlite)")
    parser.add_argument("--eval-json", type=str, required=True, help="Path to dev.json / train.json BIRD dataset")
    parser.add_argument("--mode", type=str, choices=["e2e", "schema-only"], default="e2e", help="e2e (with GraphDB) or schema-only (without GraphDB)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of queries to evaluate")
    parser.add_argument("--output", type=str, default="bird_results.json", help="Path to save output results")
    args = parser.parse_args()
    
    asyncio.run(run_evaluation(args))
