import asyncio
import sys
import os
import time
import pandas as pd
from pathlib import Path

# Thêm thư mục root của dự án vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from api.core.text2sql import ChatRequest
from api.core.graph_text2sql_v5 import run_query_graph_v4
from api.graph_db.factory import GraphDatabaseFactory
from api.config import Config

# Danh sách Test Cases
TEST_CASES = []

def load_excel_test_cases():
    """Đọc các câu hỏi từ file Excel để làm Test Cases"""
    excel_path = Path(__file__).resolve().parent.parent.parent / "dms" / "requirements" / "AI-Data-Agent-Scope-Trien-Khai.xlsx"
    if not excel_path.exists():
        print(f"⚠️ Không tìm thấy file Excel: {excel_path}")
        return []
    
    try:
        df = pd.read_excel(excel_path)
        extra_cases = []
        for index, row in df.iterrows():
            question_raw = str(row.get('Câu hỏi AI Agent cần trả lời', '')).strip()
            if question_raw and question_raw.lower() != 'nan':
                # Tách nhiều câu hỏi trong cùng 1 ô (phân cách bằng dấu '?')
                # Ví dụ: "Doanh thu hôm nay? Doanh thu theo vùng?" -> ["Doanh thu hôm nay", "Doanh thu theo vùng"]
                sub_questions = [q.strip() for q in question_raw.split('?') if q.strip()]
                
                for sub_idx, sub_q in enumerate(sub_questions):
                    # Thêm dấu '?' vào cuối câu hỏi nếu bị mất khi split
                    final_q = sub_q + "?"
                    q_id = str(row.get('ID', f"EXCEL-{index}"))
                    if len(sub_questions) > 1:
                        q_id = f"{q_id}-{sub_idx + 1}"
                        
                    extra_cases.append({
                        "id": q_id,
                        "question": final_q,
                        "expected_patterns": [],
                        "description": str(row.get('Mục tiêu sử dụng', 'Excel imported'))
                    })
        return extra_cases
    except Exception as e:
        print(f"⚠️ Lỗi khi đọc file Excel: {e}")
        return []

TEST_CASES = load_excel_test_cases()

def estimate_tokens(text: str) -> int:
    """Hàm ước lượng token dựa trên độ dài chuỗi (trung bình 4 ký tự = 1 token)."""
    return len(str(text)) // 4

async def evaluate():
    print("🚀 Bắt đầu Benchmark Đánh Giá AI Data Agent cho DMS...")
    print(f"🤖 LLM Completion Model: {Config.COMPLETION_MODEL} (Provider: {Config.LLM_PROVIDER})")
    print(f"📐 Embedding Model:      {Config.EMBEDDING_MODEL_NAME}")
    print("-" * 60)
    
    db = await GraphDatabaseFactory.get_instance()
    all_graphs = await db.list_graph()
    
    target_graph = next((g for g in all_graphs if "dms" in g.lower()), None)
    if not target_graph:
        print("❌ Không tìm thấy Graph Database nào có chữ 'dms'.")
        sys.exit(1)
        
    print(f"✅ Đã kết nối tới Target Graph: {target_graph}")
    print("-" * 60)
    
    eval_dir = Path("eval")
    eval_dir.mkdir(exist_ok=True)
    
    results = []
    total_passed = 0
    
    for case in TEST_CASES:
        print(f"\n▶️ Đang chạy Test {case['id']}: {case['question']}")
        
        chat_req = ChatRequest(chat=[case['question']])
        start_time = time.time()
        rag_time = 0
        
        sql_generated = ""
        agent_output = ""
        error_msg = None
        model_calls = 0
        total_tokens = estimate_tokens(case['question'])
        retrieved_nodes_set = set()
        
        try:
            async for chunk in run_query_graph_v4(user_id="eval_user", graph_id=target_graph, chat_data=chat_req, db=db):
                # Theo dõi tiến trình để đếm số lần gọi model và thời gian RAG
                if isinstance(chunk, dict):
                    chunk_type = chunk.get("type")
                    if chunk_type == "reasoning_step":
                        model_calls += 1
                        total_tokens += estimate_tokens(chunk.get("message", ""))
                    elif chunk_type == "reasoning_graph":
                        graph_data = chunk.get("data", {})
                        if isinstance(graph_data, dict):
                            for node in graph_data.get("nodes", []):
                                if node.get("label") in ["Table", "Metric", "Dimension"]:
                                    retrieved_nodes_set.add(f"{node.get('name')} ({node.get('label')})")
                    elif chunk_type == "sql" or chunk_type == "sql_query":
                        sql_generated = chunk.get("content", "") or chunk.get("data", "")
                        rag_time = time.time() - start_time  # Tốc độ RAG + LLM sinh SQL
                        total_tokens += estimate_tokens(sql_generated)
                        model_calls += 1
                    elif chunk_type == "error":
                        error_msg = chunk.get("content")
                    elif chunk_type == "ai_response":
                        agent_output = chunk.get("content", chunk.get("message", ""))
                        total_tokens += estimate_tokens(agent_output)
                        model_calls += 1
                elif type(chunk).__name__ == '_Final':
                    if hasattr(chunk, 'value') and hasattr(chunk.value, 'ai_response'):
                        if not agent_output:
                            agent_output = chunk.value.ai_response
                        total_tokens += estimate_tokens(agent_output)
                        
        except Exception as e:
            error_msg = str(e)
            
        exec_time = time.time() - start_time
        if rag_time == 0:
            rag_time = exec_time
            
        if error_msg:
            status = "FAIL"
            missing = error_msg
        else:
            if not sql_generated.strip():
                status = "FAIL"
                missing = "No SQL Generated"
            else:
                sql_upper = sql_generated.upper()
                missing_patterns = [p for p in case['expected_patterns'] if p.upper() not in sql_upper]
                status = "PASS" if not missing_patterns else "FAIL"
                missing = ", ".join(missing_patterns) if missing_patterns else "None"
                
            if status == "PASS":
                total_passed += 1
                
        # Lọc ra danh sách các Bảng (Table) đã được lấy từ GraphRAG
        tables_retrieved = [node.split(" (Table)")[0] for node in retrieved_nodes_set if " (Table)" in node]
        tables_str = ", ".join(sorted(tables_retrieved)) if tables_retrieved else "None"
        
        # In kết quả console
        retrieved_context_str = ", ".join(sorted(retrieved_nodes_set)) if retrieved_nodes_set else "None"
        print(f"   Trạng thái: {status}")
        print(f"   ⏱ Tốc độ RAG + Text2SQL: {rag_time:.2f}s | Tổng thời gian Agent: {exec_time:.2f}s")
        print(f"   🪙 Token ước tính: {total_tokens} | Số lần gọi Model: {model_calls}")
        print(f"   📚 Context (Full): {retrieved_context_str}")
        print(f"   📊 Context (Tables): {tables_str}")
        print(f"   💻 SQL Sinh ra: {sql_generated.strip()[:100]}...")
        if missing != "None":
            print(f"   ⚠️ Thiếu keyword: {missing}")
            
        results.append({
            "Test ID": case["id"],
            "Question": case["question"],
            "Status": status,
            "GraphRAG Tables": tables_str,
            "Retrieved Context": retrieved_context_str,
            "Agent Output": agent_output,
            "Generated SQL": sql_generated,
            "Missing Keywords": missing,
            "RAG Latency (s)": round(rag_time, 2),
            "Total Latency (s)": round(exec_time, 2),
            "Estimated Tokens": total_tokens,
            "Model Calls": model_calls
        })
        
    # Tạo Dataframe và xuất Excel & Markdown vào thư mục eval/
    df = pd.DataFrame(results)
    excel_path = eval_dir / "dms_benchmark_metrics.xlsx"
    md_path = eval_dir / "dms_benchmark_report.md"
    
    # Ghi ra file Excel
    df.to_excel(excel_path, index=False)
    
    # Ghi đè file Markdown
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 📊 DMS AI Agent Benchmark Metrics\n\n")
        f.write(f"- **LLM Completion Model:** `{Config.COMPLETION_MODEL}` (Provider: `{Config.LLM_PROVIDER}`)\n")
        f.write(f"- **Embedding Model:** `{Config.EMBEDDING_MODEL_NAME}`\n")
        f.write(f"- **Tỷ lệ thành công (Pass Rate):** {(total_passed/len(TEST_CASES))*100:.1f}%\n")
        f.write(f"- **Tốc độ xử lý trung bình:** {df['Total Latency (s)'].mean():.2f}s\n")
        f.write(f"- **Tốc độ RAG trung bình:** {df['RAG Latency (s)'].mean():.2f}s\n")
        f.write(f"- **Token sử dụng trung bình:** {df['Estimated Tokens'].mean():.0f} tokens/query\n\n")
        f.write("## Chi tiết kết quả\n\n")
        f.write(df.to_markdown(index=False))
        
    print("\n" + "=" * 60)
    print(f"🏆 TỔNG KẾT: {total_passed}/{len(TEST_CASES)} PASSED ({(total_passed/len(TEST_CASES))*100:.1f}%)")
    print(f"📁 Báo cáo đã được lưu tại:\n- {excel_path.absolute()}\n- {md_path.absolute()}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(evaluate())
