# SPDX-FileCopyrightText: 2025 Weibo, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for DingTalkWikiSpaceService — two-phase KB sync."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dingtalk_doc_service import DingTalkDocService
from app.services.dingtalk_wikispace_service import (
    MCP_TOOL_LIST_WIKI_SPACES,
    SOURCE_MY_WIKISPACE,
    SOURCE_ORG_WIKISPACE,
    DingTalkWikiSpaceService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text_content(data: object) -> MagicMock:
    """Create a mock MCP content item with type='text' carrying JSON data."""
    item = MagicMock()
    item.type = "text"
    item.text = json.dumps(data)
    return item


def _make_mcp_result(data: object) -> MagicMock:
    """Create a mock MCP tool call result wrapping JSON data."""
    result = MagicMock()
    result.content = [_make_text_content(data)]
    return result


# Helper to create a _list_wiki_spaces mock that only returns KBs for
# orgWikiSpace (matching original behaviour before myWikiSpace was added).
def _list_spaces_org_only(kb_nodes: list):
    """Return a callable suitable for patching _list_wiki_spaces.

    Returns kb_nodes for orgWikiSpace and an empty list for myWikiSpace.
    Each node is tagged with _source=SOURCE_ORG_WIKISPACE.
    """

    async def _fn(wikispace_mcp_url: str, wiki_space_type: str = "orgWikiSpace"):
        if wiki_space_type == "orgWikiSpace":
            return list(kb_nodes)
        return []

    return _fn


def _make_sync_stats(**overrides) -> dict:
    """Build a sync-stats dict with sensible defaults."""
    defaults = {
        "added": 0,
        "updated": 0,
        "deleted": 0,
        "total": 0,
        "sync_time": datetime.now(),
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# _list_wiki_spaces
# ---------------------------------------------------------------------------


class TestListWikiSpaces:
    """Tests for DingTalkWikiSpaceService._list_wiki_spaces."""

    @pytest.mark.asyncio
    async def test_returns_knowledge_bases_from_items_key(self) -> None:
        """Returns KB nodes when list_wikiSpaces responds with an 'items' envelope."""
        kb_data = [
            {"workspaceId": "WS001", "name": "KB One"},
            {"workspaceId": "WS002", "name": "KB Two"},
        ]
        result, token = DingTalkDocService._parse_list_nodes_result(
            _make_mcp_result({"items": kb_data})
        )
        assert len(result) == 2
        assert result[0]["workspaceId"] == "WS001"
        assert result[1]["name"] == "KB Two"
        assert token is None

    @pytest.mark.asyncio
    async def test_returns_knowledge_bases_from_wikiSpaces_key(self) -> None:
        """Returns KB nodes when list_wikiSpaces responds with a 'wikiSpaces' key."""
        kb_data = [{"workspaceId": "WS100", "name": "Org KB"}]
        result, token = DingTalkDocService._parse_list_nodes_result(
            _make_mcp_result({"wikiSpaces": kb_data})
        )
        assert len(result) == 1
        assert result[0]["workspaceId"] == "WS100"
        assert token is None

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_content(self) -> None:
        """Returns empty list when the MCP result has no content."""
        empty_result = MagicMock()
        empty_result.content = []
        result, token = DingTalkDocService._parse_list_nodes_result(empty_result)
        assert result == []
        assert token is None

    @pytest.mark.asyncio
    async def test_pagination_token_extracted(self) -> None:
        """nextPageToken is extracted from the response envelope."""
        data = {
            "items": [{"workspaceId": "WS1", "name": "KB 1"}],
            "nextPageToken": "tok2",
        }
        result, token = DingTalkDocService._parse_list_nodes_result(
            _make_mcp_result(data)
        )
        assert len(result) == 1
        assert token == "tok2"


# ---------------------------------------------------------------------------
# _fetch_all_wikispace_nodes
# ---------------------------------------------------------------------------


class TestFetchAllWikispaceNodes:
    """Tests for DingTalkWikiSpaceService._fetch_all_wikispace_nodes."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_kbs(self) -> None:
        """Returns empty list when list_wikiSpaces returns no knowledge bases."""
        with patch.object(
            DingTalkWikiSpaceService,
            "_list_wiki_spaces",
            new=AsyncMock(return_value=[]),
        ):
            result = await DingTalkWikiSpaceService._fetch_all_wikispace_nodes(
                wikispace_mcp_url="https://ws.mcp.example.com",
                docs_mcp_url="https://docs.mcp.example.com",
            )
        assert result == []

    @pytest.mark.asyncio
    async def test_adds_kb_root_as_folder_node(self) -> None:
        """Each knowledge base is added as a folder-type root node with _source tag."""
        kb_nodes = [
            {"workspaceId": "WSABC", "name": "Test KB", "_source": SOURCE_ORG_WIKISPACE}
        ]

        with (
            patch.object(
                DingTalkWikiSpaceService,
                "_list_wiki_spaces",
                new=_list_spaces_org_only(kb_nodes),
            ),
            patch.object(
                DingTalkWikiSpaceService,
                "_list_nodes_in_wikispace",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await DingTalkWikiSpaceService._fetch_all_wikispace_nodes(
                wikispace_mcp_url="https://ws.mcp.example.com",
                docs_mcp_url="https://docs.mcp.example.com",
            )

        assert len(result) == 1
        kb_root = result[0]
        assert kb_root["nodeId"] == "WSABC"
        assert kb_root["nodeType"] == "folder"
        assert kb_root["workspaceId"] == "WSABC"
        assert kb_root["name"] == "Test KB"
        assert kb_root["_source"] == SOURCE_ORG_WIKISPACE

    @pytest.mark.asyncio
    async def test_uses_wikispace_mcp_url_as_docs_fallback(self) -> None:
        """Falls back to wikispace MCP URL when docs MCP URL is not configured."""
        kb_nodes = [
            {"workspaceId": "WS1", "name": "KB 1", "_source": SOURCE_ORG_WIKISPACE}
        ]
        captured_urls: list[str] = []

        async def capture_url(
            docs_mcp_url: str,
            workspace_id: str,
            all_nodes: list,
            source_tag: str = "",
        ) -> None:
            captured_urls.append(docs_mcp_url)

        with (
            patch.object(
                DingTalkWikiSpaceService,
                "_list_wiki_spaces",
                new=_list_spaces_org_only(kb_nodes),
            ),
            patch.object(
                DingTalkWikiSpaceService,
                "_list_nodes_in_wikispace",
                new=AsyncMock(side_effect=capture_url),
            ),
        ):
            await DingTalkWikiSpaceService._fetch_all_wikispace_nodes(
                wikispace_mcp_url="https://ws.mcp.example.com",
                docs_mcp_url=None,  # not configured
            )

        assert captured_urls == ["https://ws.mcp.example.com"]

    @pytest.mark.asyncio
    async def test_skips_kb_with_no_workspace_id(self) -> None:
        """Skips KB nodes that have no workspaceId/nodeId/id field."""
        kb_nodes = [
            {"name": "No ID KB", "_source": SOURCE_ORG_WIKISPACE},  # missing workspaceId
            {"workspaceId": "WS2", "name": "Good KB", "_source": SOURCE_ORG_WIKISPACE},
        ]
        list_nodes_calls: list[str] = []

        async def track_call(
            docs_mcp_url: str,
            workspace_id: str,
            all_nodes: list,
            source_tag: str = "",
        ) -> None:
            list_nodes_calls.append(workspace_id)

        with (
            patch.object(
                DingTalkWikiSpaceService,
                "_list_wiki_spaces",
                new=_list_spaces_org_only(kb_nodes),
            ),
            patch.object(
                DingTalkWikiSpaceService,
                "_list_nodes_in_wikispace",
                new=AsyncMock(side_effect=track_call),
            ),
        ):
            result = await DingTalkWikiSpaceService._fetch_all_wikispace_nodes(
                wikispace_mcp_url="https://ws.mcp.example.com",
            )

        # Only the good KB should be processed
        assert list_nodes_calls == ["WS2"]
        # Only one folder node added (for the good KB)
        assert len(result) == 1
        assert result[0]["workspaceId"] == "WS2"

    @pytest.mark.asyncio
    async def test_continues_after_kb_error(self) -> None:
        """Continues syncing remaining KBs even if one fails."""
        kb_nodes = [
            {"workspaceId": "WS_FAIL", "name": "Failing KB", "_source": SOURCE_ORG_WIKISPACE},
            {"workspaceId": "WS_OK", "name": "Good KB", "_source": SOURCE_ORG_WIKISPACE},
        ]
        call_count = 0

        async def maybe_fail(
            docs_mcp_url: str,
            workspace_id: str,
            all_nodes: list,
            source_tag: str = "",
        ) -> None:
            nonlocal call_count
            call_count += 1
            if workspace_id == "WS_FAIL":
                raise ConnectionError("MCP connection failed")

        with (
            patch.object(
                DingTalkWikiSpaceService,
                "_list_wiki_spaces",
                new=_list_spaces_org_only(kb_nodes),
            ),
            patch.object(
                DingTalkWikiSpaceService,
                "_list_nodes_in_wikispace",
                new=AsyncMock(side_effect=maybe_fail),
            ),
        ):
            result = await DingTalkWikiSpaceService._fetch_all_wikispace_nodes(
                wikispace_mcp_url="https://ws.mcp.example.com",
            )

        # Both KBs attempted; both root nodes added
        assert call_count == 2
        assert len(result) == 2


# ---------------------------------------------------------------------------
# sync_wikispace_nodes (integration-style with mocked MCP)
# ---------------------------------------------------------------------------


class TestSyncWikispaceNodes:
    """Tests for DingTalkWikiSpaceService.sync_wikispace_nodes."""

    @pytest.mark.asyncio
    @patch("app.services.dingtalk_wikispace_service.UserMCPService")
    @patch("app.services.dingtalk_wikispace_service.DingTalkDocService")
    async def test_raises_when_not_configured(
        self, mock_doc_service: MagicMock, mock_mcp_svc: MagicMock
    ) -> None:
        """Raises ValueError when wikispace MCP URL is not configured."""
        mock_mcp_svc.get_provider_service_config.return_value = {"enabled": False}
        mock_user = MagicMock()
        mock_db = MagicMock()

        with pytest.raises(ValueError, match="not configured"):
            await DingTalkWikiSpaceService.sync_wikispace_nodes(mock_user, mock_db)

    @pytest.mark.asyncio
    @patch("app.services.dingtalk_wikispace_service.UserMCPService")
    async def test_uses_docs_mcp_url_for_list_nodes(
        self, mock_mcp_svc: MagicMock
    ) -> None:
        """Passes the docs MCP URL to _fetch_all_wikispace_nodes."""
        mock_mcp_svc.get_provider_service_config.return_value = {
            "enabled": True,
            "url": "https://ws.mcp.example.com",
        }
        mock_user = MagicMock()
        mock_db = MagicMock()

        captured: dict = {}

        async def fake_fetch(
            wikispace_mcp_url: str,
            docs_mcp_url: str | None = None,
        ) -> list:
            captured["wikispace_url"] = wikispace_mcp_url
            captured["docs_url"] = docs_mcp_url
            return []

        with (
            patch.object(
                DingTalkWikiSpaceService,
                "_fetch_all_wikispace_nodes",
                new=fake_fetch,
            ),
            patch(
                "app.services.dingtalk_wikispace_service.DingTalkDocService"
                ".get_user_dingtalk_mcp_url",
                return_value="https://docs.mcp.example.com",
            ),
            patch(
                "app.services.dingtalk_wikispace_service.DingTalkDocService"
                "._sync_nodes_to_db",
                return_value=_make_sync_stats(),
            ),
        ):
            await DingTalkWikiSpaceService.sync_wikispace_nodes(mock_user, mock_db)

        assert captured["wikispace_url"] == "https://ws.mcp.example.com"
        assert captured["docs_url"] == "https://docs.mcp.example.com"