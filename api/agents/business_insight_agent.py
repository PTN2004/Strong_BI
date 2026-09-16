"""Business Insight Agent (Specialized C-level BI & Data Strategy Analyst).
Focuses 100% on deep numerical analysis, impact assessment, and actionable business recommendations.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from api.agents.utils import run_completion

logger = logging.getLogger(__name__)

BUSINESS_INSIGHT_SYSTEM_PROMPT = """Bạn là Chuyên gia Phân tích Dữ liệu & Chiến lược Điều hành Doanh nghiệp (Chief Strategy & Analytics Officer).
Nhiệm vụ của bạn là phân tích kết quả dữ liệu truy vấn và lập một BẢN BÁO CÁO PHÂN TÍCH ĐIỀU HÀNH (Executive Business Report) trang trọng, chuyên nghiệp và chuẩn mực dành cho Ban Lãnh đạo.

### NGUYÊN TẮC BÁO CÁO BẮT BUỘC:
1. TUYỆT ĐỐI KHÔNG DÙNG ICON HOẶC EMOJI: Không sử dụng bất kỳ biểu tượng cảm xúc hay icon trang trí nào (ví dụ: cấm dùng 📌, 💡, 🎯, 🚀, 📊, ⚡, ⚠️, v.v.). Toàn bộ báo cáo phải giữ văn phong trang trọng, chuẩn mực của báo cáo doanh nghiệp.
2. KHÔNG DÙNG THUẬT NGỮ KỸ THUẬT / CSDL: Tuyệt đối không nhắc đến tên bảng cơ sở dữ liệu, câu lệnh SQL, tên cột kỹ thuật hay cấu trúc JSON. Diễn đạt toàn bộ bằng thuật ngữ kinh doanh và số liệu cụ thể.
3. NGÔN NGỮ: Viết bằng tiếng Việt chuẩn mực, mạch lạc, súc tích.

### CẤU TRÚC BÁO CÁO BẮT BUỘC:

### 1. Tóm tắt điều hành
[1-2 câu kết luận trọng tâm nhất trả lời trực tiếp cho câu hỏi của người dùng, nêu bật ý nghĩa kinh doanh cốt lõi]

### 2. Thực trạng & Phân tích chi tiết số liệu
- [Chỉ số quy mô & trọng số: Tổng số lượng, Tổng giá trị, Giá trị trung bình, Tỷ trọng đóng góp (%)]
- [Phân tích cơ cấu / Xếp hạng: Chỉ nêu các đối tượng dẫn đầu hoặc nhóm có biến động đáng chú ý, gắn kèm con số cụ thể]

### 3. Đánh giá tác động & Bối cảnh kinh doanh
- [Phân tích nguyên nhân & xu hướng: Động lực thúc đẩy hoặc nguyên nhân dẫn đến kết quả này]
- [Nhận diện rủi ro & cơ hội: Đánh giá tác động đến doanh thu, chi phí, khách hàng hoặc hiệu quả vận hành]

### 4. Đề xuất giải pháp & Kế hoạch hành động
1. [Giải pháp thực thi ngắn hạn: Hành động cụ thể cần triển khai ngay để giải quyết vấn đề hoặc nắm bắt cơ hội]
2. [Giải pháp tối ưu trung - dài hạn: Định hướng nâng cao hiệu suất vận hành hoặc kiểm soát rủi ro]
"""


class BusinessInsightAgent:
    """Agent dedicated strictly to generating high-value business insights and executive summaries."""

    def __init__(
        self,
        custom_api_key: Optional[str] = None,
        custom_model: Optional[str] = None,
        custom_api_base: Optional[str] = None,
    ):
        self.custom_api_key = custom_api_key
        self.custom_model = custom_model
        self.custom_api_base = custom_api_base

    def generate_insight(
        self,
        user_query: str,
        sql_query: str,
        query_results: List[Dict[str, Any]],
        schema_context: str = "",
        business_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate deep business insight from query results.
        """
        if not query_results:
            return {"insight": "Truy vấn thành công nhưng không có dữ liệu phù hợp trong cơ sở dữ liệu.", "usage": {}}

        columns = list(query_results[0].keys())
        total_rows = len(query_results)
        sample_data = query_results if total_rows <= 30 else query_results[:20]

        prompt = f"""
User Question: {user_query}
Executed SQL: {sql_query}

Semantic & Schema Context:
{schema_context}

Workspace Business Context:
{business_context or 'Doanh nghiệp thương mại / phân phối hàng hóa và bán lẻ.'}

Dataset Summary:
- Columns: {columns}
- Total Records: {total_rows}
- Data Sample (first {len(sample_data)} rows):
{json.dumps(sample_data, ensure_ascii=False, indent=2)}

Provide your executive business insight report following the McKinsey Framework (What - So What - Now What) in fluent Vietnamese.
"""

        try:
            messages = [
                {"role": "system", "content": BUSINESS_INSIGHT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]

            content, usage = run_completion(
                messages=messages,
                custom_model=self.custom_model,
                custom_api_key=self.custom_api_key,
                custom_api_base=self.custom_api_base,
                temperature=0.35,
                max_tokens=2048,
                return_usage=True,
            )

            return {
                "insight": content.strip(),
                "usage": usage or {},
            }
        except Exception as e:
            logger.error(f"Error in BusinessInsightAgent: {e}")
            return {
                "insight": f"Đã tìm thấy {total_rows} bản ghi số liệu phù hợp với yêu cầu.",
                "usage": {},
            }
