"""Data Analyst Agent using Code Interpreter (pandas) for generating business insights."""

import json
from typing import List, Dict, Any
from .utils import BaseAgent, run_completion
from .python_executor import PythonExecutor
from api.core.ai_tracer import save_ai_trace

CODE_GENERATION_PROMPT = """
You are a Senior Data Analyst. You need to write Python code using `pandas` to analyze the query results.
You are given a pandas DataFrame `df` containing the results of a SQL query.

User's Question: {QUESTION}
DataFrame Columns: {COLUMNS}

Write Python code to compute insights (e.g., trends, totals, outliers).
- Use `print()` to output your findings.
- The output of your `print()` statements will be passed to another agent to write the final report.
- DO NOT wrap the code in ```python blocks or any markdown fences, just return the raw python code.
- DO NOT output any explanation text, ONLY valid python code.
- Assume `df` and `pd` are already available.

Example:
print("Total Revenue:", df['revenue'].sum())
print("Top 3 products:\\n", df.nlargest(3, 'revenue')[['name', 'revenue']])
"""

REPORT_GENERATION_PROMPT = """
You are a Senior Business Analyst. You must generate a highly professional Business Insights report based on the data analysis results.

User's Question: {QUESTION}

Analysis Execution Output: 
{ANALYSIS_OUTPUT}

Instructions:
1. Write a final Markdown response answering the user's question based on the Analysis Output.
2. Structure your response into:
   - **Tóm tắt (Summary)**: Direct answer to the question.
   - **Phân tích chi tiết (Key Insights)**: Use bullet points to list the findings from the execution output.
   - **Đề xuất (Recommendations)**: Actionable advice based on the insights.
3. Be professional, concise, and do not mention the Python code or execution process. Just present the insights.
4. Reply in Vietnamese.
"""

class DataAnalystAgent(BaseAgent):
    def analyze_and_report(self, user_question: str, query_results: List[Dict[str, Any]]) -> str:
        if not query_results:
            return "Không có dữ liệu nào trả về cho câu hỏi này."
            
        columns = list(query_results[0].keys())
        
        # Step 1: Generate Code with Self-Healing Loop
        max_retries = 3
        analysis_output = ""
        code_response = ""
        
        # Initial prompt
        code_prompt = CODE_GENERATION_PROMPT.format(
            QUESTION=user_question,
            COLUMNS=columns
        )
        self.messages.append({"role": "user", "content": code_prompt})
        
        for attempt in range(max_retries):
            code_response = run_completion(
                self.messages, self.custom_model, self.custom_api_key, self.custom_api_base, temperature=0.1
            )
            
            # Execute Code
            analysis_output = PythonExecutor.execute_pandas_code(code_response, query_results)
            
            save_ai_trace(f"DataAnalystAgent_Step1_Attempt{attempt+1}", {"prompt": self.messages[-1]["content"]}, {"code": code_response, "execution_output": analysis_output})
            
            # Check for errors
            if "Error executing Python code:" in analysis_output or "SyntaxError:" in analysis_output or "Exception:" in analysis_output:
                if attempt < max_retries - 1:
                    # Feed error back to the model
                    error_msg = f"Your previous code failed with this error:\n{analysis_output}\nPlease fix the code and return ONLY the corrected Python code."
                    self.messages.append({"role": "assistant", "content": code_response})
                    self.messages.append({"role": "user", "content": error_msg})
                    continue
            
            # If successful or max retries reached, break
            break
        
        # Clear messages and prepare for Step 2 (Report Generation)
        self.messages = [{"role": "system", "content": "You are a professional Business Analyst."}]
            
        report_prompt = REPORT_GENERATION_PROMPT.format(
            QUESTION=user_question,
            ANALYSIS_OUTPUT=analysis_output
        )
        self.messages.append({"role": "user", "content": report_prompt})
        
        # Step 2: Generate Report
        report_response = run_completion(
            self.messages, self.custom_model, self.custom_api_key, self.custom_api_base, temperature=0.3
        )
        
        save_ai_trace("DataAnalystAgent_Step2", {"prompt": report_prompt}, {"report": report_response})
        
        return report_response
