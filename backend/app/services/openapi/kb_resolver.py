# SPDX-FileCopyrightText: 2025 Weibo, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""
Knowledge base name resolver for OpenAPI v1/responses endpoint.

This module provides functionality to resolve knowledge base display names
to their internal IDs with permission checking.
"""

import logging
from typing import Dict, List, NamedTuple, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.kind import Kind
from app.services.knowledge.task_knowledge_base_service import (
    TaskKnowledgeBaseService,
)

logger = logging.getLogger(__name__)


class ResolvedKnowledgeBase(NamedTuple):
    """Result of resolving a knowledge base name."""

    kb_id: int
    namespace: str
    name: str
    display_name: str


class KnowledgeBaseResolutionResult(NamedTuple):
    """Result of batch knowledge base name resolution."""

    resolved: List[ResolvedKnowledgeBase]
    not_found: List[Dict[str, str]]
    no_access: List[Dict[str, str]]


class KnowledgeBaseNameResolver:
    """
    Resolver for knowledge base names to IDs with permission checking.

    This class handles the resolution of knowledge base display names
    (in 'namespace#name' format) to their internal Kind IDs, including
    permission validation for the requesting user.
    """

    def __init__(self, db: Session, user_id: int):
        """
        Initialize the resolver.

        Args:
            db: Database session
            user_id: ID of the user requesting KB access
        """
        self.db = db
        self.user_id = user_id
        self.kb_service = TaskKnowledgeBaseService()

    def resolve(
        self,
        kb_names: List[Dict[str, str]],
        raise_on_error: bool = True,
    ) -> KnowledgeBaseResolutionResult:
        """
        Resolve a list of knowledge base names to IDs.

        Args:
            kb_names: List of dicts with 'namespace' and 'name' keys
            raise_on_error: If True, raise HTTPException on any error.
                           If False, return partial results and errors.

        Returns:
            KnowledgeBaseResolutionResult with resolved KBs and errors

        Raises:
            HTTPException: If raise_on_error=True and any KB not found or no access
        """
        resolved: List[ResolvedKnowledgeBase] = []
        not_found: List[Dict[str, str]] = []
        no_access: List[Dict[str, str]] = []

        for kb_ref in kb_names:
            namespace = kb_ref.get("namespace", "default")
            name = kb_ref.get("name", "")

            if not name:
                logger.warning(
                    "[KBResolver] Empty knowledge base name in reference: %s",
                    kb_ref,
                )
                not_found.append(kb_ref)
                continue

            # Look up the knowledge base by display name
            kb = self.kb_service.get_knowledge_base_by_name(self.db, name, namespace)

            if not kb:
                logger.warning(
                    "[KBResolver] Knowledge base not found: namespace=%s, name=%s",
                    namespace,
                    name,
                )
                not_found.append(kb_ref)
                continue

            # Check user access permission
            if not self.kb_service.can_access_knowledge_base(
                self.db, self.user_id, name, namespace
            ):
                logger.warning(
                    "[KBResolver] User %s has no access to KB: namespace=%s, name=%s",
                    self.user_id,
                    namespace,
                    name,
                )
                no_access.append(kb_ref)
                continue

            # Extract display name from spec
            kb_spec = kb.json.get("spec", {}) if kb.json else {}
            display_name = kb_spec.get("name", name)

            resolved.append(
                ResolvedKnowledgeBase(
                    kb_id=kb.id,
                    namespace=namespace,
                    name=name,
                    display_name=display_name,
                )
            )
            logger.debug(
                "[KBResolver] Resolved KB: namespace=%s, name=%s -> id=%d",
                namespace,
                name,
                kb.id,
            )

        # Handle errors based on raise_on_error flag
        if raise_on_error:
            self._handle_errors(resolved, not_found, no_access)

        return KnowledgeBaseResolutionResult(
            resolved=resolved,
            not_found=not_found,
            no_access=no_access,
        )

    def _handle_errors(
        self,
        resolved: List[ResolvedKnowledgeBase],
        not_found: List[Dict[str, str]],
        no_access: List[Dict[str, str]],
    ) -> None:
        """
        Handle resolution errors by raising appropriate exceptions.

        Args:
            resolved: List of successfully resolved KBs
            not_found: List of KB refs that were not found
            no_access: List of KB refs that user has no access to

        Raises:
            HTTPException: With appropriate error message
        """
        if not_found:
            kb_list = [
                f"{r.get('namespace', 'default')}#{r.get('name', '')}"
                for r in not_found
            ]
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge base(s) not found: {', '.join(kb_list)}",
            )

        if no_access:
            kb_list = [
                f"{r.get('namespace', 'default')}#{r.get('name', '')}"
                for r in no_access
            ]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to knowledge base(s): {', '.join(kb_list)}",
            )

    def resolve_single(
        self,
        namespace: str,
        name: str,
        raise_on_error: bool = True,
    ) -> Optional[ResolvedKnowledgeBase]:
        """
        Resolve a single knowledge base name to ID.

        Args:
            namespace: Knowledge base namespace
            name: Knowledge base display name
            raise_on_error: If True, raise HTTPException on error

        Returns:
            ResolvedKnowledgeBase if found and accessible, None otherwise

        Raises:
            HTTPException: If raise_on_error=True and KB not found or no access
        """
        result = self.resolve([{"namespace": namespace, "name": name}], raise_on_error)

        if result.resolved:
            return result.resolved[0]
        return None


def resolve_knowledge_base_names(
    db: Session,
    user_id: int,
    kb_names: List[Dict[str, str]],
    raise_on_error: bool = True,
) -> KnowledgeBaseResolutionResult:
    """
    Convenience function to resolve knowledge base names.

    Args:
        db: Database session
        user_id: ID of the user requesting KB access
        kb_names: List of dicts with 'namespace' and 'name' keys
        raise_on_error: If True, raise HTTPException on any error

    Returns:
        KnowledgeBaseResolutionResult with resolved KBs and errors
    """
    resolver = KnowledgeBaseNameResolver(db, user_id)
    return resolver.resolve(kb_names, raise_on_error)
