from dataclasses import dataclass, field


@dataclass
class QueryRequest:
    question: str
    chat_history: list[str] = field(default_factory=list)
    result_history: list[str] = field(default_factory=list)
    instruction: str | None = None
    use_memory: bool = False
    use_user_rule: bool = True
    custom_api_key: str | None = None
    custom_model: str | None = None
