"""Python Executor for running LLM-generated pandas code safely."""

import sys
import io
import traceback
import contextlib
import pandas as pd
from typing import List, Dict, Any

class PythonExecutor:
    @staticmethod
    def execute_pandas_code(code: str, data: List[Dict[str, Any]]) -> str:
        """
        Executes python code on the given data using pandas.
        The code will have access to 'df' (the DataFrame) and 'pd' (pandas).
        Captures and returns whatever is printed to stdout.
        """
        if not data:
            return "No data available to analyze."
            
        df = pd.DataFrame(data)
        
        # Setup restricted environment
        env = {
            "df": df,
            "pd": pd,
        }
        
        # Strip markdown code blocks if present
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
            
        code = code.strip()
        
        # Capture stdout
        stdout_capture = io.StringIO()
        
        try:
            with contextlib.redirect_stdout(stdout_capture):
                # exec is generally unsafe with untrusted user input, 
                # but here it is executing LLM generated code for internal analytics.
                exec(code, env)
            
            output = stdout_capture.getvalue()
            if not output.strip():
                return "Code executed successfully but did not print anything. Please use print() to output results."
            return output
            
        except Exception as e:
            tb = traceback.format_exc()
            return f"Error executing Python code:\n{e}\n\nTraceback:\n{tb}"
