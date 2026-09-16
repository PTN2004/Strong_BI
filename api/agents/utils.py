import json
import os
import re
from typing import Any, Dict, List

from litellm import completion
from api.config import Config, get_dynamic_api_key


def run_completion(messages: List[Dict[str, str]], custom_model: str = None,
                   custom_api_key: str = None, custom_api_base: str = None, 
                   return_usage: bool = False, **kwargs) -> str | tuple[str, dict]:

    model = custom_model if custom_model else Config.COMPLETION_MODEL

    completion_args = {
        "model": model,
        "messages": messages,
        "top_p": 1,
        **kwargs,
    }

    if custom_api_base:
        completion_args["api_base"] = custom_api_base

    if custom_api_key:
        completion_args["api_key"] = custom_api_key
    else:
        if model.startswith("vllm/") or model.startswith("custom_openai/"):
            api_base = os.getenv("VLLM_API_BASE") or os.getenv("OPENAI_API_BASE")
            if api_base:
                completion_args["api_base"] = api_base.strip()
            api_key = os.getenv("VLLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "none"
            completion_args["api_key"] = api_key.strip()
        elif model.startswith("ollama/"):
            api_base = os.getenv("OLLAMA_API_BASE")
            if api_base:
                completion_args["api_base"] = api_base.strip()
        elif model.startswith("openai/") or model.startswith("gemini/") or model.startswith("openrouter/"):
            api_base = os.getenv("OPENAI_API_BASE")
            if api_base and model.startswith("openai/"):
                completion_args["api_base"] = api_base.strip()
            
            dynamic_key = get_dynamic_api_key(model)
            if dynamic_key:
                completion_args["api_key"] = dynamic_key

    # Nếu key là "none" (placeholder) hoặc thiếu, mà không có api_base tuỳ chỉnh -> Không gọi được API ngoài
    current_key = completion_args.get("api_key")
    if (not current_key or current_key == "none") and not completion_args.get("api_base"):
        import logging
        logging.warning(f"No valid API key found for {model}. Falling back to system default {Config.COMPLETION_MODEL}")
        
        # Fallback về system default model
        model = Config.COMPLETION_MODEL
        completion_args["model"] = model
        
        # Resolve lại api key cho system default model
        if model.startswith("vllm/") or model.startswith("custom_openai/"):
            api_base = os.getenv("VLLM_API_BASE") or os.getenv("OPENAI_API_BASE")
            if api_base:
                completion_args["api_base"] = api_base.strip()
            api_key = os.getenv("VLLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "none"
            completion_args["api_key"] = api_key.strip()
        elif model.startswith("ollama/"):
            api_base = os.getenv("OLLAMA_API_BASE")
            if api_base:
                completion_args["api_base"] = api_base.strip()
        elif model.startswith("openai/") or model.startswith("gemini/") or model.startswith("openrouter/"):
            api_base = os.getenv("OPENAI_API_BASE")
            if api_base and model.startswith("openai/"):
                completion_args["api_base"] = api_base.strip()
            
            dynamic_key = get_dynamic_api_key(model)
            if dynamic_key:
                completion_args["api_key"] = dynamic_key

    completion_args["timeout"] = 120

    result = completion(**completion_args)
    content = filter_thinking_process(result.choices[0].message.content)
    
    if return_usage:
        usage = {}
        if hasattr(result, "usage") and result.usage:
            usage = {
                "prompt_tokens": getattr(result.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(result.usage, "completion_tokens", 0),
                "total_tokens": getattr(result.usage, "total_tokens", 0),
            }
        return content, usage
    return content


def filter_thinking_process(text: str) -> str:
    if not text:
        return ""
        
    if '</think>' in text.lower():
        text = re.sub(r'^.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    if '<think>' in text.lower():
        text = re.sub(r'<think>.*$', '', text, flags=re.DOTALL | re.IGNORECASE)
        
    text = re.sub(r'Thinking Process:.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    return text.strip()


class BaseAgent:  

    def __init__(self, queries_history: list = None, result_history: list = None,
                 custom_api_key: str = None, custom_model: str = None, custom_api_base: str = None):
        if not result_history or not queries_history:
            self.messages = []
        else:
            self.messages = []
            for query, result in zip(queries_history[:-1], result_history):
                self.messages.append({"role": "user", "content": query})
                clean_result = filter_thinking_process(result)
                self.messages.append({"role": "assistant", "content": clean_result})

        self.custom_api_key = custom_api_key
        self.custom_model = custom_model
        self.custom_api_base = custom_api_base


def parse_response(response: str) -> Dict[str, Any]:
    response = filter_thinking_process(response)
    
    try:
        json_blocks = []
        depth = 0
        start_idx = None
        
        for i, char in enumerate(response):
            if char == '{':
                if depth == 0:
                    start_idx = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and start_idx is not None:
                    json_blocks.append(response[start_idx:i+1])
                    start_idx = None

        # Try to parse JSON blocks from last to first (prefer the corrected version)
        for json_str in reversed(json_blocks):
            try:
                analysis = json.loads(json_str)
                # Validate it has required fields
                if "is_sql_translatable" in analysis and "sql_query" in analysis:
                    return analysis
            except json.JSONDecodeError:
                continue

        # Fallback to original method if block parsing fails
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        json_str = response[json_start:json_end]
        analysis = json.loads(json_str)
        return analysis
    except (json.JSONDecodeError, ValueError) as e:
        # Fallback if JSON parsing fails
        return {
            "is_sql_translatable": False,
            "confidence": 0,
            "explanation": f"Failed to parse response: {str(e)}",
            "error": str(response),
        }
