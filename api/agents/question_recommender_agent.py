"""Question Recommender Agent for AI-driven Business Intelligence.
Generates schema-aware, high-impact business analytical questions categorized by business intent.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from .utils import BaseAgent, run_completion


QUESTION_RECOMMENDER_PROMPT = """
You are a Chief BI Analytics Architect and Data Strategy Lead.
Analyze the following database schema, tables, columns, and business relationships to generate 6 to 9 deep, practical, high-value business questions in Vietnamese for executives and managers.

Database Schema / Tables & Columns:
{SCHEMA_CONTEXT}

User Custom Focus / Keyword (optional):
{USER_FOCUS}

Rules for Question Generation:
1. Questions must be 100% answerable using the provided tables & columns.
2. Group questions into 5 core business categories:
   - "kpi": Tổng quan & Chỉ số KPI cốt lõi
   - "breakdown": Phân tích đa chiều & Cơ cấu tỷ trọng
   - "trend": Xu hướng & Biến động theo thời gian
   - "ranking": Xếp hạng & Top đóng góp
   - "anomaly": Cảnh báo rủi ro & Bất thường vận hành
3. Provide rich analytical context for each recommendation:
   - "business_value": Giá trị chiến lược & quyết định điều hành mang lại
   - "metrics": Danh sách chỉ số cốt lõi (ví dụ: ["Tổng doanh thu", "Số đơn hàng", "AOV"])
   - "dimensions": Các chiều phân tích (ví dụ: ["Tháng", "Khu vực", "Nhóm sản phẩm"])
   - "chart_type": Loại trực quan hóa tối ưu ("bar", "line", "area", "pie")
   - "complexity": Độ phức tạp ("Cơ bản", "Nâng cao")
   - "follow_ups": 1-2 câu hỏi đào sâu tiếp theo sau khi có kết quả

Output strictly valid JSON (and nothing else) matching this exact format:
{{
  "recommendations": [
    {{
      "id": "q1",
      "question": "Tổng doanh thu và số lượng đơn hàng theo từng tháng năm nay",
      "category": "kpi",
      "category_label": "Chỉ số KPI",
      "description": "Đo lường nhịp độ kinh doanh và quy mô đơn hàng phát sinh theo từng tháng",
      "business_value": "Giúp Ban Giám đốc đánh giá tiến độ hoàn thành mục tiêu doanh thu năm và dự báo dòng tiền",
      "metrics": ["Tổng doanh thu", "Số lượng đơn hàng"],
      "dimensions": ["Tháng giao dịch"],
      "chart_type": "bar",
      "complexity": "Cơ bản",
      "tables": ["orders", "order_items"],
      "follow_ups": ["Tháng nào có giá trị trung bình mỗi đơn (AOV) cao nhất?", "Tỷ lệ đơn hàng bị hủy theo từng tháng?"]
    }}
  ]
}}
"""


class QuestionRecommenderAgent:
    """Agent for recommending schema-driven analytical questions."""

    def __init__(
        self,
        custom_api_key: Optional[str] = None,
        custom_model: Optional[str] = None,
        custom_api_base: Optional[str] = None,
    ):
        self.custom_api_key = custom_api_key
        self.custom_model = custom_model
        self.custom_api_base = custom_api_base

    def recommend_questions(
        self,
        schema_context: str,
        user_focus: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Generate contextual question recommendations.
        """
        prompt = QUESTION_RECOMMENDER_PROMPT.format(
            SCHEMA_CONTEXT=schema_context or "Bảng bán hàng: orders, order_items, customers, products, stores",
            USER_FOCUS=user_focus or "Tất cả các khía cạnh bán hàng, doanh thu và vận hành",
        )

        try:
            raw_response = run_completion(
                [{"role": "user", "content": prompt}],
                self.custom_model,
                self.custom_api_key,
                self.custom_api_base,
                temperature=0.7,
            )

            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            recs = parsed.get("recommendations", [])
            if isinstance(recs, list) and len(recs) > 0:
                return recs
        except Exception as e:
            logging.warning("LLM question recommendation fallback triggered: %s", str(e))

        # Rich executive fallbacks
        return [
            {
                "id": "fb_1",
                "question": "Tổng doanh thu và số lượng đơn hàng 30 ngày qua",
                "category": "kpi",
                "category_label": "Chỉ số KPI",
                "description": "Đo lường sức khỏe doanh số và tốc độ phát sinh đơn hàng trong chu kỳ gần nhất",
                "business_value": "Đánh giá hiệu suất kinh doanh tức thời và cảnh báo sớm biến động doanh số",
                "metrics": ["Tổng doanh thu", "Số lượng đơn hàng", "Doanh thu trung bình/đơn"],
                "dimensions": ["Ngày đặt hàng"],
                "chart_type": "bar",
                "complexity": "Cơ bản",
                "tables": ["orders"],
                "follow_ups": ["Doanh thu ngày nào cao nhất trong tuần?", "Tỷ lệ đơn hàng giao thành công?"]
            },
            {
                "id": "fb_2",
                "question": "Top 10 sản phẩm có doanh thu cao nhất tháng này",
                "category": "ranking",
                "category_label": "Xếp hạng",
                "description": "Nhận diện danh mục mặt hàng chủ lực đóng góp lớn nhất vào tổng doanh thu",
                "business_value": "Tối ưu hóa kế hoạch nhập hàng và phân bổ ngân sách tiếp thị cho sản phẩm Hero",
                "metrics": ["Doanh số bán", "Số lượng bán ra"],
                "dimensions": ["Tên sản phẩm", "Nhóm danh mục"],
                "chart_type": "bar",
                "complexity": "Cơ bản",
                "tables": ["order_items", "products"],
                "follow_ups": ["Biên lợi nhuận của Top 10 sản phẩm này?", "Khách hàng nào mua nhiều nhất các sản phẩm này?"]
            },
            {
                "id": "fb_3",
                "question": "Tỷ trọng doanh số theo từng nhóm danh mục sản phẩm",
                "category": "breakdown",
                "category_label": "Phân tích đa chiều",
                "description": "Phân tích cơ cấu đóng góp của từng dòng sản phẩm để tối ưu danh mục kinh doanh",
                "business_value": "Giúp Ban Lãnh đạo đánh giá mức độ phụ thuộc danh mục và đa dạng hóa sản phẩm",
                "metrics": ["Tỷ trọng % doanh thu", "Tổng giá trị danh mục"],
                "dimensions": ["Danh mục ngành hàng"],
                "chart_type": "pie",
                "complexity": "Cơ bản",
                "tables": ["products", "order_items"],
                "follow_ups": ["Danh mục nào có tốc độ tăng trưởng nhanh nhất?", "Tồn kho tương ứng của từng danh mục?"]
            },
            {
                "id": "fb_4",
                "question": "Xu hướng tăng trưởng đơn hàng theo tuần trong quý này",
                "category": "trend",
                "category_label": "Xu hướng",
                "description": "Phân tích chu kỳ dao động và tốc độ tăng trưởng quy mô bán hàng theo thời gian",
                "business_value": "Dự báo nhu cầu nhân sự vận hành kho vận và kế hoạch bán lẻ các tuần tiếp theo",
                "metrics": ["Số lượng đơn hàng", "Tốc độ tăng trưởng tuần (WoW)"],
                "dimensions": ["Tuần trong quý"],
                "chart_type": "area",
                "complexity": "Nâng cao",
                "tables": ["orders"],
                "follow_ups": ["Nguyên nhân các tuần sụt giảm đơn hàng?", "Khung giờ đặt hàng cao điểm trong tuần?"]
            },
            {
                "id": "fb_5",
                "question": "Top 10 khách hàng có giá trị mua sắm lớn nhất",
                "category": "ranking",
                "category_label": "Xếp hạng",
                "description": "Định vị và chăm sóc tệp khách hàng VIP mang lại giá trị vòng đời cao nhất",
                "business_value": "Thiết lập chính sách chăm sóc khách hàng đặc biệt và giữ chân khách hàng then chốt",
                "metrics": ["Tổng chi tiêu tích lũy", "Tần suất mua hàng"],
                "dimensions": ["Khách hàng", "Khu vực địa lý"],
                "chart_type": "bar",
                "complexity": "Cơ bản",
                "tables": ["customers", "orders"],
                "follow_ups": ["Chu kỳ quay lại mua hàng của tệp VIP này?", "Mặt hàng ưa thích của nhóm VIP?"]
            },
            {
                "id": "fb_6",
                "question": "Các sản phẩm có lượng tồn kho cao nhưng doanh số bán thấp",
                "category": "anomaly",
                "category_label": "Cảnh báo rủi ro",
                "description": "Cảnh báo các mặt hàng có nguy cơ đọng vốn và chi phí lưu kho kéo dài",
                "business_value": "Kịp thời tung chương trình khuyến mãi xả hàng giải phóng dòng tiền lưu động",
                "metrics": ["Số lượng tồn kho", "Doanh số 30 ngày qua", "Thời gian lưu kho"],
                "dimensions": ["Sản phẩm", "Kho lưu trữ"],
                "chart_type": "bar",
                "complexity": "Nâng cao",
                "tables": ["products", "inventory"],
                "follow_ups": ["Tổng giá trị vốn đang bị đọng là bao nhiêu?", "Đề xuất mức giảm giá tối ưu để thu hồi vốn?"]
            },
        ]
