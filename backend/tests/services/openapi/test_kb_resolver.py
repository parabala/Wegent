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
    def resolver(self, mock_db):
        """Create a KnowledgeBaseNameResolver instance."""
        with patch(
            "app.services.openapi.kb_resolver.TaskKnowledgeBaseService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            yield KnowledgeBaseNameResolver(mock_db, user_id=1)

    def _create_mock_kb(self, kb_id, namespace, name, user_id=1):
        """Helper to create a mock KB object."""
        mock_kb = MagicMock()
        mock_kb.id = kb_id
        mock_kb.namespace = namespace
        mock_kb.user_id = user_id
        mock_kb.json = {"spec": {"name": name}}
        return mock_kb

    def test_resolve_single_kb_success(self, resolver, mock_db):
        """Test resolving a single knowledge base successfully."""
        mock_kb = self._create_mock_kb(123, "default", "my_kb", user_id=1)

        with patch.object(resolver, "_batch_query_kbs") as mock_batch_query:
            mock_batch_query.return_value = {("default", "my_kb"): mock_kb}
            resolver.kb_service._check_kb_access_permission.return_value = True

            kb_names = [{"namespace": "default", "name": "my_kb"}]
            result = resolver.resolve(kb_names, raise_on_error=True)

            assert len(result.resolved) == 1
            assert result.resolved[0].kb_id == 123
            assert result.resolved[0].namespace == "default"
            assert result.resolved[0].name == "my_kb"
            assert len(result.not_found) == 0
            assert len(result.no_access) == 0

    def test_resolve_multiple_kbs_success(self, resolver, mock_db):
        """Test resolving multiple knowledge bases successfully."""
        mock_kb1 = self._create_mock_kb(1, "default", "kb1", user_id=1)
        mock_kb2 = self._create_mock_kb(2, "org", "kb2", user_id=999)

        with patch.object(resolver, "_batch_query_kbs") as mock_batch_query:
            mock_batch_query.return_value = {
                ("default", "kb1"): mock_kb1,
                ("org", "kb2"): mock_kb2,
            }
            resolver.kb_service._check_kb_access_permission.return_value = True

            kb_names = [
                {"namespace": "default", "name": "kb1"},
                {"namespace": "org", "name": "kb2"},
            ]
            result = resolver.resolve(kb_names, raise_on_error=True)

            assert len(result.resolved) == 2
            kb_ids = {r.kb_id for r in result.resolved}
            assert kb_ids == {1, 2}

    def test_resolve_kb_not_found(self, resolver, mock_db):
        """Test resolving a KB that doesn't exist."""
        with patch.object(resolver, "_batch_query_kbs") as mock_batch_query:
            mock_batch_query.return_value = {}

            kb_names = [{"namespace": "default", "name": "nonexistent"}]

            with pytest.raises(HTTPException) as exc_info:
                resolver.resolve(kb_names, raise_on_error=True)

            assert exc_info.value.status_code == 404

    def test_resolve_kb_no_access(self, resolver, mock_db):
        """Test resolving a KB without access permission."""
        mock_kb = self._create_mock_kb(123, "default", "private_kb", user_id=999)

        with patch.object(resolver, "_batch_query_kbs") as mock_batch_query:
            mock_batch_query.return_value = {("default", "private_kb"): mock_kb}
            resolver.kb_service._check_kb_access_permission.return_value = False

            kb_names = [{"namespace": "default", "name": "private_kb"}]

            with pytest.raises(HTTPException) as exc_info:
                resolver.resolve(kb_names, raise_on_error=True)

            assert exc_info.value.status_code == 403

    def test_resolve_partial_failure_no_raise(self, resolver, mock_db):
        """Test partial failure with raise_on_error=False."""
        mock_kb = self._create_mock_kb(123, "default", "existing_kb", user_id=1)

        with patch.object(resolver, "_batch_query_kbs") as mock_batch_query:
            mock_batch_query.return_value = {("default", "existing_kb"): mock_kb}
            resolver.kb_service._check_kb_access_permission.return_value = True

            kb_names = [
                {"namespace": "default", "name": "existing_kb"},
                {"namespace": "default", "name": "nonexistent"},
            ]
            result = resolver.resolve(kb_names, raise_on_error=False)

            assert len(result.resolved) == 1
            assert len(result.not_found) == 1

    def test_resolve_empty_name(self, resolver, mock_db):
        """Test resolving with empty name."""
        kb_names = [{"namespace": "default", "name": ""}]
        result = resolver.resolve(kb_names, raise_on_error=False)

        assert len(result.resolved) == 0
        assert len(result.not_found) == 1

    def test_resolve_single_method(self, resolver, mock_db):
        """Test resolve_single convenience method."""
        mock_kb = self._create_mock_kb(456, "org", "team_kb", user_id=999)

        with patch.object(resolver, "_batch_query_kbs") as mock_batch_query:
            mock_batch_query.return_value = {("org", "team_kb"): mock_kb}
            resolver.kb_service._check_kb_access_permission.return_value = True

            result = resolver.resolve_single("org", "team_kb")

            assert result is not None
            assert result.kb_id == 456

    def test_resolve_single_not_found(self, resolver, mock_db):
        """Test resolve_single with non-existent KB."""
        with patch.object(resolver, "_batch_query_kbs") as mock_batch_query:
            mock_batch_query.return_value = {}

            with pytest.raises(HTTPException) as exc_info:
                resolver.resolve_single("default", "nonexistent")

            assert exc_info.value.status_code == 404

    def test_resolve_organization_kb_access(self, resolver, mock_db):
        """Test resolving organization KB - all users have access."""
        mock_kb = self._create_mock_kb(100, "org-namespace", "org_kb", user_id=999)

        with patch.object(resolver, "_batch_query_kbs") as mock_batch_query:
            mock_batch_query.return_value = {("org-namespace", "org_kb"): mock_kb}
            resolver.kb_service._check_kb_access_permission.return_value = True

            kb_names = [{"namespace": "org-namespace", "name": "org_kb"}]
            result = resolver.resolve(kb_names, raise_on_error=True)

            assert len(result.resolved) == 1
            assert result.resolved[0].kb_id == 100

    def test_resolve_team_kb_with_group_membership(self, resolver, mock_db):
        """Test resolving team KB with group membership."""
        mock_kb = self._create_mock_kb(200, "team-ns", "team_kb", user_id=999)

        with patch.object(resolver, "_batch_query_kbs") as mock_batch_query:
            mock_batch_query.return_value = {("team-ns", "team_kb"): mock_kb}
            resolver.kb_service._check_kb_access_permission.return_value = True

            kb_names = [{"namespace": "team-ns", "name": "team_kb"}]
            result = resolver.resolve(kb_names, raise_on_error=True)

            assert len(result.resolved) == 1
            assert result.resolved[0].kb_id == 200

    def test_resolve_team_kb_no_group_membership(self, resolver, mock_db):
        """Test resolving team KB without group membership."""
        mock_kb = self._create_mock_kb(200, "team-ns", "team_kb", user_id=999)

        with patch.object(resolver, "_batch_query_kbs") as mock_batch_query:
            mock_batch_query.return_value = {("team-ns", "team_kb"): mock_kb}
            resolver.kb_service._check_kb_access_permission.return_value = False

            kb_names = [{"namespace": "team-ns", "name": "team_kb"}]

            with pytest.raises(HTTPException) as exc_info:
                resolver.resolve(kb_names, raise_on_error=True)

            assert exc_info.value.status_code == 403

    def test_resolve_empty_list(self, resolver, mock_db):
        """Test resolving empty list of KB names."""
        result = resolver.resolve([], raise_on_error=True)

        assert len(result.resolved) == 0
        assert len(result.not_found) == 0
        assert len(result.no_access) == 0


class TestResolveKnowledgeBaseNamesFunction:
    """Test cases for resolve_knowledge_base_names convenience function."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    def test_convenience_function(self, mock_db):
        """Test the convenience function works correctly."""
        mock_kb = MagicMock()
        mock_kb.id = 789
        mock_kb.namespace = "default"
        mock_kb.user_id = 1
        mock_kb.json = {"spec": {"name": "test_kb"}}

        with patch("app.services.openapi.kb_resolver.TaskKnowledgeBaseService"):
            with patch.object(
                KnowledgeBaseNameResolver, "_batch_query_kbs"
            ) as mock_batch_query:
                mock_batch_query.return_value = {("default", "test_kb"): mock_kb}

                resolver = KnowledgeBaseNameResolver(mock_db, 1)
                resolver.kb_service._check_kb_access_permission.return_value = True

                kb_names = [{"namespace": "default", "name": "test_kb"}]
                result = resolve_knowledge_base_names(mock_db, 1, kb_names)

                assert len(result.resolved) == 1
                assert result.resolved[0].kb_id == 789


class TestResolvedKnowledgeBase:
    """Test cases for ResolvedKnowledgeBase named tuple."""

    def test_named_tuple_fields(self):
        """Test ResolvedKnowledgeBase has correct fields."""
        resolved = ResolvedKnowledgeBase(
            kb_id=1, namespace="default", name="test", display_name="Test KB"
        )

        assert resolved.kb_id == 1
        assert resolved.namespace == "default"
        assert resolved.name == "test"
        assert resolved.display_name == "Test KB"


class TestKnowledgeBaseResolutionResult:
    """Test cases for KnowledgeBaseResolutionResult named tuple."""

    def test_named_tuple_fields(self):
        """Test KnowledgeBaseResolutionResult has correct fields."""
        resolved = [ResolvedKnowledgeBase(1, "default", "kb1", "KB1")]
        not_found = [{"namespace": "default", "name": "missing"}]
        no_access = [{"namespace": "org", "name": "private"}]

        result = KnowledgeBaseResolutionResult(
            resolved=resolved, not_found=not_found, no_access=no_access
        )

        assert len(result.resolved) == 1
        assert len(result.not_found) == 1
        assert len(result.no_access) == 1
