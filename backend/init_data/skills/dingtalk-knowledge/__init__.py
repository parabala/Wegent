# SPDX-FileCopyrightText: 2025 WeCode, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""DingTalk Knowledge Base Upload Skill.

This skill provides tools to upload DingTalk documents, spreadsheets,
and AI tables to Wegent knowledge base.
"""

from .provider import DingTalkKnowledgeToolProvider

__all__ = ["DingTalkKnowledgeToolProvider"]
