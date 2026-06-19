from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class QueryMetadata:
    confidence: float = 0.0
    excution_time: float = 0.0
    is_valid: bool = True
    is_destructive: bool = False  # If have create, insert, delete
    requires_confirmation: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
 
    
@dataclass
class QueryAnalyst:
    missing_infomation: str = ""
    ambiguities:str = ""
    explantation:str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
  
    
@dataclass
class QueryResult:
    sql_result: str
    results:list[dict[str]]
    ai_response: str
    metadata: QueryMetadata = field(default_factory=QueryMetadata)
    analyst: QueryAnalyst = field(default_factory=QueryAnalyst)
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        result = {
           "sql_result" : self.sql_result,
           "results": self.results,
           "ai_response": self.ai_response,
        }
        result.update(self.metadata.to_dict())
        result.update(self.analyst.to_dict())
        
        return result
    
    @property
    def confidence(self) -> float:
        return self.metadata.confidence
    
    @property
    def excute_time(self) -> float:
        return self.metadata.excution_time
    
    @property
    def is_destructive(self) -> bool:
        return self.metadata.is_destructive
    
    @property
    def is_valid(self) -> bool:
        return self.metadata.is_valid
    
    @property
    def requires_confirmation(self) -> bool:
        return self.metadata.requires_confirmation
    
    @property
    def missing_infomation(self) -> str:
        return self.analyst.missing_infomation
    
    @property
    def ambiguities(self) -> str:
        return self.analyst.ambiguities
    
    @property
    def expplaintion(self) -> str:
        return self.analyst.explantation


@dataclass
class SchemaResult:
    nodes: list[dict[str, Any]]
    links: list[dict[str, str]]
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)        
  
    
@dataclass
class DatabaseConnection:
    database_id: str
    cuccess: bool
    table_load: int = 0
    message: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    

@dataclass
class RefreshResult:
    success: bool
    message: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
class ChatMessage:
    questions: str
    sql_query: str = ""
    result: str = ""
    