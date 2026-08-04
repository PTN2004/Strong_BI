"""
ChartAgent - Specialized agent for generating ECharts configurations from SQL results.
"""
import json
import logging
from typing import Any, Dict, List, Optional
from api.agents.utils import run_completion

logger = logging.getLogger(__name__)


class ChartAgent:
    
    def __init__(self, custom_api_key: Optional[str] = None, custom_model: Optional[str] = None, custom_api_base: Optional[str] = None):
        self.custom_api_key = custom_api_key
        self.custom_model = custom_model
        self.custom_api_base = custom_api_base

    def generate_chart_config(
        self,
        user_query: str,
        sql_query: str,
        query_results: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        if not query_results or len(query_results) < 2:
            return None
            
        columns = list(query_results[0].keys())
        sample_data = query_results[:5]
        
        system_prompt = """
        You are an elite Data Analyst and BI Expert. Your task is to analyze a dataset and the user's natural language query, determine if the data is suitable for visualization, and if so, generate a valid Apache ECharts option JSON config.

        Rules for generating the ECharts config:
        1. Return ONLY a valid JSON object. Do not include any markdown styling (like ```json), explanations, or surrounding text.
        2. The JSON object must be a valid ECharts option object that can be passed directly to ECharts.
        3. Use standard ECharts configuration options: 'title' (with 'text'), 'tooltip' (trigger: 'axis' or 'item'), 'legend', and the relevant coordinate systems.
        4. Populate the chart series and categories dynamically using the actual keys and values from the provided dataset. Ensure numeric columns are mapped to values.
        5. Choose the most appropriate chart type from the following:
           - 'line': For trends over time, dates, or sequential continuous categories.
           - 'bar': For comparing quantities across discrete categories (supports grouped/stacked bars if multiple numeric columns exist).
           - 'pie': For composition, distributions, or parts-of-a-whole relations (donut-style is also acceptable). Note: Pie charts do not use xAxis/yAxis.
           - 'scatter': For showing correlations or distributions of data points across two numeric dimensions (requires xAxis and yAxis of type 'value').
           - 'radar': For multi-dimensional comparisons of categories across 3+ different metrics (requires a 'radar' indicator list, and a 'radar' series).
           - 'funnel': For conversion pipelines, stages, or leakage analysis (e.g., Sales Funnel stages). Note: Funnel charts do not use xAxis/yAxis.
           - 'gauge': For displaying a single key metric or KPI percentage relative to a target or range (e.g. completion rate). Note: Gauge does not use xAxis/yAxis.
           - 'treemap': For nested/hierarchical category comparisons where sizes represent values.
        6. If the dataset contains only 1 row, is just a list of text names without numerical metrics, or is otherwise not suitable for visualization, return {"should_visualize": false}.
        7. If suitable, return the JSON starting with {"should_visualize": true, "chart_type": "<chart_type>", "option": { ... }}.
        """

        prompt = f"""
        User Question: {user_query}
        SQL Query: {sql_query}
        Dataset Columns: {columns}
        Total Rows: {len(query_results)}
        Dataset Sample (First 5 rows): {json.dumps(sample_data, ensure_ascii=False)}
        Full Dataset: {json.dumps(query_results, ensure_ascii=False)}

        Please analyze this and return the JSON object following the rules.
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
                max_tokens=4096,
                response_format={"type": "json_object"}
            )
            
            # Robust JSON extraction
            content = content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "{" in content and "}" in content:
                content = content[content.find("{"):content.rfind("}")+1]
                
            result = json.loads(content)
            if result.get("should_visualize") and "option" in result:
                return {
                    "chart_type": result.get("chart_type", "bar"),
                    "option": result.get("option")
                }
            return None
        except Exception as e:
            logger.error(f"Error in ChartAgent: {e}")
            return None
