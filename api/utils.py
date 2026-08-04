import json
from typing import List, Dict, Optional, TypedDict
from litellm import batch_completion, completion

from api.config import Config
from api.agents.utils import filter_thinking_process


class ForeignKeyInfo(TypedDict):
    constrain_name: str
    column: str
    refer_table: str
    refer_column: str


class ColumnInfo(TypedDict):
    key: str
    type: str
    null: str
    description: str
    default: Optional[str]
    sample_value: List[str]


class TableInfo(TypedDict):
    description: str
    columns: Dict[str, ColumnInfo]
    foreign_key: List[ForeignKeyInfo]
    col_descriptions: List[str]


def create_combined_description(
    table_info: Dict[str, TableInfo], batch_size: int = 10
) -> Dict[str, TableInfo]:

    if not isinstance(table_info, dict):
        raise TypeError("table_info must be a dictionary keyed by table name.")
    
    messages_list = []
    table_key = []
    
    system_prompt = (
        "You are a database table description generator. "
        "Generate ONE concise sentence starting with the table name, "
        "describing what the table stores, using present tense. "
        "Do not add explanations. You MUST enclose your final answer inside <description> tags. "
        "For example: <description>The table users stores...</description>"
    )
    
    user_prompt = (
        "Table Name: {table_name}\n"
        "Table Schema: {table_prop}\n"
        "Provide a concise description of this table."
    )
    
    for table_name, table_prop in table_info.items():
        table_prop = table_prop.copy()
        table_prop.pop("col_descriptions", None)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user", 
                "content": user_prompt.format(
                    table_name=table_name,
                    table_prop=json.dumps(table_prop)
                )
            }
        ]
        
        messages_list.append(messages)
        table_key.append(table_name)
        
    
    for batch in range(0, len(messages_list), batch_size):
        batch_message = messages_list[batch : batch + batch_size]
        response = batch_completion(
            model=Config.COMPLETION_MODEL,
            messages=batch_message,
            temperature=0.0,

        )
        
        for offset, batch_response in enumerate(response):
            table_index = batch + offset
            if table_index >= len(table_key):
                break
            
            table_name = table_key[table_index]
            if isinstance(batch_response, Exception):
                table_info[table_name]["description"] = table_name
                
            else:
                msg_content = batch_response.choices[0].message["content"]
                if msg_content:
                    import re
                    match = re.search(r'<description>(.*?)</description>', msg_content, flags=re.DOTALL | re.IGNORECASE)
                    if match:
                        msg_content = match.group(1)
                    else:
                        msg_content = filter_thinking_process(msg_content)
                content = msg_content.strip() if msg_content else table_name
                table_info[table_name]["description"] = content
                
    return table_info


def generate_db_description(
    db_name: str,
    table_names: List[str],
    temperature: float = 0.5,
    max_tokens: int = 1024,
) -> str:
    
    if not isinstance(db_name, str):
        raise TypeError("database_name must be a string.")

    if not isinstance(table_names, list):
        raise TypeError("table_names must be a list of strings.")

    if not all(isinstance(table, str) for table in table_names):
        raise ValueError("All items in table_names must be strings.")

    if not table_names:
        return f"{db_name} is a database with no tables."

    if len(table_names) == 1:
        tables_formatted = table_names[0]
    elif len(table_names) == 2:
        tables_formatted = " and ".join(table_names)
    else:
        tables_formatted = ", ".join(table_names[:-1]) + f", and {table_names[-1]}"

    prompt = (
        f"You are a Data Architect. Describe the business domain of the database named '{db_name}' "
        f"based on these tables: {tables_formatted}.\n\n"
        f"You MUST enclose your final answer inside <description> tags. "
        f"For example: <description>This database stores e-commerce information.</description>"
    )

    response = completion(
        model=Config.COMPLETION_MODEL,
        messages=[
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        n=1,
        stop=None,
    )
    raw_content = response.choices[0].message["content"]
    if raw_content:
        import re
        match = re.search(r'<description>(.*?)</description>', raw_content, flags=re.DOTALL | re.IGNORECASE)
        if match:
            description = match.group(1).strip()
        else:
            description = filter_thinking_process(raw_content).strip()
    else:
        description = f"Database containing {len(table_names)} tables."
        
    return description
        
    
    