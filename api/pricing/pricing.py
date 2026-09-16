import logging

logger = logging.getLogger(__name__)

# Pricing per 1,000,000 tokens (in USD)
# Structure: "model_name": (input_cost_per_1m, output_cost_per_1m)
MODEL_PRICING = {
    # OpenAI Models
    "gpt-4o": (5.0, 15.0),
    "gpt-4o-2024-05-13": (5.0, 15.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "gpt-4-turbo": (10.0, 30.0),
    "gpt-3.5-turbo": (0.50, 1.50),
    
    # Anthropic Models
    "claude-3-5-sonnet-20240620": (3.0, 15.0),
    "claude-3-opus-20240229": (15.0, 75.0),
    "claude-3-haiku-20240307": (0.25, 1.25),
    
    # Google Models
    "gemini-1.5-pro": (3.5, 10.5),
    "gemini-1.5-flash": (0.35, 1.05),
}

# Default fallback if model is unknown
DEFAULT_PRICING = (0.50, 1.50)

def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Calculate the total cost in USD for a given API call based on token counts.
    """
    if not model_name:
        return 0.0
        
    model_name = model_name.lower()
    
    # Try exact match first
    pricing = MODEL_PRICING.get(model_name)
    
    # Try partial match (e.g. if model_name is "gpt-4o" it matches "gpt-4o")
    if not pricing:
        for known_model, rates in MODEL_PRICING.items():
            if known_model in model_name:
                pricing = rates
                break
                
    if not pricing:
        logger.debug(f"Pricing for model {model_name} not found. Using default.")
        pricing = DEFAULT_PRICING
        
    input_cost_per_1m, output_cost_per_1m = pricing
    
    prompt_cost = (prompt_tokens / 1_000_000) * input_cost_per_1m
    completion_cost = (completion_tokens / 1_000_000) * output_cost_per_1m
    
    return prompt_cost + completion_cost
