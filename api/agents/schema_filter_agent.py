import json
import logging
from typing import List, Dict, Any

from api.agents.utils import run_completion

logger = logging.getLogger(__name__)

class SchemaFilterAgent:
    def __init__(self, custom_api_key: str = None, custom_model: str = None, custom_api_base: str = None):
        self.custom_api_key = custom_api_key
        self.custom_model = custom_model
        self.custom_api_base = custom_api_base

    def filter_tables(self, user_query: str, candidate_tables: List[List[Any]]) -> List[str]:
        """
        Takes a list of candidate tables and uses LLM to select ONLY the ones necessary for the query.
        candidate_tables format: [table_name, description, foreign_keys, columns]
        """
        if not candidate_tables:
            return []
            
        if len(candidate_tables) <= 2:
            # No need to filter if it's already a very small set
            return [t[0] for t in candidate_tables]

        # Prepare a lightweight summary of candidate tables
        table_summaries = []
        for table in candidate_tables:
            table_name = table[0]
            description = table[1] if len(table) > 1 else ""
            table_summaries.append(f"- Table: {table_name}\n  Description: {description}")

        schema_text = "\n\n".join(table_summaries)

        system_prompt = """
        You are an expert Database Architect. Your job is to select the MINIMAL set of SQL tables strictly required to answer the user's query.
        
        Rules:
        1. You will be provided with a user query and a list of candidate tables with their descriptions.
        2. Select only the tables that are absolutely necessary to answer the query (including junction tables needed for joins).
        3. Do NOT include tables that are merely related but not required for the specific metrics or dimensions asked by the user.
        4. Return ONLY a valid JSON array of strings, where each string is a table name.
        5. Do not include markdown blocks like ```json. Just return the JSON array.
        """

        user_prompt = f"""
        User Query: {user_query}
        
        Candidate Tables:
        {schema_text}
        
        Return the JSON array of required table names:
        """

        try:
            content = run_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                custom_model=self.custom_model,
                custom_api_key=self.custom_api_key,
                temperature=0.0,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            # Robust JSON extraction
            content = content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "[" in content and "]" in content:
                content = content[content.find("["):content.rfind("]")+1]
                
            selected_tables = json.loads(content)
            
            # If the LLM returned a dict (e.g. {"tables": [...]}) instead of a list due to json_object constraints
            if isinstance(selected_tables, dict):
                for key in selected_tables:
                    if isinstance(selected_tables[key], list):
                        selected_tables = selected_tables[key]
                        break
            
            if not isinstance(selected_tables, list):
                logger.warning(f"SchemaFilterAgent returned non-list: {selected_tables}")
                return [t[0] for t in candidate_tables]
                
            # Ensure returned tables actually exist in the candidates
            candidate_names = {t[0] for t in candidate_tables}
            valid_selections = [t for t in selected_tables if t in candidate_names]
            
            logger.info(f"Schema Filter pruned {len(candidate_tables)} tables down to {len(valid_selections)}")
            return valid_selections
            
        except Exception as e:
            logger.error(f"Error in SchemaFilterAgent: {e}")
            # Fallback to returning all tables on error
            return [t[0] for t in candidate_tables]
