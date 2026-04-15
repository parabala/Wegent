---
description: "Upload DingTalk documents, spreadsheets, and AI tables to Wegent knowledge base. Supports downloading files from DingTalk (docs, tables, AI tables) and uploading them as attachments to the current knowledge base."
displayName: "钉钉文档导入知识库"
version: "1.0.0"
author: "Wegent Team"
tags: ["dingtalk", "knowledge-base", "document", "upload", "import"]
bindShells: ["Chat", "ClaudeCode", "Agno"]
provider:
  module: provider
  class: DingTalkKnowledgeToolProvider
tools:
  - name: upload_dingtalk_to_kb
    provider: dingtalk-knowledge
---

# DingTalk Knowledge Base Upload Skill

This skill provides tools to upload DingTalk documents, spreadsheets, and AI tables to Wegent knowledge base.

## Overview

When a user wants to import a DingTalk document into the current knowledge base, this skill:

1. Retrieves DingTalk MCP authentication configuration from user preferences
2. Determines the appropriate MCP service based on the document URL type
3. Downloads the file from DingTalk using MCP tools
4. Uploads the file to the current knowledge base as an attachment

## Supported Document Types

| Document Type | URL Pattern | MCP Service |
|--------------|-------------|-------------|
| DingTalk Docs | `alidocs.dingtalk.com/i/nodes/{id}` | `dingtalk_docs` |
| DingTalk Table | `alidocs.dingtalk.com/i/nodes/{id}` (spreadsheet) | `dingtalk_table` |
| DingTalk AI Table | `alidocs.dingtalk.com/i/nodes/{id}` (multidimensional) | `dingtalk_ai_table` |

## Authentication

DingTalk MCP configuration is stored in the user table's `preferences` field:

```json
{
  "mcps": {
    "dingtalk": {
      "services": {
        "docs": {
          "enabled": true,
          "credentials": {
            "url": "encrypted_url"
          }
        },
        "table": {
          "enabled": true,
          "credentials": {
            "url": "encrypted_url"
          }
        },
        "ai_table": {
          "enabled": true,
          "credentials": {
            "url": "encrypted_url"
          }
        }
      }
    }
  }
}
```

## Usage

### Upload a DingTalk Document to Knowledge Base

```json
{
  "name": "upload_dingtalk_to_kb",
  "arguments": {
    "document_url": "https://alidocs.dingtalk.com/i/nodes/nYMoO1rWx2347Z3je9",
    "knowledge_base_id": 123,
    "document_name": "My Document"
  }
}
```

**Parameters:**

- `document_url` (required): The DingTalk document URL
- `knowledge_base_id` (required): Target knowledge base ID
- `document_name` (optional): Custom name for the document (defaults to original filename)
- `document_type` (optional): Force a specific document type ("docs", "table", "ai_table"). Auto-detected if not specified.

## Workflow

1. **Parse URL**: Extract document ID and determine document type from the DingTalk URL
2. **Get Auth Config**: Retrieve and decrypt DingTalk MCP credentials from user preferences
3. **Download File**: Use appropriate DingTalk MCP tool to download the file to sandbox
4. **Upload to KB**: Upload the downloaded file to the specified knowledge base

## Example User Requests

- "将钉钉文档 https://alidocs.dingtalk.com/i/nodes/xxx 添加到当前知识库"
- "Import this DingTalk spreadsheet to my knowledge base"
- "Upload the AI table from DingTalk to knowledge base ID 123"

## Error Handling

The tool handles common error scenarios:

- Invalid or unsupported DingTalk URLs
- Missing or disabled MCP configuration
- Download failures from DingTalk
- Upload failures to knowledge base
- File size limits

## Dependencies

This skill requires:
- Sandbox environment for file operations
- DingTalk MCP services configured in user preferences
- Access to Wegent knowledge base API
