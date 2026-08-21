import threading
import logging
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

class DatabasePoolManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabasePoolManager, cls).__new__(cls)
                cls._instance.engines = {}
            return cls._instance

    def _normalize_url(self, db_url: str) -> str:
        """
        Normalizes database URLs to ensure they use proper SQLAlchemy dialects.
        Example: postgres:// -> postgresql+psycopg2://
                 mysql:// -> mysql+pymysql://
        """
        if db_url.startswith("postgres://"):
            return db_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif db_url.startswith("postgresql://"):
            return db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        elif db_url.startswith("mysql://"):
            return db_url.replace("mysql://", "mysql+pymysql://", 1)
        return db_url

    def get_engine(self, db_url: str):
        """
        Returns a cached SQLAlchemy engine for the given URL, creating it if necessary.
        Uses QueuePool for efficient connection reuse.
        """
        normalized_url = self._normalize_url(db_url)
        
        with self._lock:
            if normalized_url not in self.engines:
                logger.info(f"Creating new Connection Pool for {normalized_url.split('@')[-1]}")
                # For SQLite, we might need different pool settings or no pooling
                if normalized_url.startswith("sqlite"):
                    self.engines[normalized_url] = create_engine(normalized_url)
                else:
                    self.engines[normalized_url] = create_engine(
                        normalized_url,
                        poolclass=QueuePool,
                        pool_size=5,
                        max_overflow=10,
                        pool_pre_ping=True, # Verifies connection is alive before checking out
                        pool_recycle=1800   # Recycle connections every 30 minutes
                    )
            return self.engines[normalized_url]

# Global singleton instance
pool_manager = DatabasePoolManager()
