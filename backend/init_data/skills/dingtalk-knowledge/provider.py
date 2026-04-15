# SPDX-FileCopyrightText: 2025 WeCode, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""DingTalk Knowledge Base Upload Tool Provider.

This module provides the DingTalkKnowledgeToolProvider class that creates
tools for uploading DingTalk documents to Wegent knowledge base.
"""

from typing import Any, Optional

from langchain_core.tools import BaseTool

from chat_shell.skills import SkillToolContext, SkillToolProvider


class DingTalkKnowledgeToolProvider(SkillToolProvider):
    """Tool provider for DingTalk to Knowledge Base upload operations.

    This provider creates tools that allow agents to:
    1. Download files from DingTalk (docs, tables, AI tables)
    2. Upload them to Wegent knowledge base

    Example SKILL.md configuration:
        tools:
          - name: upload_dingtalk_to_kb
            provider: dingtalk-knowledge
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name used in SKILL.md.

        Returns:
            The string "dingtalk-knowledge"
        """
        return "dingtalk-knowledge"

    @property
    def supported_tools(self) -> list[str]:
        """Return the list of tools this provider can create.

        Returns:
            List containing supported tool names
        """
        return ["upload_dingtalk_to_kb"]

    def create_tool(
        self,
        tool_name: str,
        context: SkillToolContext,
        tool_config: Optional[dict[str, Any]] = None,
    ) -> BaseTool:
        """Create a DingTalk knowledge upload tool instance.

        Args:
            tool_name: Name of the tool to create
            context: Context with dependencies (task_id, subtask_id, ws_emitter, user_id, db_session)
            tool_config: Optional configuration

        Returns:
            Configured tool instance

        Raises:
            ValueError: If tool_name is unknown
        """
        if tool_name == "upload_dingtalk_to_kb":
            from .upload_dingtalk_to_kb import UploadDingTalkToKBTool

            return UploadDingTalkToKBTool(
                task_id=context.task_id,
                subtask_id=context.subtask_id,
                ws_emitter=context.ws_emitter,
                user_id=context.user_id,
                db_session=context.db_session,
                auth_token=context.auth_token,
            )

        raise ValueError(f"Unknown tool: {tool_name}")

    def validate_config(self, tool_config: dict[str, Any]) -> bool:
        """Validate tool configuration.

        Args:
            tool_config: Configuration to validate

        Returns:
            True if valid, False otherwise
        """
        return True
