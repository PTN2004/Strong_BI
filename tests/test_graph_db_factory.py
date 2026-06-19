"""Unit tests for graph database factory."""

import os
import pytest
from api.graph_db import GraphDatabaseFactory


class TestGraphDatabaseFactory:
    """Test suite for GraphDatabaseFactory."""

    def test_create_falkordb_from_url(self, monkeypatch):
        """Test creating FalkorDB instance from URL."""
        monkeypatch.setenv("FALKORDB_URL", "redis://localhost:6379/0")
        monkeypatch.delenv("NEO4J_URL", raising=False)

        db = GraphDatabaseFactory.create()
        assert db.db_type == "falkordb"
        assert "localhost" in db.connection_string
        assert "6379" in db.connection_string

    def test_create_falkordb_from_env_vars(self, monkeypatch):
        """Test creating FalkorDB instance from individual environment variables."""
        monkeypatch.delenv("FALKORDB_URL", raising=False)
        monkeypatch.delenv("NEO4J_URL", raising=False)
        monkeypatch.setenv("FALKORDB_HOST", "redis-host")
        monkeypatch.setenv("FALKORDB_PORT", "6380")
        monkeypatch.setenv("FALKORDB_DB", "1")

        db = GraphDatabaseFactory.create()
        assert db.db_type == "falkordb"
        assert db.connection_string == "redis-host:6380/1"

    def test_get_db_type_neo4j(self, monkeypatch):
        """Test get_db_type returns neo4j when configured."""
        monkeypatch.setenv("NEO4J_URL", "bolt://localhost:7687")
        monkeypatch.delenv("FALKORDB_URL", raising=False)

        assert GraphDatabaseFactory.get_db_type() == "neo4j"

    def test_get_db_type_falkordb(self, monkeypatch):
        """Test get_db_type returns falkordb by default."""
        monkeypatch.delenv("NEO4J_URL", raising=False)
        monkeypatch.setenv("FALKORDB_URL", "redis://localhost:6379/0")

        assert GraphDatabaseFactory.get_db_type() == "falkordb"

    def test_parse_redis_url_default_port(self):
        """Test parsing Redis URL with default port."""
        host, port, db = GraphDatabaseFactory._parse_redis_url(
            "redis://myhost:6379/2")
        assert host == "myhost"
        assert port == 6379
        assert db == 2

    def test_parse_redis_url_custom_port(self):
        """Test parsing Redis URL with custom port."""
        host, port, db = GraphDatabaseFactory._parse_redis_url(
            "redis://redis-server:6380/1")
        assert host == "redis-server"
        assert port == 6380
        assert db == 1

    def test_parse_redis_url_no_db_defaults_to_zero(self):
        """Test parsing Redis URL without db defaults to 0."""
        host, port, db = GraphDatabaseFactory._parse_redis_url(
            "redis://localhost:6379")
        assert host == "localhost"
        assert port == 6379
        assert db == 0

    def test_parse_redis_url_invalid_format(self):
        """Test parsing invalid Redis URL raises ValueError."""
        with pytest.raises(ValueError, match="Invalid Redis URL"):
            GraphDatabaseFactory._parse_redis_url("invalid://url")

    def test_neo4j_creation_requires_password(self, monkeypatch):
        """Test creating Neo4j instance requires password."""
        monkeypatch.setenv("NEO4J_URL", "bolt://localhost:7687")
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
        monkeypatch.delenv("FALKORDB_URL", raising=False)

        # This will raise ValueError due to missing password
        with pytest.raises(ValueError, match="NEO4J_PASSWORD"):
            GraphDatabaseFactory.create()

    def test_falkordb_default_when_nothing_configured(self, monkeypatch):
        """Test FalkorDB is default when no database is configured."""
        monkeypatch.delenv("NEO4J_URL", raising=False)
        monkeypatch.delenv("FALKORDB_URL", raising=False)
        monkeypatch.delenv("FALKORDB_HOST", raising=False)

        db = GraphDatabaseFactory.create()
        assert db.db_type == "falkordb"

    def test_neo4j_takes_priority_over_falkordb(self, monkeypatch):
        """Test Neo4j is chosen when both are configured."""
        monkeypatch.setenv("NEO4J_URL", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_PASSWORD", "password")
        monkeypatch.setenv("FALKORDB_URL", "redis://localhost:6379/0")

        db_type = GraphDatabaseFactory.get_db_type()
        assert db_type == "neo4j"
