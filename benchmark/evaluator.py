import os
import asyncio
import logging
from typing import Set

from api.agents import AnalysisAgent
from api.agents.healer_agent import HealerAgent
from api.core.schema_loader import load_database_sync
from api.core.text2sql import run_query, ChatRequest
from benchmark.sqlite_helper import get_sqlite_schema_as_tables, execute_sql

logger = logging.getLogger("BIRD_Evaluator.Evaluator")

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
            combined_tables=tables,
            db_description="BIRD SQLite Evaluation (Schema Only)",
            instructions="",
            memory_context=None,
            database_type="sqlite",
            user_rules_spec=None
        )
    )
    generated_sql = answer_an.get("sql_query", "")
    if generated_sql:
        generated_sql = await execute_and_heal_sql(db_path, "BIRD SQLite Evaluation (Schema Only)", question, generated_sql)
        
    return generated_sql

async def evaluate_e2e(db_path: str, db_id: str, question: str, existing_graphs: Set[str]) -> str:
    """Đăng ký CSDL vào Graph DB (FalkorDB/Neo4j) sau đó chạy qua Pipeline tìm kiếm thực tế."""
    user_id = "bird_eval"
    sqlite_url = f"sqlite:///{os.path.abspath(db_path)}"
    graph_name = f"{user_id}_{db_id}"
    
    # 1. Nạp cơ sở dữ liệu đồng bộ (chỉ nạp nếu chưa tồn tại trong GraphDB)
    if graph_name not in existing_graphs:
        logger.info(f"Syncing DB '{db_id}' to GraphDB (Graph ID: {graph_name})...")
        db_conn = await load_database_sync(sqlite_url, user_id)
        if not db_conn or not db_conn.success:
            logger.error(f"Failed to sync DB '{db_id}' to GraphDB")
            return ""
        existing_graphs.add(graph_name)
    else:
        logger.info(f"Graph '{graph_name}' already exists in GraphDB. Skipping import.")
        
    # 2. Sử dụng Retriever và AnalysisAgent trực tiếp để bỏ qua Chart, Relevancy
    from api.retriever import Retriever
    from api.graph_db.factory import GraphDatabaseFactory
    
    db_instance = GraphDatabaseFactory._instance
    retriever = Retriever(graph_id=graph_name, db=db_instance)
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
            combined_tables=tables,
            db_description=db_description,
            instructions="",
            memory_context=None,
            database_type="sqlite",
            user_rules_spec=None
        )
    )
    
    generated_sql = answer_an.get("sql_query", "")
    if generated_sql:
        generated_sql = await execute_and_heal_sql(db_path, db_description, question, generated_sql)
            
    return generated_sql
