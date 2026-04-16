# SPDX-FileCopyrightText: 2025 WeCode, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""Internal DingTalk MCP proxy API endpoints.

Provides endpoints to proxy DingTalk MCP tool calls for skills running in sandbox.
These endpoints handle the MCP authentication and tool invocation on behalf of skills.
"""

import json
import logging
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core import security
from app.schemas.user import UserInDB
from app.services.mcp_provider_registry import get_mcp_provider_service
from app.services.user_mcp_service import UserMCPService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp/dingtalk", tags=["internal-dingtalk-mcp"])


class MCPToolCallRequest(BaseModel):
    """Request to call a DingTalk MCP tool."""

    tool_name: str = Field(..., description="Name of the MCP tool to call")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")


class MCPToolCallResponse(BaseModel):
    """Response from a DingTalk MCP tool call."""

    success: bool = Field(..., description="Whether the call succeeded")
    result: Optional[dict[str, Any]] = Field(None, description="Tool result")
    error: Optional[str] = Field(None, description="Error message if failed")


@router.post("/{service_id}/call", response_model=MCPToolCallResponse)
async def call_dingtalk_mcp_tool(
    request: Request,
    service_id: str = Path(..., description="DingTalk service ID (docs, table, ai_table)"),
    tool_request: MCPToolCallRequest = None,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(security.get_current_user),
) -> MCPToolCallResponse:
    """Call a DingTalk MCP tool on behalf of the user.

    This endpoint proxies MCP tool calls to DingTalk MCP servers,
    handling authentication using the user's stored MCP credentials.

    Args:
        request: FastAPI request object
        service_id: DingTalk service ID (docs, table, ai_table)
        tool_request: Tool call request with name and parameters
        db: Database session
        current_user: Current authenticated user

    Returns:
        MCPToolCallResponse with tool result or error
    """
    logger.info(
        "[DingTalkMCP] Tool call requested: service=%s, tool=%s, user=%s",
        service_id,
        tool_request.tool_name if tool_request else None,
        current_user.id,
    )

    # Validate service_id
    valid_services = ["docs", "table", "ai_table"]
    if service_id not in valid_services:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service_id. Must be one of: {', '.join(valid_services)}",
        )

    # Get service metadata from registry
    service_metadata = get_mcp_provider_service("dingtalk", service_id)
    if not service_metadata:
        raise HTTPException(
            status_code=404,
            detail=f"DingTalk service '{service_id}' not found in registry",
        )

    # Get user's MCP configuration
    mcp_config = UserMCPService.get_provider_service_config(
        current_user.preferences, "dingtalk", service_id
    )

    if not mcp_config.get("enabled"):
        return MCPToolCallResponse(
            success=False,
            error=f"DingTalk {service_id} MCP is not enabled for this user",
        )

    mcp_url = mcp_config.get("url", "").strip()
    if not mcp_url:
        return MCPToolCallResponse(
            success=False,
            error=f"DingTalk {service_id} MCP URL is not configured",
        )

    # Call the MCP tool
    try:
        result = await _call_mcp_tool(
            mcp_url=mcp_url,
            tool_name=tool_request.tool_name if tool_request else "",
            parameters=tool_request.parameters if tool_request else {},
        )

        return MCPToolCallResponse(success=True, result=result)

    except Exception as e:
        logger.exception("[DingTalkMCP] Failed to call MCP tool: %s", e)
        return MCPToolCallResponse(
            success=False,
            error=f"Failed to call MCP tool: {str(e)}",
        )


@router.post("/{service_id}/tools/list")
async def list_dingtalk_mcp_tools(
    service_id: str = Path(..., description="DingTalk service ID (docs, table, ai_table)"),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(security.get_current_user),
) -> dict[str, Any]:
    """List available tools from a DingTalk MCP server.

    Args:
        service_id: DingTalk service ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Dictionary with available tools
    """
    logger.info(
        "[DingTalkMCP] List tools requested: service=%s, user=%s",
        service_id,
        current_user.id,
    )

    # Validate service_id
    valid_services = ["docs", "table", "ai_table"]
    if service_id not in valid_services:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service_id. Must be one of: {', '.join(valid_services)}",
        )

    # Get user's MCP configuration
    mcp_config = UserMCPService.get_provider_service_config(
        current_user.preferences, "dingtalk", service_id
    )

    if not mcp_config.get("enabled"):
        raise HTTPException(
            status_code=403,
            detail=f"DingTalk {service_id} MCP is not enabled for this user",
        )

    mcp_url = mcp_config.get("url", "").strip()
    if not mcp_url:
        raise HTTPException(
            status_code=400,
            detail=f"DingTalk {service_id} MCP URL is not configured",
        )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Call MCP server to list tools
            response = await client.post(
                f"{mcp_url}/tools/list",
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()

    except httpx.HTTPError as e:
        logger.error("[DingTalkMCP] HTTP error listing tools: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to list MCP tools: {str(e)}",
        )
    except Exception as e:
        logger.exception("[DingTalkMCP] Error listing tools: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}",
        )


async def _call_mcp_tool(
    mcp_url: str,
    tool_name: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Call an MCP tool.

    Args:
        mcp_url: MCP server URL
        tool_name: Name of the tool to call
        parameters: Tool parameters

    Returns:
        Tool result as dictionary
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Call MCP tool endpoint
        tool_endpoint = f"{mcp_url}/tools/{tool_name}"

        logger.debug("[DingTalkMCP] Calling tool endpoint: %s", tool_endpoint)

        response = await client.post(
            tool_endpoint,
            json=parameters,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

        # Parse response
        result = response.json()

        # Handle different response formats
        if isinstance(result, dict):
            return result
        else:
            return {"result": result}


@router.get("/{service_id}/config")
async def get_dingtalk_mcp_config(
    service_id: str = Path(..., description="DingTalk service ID (docs, table, ai_table)"),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(security.get_current_user),
) -> dict[str, Any]:
    """Get DingTalk MCP configuration metadata for a service.

    This endpoint returns the MCP service metadata from the registry,
    which includes the detail_url for MCP documentation.

    Args:
        service_id: DingTalk service ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Service metadata including detail_url
    """
    logger.info(
        "[DingTalkMCP] Get config requested: service=%s, user=%s",
        service_id,
        current_user.id,
    )

    # Validate service_id
    valid_services = ["docs", "table", "ai_table"]
    if service_id not in valid_services:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service_id. Must be one of: {', '.join(valid_services)}",
        )

    # Get service metadata from registry
    service_metadata = get_mcp_provider_service("dingtalk", service_id)
    if not service_metadata:
        raise HTTPException(
            status_code=404,
            detail=f"DingTalk service '{service_id}' not found in registry",
        )

    # Get user's MCP configuration status
    user_config = UserMCPService.get_provider_service_config(
        current_user.preferences, "dingtalk", service_id
    )

    return {
        "service_id": service_metadata["service_id"],
        "server_name": service_metadata["server_name"],
        "skill_name": service_metadata["skill_name"],
        "display_name": service_metadata["display_name"],
        "detail_url": service_metadata["detail_url"],
        "enabled": user_config.get("enabled", False),
        "configured": bool(user_config.get("url", "").strip()),
    }
