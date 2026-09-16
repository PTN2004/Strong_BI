"""Visual Chart Agent (Specialized BI Visualization & ECharts Architect).
Focuses 100% on chart type selection, dimensional encoding, and robust Apache ECharts configuration.
"""

import json
import re
import logging
from typing import Any, Dict, List, Optional
from api.agents.utils import run_completion

logger = logging.getLogger(__name__)

VISUAL_CHART_SYSTEM_PROMPT = """You are a Principal BI Visualization Engineer and Apache ECharts Specialist.
Your sole mission is to analyze a dataset, its column types, and the user's inquiry, then determine if visualization is appropriate and construct a valid, high-aesthetic Apache ECharts configuration.

### STRICT RULES & OUTPUT FORMAT:
You MUST return a single, valid JSON object with NO markdown code fences.

JSON Structure:
{
  "should_visualize": true,
  "chart_type": "bar",
  "chart_title": "Tên biểu đồ trực quan",
  "option": { ... }
}

### CHART TYPE SELECTION LOGIC:
- "bar": Comparisons across categories, rankings, top/bottom entities.
- "line": Continuous time-series trends (dates, months, years).
- "area": Volume trends over time with areaStyle.
- "pie": Proportions and shares of a whole (< 7 slices).
- "combo": Dual Y-axes (e.g. Bar for Volume + Line for Growth %).
- "scatter": Correlation between 2 numeric metrics.
- "treemap": Hierarchical composition (category -> subcategory).
- "gauge": Single metric KPI completion rate (%) vs target.
- "map": Geographic distribution across Vietnam provinces or global countries.
- "should_visualize": Set to false ONLY if the query result is a single number, a simple confirmation, or unstructured text.

### ECHARTS OPTION RULES:
1. We will automatically inject `dataset.source` as an Array of Arrays format (first row is headers).
2. CRITICAL FOR MAPPING: Because the dataset will contain ALL queried columns, you MUST explicitly define `encode: { x: 'Column_Name', y: 'Column_Name' }` inside EVERY `series` object so ECharts knows exactly which columns to plot.
3. Color palette: Use modern, sleek colors like `['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4']`.
4. Include responsive tooltips `tooltip: { trigger: 'axis' }` (or `'item'` for pie), grid padding, and clean axis formatting.
5. DO NOT use Python format strings like `{value:,.0f}` in `formatter`. Only use standard ECharts string templates like `'{value}'` or `'{value} %'`. The frontend will handle complex number formatting.
6. Return strictly valid JSON. Do NOT include trailing commas. Do NOT include ```json markdown fences.
"""


class VisualChartAgent:
    """Agent dedicated strictly to generating optimal Apache ECharts visualizations."""

    def __init__(
        self,
        custom_api_key: Optional[str] = None,
        custom_model: Optional[str] = None,
        custom_api_base: Optional[str] = None,
    ):
        self.custom_api_key = custom_api_key
        self.custom_model = custom_model
        self.custom_api_base = custom_api_base

    def generate_chart(
        self,
        user_query: str,
        sql_query: str,
        query_results: List[Dict[str, Any]],
        schema_context: str = "",
    ) -> Dict[str, Any]:
        """
        Generate Apache ECharts visual configuration.
        """
        if not query_results or len(query_results) == 0:
            return {"should_visualize": False, "chart_type": "none", "option": None, "usage": {}}

        columns = list(query_results[0].keys())
        total_rows = len(query_results)
        sample_data = query_results if total_rows <= 50 else query_results[:15]

        prompt = f"""
User Question: {user_query}
Executed SQL: {sql_query}

Dataset Columns: {columns}
Total Records: {total_rows}
Sample Rows:
{json.dumps(sample_data, ensure_ascii=False, indent=2)}

Determine if this dataset should be visualized and construct the optimal Apache ECharts JSON config.
"""

        try:
            messages = [
                {"role": "system", "content": VISUAL_CHART_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]

            content, usage = run_completion(
                messages=messages,
                custom_model=self.custom_model,
                custom_api_key=self.custom_api_key,
                custom_api_base=self.custom_api_base,
                temperature=0.0,
                max_tokens=2048,
                response_format={"type": "json_object"},
                return_usage=True,
            )

            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            # Clean up potential trailing commas caused by LLM hallucination
            content = re.sub(r',\s*([}\]])', r'\1', content)

            result = json.loads(content)
            
            # Post-process & Inject full dataset if option is present
            if result.get("should_visualize") and result.get("option"):
                option = result["option"]
                chart_type = result.get("chart_type", "bar")
                
                # Convert List of Dicts to Array of Arrays for foolproof ECharts dataset mapping
                dataset_source = [columns]
                for row in query_results:
                    dataset_source.append([row.get(col) for col in columns])
                
                # Always force inject dataset to guarantee data presence
                if "dataset" not in option:
                    option["dataset"] = {}
                
                if isinstance(option["dataset"], dict):
                    option["dataset"]["source"] = dataset_source
                elif isinstance(option["dataset"], list) and len(option["dataset"]) > 0:
                    option["dataset"][0]["source"] = dataset_source

                # Strip out manually hallucinated data arrays to avoid conflicts with dataset
                if isinstance(option.get("xAxis"), dict):
                    option["xAxis"].pop("data", None)
                elif isinstance(option.get("xAxis"), list):
                    for ax in option["xAxis"]:
                        if isinstance(ax, dict):
                            ax.pop("data", None)
                            
                for s in option.get("series", []):
                    if isinstance(s, dict):
                        s.pop("data", None)

                # Fix Legend overlapping with X-axis by forcing it to the top
                if "legend" not in option:
                    option["legend"] = {}
                if isinstance(option["legend"], dict):
                    option["legend"]["top"] = 0
                    option["legend"]["bottom"] = "auto"
                
                # Ensure grid has enough padding to avoid clipping
                if "grid" not in option:
                    option["grid"] = {"containLabel": True, "bottom": 30, "top": 40}
                elif isinstance(option["grid"], dict):
                    option["grid"]["containLabel"] = True
                    if "bottom" not in option["grid"]:
                        option["grid"]["bottom"] = 30
                    if "top" not in option["grid"]:
                        option["grid"]["top"] = 40

            return {
                "should_visualize": result.get("should_visualize", False),
                "chart_type": result.get("chart_type", "bar"),
                "option": result.get("option"),
                "usage": usage or {},
            }
        except Exception as e:
            logger.error(f"Error in VisualChartAgent: {e}")
            return {
                "should_visualize": False,
                "chart_type": "none",
                "option": None,
                "usage": {},
            }
