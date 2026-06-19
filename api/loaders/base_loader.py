from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Any, TYPE_CHECKING


class BaseLoader(ABC):

    @staticmethod
    @abstractmethod
    async def load(_graph_id: str, _data) -> AsyncGenerator[tuple[bool, str], None]:
        if TYPE_CHECKING: 
            yield True, ""

    @staticmethod
    @abstractmethod
    def _execute_sample_query(
        cursor, table_name: str, col_name: str, sample_size: int = 3
    ) -> List[Any]:
        ...
        
    @classmethod
    def extract_sample_values_for_column(
        cls, cursor, table_name: str, col_name: str, sample_size: int = 3
    ) -> List[Any]:
        sample_values = cls._execute_sample_query(cursor, table_name, col_name, sample_size)

        if sample_values:
            first_val = sample_values[0]
            if isinstance(first_val, (str, int, float)):
                return [str(v) for v in sample_values]

        return []
