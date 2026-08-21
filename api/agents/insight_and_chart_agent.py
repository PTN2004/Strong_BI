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
        schema_context: str
    ) -> Optional[Dict[str, Any]]:
        if not query_results or len(query_results) == 0:
            return None
            
        columns = list(query_results[0].keys())
        # ONLY take a sample of up to 5 rows to save tokens and prevent crashes
        sample_data = query_results[:5]
        
        system_prompt = """You are an elite Data Analyst and BI Expert. Your task is to analyze a dataset, the user's natural language query, and the SQL/Schema context, and then provide a textual insight and an Apache ECharts configuration.

You MUST return a single valid JSON object containing exactly the following keys:
1. "insight" (string): Provide a very brief and direct business insight summarizing the data. This system is used by Enterprise Software (DMS, CRM, etc.), so users prefer short, actionable, and straight-to-the-point answers rather than long conversational text.
   - Answer the user's question directly in 1-3 short sentences.
   - Highlight key takeaways (e.g., maximum/minimum values, totals, percentages) concisely.
   - **MANDATORY PRESCRIPTIVE RULES**:
     * If the data is about Staff/Sales KPI and some are underperforming (< 80%), you MUST include a short "Coaching Suggestion" (Gợi ý coaching).
     * If the data is about Stores/Shops with no orders or dropping revenue, you MUST flag them as "Needs immediate care" (Cần ưu tiên chăm sóc) and suggest a visit.
     * If you detect significant abnormalities (e.g., huge drop in revenue, very low performance), you MUST output a "Warning" (Cảnh báo).
   - Do NOT use filler words or lengthy explanations.
   - Keep it in the SAME language as the user's question.
2. "should_visualize" (boolean): True if the data can and should be visualized (e.g. trends, comparisons, proportions). False if it's just a single scalar number or irrelevant for charting.
3. "chart_type" (string): The best matching chart type: "line", "bar", "pie", "scatter", "radar", "funnel", or "map". (Use "map" if the user asks for geographical distribution, branches, locations, or regions).
4. "option" (object): A valid Apache ECharts option object.

### ECHARTS `option` STRICT RULES:
- If `chart_type` is "map", you MUST configure `series: [{ type: 'map', map: 'vietnam' (or 'world'), data: [...] }]`. The `data` array must contain objects like `{name: 'Hà Nội', value: 100}` matching standard province or country names.
- Use the `dataset` component approach where possible for non-map charts. Configure `dataset: { source: [...] }` if you generate data arrays, OR assume the frontend will inject the dataset and simply provide `dataset: {}` and use `encode` mapping in series. (For this application, assume the frontend uses the raw keys, so configure `xAxis`, `yAxis`, and `series` with `encode` or simple mappings).
- Make sure `xAxis.type` is 'category' or 'value' or 'time' based on the sample data.
- Do NOT hallucinate data. Map the axes directly to the actual column names from the "Dataset Columns".
- Ensure the JSON is 100% syntactically correct. Do NOT include markdown blocks like ```json or ```. Just raw JSON text.
"""

        prompt = f"""
        User Question: {user_query}
        SQL Query: {sql_query}
        Semantic & Schema Context:
        {schema_context}
        
        Dataset Columns: {columns}
        Total Rows Returned: {len(query_results)}
        Dataset Sample (First 5 rows ONLY): 
        {json.dumps(sample_data, ensure_ascii=False)}

        Analyze the sample and return the JSON object following the rules. Provide insights in the same language as the User Question.
        """

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]

            content = run_completion(
                messages=messages,
                custom_model=self.custom_model,
                custom_api_key=self.custom_api_key,
                temperature=0.1,
                max_tokens=2048,
                response_format={"type": "json_object"}
            )
            
            content = content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "{" in content and "}" in content:
                content = content[content.find("{"):content.rfind("}")+1]
                
            result = json.loads(content)
            return result
        except Exception as e:
            logger.error(f"Error in InsightAndChartAgent: {e}")
            return None
