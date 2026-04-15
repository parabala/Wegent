# SPDX-FileCopyrightText: 2025 WeCode, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""DingTalk to Knowledge Base Upload Tool.

This module provides the UploadDingTalkToKBTool class that downloads
files from DingTalk and uploads them to Wegent knowledge base.
"""

import json
import logging
import os
import re
import time
import urllib.parse
from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Default API base URL
DEFAULT_API_BASE_URL = "http://backend:8000"

# MCP Provider registry for DingTalk
MCP_PROVIDER_REGISTRY = {
    "dingtalk": {
        "provider_id": "dingtalk",
        "services": {
            "docs": {
                "service_id": "docs",
                "server_name": "dingtalk_docs",
                "skill_name": "dingtalk-docs",
            },
            "table": {
                "service_id": "table",
                "server_name": "dingtalk_table",
                "skill_name": "dingtalk-table",
            },
            "ai_table": {
                "service_id": "ai_table",
                "server_name": "dingtalk_ai_table",
                "skill_name": "dingtalk-ai-table",
            },
        },
    }
}


class UploadDingTalkToKBInput(BaseModel):
    """Input schema for upload_dingtalk_to_kb tool."""

    document_url: str = Field(
        ...,
        description="DingTalk document URL (e.g., https://alidocs.dingtalk.com/i/nodes/xxx)",
    )
    knowledge_base_id: int = Field(
        ...,
        description="Target knowledge base ID to upload the document to",
    )
    document_name: Optional[str] = Field(
        default=None,
        description="Custom name for the document (defaults to original filename)",
    )
    document_type: Optional[str] = Field(
        default=None,
        description="Force a specific document type ('docs', 'table', 'ai_table'). Auto-detected if not specified.",
    )


class UploadDingTalkToKBTool(BaseTool):
    """Tool for uploading DingTalk documents to Wegent knowledge base.

    This tool:
    1. Parses the DingTalk URL to extract document ID and type
    2. Retrieves DingTalk MCP credentials from user preferences
    3. Downloads the file from DingTalk using MCP tools
    4. Uploads the file to the specified knowledge base
    """

    name: str = "upload_dingtalk_to_kb"
    display_name: str = "上传钉钉文档到知识库"
    description: str = """Upload a DingTalk document, spreadsheet, or AI table to Wegent knowledge base.

This tool downloads files from DingTalk and uploads them to the specified knowledge base.

Parameters:
- document_url (required): DingTalk document URL (e.g., https://alidocs.dingtalk.com/i/nodes/xxx)
- knowledge_base_id (required): Target knowledge base ID
- document_name (optional): Custom name for the document
- document_type (optional): Force type ('docs', 'table', 'ai_table'). Auto-detected if not specified.

Returns:
- success: Whether the upload succeeded
- document_id: ID of the created document in knowledge base
- message: Status message

Example:
{
  "document_url": "https://alidocs.dingtalk.com/i/nodes/nYMoO1rWx2347Z3je9",
  "knowledge_base_id": 123,
  "document_name": "My Document"
}
"""

    args_schema: type[BaseModel] = UploadDingTalkToKBInput

    # Context parameters
    task_id: int = 0
    subtask_id: int = 0
    user_id: int = 0
    ws_emitter: Any = None
    db_session: Any = None
    auth_token: str = ""

    def _run(
        self,
        document_url: str,
        knowledge_base_id: int,
        document_name: Optional[str] = None,
        document_type: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Synchronous run - not implemented."""
        raise NotImplementedError(
            "UploadDingTalkToKBTool only supports async execution"
        )

    async def _arun(
        self,
        document_url: str,
        knowledge_base_id: int,
        document_name: Optional[str] = None,
        document_type: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Upload DingTalk document to knowledge base.

        Args:
            document_url: DingTalk document URL
            knowledge_base_id: Target knowledge base ID
            document_name: Custom document name
            document_type: Force specific document type
            run_manager: Callback manager

        Returns:
            JSON string with upload result
        """
        start_time = time.time()

        logger.info(
            f"[UploadDingTalkToKBTool] Starting upload: url={document_url}, "
            f"kb_id={knowledge_base_id}, user_id={self.user_id}"
        )

        # Emit status update
        await self._emit_status("running", "Parsing DingTalk URL...")

        try:
            # Step 1: Parse URL and extract document info
            doc_info = self._parse_dingtalk_url(document_url)
            if not doc_info:
                error_msg = "Invalid DingTalk URL format"
                await self._emit_status("failed", error_msg)
                return self._format_error(error_msg)

            doc_id = doc_info["doc_id"]
            detected_type = doc_info["doc_type"]
            final_doc_type = document_type or detected_type

            logger.info(
                f"[UploadDingTalkToKBTool] Parsed document: id={doc_id}, type={final_doc_type}"
            )

            # Step 2: Get user MCP configuration
            await self._emit_status("running", "Retrieving DingTalk configuration...")
            mcp_config = await self._get_mcp_config(final_doc_type)
            if not mcp_config:
                error_msg = f"DingTalk {final_doc_type} MCP not configured or disabled"
                await self._emit_status("failed", error_msg)
                return self._format_error(error_msg)

            # Step 3: Get sandbox manager and create sandbox
            await self._emit_status("running", "Preparing sandbox environment...")
            sandbox_manager = self._get_sandbox_manager()

            sandbox, error = await sandbox_manager.get_or_create_sandbox(
                shell_type="ClaudeCode",
                workspace_ref=None,
            )

            if error:
                error_msg = f"Failed to create sandbox: {error}"
                await self._emit_status("failed", error_msg)
                return self._format_error(error_msg)

            # Step 4: Download file from DingTalk
            await self._emit_status("running", "Downloading file from DingTalk...")

            # Determine file extension based on document type
            file_extension = self._get_file_extension(final_doc_type)
            temp_filename = f"dingtalk_doc_{doc_id}{file_extension}"
            temp_filepath = f"/home/user/{temp_filename}"

            download_result = await self._download_from_dingtalk(
                sandbox=sandbox,
                doc_id=doc_id,
                doc_type=final_doc_type,
                mcp_url=mcp_config["url"],
                save_path=temp_filepath,
            )

            if not download_result["success"]:
                error_msg = f"Failed to download from DingTalk: {download_result.get('error', 'Unknown error')}"
                await self._emit_status("failed", error_msg)
                return self._format_error(error_msg)

            actual_filepath = download_result["file_path"]
            actual_filename = download_result.get("filename", temp_filename)
            file_size = download_result.get("file_size", 0)

            logger.info(
                f"[UploadDingTalkToKBTool] Downloaded: path={actual_filepath}, "
                f"size={file_size}"
            )

            # Step 5: Upload to knowledge base
            await self._emit_status("running", "Uploading to knowledge base...")

            final_document_name = document_name or actual_filename
            upload_result = await self._upload_to_knowledge_base(
                sandbox=sandbox,
                file_path=actual_filepath,
                knowledge_base_id=knowledge_base_id,
                document_name=final_document_name,
                file_size=file_size,
            )

            if not upload_result["success"]:
                error_msg = f"Failed to upload to knowledge base: {upload_result.get('error', 'Unknown error')}"
                await self._emit_status("failed", error_msg)
                return self._format_error(error_msg)

            execution_time = time.time() - start_time

            response = {
                "success": True,
                "document_id": upload_result.get("document_id"),
                "knowledge_base_id": knowledge_base_id,
                "document_name": final_document_name,
                "file_size": file_size,
                "dingtalk_doc_id": doc_id,
                "document_type": final_doc_type,
                "message": f"Successfully uploaded '{final_document_name}' to knowledge base",
                "execution_time": execution_time,
            }

            logger.info(
                f"[UploadDingTalkToKBTool] Upload successful: doc_id={upload_result.get('document_id')}"
            )

            await self._emit_status("completed", response["message"], response)
            return json.dumps(response, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"[UploadDingTalkToKBTool] Upload failed: {e}", exc_info=True)
            error_msg = f"Upload failed: {str(e)}"
            await self._emit_status("failed", error_msg)
            return self._format_error(error_msg)

    def _parse_dingtalk_url(self, url: str) -> Optional[dict[str, str]]:
        """Parse DingTalk URL to extract document ID and type.

        Args:
            url: DingTalk document URL

        Returns:
            Dictionary with doc_id and doc_type, or None if invalid
        """
        # Pattern for alidocs.dingtalk.com URLs
        # Examples:
        # https://alidocs.dingtalk.com/i/nodes/nYMoO1rWx2347Z3je9
        # https://alidocs.dingtalk.com/i/nodes/nYMoO1rWx2347Z3je9?utm_scene=person_space
        pattern = r"alidocs\.dingtalk\.com/i/nodes/([a-zA-Z0-9]+)"
        match = re.search(pattern, url)

        if not match:
            logger.warning(f"[UploadDingTalkToKBTool] URL does not match pattern: {url}")
            return None

        doc_id = match.group(1)

        # Try to detect document type from URL parameters or path
        # Default to 'docs' if cannot determine
        doc_type = "docs"

        # Parse query parameters
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed.query)

        # Check for type hints in URL
        path = parsed.path.lower()
        if "sheet" in path or "table" in path:
            doc_type = "table"
        elif "ai" in path or "multidimensional" in path or "able" in path:
            doc_type = "ai_table"

        return {"doc_id": doc_id, "doc_type": doc_type}

    async def _get_mcp_config(self, doc_type: str) -> Optional[dict[str, Any]]:
        """Get MCP configuration for the specified document type.

        Args:
            doc_type: Document type ('docs', 'table', 'ai_table')

        Returns:
            MCP configuration with URL, or None if not configured
        """
        if not self.db_session:
            logger.error("[UploadDingTalkToKBTool] No database session available")
            return None

        try:
            # Import here to avoid circular dependencies
            from app.services.user_mcp_service import UserMCPService
            from app.models.user import User

            # Query user preferences
            result = await self.db_session.execute(
                "SELECT preferences FROM users WHERE id = :user_id",
                {"user_id": self.user_id},
            )
            row = result.fetchone()

            if not row:
                logger.warning(f"[UploadDingTalkToKBTool] User not found: {self.user_id}")
                return None

            preferences = row[0]

            # Get service config using UserMCPService
            service_config = UserMCPService.get_provider_service_config(
                preferences, "dingtalk", doc_type
            )

            if not service_config.get("enabled") or not service_config.get("url"):
                logger.warning(
                    f"[UploadDingTalkToKBTool] MCP not enabled or no URL for {doc_type}"
                )
                return None

            return {
                "enabled": service_config["enabled"],
                "url": service_config["url"],
            }

        except Exception as e:
            logger.error(f"[UploadDingTalkToKBTool] Failed to get MCP config: {e}")
            return None

    def _get_sandbox_manager(self):
        """Get sandbox manager instance.

        Returns:
            SandboxManager instance
        """
        # Import here to avoid circular dependencies
        from chat_shell.tools.sandbox import SandboxManager

        return SandboxManager(
            task_id=self.task_id,
            subtask_id=self.subtask_id,
            ws_emitter=self.ws_emitter,
        )

    def _get_file_extension(self, doc_type: str) -> str:
        """Get file extension based on document type.

        Args:
            doc_type: Document type

        Returns:
            File extension including dot
        """
        extensions = {
            "docs": ".docx",
            "table": ".xlsx",
            "ai_table": ".xlsx",
        }
        return extensions.get(doc_type, ".bin")

    async def _download_from_dingtalk(
        self,
        sandbox: Any,
        doc_id: str,
        doc_type: str,
        mcp_url: str,
        save_path: str,
    ) -> dict[str, Any]:
        """Download file from DingTalk using MCP tools.

        Args:
            sandbox: Sandbox instance
            doc_id: DingTalk document ID
            doc_type: Document type
            mcp_url: MCP server URL
            save_path: Path to save the file

        Returns:
            Dictionary with success status and file info
        """
        try:
            # Determine which MCP tool to use based on document type
            if doc_type == "docs":
                # For docs, we need to get document info first, then download
                return await self._download_dingtalk_doc(sandbox, doc_id, mcp_url, save_path)
            elif doc_type == "table":
                return await self._download_dingtalk_table(sandbox, doc_id, mcp_url, save_path)
            elif doc_type == "ai_table":
                return await self._download_dingtalk_ai_table(sandbox, doc_id, mcp_url, save_path)
            else:
                return {"success": False, "error": f"Unsupported document type: {doc_type}"}

        except Exception as e:
            logger.error(f"[UploadDingTalkToKBTool] Download error: {e}")
            return {"success": False, "error": str(e)}

    async def _download_dingtalk_doc(
        self,
        sandbox: Any,
        doc_id: str,
        mcp_url: str,
        save_path: str,
    ) -> dict[str, Any]:
        """Download DingTalk document using MCP.

        For DingTalk docs, we:
        1. Get document info to check type
        2. Download as appropriate format
        """
        try:
            # First, get document info
            api_base_url = os.getenv("BACKEND_API_URL", DEFAULT_API_BASE_URL).rstrip("/")
            auth_token = self.auth_token

            if not auth_token:
                return {"success": False, "error": "No auth token available"}

            # Build curl command to call MCP through backend proxy
            # First get document info
            get_info_cmd = (
                f"curl -s -X POST '{mcp_url}/tools/get_document_info' "
                f'-H "Content-Type: application/json" '
                f'-H "Authorization: Bearer {auth_token}" '
                f'--data \'{"nodeId": "' + doc_id + '"}\' '
            )

            result = await sandbox.commands.run(
                cmd=get_info_cmd,
                cwd="/home/user",
                timeout=60,
            )

            if result.exit_code != 0:
                return {"success": False, "error": f"Failed to get doc info: {result.stderr}"}

            # Parse document info
            try:
                doc_info = json.loads(result.stdout)
            except json.JSONDecodeError:
                doc_info = {}

            content_type = doc_info.get("contentType", "")
            extension = doc_info.get("extension", "")
            doc_name = doc_info.get("name", f"dingtalk_doc_{doc_id}")

            # Determine download method based on document type
            if content_type == "ALIDOC" and extension == "adoc":
                # Online document - get content as markdown
                return await self._download_dingtalk_adoc(
                    sandbox, doc_id, mcp_url, save_path, doc_name
                )
            else:
                # Regular file - download directly
                return await self._download_dingtalk_file(
                    sandbox, doc_id, mcp_url, save_path, doc_name
                )

        except Exception as e:
            logger.error(f"[UploadDingTalkToKBTool] Doc download error: {e}")
            return {"success": False, "error": str(e)}

    async def _download_dingtalk_adoc(
        self,
        sandbox: Any,
        doc_id: str,
        mcp_url: str,
        save_path: str,
        doc_name: str,
    ) -> dict[str, Any]:
        """Download DingTalk online document as markdown."""
        try:
            auth_token = self.auth_token

            # Get document content as markdown
            get_content_cmd = (
                f"curl -s -X POST '{mcp_url}/tools/get_document_content' "
                f'-H "Content-Type: application/json" '
                f'-H "Authorization: Bearer {auth_token}" '
                f'--data \'{"nodeId": "' + doc_id + '"}\' '
            )

            result = await sandbox.commands.run(
                cmd=get_content_cmd,
                cwd="/home/user",
                timeout=120,
            )

            if result.exit_code != 0:
                return {"success": False, "error": f"Failed to get doc content: {result.stderr}"}

            # Parse response
            try:
                response = json.loads(result.stdout)
                content = response.get("content", "")
            except json.JSONDecodeError:
                content = result.stdout

            # Save as markdown file
            if not save_path.endswith(".md"):
                save_path = save_path.rsplit(".", 1)[0] + ".md"

            # Write content to file
            write_cmd = f'cat > "{save_path}" << \'EOF\'\n{content}\nEOF'

            result = await sandbox.commands.run(
                cmd=write_cmd,
                cwd="/home/user",
                timeout=30,
            )

            if result.exit_code != 0:
                return {"success": False, "error": f"Failed to write file: {result.stderr}"}

            # Get file size
            file_info = await sandbox.files.get_info(save_path)

            return {
                "success": True,
                "file_path": save_path,
                "filename": f"{doc_name}.md",
                "file_size": file_info.size,
            }

        except Exception as e:
            logger.error(f"[UploadDingTalkToKBTool] Adoc download error: {e}")
            return {"success": False, "error": str(e)}

    async def _download_dingtalk_file(
        self,
        sandbox: Any,
        doc_id: str,
        mcp_url: str,
        save_path: str,
        doc_name: str,
    ) -> dict[str, Any]:
        """Download DingTalk file using download_file MCP tool."""
        try:
            auth_token = self.auth_token

            # Call download_file MCP tool to get download URL
            download_info_cmd = (
                f"curl -s -X POST '{mcp_url}/tools/download_file' "
                f'-H "Content-Type: application/json" '
                f'-H "Authorization: Bearer {auth_token}" '
                f'--data \'{"nodeId": "' + doc_id + '"}\' '
            )

            result = await sandbox.commands.run(
                cmd=download_info_cmd,
                cwd="/home/user",
                timeout=60,
            )

            if result.exit_code != 0:
                return {"success": False, "error": f"Failed to get download info: {result.stderr}"}

            # Parse download info
            try:
                download_info = json.loads(result.stdout)
                resource_url = download_info.get("resourceUrl", "")
                headers = download_info.get("headers", {})
            except json.JSONDecodeError as e:
                return {"success": False, "error": f"Failed to parse download info: {e}"}

            if not resource_url:
                return {"success": False, "error": "No download URL returned"}

            # Download file using curl with headers
            header_args = " ".join([f'-H "{k}: {v}"' for k, v in headers.items()])
            download_cmd = f'curl -s -L {header_args} "{resource_url}" -o "{save_path}"'

            result = await sandbox.commands.run(
                cmd=download_cmd,
                cwd="/home/user",
                timeout=300,
            )

            if result.exit_code != 0:
                return {"success": False, "error": f"Failed to download file: {result.stderr}"}

            # Get file size
            file_info = await sandbox.files.get_info(save_path)

            return {
                "success": True,
                "file_path": save_path,
                "filename": doc_name,
                "file_size": file_info.size,
            }

        except Exception as e:
            logger.error(f"[UploadDingTalkToKBTool] File download error: {e}")
            return {"success": False, "error": str(e)}

    async def _download_dingtalk_table(
        self,
        sandbox: Any,
        doc_id: str,
        mcp_url: str,
        save_path: str,
    ) -> dict[str, Any]:
        """Download DingTalk spreadsheet.

        For spreadsheets, we export as Excel file.
        """
        try:
            auth_token = self.auth_token

            # First get all sheets
            get_sheets_cmd = (
                f"curl -s -X POST '{mcp_url}/tools/get_all_sheets' "
                f'-H "Content-Type: application/json" '
                f'-H "Authorization: Bearer {auth_token}" '
                f'--data \'{"nodeId": "' + doc_id + '"}\' '
            )

            result = await sandbox.commands.run(
                cmd=get_sheets_cmd,
                cwd="/home/user",
                timeout=60,
            )

            if result.exit_code != 0:
                return {"success": False, "error": f"Failed to get sheets: {result.stderr}"}

            # Parse sheets info
            try:
                sheets_info = json.loads(result.stdout)
                sheets = sheets_info.get("sheets", [])
            except json.JSONDecodeError:
                sheets = []

            if not sheets:
                return {"success": False, "error": "No sheets found in spreadsheet"}

            # For now, export the first sheet as CSV
            # In a more complete implementation, we could export all sheets
            first_sheet = sheets[0]
            sheet_id = first_sheet.get("id") or first_sheet.get("name", "Sheet1")

            # Get sheet data
            get_range_cmd = (
                f"curl -s -X POST '{mcp_url}/tools/get_range' "
                f'-H "Content-Type: application/json" '
                f'-H "Authorization: Bearer {auth_token}" '
                f'--data \'{"nodeId": "' + doc_id + '", "sheetId": "' + sheet_id + '"}\' '
            )

            result = await sandbox.commands.run(
                cmd=get_range_cmd,
                cwd="/home/user",
                timeout=120,
            )

            if result.exit_code != 0:
                return {"success": False, "error": f"Failed to get sheet data: {result.stderr}"}

            # Parse sheet data
            try:
                sheet_data = json.loads(result.stdout)
                values = sheet_data.get("values", [])
            except json.JSONDecodeError:
                values = []

            # Convert to CSV and save
            import csv
            import io

            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerows(values)
            csv_content = csv_buffer.getvalue()

            # Save as CSV
            if not save_path.endswith(".csv"):
                save_path = save_path.rsplit(".", 1)[0] + ".csv"

            write_cmd = f'cat > "{save_path}" << \'EOF\'\n{csv_content}\nEOF'

            result = await sandbox.commands.run(
                cmd=write_cmd,
                cwd="/home/user",
                timeout=30,
            )

            if result.exit_code != 0:
                return {"success": False, "error": f"Failed to write CSV: {result.stderr}"}

            # Get file size
            file_info = await sandbox.files.get_info(save_path)

            return {
                "success": True,
                "file_path": save_path,
                "filename": f"dingtalk_table_{doc_id}.csv",
                "file_size": file_info.size,
            }

        except Exception as e:
            logger.error(f"[UploadDingTalkToKBTool] Table download error: {e}")
            return {"success": False, "error": str(e)}

    async def _download_dingtalk_ai_table(
        self,
        sandbox: Any,
        doc_id: str,
        mcp_url: str,
        save_path: str,
    ) -> dict[str, Any]:
        """Download DingTalk AI table (multidimensional table).

        For AI tables, we export as JSON or CSV.
        """
        try:
            auth_token = self.auth_token

            # Get all tables in the base
            get_tables_cmd = (
                f"curl -s -X POST '{mcp_url}/tools/get_tables' "
                f'-H "Content-Type: application/json" '
                f'-H "Authorization: Bearer {auth_token}" '
                f'--data \'{"nodeId": "' + doc_id + '"}\' '
            )

            result = await sandbox.commands.run(
                cmd=get_tables_cmd,
                cwd="/home/user",
                timeout=60,
            )

            if result.exit_code != 0:
                return {"success": False, "error": f"Failed to get tables: {result.stderr}"}

            # Parse tables info
            try:
                tables_info = json.loads(result.stdout)
                tables = tables_info.get("tables", [])
            except json.JSONDecodeError:
                tables = []

            if not tables:
                return {"success": False, "error": "No tables found in AI table"}

            # Get records from the first table
            first_table = tables[0]
            table_id = first_table.get("id")

            get_records_cmd = (
                f"curl -s -X POST '{mcp_url}/tools/query_records' "
                f'-H "Content-Type: application/json" '
                f'-H "Authorization: Bearer {auth_token}" '
                f'--data \'{"nodeId": "' + doc_id + '", "tableId": "' + table_id + '"}\' '
            )

            result = await sandbox.commands.run(
                cmd=get_records_cmd,
                cwd="/home/user",
                timeout=120,
            )

            if result.exit_code != 0:
                return {"success": False, "error": f"Failed to get records: {result.stderr}"}

            # Parse records
            try:
                records_data = json.loads(result.stdout)
                records = records_data.get("records", [])
            except json.JSONDecodeError:
                records = []

            # Save as JSON
            if not save_path.endswith(".json"):
                save_path = save_path.rsplit(".", 1)[0] + ".json"

            json_content = json.dumps(records, ensure_ascii=False, indent=2)

            write_cmd = f'cat > "{save_path}" << \'EOF\'\n{json_content}\nEOF'

            result = await sandbox.commands.run(
                cmd=write_cmd,
                cwd="/home/user",
                timeout=30,
            )

            if result.exit_code != 0:
                return {"success": False, "error": f"Failed to write JSON: {result.stderr}"}

            # Get file size
            file_info = await sandbox.files.get_info(save_path)

            return {
                "success": True,
                "file_path": save_path,
                "filename": f"dingtalk_ai_table_{doc_id}.json",
                "file_size": file_info.size,
            }

        except Exception as e:
            logger.error(f"[UploadDingTalkToKBTool] AI table download error: {e}")
            return {"success": False, "error": str(e)}

    async def _upload_to_knowledge_base(
        self,
        sandbox: Any,
        file_path: str,
        knowledge_base_id: int,
        document_name: str,
        file_size: int,
    ) -> dict[str, Any]:
        """Upload file to knowledge base.

        Args:
            sandbox: Sandbox instance
            file_path: Path to the file in sandbox
            knowledge_base_id: Target knowledge base ID
            document_name: Document name
            file_size: File size in bytes

        Returns:
            Dictionary with success status and document info
        """
        try:
            api_base_url = os.getenv("BACKEND_API_URL", DEFAULT_API_BASE_URL).rstrip("/")
            auth_token = self.auth_token

            if not auth_token:
                return {"success": False, "error": "No auth token available"}

            # Read file content and encode as base64
            read_cmd = f'base64 "{file_path}"'
            result = await sandbox.commands.run(
                cmd=read_cmd,
                cwd="/home/user",
                timeout=60,
            )

            if result.exit_code != 0:
                return {"success": False, "error": f"Failed to read file: {result.stderr}"}

            file_base64 = result.stdout.strip()

            # Determine file extension
            file_extension = os.path.splitext(file_path)[1].lstrip(".")
            if not file_extension:
                file_extension = "txt"

            # Build API request to create document
            create_doc_url = f"{api_base_url}/api/knowledge/bases/{knowledge_base_id}/documents"

            payload = {
                "name": document_name,
                "source_type": "file",
                "file_base64": file_base64,
                "file_extension": file_extension,
                "trigger_indexing": True,
                "trigger_summary": True,
            }

            # Use curl to call API
            json_payload = json.dumps(payload, ensure_ascii=False)
            # Escape for shell
            json_payload_escaped = json_payload.replace("'", "'\\''")

            curl_cmd = (
                f"curl -s -X POST '{create_doc_url}' "
                f'-H "Content-Type: application/json" '
                f'-H "Authorization: Bearer {auth_token}" '
                f"--data '{json_payload_escaped}'"
            )

            result = await sandbox.commands.run(
                cmd=curl_cmd,
                cwd="/home/user",
                timeout=120,
            )

            if result.exit_code != 0:
                return {"success": False, "error": f"API request failed: {result.stderr}"}

            # Parse response
            try:
                response = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                return {"success": False, "error": f"Failed to parse API response: {e}"}

            if "id" not in response and "document_id" not in response:
                # Check for error
                if "detail" in response:
                    return {"success": False, "error": f"API error: {response['detail']}"}
                return {"success": False, "error": f"Unexpected API response: {result.stdout[:500]}"}

            document_id = response.get("id") or response.get("document_id")

            return {
                "success": True,
                "document_id": document_id,
            }

        except Exception as e:
            logger.error(f"[UploadDingTalkToKBTool] Upload to KB error: {e}")
            return {"success": False, "error": str(e)}

    async def _emit_status(
        self,
        status: str,
        message: str,
        result: Optional[dict[str, Any]] = None,
    ) -> None:
        """Emit status update via WebSocket.

        Args:
            status: Status string (running, completed, failed)
            message: Status message
            result: Optional result data
        """
        if not self.ws_emitter:
            return

        try:
            await self.ws_emitter.emit_tool_call(
                task_id=self.task_id,
                tool_name=self.name,
                tool_input={},
                status=status,
                result=result,
            )
        except Exception as e:
            logger.warning(f"[UploadDingTalkToKBTool] Failed to emit status: {e}")

    def _format_error(self, error_message: str) -> str:
        """Format error response.

        Args:
            error_message: Error message

        Returns:
            JSON error response string
        """
        return json.dumps(
            {
                "success": False,
                "error": error_message,
                "document_id": None,
                "knowledge_base_id": None,
                "document_name": None,
            },
            ensure_ascii=False,
            indent=2,
        )
