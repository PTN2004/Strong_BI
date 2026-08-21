import asyncio
import sys
from pathlib import Path

# Thêm root dự án vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from api.graph_db.factory import GraphDatabaseFactory

async def check_semantics():
    db = await GraphDatabaseFactory.get_instance()
    
    # Lấy danh sách graph
    all_graphs = await db.list_graph()
    target_graph = next((g for g in all_graphs if "dms" in g.lower()), None)
    
    if not target_graph:
        print("❌ Không tìm thấy Graph DMS.")
        return
        
    print(f"✅ Đang truy vấn Graph: {target_graph}")
    db.select_graph(target_graph)
    
    print("\n" + "="*50)
    print("📊 KIỂM TRA METRIC (Các chỉ số đo lường):")
    print("="*50)
    metrics_res = await db.query("MATCH (m:Metric) RETURN m.name, m.description, m.formula")
    metrics = getattr(metrics_res, 'result_set', metrics_res) if metrics_res else []
    
    for row in metrics:
        if isinstance(row, dict):
            name = row.get('m.name', 'N/A')
            desc = row.get('m.description', 'N/A')
            formula = row.get('m.formula')
            
            print(f"👉 Metric: {name}")
            print(f"   Mô tả: {desc}")
            if formula:
                print(f"   Công thức: {formula}")
            print()
                
    if not metrics:
        print("⚠️ Chưa có Metric nào được nạp.")

    print("="*50)
    print("📐 KIỂM TRA DIMENSION (Các chiều phân tích):")
    print("="*50)
    dimensions_res = await db.query("MATCH (d:Dimension) RETURN d.name, d.description")
    dimensions = getattr(dimensions_res, 'result_set', dimensions_res) if dimensions_res else []
    
    for row in dimensions:
        if isinstance(row, dict):
            name = row.get('d.name', 'N/A')
            desc = row.get('d.description', 'N/A')
            print(f"👉 Dimension: {name}")
            print(f"   Mô tả: {desc}\n")
                
    if not dimensions:
        print("⚠️ Chưa có Dimension nào được nạp.")

    try:
        metric_count_res = await db.query("MATCH (m:Metric) WHERE m.embedding IS NOT NULL RETURN count(m)")
        dim_count_res = await db.query("MATCH (d:Dimension) WHERE d.embedding IS NOT NULL RETURN count(d)")
        
        metric_count = getattr(metric_count_res, 'result_set', metric_count_res) if metric_count_res else []
        dim_count = getattr(dim_count_res, 'result_set', dim_count_res) if dim_count_res else []
        
        m_count = metric_count[0].get('count(m)', 0) if metric_count and isinstance(metric_count[0], dict) else 0
        d_count = dim_count[0].get('count(d)', 0) if dim_count and isinstance(dim_count[0], dict) else 0
    except Exception:
        m_count, d_count = 0, 0
    
    print("="*50)
    print("🧠 TÌNH TRẠNG VECTOR EMBEDDING (Hệ thống nhúng):")
    print("="*50)
    print(f"   - Số lượng Metric đã nhúng vector thành công: {m_count}")
    print(f"   - Số lượng Dimension đã nhúng vector thành công: {d_count}")
    
    if m_count > 0 or d_count > 0:
        print("\n✅ Tuyệt vời! Hệ thống RAG Semantics đã có dữ liệu Vector.")
    else:
        print("\n⚠️ Có Node nhưng CHƯA CÓ Vector Embedding (do lúc nãy bị lỗi 401). Bạn cần chạy lại file `load_semantic.py`!")

if __name__ == "__main__":
    asyncio.run(check_semantics())
