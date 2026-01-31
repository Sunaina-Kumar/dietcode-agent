import asyncio
import json
import os
from typing import Any, Dict, List, Optional


class MCPClient:
    """Client for interacting with MCP servers"""
    
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        self.servers = {}
    
    async def start_server(self, server_name: str):
        """Start an MCP server process"""
        if server_name in self.servers:
            return
        
        server_config = self.config['mcpServers'][server_name]
        command = server_config['command']
        args = server_config.get('args', [])
        env = os.environ.copy()
        
        # Replace environment variable placeholders
        for key, value in server_config.get('env', {}).items():
            if value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                env[key] = os.environ.get(env_var, '')
            else:
                env[key] = value
        
        # Start MCP server process
        process = await asyncio.create_subprocess_exec(
            command,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        self.servers[server_name] = process
        print(f"✅ Started MCP server: {server_name}")
    
    async def call_tool(
        self, 
        server_name: str, 
        tool_name: str, 
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool on an MCP server"""
        if server_name not in self.servers:
            await self.start_server(server_name)
        
        process = self.servers[server_name]
        
        # MCP protocol: send tool call request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        request_json = json.dumps(request) + "\n"
        process.stdin.write(request_json.encode())
        await process.stdin.drain()
        
        # Read response
        response_line = await process.stdout.readline()
        response = json.loads(response_line.decode())
        
        if "error" in response:
            raise Exception(f"MCP tool call failed: {response['error']}")
        
        return response.get("result", {})
    
    async def close(self):
        """Close all MCP server processes"""
        for server_name, process in self.servers.items():
            process.terminate()
            await process.wait()
            print(f"✅ Stopped MCP server: {server_name}")


class GitHubMCP:
    """Wrapper for GitHub MCP server tools"""
    
    def __init__(self, client: MCPClient):
        self.client = client
        self.server_name = "github"
    
    async def get_pr_info(self, owner: str, repo: str, pr_number: int) -> Dict:
        """Get PR information"""
        return await self.client.call_tool(
            self.server_name,
            "get_pull_request",
            {"owner": owner, "repo": repo, "pull_number": pr_number}
        )
    
    async def get_pr_checks(self, owner: str, repo: str, pr_number: int) -> List[Dict]:
        """Get CI check runs for a PR"""
        return await self.client.call_tool(
            self.server_name,
            "list_check_runs",
            {"owner": owner, "repo": repo, "pull_number": pr_number}
        )
    
    async def get_check_logs(self, owner: str, repo: str, check_run_id: int) -> str:
        """Get logs from a check run"""
        return await self.client.call_tool(
            self.server_name,
            "get_check_run_logs",
            {"owner": owner, "repo": repo, "check_run_id": check_run_id}
        )
    
    async def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """Get PR diff"""
        return await self.client.call_tool(
            self.server_name,
            "get_pull_request_diff",
            {"owner": owner, "repo": repo, "pull_number": pr_number}
        )
    
    async def post_comment(self, owner: str, repo: str, pr_number: int, body: str) -> Dict:
        """Post a comment on a PR"""
        return await self.client.call_tool(
            self.server_name,
            "create_issue_comment",
            {"owner": owner, "repo": repo, "issue_number": pr_number, "body": body}
        )
    
    async def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str:
        """Get file content from repository"""
        return await self.client.call_tool(
            self.server_name,
            "get_file_contents",
            {"owner": owner, "repo": repo, "path": path, "ref": ref}
        )


class FilesystemMCP:
    """Wrapper for Filesystem MCP server tools"""
    
    def __init__(self, client: MCPClient):
        self.client = client
        self.server_name = "filesystem"
    
    async def read_file(self, path: str) -> str:
        """Read file contents"""
        result = await self.client.call_tool(
            self.server_name,
            "read_file",
            {"path": path}
        )
        return result.get("content", "")
    
    async def write_file(self, path: str, content: str) -> Dict:
        """Write content to file"""
        return await self.client.call_tool(
            self.server_name,
            "write_file",
            {"path": path, "content": content}
        )
    
    async def list_directory(self, path: str) -> List[str]:
        """List directory contents"""
        result = await self.client.call_tool(
            self.server_name,
            "list_directory",
            {"path": path}
        )
        return result.get("entries", [])