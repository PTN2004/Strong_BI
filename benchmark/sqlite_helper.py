import sqlite3
import datetime
import logging
from typing import List, Dict, Any, Tuple
from api.loaders.sqlite_loader import SQLiteLoader

logger = logging.getLogger("BIRD_Evaluator.SQLiteHelper")

def get_sqlite_schema_as_tables(db_path: str) -> List[List[Any]]:
    """Đọc trực tiếp SQLite schema và chuyển đổi thành cấu trúc TableInfo mà AnalysisAgent mong đợi."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Sử dụng các hàm trích xuất thông tin có sẵn trong SQLiteLoader của StrongBI
        entities = SQLiteLoader.extract_tables_info(cursor)
        relationships = SQLiteLoader.extract_relationships(cursor)
    except Exception as e:
        logger.error(f"Error extracting schema from SQLite database {db_path}: {e}")
        entities, relationships = {}, {}
    finally:
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
            
        # Tìm các khoá ngoại liên kết đến bảng này
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
