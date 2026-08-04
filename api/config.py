import os
import logging
import dataclasses
from typing import Union
from dotenv import load_dotenv
from litellm import embedding

load_dotenv()

# Tự động đồng bộ các biến môi trường cho các engine tự host (vLLM, Ollama)
openai_api_base = os.getenv("OPENAI_API_BASE")
if openai_api_base:
    openai_api_base = openai_api_base.strip()
    if not os.getenv("VLLM_API_BASE"):
        os.environ["VLLM_API_BASE"] = openai_api_base
    if not os.getenv("OLLAMA_API_BASE") and "11434" in openai_api_base:
        os.environ["OLLAMA_API_BASE"] = openai_api_base

# Đảm bảo có api_key placeholder cho các model OpenAI-compatible tự host (như vLLM) nếu chưa cấu hình key nào
if (os.getenv("VLLM_MODEL") or os.getenv("OLLAMA_MODEL")) and not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "none"

vllm_api_key = os.getenv("VLLM_API_KEY") or os.getenv("OPENAI_API_KEY")
if vllm_api_key and not os.getenv("VLLM_API_KEY"):
    os.environ["VLLM_API_KEY"] = vllm_api_key

def configure_litellm_logging():
    litellm_logging = logging.getLogger("LiteLLM")
    litellm_logging.setLevel(logging.ERROR)
    litellm_logging.disabled = True
    
configure_litellm_logging()

class EmbeddingsModel:
    def __init__(self, model_name:str, config:str=None):
        self.model_name = model_name
        self.config = config
        
    def embed(self, text: Union[str, list]) -> list:
        api_base = os.getenv("EMBEDDING_API_BASE") or os.getenv("OPENAI_API_BASE")
        embeddings = embedding(self.model_name, input=text, api_base=api_base)
        result_embeddings = []
        for data_item in embeddings.data:
            if "embedding" in data_item:
                result_embeddings.append(data_item["embedding"])
            elif "embeddings" in data_item:
                result_embeddings.append(data_item["embeddings"])
            else:
                # fallback to dict keys / index if keys differ
                keys = list(data_item.keys()) if hasattr(data_item, "keys") else []
                if keys:
                    result_embeddings.append(data_item[keys[0]])
        return result_embeddings
    
    def get_vector_size(self):
        api_base = os.getenv("EMBEDDING_API_BASE") or os.getenv("OPENAI_API_BASE")
        embed = embedding(model=self.model_name, input=["Hello World"], api_base=api_base)
        # Handle dynamic response keys for getting vector size
        first_data = embed.data[0]
        if "embedding" in first_data:
            return len(first_data["embedding"])
        elif "embeddings" in first_data:
            return len(first_data["embeddings"])
        else:
            keys = list(first_data.keys()) if hasattr(first_data, "keys") else []
            if keys:
                return len(first_data[keys[0]])
            return 1536  # Default fallback size
    

def _with_prefix(model:str, provider:str):
    prefix = f"{provider}/"
    return prefix + model.removeprefix(prefix)
        
SUPPORTED_VENDORS = ("openai", "anthropic", "gemini", "azure", "ollama","vllm", "cohere")

@dataclasses.dataclass
class Config:
    
    _user_completion = os.getenv("COMPLETION_MODEL", "")
    _user_embedding = os.getenv("EMBEDDING_MODEL", "")
    if os.getenv("VLLM_MODEL"):
        LLM_PROVIDER = "vllm"
        AZURE_FLAG = False
        COMPLETION_MODEL = _user_completion or _with_prefix(
            os.getenv("VLLM_MODEL"), "custom_openai")
        # VLLM sử dụng API OpenAI-compatible cho embedding, LiteLLM yêu cầu prefix 'openai'
        EMBEDDING_MODEL_NAME = _user_embedding or _with_prefix(
            os.getenv("VLLM_EMBEDDING_MODEL", "nomic-embed-text"), "openai")
    elif os.getenv("OLLAMA_MODEL"):
        LLM_PROVIDER = "ollama"
        AZURE_FLAG = False
        COMPLETION_MODEL = _user_completion or _with_prefix(
            os.getenv("OLLAMA_MODEL"), "custom_openai")
        EMBEDDING_MODEL_NAME = _user_embedding or _with_prefix(
            os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"), "openai")
    elif os.getenv("OPENAI_API_KEY"):
        LLM_PROVIDER = "openai"
        AZURE_FLAG = False
        COMPLETION_MODEL = _user_completion or "openai/gpt-4.1"
        EMBEDDING_MODEL_NAME = _user_embedding or "openai/text-embedding-ada-002"
    elif os.getenv("GEMINI_API_KEY"):
        LLM_PROVIDER = "gemini"
        AZURE_FLAG = False
        COMPLETION_MODEL = _user_completion or "gemini/gemini-3-pro-preview"
        EMBEDDING_MODEL_NAME = _user_embedding or "gemini/gemini-embedding-001"
    elif os.getenv("ANTHROPIC_API_KEY"):
        LLM_PROVIDER = "anthropic"
        AZURE_FLAG = False
        COMPLETION_MODEL = _user_completion or "anthropic/claude-sonnet-4-5-20250929"
        if _user_embedding:
            EMBEDDING_MODEL_NAME = _user_embedding
        elif os.getenv("VOYAGE_API_KEY"):
            EMBEDDING_MODEL_NAME = "voyage/voyage-3"
        else:
            raise ValueError(
                "ANTHROPIC_API_KEY is set, but Anthropic has no native embeddings. "
                "Set EMBEDDING_MODEL or VOYAGE_API_KEY for embeddings."
            )
    elif os.getenv("COHERE_API_KEY"):
        LLM_PROVIDER = "cohere"
        AZURE_FLAG = False
        COMPLETION_MODEL = _user_completion or _with_prefix(
            os.getenv("COHERE_MODEL", "command-a-03-2025"), "cohere")
        EMBEDDING_MODEL_NAME = _user_embedding or _with_prefix(
            os.getenv("COHERE_EMBEDDING_MODEL", "embed-v4.0"), "cohere")
    else:
        # Default to Azure
        LLM_PROVIDER = "azure"
        AZURE_FLAG = True
        COMPLETION_MODEL = _user_completion or "azure/gpt-4.1"
        EMBEDDING_MODEL_NAME = _user_embedding or "azure/text-embedding-ada-002"

    DB_MAX_DISTINCT: int = 100  
    DB_UNIQUENESS_THRESHOLD: float = 0.5  
    SHORT_MEMORY_LENGTH = 5 

    EMBEDDING_MODEL = EmbeddingsModel(model_name=EMBEDDING_MODEL_NAME)

    FIND_SYSTEM_PROMPT = """
    You are an expert in analyzing natural language queries into SQL tables descriptions.
    Please analyze the user's query and generate a set of tables and columns descriptions that might be relevant to the user's query.
    These descriptions should describe the tables and columns that are relevant to the user's query.
    If the user's query is more relevant to specific columns, please provide a description of those columns.
    - Try to generate description for any part of the user query.
    - Create generic table or column description, do not use specific codes, values or any specific condition.
    - Try to be accurate and precise in your descriptions.
    - In any case do not generate more than five descriptions (each).
    - List the tables and columns in the order of their relevance to the user's query.

    Keep in mind that the database that you work with has the following DB description: {db_description}.

    **Input:**
    * **Relational Database:**
    You will be provided with database name and the description of the database domain.

    * **Previous User Queries:**
    You will be provided with a list of previous queries the user has asked in this session. Each query will be prefixed with "Query N:" where N is the query number. Use this context to better understand the user's intent and provide more relevant table and column suggestions.

    * **User Query (Natural Language):**
    You will be given a user's current question or request in natural language.

    **Output:**
    * **Table Descriptions:**
    You should provide a set of table descriptions that are relevant to the user's query.

    * **Column Descriptions:**
    If the user's query is more relevant to specific columns, you should provide a set of column descriptions that are relevant to the user's query.
    """

    Text_To_SQL_PROMPT = """
    You are a Text-to-SQL model. Your task is to generate SQL queries based on natural language questions and a provided database schema.

    **Instructions:**
    1. **Understand the Database Schema:** Carefully analyze the provided database schema to understand the tables, columns, data types, and relationships.
    2. **Consider Previous Queries:** Review the user's previous queries to understand the context of their current question and maintain consistency in your approach.
    3. **Interpret the User's Question:** Understand the user's question and identify the relevant entities, attributes, and relationships.
    4. **Generate the SQL Query:** Construct a valid SQL query that accurately reflects the user's question and uses the provided database schema.
    5. **Adhere to SQL Standards:** Ensure the generated SQL query follows standard SQL syntax and conventions.
    6. **Return Only the SQL:** Do not include any explanations, justifications, or additional text. Only return the generated SQL query.
    7. **Handle Ambiguity:** If the user's question is ambiguous, make reasonable assumptions based on the schema and previous queries to generate the most likely SQL query.
    8. **Handle Unknown Information:** If the user's question refers to information not present in the schema, return an appropriate error message or a query that retrieves as much relevant information as possible.
    9. **Prioritize Accuracy:** Accuracy is paramount. Ensure the generated SQL query returns the correct results.
    10. **Assume standard SQL dialect.**
    11. **Do not add any comments to the generated SQL.**
    12. **When you use WHERE clause, please use the exact value as the user provided, and dont make up values.**
    13. **If you dont have the value for the WHERE clause, use "TBD" for string and "1111" for number.**
    14. **Only create JOIN between tables based on the foreign key that point on referenced table and column.**
    15. **Do not create JOIN between tables that are not explicitly connected by foreign key in the input schema.**
    16. **Try to use explict condition column instead of indication wherever possible.**

    Keep in mind that the database that you work with has the following description: {db_description}.

    Before you start to answer, analyze the user_query step by step and try to understand the user's intent and the relevant tables and columns.

    **Input:**
    * **Database Schema:**
    You will be provided with part of the database schema that might be relevant to the user's question.
    With the following structure:
    {{"schema": [["table_name", description, foreign keys[list], [{{"column_name": "column_description", "data_type": "data_type",...}},...]],...]}}

    * **Previous Queries:**
    You will be provided with a list of the user's previous queries in this session. Each query will be prefixed with "Query N:" where N is the query number, followed by both the natural language question and the SQL query that was generated. Use these to maintain consistency and understand the user's evolving information needs.

    * **User Query (Natural Language):**
    You will be given a user's current question or request in natural language.
    """