import json
from .utils import BaseAgent, parse_response, run_completion


VALIDATOR_PROMPT = """
You are a Data Analyst and QA Expert. Your job is to semantically validate if the results returned by a SQL query actually answer the user's question logically and correctly based on the requested business logic.

You are given:
1. User's question: {QUESTION}
2. SQL Query executed: {SQL_QUERY}
3. Data Results (first few rows): {DATA_RESULTS}

Guidelines for Validation:
1. Did the SQL query return the correct grain of data requested? (e.g., if the user asked for "total sales", did it return a single sum, or did it return all individual orders?)
2. Did the SQL calculate the correct metric? (e.g., if asked for "profit margin", did it just return "revenue"?)
3. If the results are empty `[]`, does the SQL look logically correct but there's just no data, or is there an obvious logic flaw (like an impossible WHERE condition)?

Output Format:

If the data perfectly answers the question semantically (or if it's empty but the SQL is logically sound):
{{
    "status": "Valid",
    "reason": "Brief explanation of why it is valid.",
    "feedback": ""
}}

If the SQL is logically flawed or the data returned does not match the user's semantic intent:
{{
    "status": "Invalid",
    "reason": "Brief explanation of the flaw.",
    "feedback": "Specific instruction for the SQL generator to fix the query (e.g., 'You grouped by day instead of month', 'You selected all rows instead of calculating the SUM')."
}}

Output ONLY valid JSON.
"""


class ValidatorAgent(BaseAgent):
    def validate(self, user_question: str, sql_query: str, query_results: list) -> dict:
        # truncate results to avoid blowing up context window
        preview_results = query_results[:5] if isinstance(query_results, list) else query_results
        
        self.messages.append(
            {
                "role": "user",
                "content": VALIDATOR_PROMPT.format(
                    QUESTION=user_question,
                    SQL_QUERY=sql_query,
                    DATA_RESULTS=json.dumps(preview_results, default=str),
                ),
            }
        )

        answer, usage = run_completion(
            self.messages, self.custom_model, self.custom_api_key, self.custom_api_base, temperature=0, return_usage=True
        )
        self.messages.append({"role": "assistant", "content": answer})
        res = parse_response(answer)
        res["usage"] = usage
        return res
