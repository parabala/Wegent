# SPDX-FileCopyrightText: 2025 WeCode, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""DingTalk to Knowledge Base Upload Tool.

This module provides the UploadDingTalkToKBTool class that downloads
files from DingTalk and uploads them to Wegent knowledge base.

The tool uses the backend MCP proxy API to call DingTalk MCP tools,
which handles authentication and MCP protocol details.
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
    2. Retrieves DingTalk MCP credentials from user preferences via backend API
    3. Downloads the file from DingTalk using backend MCP proxy API
    4. Uploads the file to the specified knowledge base

    The backend MCP proxy API handles:
    - User MCP configuration retrieval and decryption
    - MCP tool invocation
    - Authentication with DingTalk MCP servers
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

            # Step 2: Get sandbox manager and create sandbox
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

            # Step 3: Download file from DingTalk via backend MCP proxy
            await self._emit_status("running", "Downloading file from DingTalk...")

            # Determine file extension based on document type
            file_extension = self._get_file_extension(final_doc_type)
            temp_filename = f"dingtalk_doc_{doc_id}{file_extension}"
            temp_filepath = f"/home/user/{temp_filename}"

            download_result = await self._download_from_dingtalk(
                sandbox=sandbox,
                doc_id=doc_id,
                doc_type=final_doc_type,
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

            # Step 4: Upload to knowledge base
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
        save_path: str,
    ) -> dict[str, Any]:
        """Download file from DingTalk using backend MCP proxy API.

        Args:
            sandbox: Sandbox instance
            doc_id: DingTalk document ID
            doc_type: Document type
            save_path: Path to save the file

        Returns:
            Dictionary with success status and file info
        """
        try:
            # Determine which MCP tool flow to use based on document type
            if doc_type == "docs":
                return await self._download_dingtalk_doc(sandbox, doc_id, save_path)
            elif doc_type == "table":
                return await self._download_dingtalk_table(sandbox, doc_id, save_path)
            elif doc_type == "ai_table":
                return await self._download_dingtalk_ai_table(sandbox, doc_id, save_path)
            else:
                return {"success": False, "error": f"Unsupported document type: {doc_type}"}

        except Exception as e:
            logger.error(f"[UploadDingTalkToKBTool] Download error: {e}")
            return {"success": False, "error": str(e)}

    async def _call_backend_mcp_proxy(
        self,
        sandbox: Any,
        service_id: str,
        tool_name: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Call DingTalk MCP tool via backend proxy API.

        Args:
            sandbox: Sandbox instance
            service_id: DingTalk service ID (docs, table, ai_table)
            tool_name: Name of the MCP tool to call
            parameters: Tool parameters

        Returns:
            Tool result as dictionary
        """
        api_base_url = os.getenv("BACKEND_API_URL", DEFAULT_API_BASE_URL).rstrip("/")
        auth_token = self.auth_token

        if not auth_token:
            raise ValueError("No auth token available for MCP proxy call")

        # Build backend MCP proxy URL
        proxy_url = f"{api_base_url}/api/internal/mcp/dingtalk/{service_id}/call"

        # Build request payload
        payload = {
            "tool_name": tool_name,
            "parameters": parameters,
        }

        # Build curl command
        json_payload = json.dumps(payload, ensure_ascii=False)
        json_payload_escaped = json_payload.replace("'", "'\\''")

        curl_cmd = (
            f"curl -s -X POST '{proxy_url}' "
            f'-H "Content-Type: application/json" '
            f'-H "Authorization: Bearer {auth_token}" '
            f"--data '{json_payload_escaped}'"
        )

        logger.debug(f"[UploadDingTalkToKBTool] Calling MCP proxy: {tool_name}")

        result = await sandbox.commands.run(
            cmd=curl_cmd,
            cwd="/home/user",
            timeout=120,
        )

        if result.exit_code != 0:
            raise RuntimeError(f"MCP proxy call failed: {result.stderr}")

        # Parse response
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse MCP proxy response: {e}")

        if not response.get("success"):
            error_msg = response.get("error", "Unknown error from MCP proxy")
            raise RuntimeError(error_msg)

        return response.get("result", {})

    async def _download_dingtalk_doc(
        self,
        sandbox: Any,
        doc_id: str,
        save_path: str,
    ) -> dict[str, Any]:
        """Download DingTalk document using backend MCP proxy.

        For DingTalk docs, we:
        1. Get document info to check type
        2. Download as appropriate format
        """
        try:
            # Step 1: Get document info
            logger.debug(f"[UploadDingTalkToKBTool] Getting doc info for {doc_id}")

            doc_info = await self._call_backend_mcp_proxy(
                sandbox=sandbox,
                service_id="docs",
                tool_name="get_document_info",
                parameters={"nodeId": doc_id},
            )

            content_type = doc_info.get("contentType", "")
            extension = doc_info.get("extension", "")
            doc_name = doc_info.get("name", f"dingtalk_doc_{doc_id}")

            logger.debug(
                f"[UploadDingTalkToKBTool] Doc info: type={content_type}, ext={extension}"
            )

            # Determine download method based on document type
            if content_type == "ALIDOC" and extension == "adoc":
                # Online document - get content as markdown
                return await self._download_dingtalk_adoc(
                    sandbox, doc_id, save_path, doc_name
                )
            else:
                # Regular file - download using download_file
                return await self._download_dingtalk_file(
                    sandbox, doc_id, save_path, doc_name
                )

        except Exception as e:
            logger.error(f"[UploadDingTalkToKBTool] Doc download error: {e}")
            return {"success": False, "error": str(e)}

    async def _download_dingtalk_adoc(
        self,
        sandbox: Any,
        doc_id: str,
        save_path: str,
        doc_name: str,
    ) -> dict[str, Any]:
        """Download DingTalk online document as markdown."""
        try:
            # Get document content as markdown
            logger.debug(f"[UploadDingTalkToKBTool] Getting doc content for {doc_id}")

            content_result = await self._call_backend_mcp_proxy(
                sandbox=sandbox,
                service_id="docs",
                tool_name="get_document_content",
                parameters={"nodeId": doc_id},
            )

            content = content_result.get("content", "")

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
        save_path: str,
        doc_name: str,
    ) -> dict[str, Any]:
        """Download DingTalk file using download_file MCP tool."""
        try:
            # Step 1: Call download_file to get download URL
            logger.debug(f"[UploadDingTalkToKBTool] Getting download URL for {doc_id}")

            download_info = await self._call_backend_mcp_proxy(
                sandbox=sandbox,
                service_id="docs",
                tool_name="download_file",
                parameters={"nodeId": doc_id},
            )

            resource_url = download_info.get("resourceUrl", "")
            headers = download_info.get("headers", {})

            if not resource_url:
                return {"success": False, "error": "No download URL returned from MCP"}

            logger.debug(f"[UploadDingTalkToKBTool] Downloading from: {resource_url[:100]}...")

            # Step 2: Download file using curl with headers
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
        save_path: str,
    ) -> dict[str, Any]:
        """Download DingTalk spreadsheet.

        For spreadsheets, we export as CSV file.
        """
        try:
            # Step 1: Get all sheets
            logger.debug(f"[UploadDingTalkToKBTool] Getting sheets for {doc_id}")

            sheets_info = await self._call_backend_mcp_proxy(
                sandbox=sandbox,
                service_id="table",
                tool_name="get_all_sheets",
                parameters={"nodeId": doc_id},
            )

            sheets = sheets_info.get("sheets", [])

            if not sheets:
                return {"success": False, "error": "No sheets found in spreadsheet"}

            # For now, export the first sheet as CSV
            first_sheet = sheets[0]
            sheet_id = first_sheet.get("id") or first_sheet.get("name", "Sheet1")
            sheet_name = first_sheet.get("name", "Sheet1")

            logger.debug(f"[UploadDingTalkToKBTool] Getting data from sheet: {sheet_id}")

            # Step 2: Get sheet data
            sheet_data = await self._call_backend_mcp_proxy(
                sandbox=sandbox,
                service_id="table",
                tool_name="get_range",
                parameters={"nodeId": doc_id, "sheetId": sheet_id},
            )

            values = sheet_data.get("values", [])

            # Step 3: Convert to CSV and save
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
                "filename": f"{sheet_name}.csv",
                "file_size": file_info.size,
            }

        except Exception as e:
            logger.error(f"[UploadDingTalkToKBTool] Table download error: {e}")
            return {"success": False, "error": str(e)}

    async def _download_dingtalk_ai_table(
        self,
        sandbox: Any,
        doc_id: str,
        save_path: str,
    ) -> dict[str, Any]:
        """Download DingTalk AI table (multidimensional table).

        For AI tables, we export as JSON.
        """
        try:
            # Step 1: Get all tables in the base
            logger.debug(f"[UploadDingTalkToKBTool] Getting tables for {doc_id}")

            tables_info = await self._call_backend_mcp_proxy(
                sandbox=sandbox,
                service_id="ai_table",
                tool_name="get_tables",
                parameters={"nodeId": doc_id},
            )

            tables = tables_info.get("tables", [])

            if not tables:
                return {"success": False, "error": "No tables found in AI table"}

            # Get records from the first table
            first_table = tables[0]
            table_id = first_table.get("id")
            table_name = first_table.get("name", "Table1")

            logger.debug(f"[UploadDingTalkToKBTool] Getting records from table: {table_id}")

            # Step 2: Get records
            records_data = await self._call_backend_mcp_proxy(
                sandbox=sandbox,
                service_id="ai_table",
                tool_name="query_records",
                parameters={"nodeId": doc_id, "tableId": table_id},
            )

            records = records_data.get("records", [])

            # Step 3: Save as JSON
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
                "filename": f"{table_name}.json",
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
