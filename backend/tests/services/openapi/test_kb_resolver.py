# SPDX-FileCopyrightText: 2025 Weibo, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for KnowledgeBaseNameResolver.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.openapi.kb_resolver import (
    KnowledgeBaseNameResolver,
    KnowledgeBaseResolutionResult,
    ResolvedKnowledgeBase,
    resolve_knowledge_base_names,
)


class TestKnowledgeBaseNameResolver:
    """Test cases for KnowledgeBaseNameResolver."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_kb_service(self):
        """Create a mock TaskKnowledgeBaseService."""
        with patch(
            "app.services.openapi.kb_resolver.TaskKnowledgeBaseService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            yield mock_service

    @pytest.fixture
    def resolver(self, mock_db, mock_kb_service):
        """Create a KnowledgeBaseNameResolver instance."""
        return KnowledgeBaseNameResolver(mock_db, user_id=1)

    def test_resolve_single_kb_success(self, resolver, mock_kb_service):
        """Test resolving a single knowledge base successfully."""
        # Arrange
        mock_kb = MagicMock()
        mock_kb.id = 123
        mock_kb.namespace = "default"
        mock_kb.json = {"spec": {"name": "my_kb"}}
        mock_kb_service.get_knowledge_base_by_name.return_value = mock_kb
        mock_kb_service.can_access_knowledge_base.return_value = True

        kb_names = [{"namespace": "default", "name": "my_kb"}]

        # Act
        result = resolver.resolve(kb_names, raise_on_error=True)

        # Assert
        assert len(result.resolved) == 1
        assert result.resolved[0].kb_id == 123
        assert result.resolved[0].namespace == "default"
        assert result.resolved[0].name == "my_kb"
        assert result.resolved[0].display_name == "my_kb"
        assert len(result.not_found) == 0
        assert len(result.no_access) == 0

    def test_resolve_multiple_kbs_success(self, resolver, mock_kb_service):
        """Test resolving multiple knowledge bases successfully."""

        # Arrange
        def mock_get_kb(db, name, namespace):
            mock_kb = MagicMock()
            mock_kb.id = 1 if name == "kb1" else 2
            mock_kb.namespace = namespace
            mock_kb.json = {"spec": {"name": name}}
            return mock_kb

        mock_kb_service.get_knowledge_base_by_name.side_effect = mock_get_kb
        mock_kb_service.can_access_knowledge_base.return_value = True

        kb_names = [
            {"namespace": "default", "name": "kb1"},
            {"namespace": "org", "name": "kb2"},
        ]

        # Act
        result = resolver.resolve(kb_names, raise_on_error=True)

        # Assert
        assert len(result.resolved) == 2
        assert result.resolved[0].kb_id == 1
        assert result.resolved[1].kb_id == 2
        assert len(result.not_found) == 0
        assert len(result.no_access) == 0

    def test_resolve_kb_not_found(self, resolver, mock_kb_service):
        """Test resolving a KB that doesn't exist."""
        # Arrange
        mock_kb_service.get_knowledge_base_by_name.return_value = None
        kb_names = [{"namespace": "default", "name": "nonexistent"}]

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            resolver.resolve(kb_names, raise_on_error=True)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    def test_resolve_kb_no_access(self, resolver, mock_kb_service):
        """Test resolving a KB without access permission."""
        # Arrange
        mock_kb = MagicMock()
        mock_kb.id = 123
        mock_kb.namespace = "default"
        mock_kb.json = {"spec": {"name": "private_kb"}}
        mock_kb_service.get_knowledge_base_by_name.return_value = mock_kb
        mock_kb_service.can_access_knowledge_base.return_value = False

        kb_names = [{"namespace": "default", "name": "private_kb"}]

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            resolver.resolve(kb_names, raise_on_error=True)

        assert exc_info.value.status_code == 403
        assert "access denied" in exc_info.value.detail.lower()

    def test_resolve_partial_failure_no_raise(self, resolver, mock_kb_service):
        """Test partial failure with raise_on_error=False."""
        # Arrange
        mock_kb = MagicMock()
        mock_kb.id = 123
        mock_kb.namespace = "default"
        mock_kb.json = {"spec": {"name": "existing_kb"}}

        def mock_get_kb(db, name, namespace):
            if name == "existing_kb":
                return mock_kb
            return None

        mock_kb_service.get_knowledge_base_by_name.side_effect = mock_get_kb
        mock_kb_service.can_access_knowledge_base.return_value = True

        kb_names = [
            {"namespace": "default", "name": "existing_kb"},
            {"namespace": "default", "name": "nonexistent"},
        ]

        # Act
        result = resolver.resolve(kb_names, raise_on_error=False)

        # Assert
        assert len(result.resolved) == 1
        assert len(result.not_found) == 1
        assert result.resolved[0].name == "existing_kb"
        assert result.not_found[0]["name"] == "nonexistent"

    def test_resolve_empty_name(self, resolver, mock_kb_service):
        """Test resolving with empty name."""
        # Arrange
        kb_names = [{"namespace": "default", "name": ""}]

        # Act
        result = resolver.resolve(kb_names, raise_on_error=False)

        # Assert
        assert len(result.resolved) == 0
        assert len(result.not_found) == 1

    def test_resolve_single_method(self, resolver, mock_kb_service):
        """Test resolve_single convenience method."""
        # Arrange
        mock_kb = MagicMock()
        mock_kb.id = 456
        mock_kb.namespace = "org"
        mock_kb.json = {"spec": {"name": "team_kb"}}
        mock_kb_service.get_knowledge_base_by_name.return_value = mock_kb
        mock_kb_service.can_access_knowledge_base.return_value = True

        # Act
        result = resolver.resolve_single("org", "team_kb")

        # Assert
        assert result is not None
        assert result.kb_id == 456
        assert result.namespace == "org"
        assert result.name == "team_kb"

    def test_resolve_single_not_found(self, resolver, mock_kb_service):
        """Test resolve_single with non-existent KB."""
        # Arrange
        mock_kb_service.get_knowledge_base_by_name.return_value = None

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            resolver.resolve_single("default", "nonexistent")

        assert exc_info.value.status_code == 404


class TestResolveKnowledgeBaseNamesFunction:
    """Test cases for resolve_knowledge_base_names convenience function."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @patch("app.services.openapi.kb_resolver.TaskKnowledgeBaseService")
    def test_convenience_function(self, mock_service_class, mock_db):
        """Test the convenience function works correctly."""
        # Arrange
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_kb = MagicMock()
        mock_kb.id = 789
        mock_kb.namespace = "default"
        mock_kb.json = {"spec": {"name": "test_kb"}}
        mock_service.get_knowledge_base_by_name.return_value = mock_kb
        mock_service.can_access_knowledge_base.return_value = True

        kb_names = [{"namespace": "default", "name": "test_kb"}]

        # Act
        result = resolve_knowledge_base_names(mock_db, 1, kb_names)

        # Assert
        assert len(result.resolved) == 1
        assert result.resolved[0].kb_id == 789


class TestResolvedKnowledgeBase:
    """Test cases for ResolvedKnowledgeBase named tuple."""

    def test_named_tuple_fields(self):
        """Test ResolvedKnowledgeBase has correct fields."""
        # Act
        resolved = ResolvedKnowledgeBase(
            kb_id=1, namespace="default", name="test", display_name="Test KB"
        )

        # Assert
        assert resolved.kb_id == 1
        assert resolved.namespace == "default"
        assert resolved.name == "test"
        assert resolved.display_name == "Test KB"


class TestKnowledgeBaseResolutionResult:
    """Test cases for KnowledgeBaseResolutionResult named tuple."""

    def test_named_tuple_fields(self):
        """Test KnowledgeBaseResolutionResult has correct fields."""
        # Arrange
        resolved = [ResolvedKnowledgeBase(1, "default", "kb1", "KB1")]
        not_found = [{"namespace": "default", "name": "missing"}]
        no_access = [{"namespace": "org", "name": "private"}]

        # Act
        result = KnowledgeBaseResolutionResult(
            resolved=resolved, not_found=not_found, no_access=no_access
        )

        # Assert
        assert len(result.resolved) == 1
        assert len(result.not_found) == 1
        assert len(result.no_access) == 1
