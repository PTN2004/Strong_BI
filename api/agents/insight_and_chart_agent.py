import json
import logging
from typing import Any, Dict, List, Optional
from api.agents.utils import run_completion

logger = logging.getLogger(__name__)

class InsightAndChartAgent:
    
    def __init__(self, custom_api_key: Optional[str] = None, custom_model: Optional[str] = None, custom_api_base: Optional[str] = None):
        self.custom_api_key = custom_api_key
        self.custom_model = custom_model
        self.custom_api_base = custom_api_base

    def generate(
        self,
        user_query: str,
        sql_query: str,
        query_results: List[Dict[str, Any]],
        schema_context: str,
        business_context: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if not query_results or len(query_results) == 0:
            return None
            
        columns = list(query_results[0].keys())
        # Kết quả nhỏ (hoặc cần vẽ map vì map yêu cầu chuẩn hóa tên): đưa TOÀN BỘ vào prompt 
        # (tối đa 100 dòng để tránh lố token). Kết quả lớn: sample 15 dòng để tiết kiệm token.
        # Ở bước hậu xử lý dưới cùng, ta sẽ tự động inject toàn bộ data vào dataset.
        sample_data = query_results if len(query_results) <= 100 else query_results[:15]
        
        system_prompt = """You are an elite Data Analyst and BI Expert. Your task is to analyze a dataset, the user's natural language query, and the SQL/Schema context, and then provide a textual insight and an Apache ECharts configuration.

CRITICAL JSON FORMATTING RULE: You MUST return a single, valid JSON object. All string values MUST have their newlines properly escaped as `\\n`. Do NOT output raw newline characters inside JSON string values. You MUST escape any double quotes inside string values as `\\"`.

You MUST return a single valid JSON object containing exactly the following keys:
1. "insight" (string): Provide a brief and direct business insight summarizing the data. This system is used by Enterprise Software (DMS, CRM, etc.), so users prefer short, actionable, and straight-to-the-point answers rather than long conversational text.
   IMPORTANT — LIST QUESTIONS: if the user asked for a list/ranking, DO NOT enumerate every single row from the data. That is too long. Instead, ONLY highlight the Top 3 and Bottom 3 (if applicable) using markdown bullets. For larger results, summarize the overall trend instead of listing items.
   FORMAT RULE (markdown): any closing remark/summary sentence MUST be a SEPARATE paragraph placed AFTER the bullet list with ONE EMPTY LINE between the last bullet and the remark ("\n\n").
   - Answer the user's question directly in 1-3 short sentences.
   - Highlight key takeaways (e.g., maximum/minimum values, totals, percentages) concisely.
   - **MANDATORY MCKINSEY FRAMEWORK (What - So What - Now What)**: Regardless of the database domain, you MUST structure your concluding analysis using this exact framework:
     1. **Thực trạng (What):** Describe what the data is showing briefly.
     2. **Ý nghĩa (So What):** Identify if this is a positive/negative trend, an anomaly, or an expected outcome based on the numbers.
     3. **Hành động (Now What):** Always suggest 1-2 immediate, logical actions or follow-up questions to investigate further.
   - Do NOT use filler words or lengthy explanations. Format the analysis beautifully with bold text for the framework sections.
   - Keep it in the SAME language as the user's question (e.g. Vietnamese).
2. "should_visualize" (boolean): True if the data can and should be visualized (e.g. trends, comparisons, proportions). False if it's just a single scalar number or irrelevant for charting.
4. "chart_type" (string): The best matching chart type: "line", "bar", "pie", "scatter", "radar", "funnel", "map", "gauge", "treemap", "heatmap", "area", or "combo".
   - "combo": Combine Bar and Line charts on dual Y-axes (e.g., Volume vs. Percentage).
   - "area": A line chart with `areaStyle` to show volume trends.
   - "gauge": For single KPI completion rates or percentages.
   - "treemap": For hierarchical compositions (e.g., revenue by region -> store).
5. "option" (object): A valid Apache ECharts option object.

### ECHARTS `option` STRICT RULES:
- If `chart_type` is "map", you MUST configure `series: [{ type: 'map', map: 'vietnam' (or 'world'), data: [...] }]`. The `data` array must contain objects like `{name: 'Hà Nội', value: 100}` matching standard province or country names.
- For "map", "gauge", "treemap", and "heatmap", the `dataset` component DOES NOT work well. You MUST manually construct the `data` array inside `series` using the provided sample data.
- For ALL OTHER chart types ("line", "bar", "pie", "scatter", "funnel", "area", "combo", "radar"), you MUST use the `dataset` component. Provide an empty dataset `dataset: {}` and use `encode` mapping in series. DO NOT hardcode data into `series.data`. The backend will automatically inject the full dataset source later.
- CRITICAL: For `axisLabel.formatter` or `tooltip.formatter`, DO NOT use Python format strings like `{value:,.0f}`. Only use standard ECharts string templates like `'{value}'` or `'{value} %'`. The frontend will handle complex number formatting.
- Make sure `xAxis.type` is 'category' or 'value' or 'time' based on the sample data.
- Do NOT hallucinate data. Map the axes directly to the actual column names from the "Dataset Columns".
- Ensure the JSON is 100% syntactically correct. Do NOT include markdown blocks like ```json or ```. Just raw JSON text.
"""

        prompt = f"""
        User Question: {user_query}
        SQL Query: {sql_query}
        Semantic & Schema Context:
        {schema_context}
        
        Business Context (Workspace Config):
        {business_context or 'Not provided.'}
        
        Dataset Columns: {columns}
        Total Rows Returned: {len(query_results)}
        Dataset (đầy đủ nếu <=25 dòng, ngược lại 15 dòng đầu): 
        {json.dumps(sample_data, ensure_ascii=False)}

        Analyze the sample and return the JSON object following the rules. Provide insights in the same language as the User Question.
        """

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]

            content, usage = run_completion(
                messages=messages,
                custom_model=self.custom_model,
                custom_api_key=self.custom_api_key,
                temperature=0.1,
                max_tokens=2048,
                response_format={"type": "json_object"},
                return_usage=True
            )
            
            content = content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "{" in content and "}" in content:
                content = content[content.find("{"):content.rfind("}")+1]
                
            result = json.loads(content, strict=False)
            
            # --- BƯỚC TỐI ƯU: TỰ ĐỘNG INJECT TOÀN BỘ DỮ LIỆU Ở BACKEND ---
            # LLM chỉ cần tạo khung cấu hình (tiết kiệm token). Ta sẽ tiêm data thật vào đây.
            if result and result.get("should_visualize") and result.get("option"):
                chart_type = result.get("chart_type")
                # Các loại biểu đồ không hỗ trợ dataset tốt thì bỏ qua inject (map, gauge, treemap, heatmap)
                if chart_type in ["line", "bar", "pie", "scatter", "funnel", "area", "combo", "radar"]:
                    option = result.get("option", {})
                    # Xóa data bị LLM lỡ hardcode trong series (nếu có) để ép dùng dataset
                    if "series" in option and isinstance(option["series"], list):
                        for s in option["series"]:
                            if isinstance(s, dict):
                                s.pop("data", None)
                    # Tiêm toàn bộ query_results gốc vào dataset
                    option["dataset"] = {"source": query_results}
                    result["option"] = option
                    
            
            result["usage"] = usage
            return result
        except Exception as e:
            logger.error(f"Error in InsightAndChartAgent: {e}\nRaw content:\n{content}")
            return None
