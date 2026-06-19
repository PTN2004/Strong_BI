from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any


class GraphDatabase(ABC):
    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...

    @abstractmethod
    async def query(self, query: str, params: Optional[Dict[str, Any]]) -> Any:
        ...

    @abstractmethod
    async def create_vector_index(
        self,
        node_label: str,
        property_name: str,
        dimension: int,
        similarity_function: str = "euclidean",
    ) -> None:
        ...

    @abstractmethod
    async def create_index(self, node_label: str, property_name: str) -> None:
        ...

    @abstractmethod
    def is_connect(self) -> bool:
        ...

    @abstractmethod
    def format_vector(self, param_name: str) -> str:
        ...
    
    @abstractmethod
    def select_graph(self, graph_id: str) -> None:
        ...
    
    @abstractmethod
    async def list_graph(self) -> List[str]:
        ...
    
    @abstractmethod
    async def clear_graph(self) -> None:
        ...
    
    @property
    @abstractmethod
    def db_type(self) -> str:
        ...

    @property
    @abstractmethod
    def connection_string(self) -> str:
        ...

