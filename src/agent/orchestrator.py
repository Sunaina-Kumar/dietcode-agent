import asyncio
import os
import re
from typing import Dict, List, Optional
from dotenv import load_dotenv

from ..mcp.client import MCPClient, GitHubMCP, FilesystemMCP
from .analyzer import CILogAnalyzer, FailureType
from .fix_generator import FixGenerator


class DietCodeAgent:
    """Main orchestrator for CI failure diagnosis and repair"""
    
    def __init__(self):
        load_dotenv()
        
        # Initialize MCP client
        mcp_config_path = os.getenv("MCP_CONFIG_PATH", "./config/mcp_config.json")
        self.mcp_client = MCPClient(mcp_config_path)
        self.github = GitHubMCP(self.mcp_client)
        self.filesystem = FilesystemMCP(self.mcp_client)
        
        # Initialize components
        self.analyzer = CILogAnalyzer()
        self.fix_generator = FixGenerator(
            api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
        )
        
        # Configuration
        self.max_attempts = int(os.getenv("MAX_DIAGNOSIS_ATTEMPTS", "3"))
        self.confidence_threshold = float(os.getenv("PATCH_CONFIDENCE_THRESHOLD", "0.7"))
    
    async def process_pr_failure(
        self,
        owner: str,
        repo: str,
        pr_number: int
    ) -> Dict:
        """
        Main entry point: process a failed PR
        
        Returns:
            dict with diagnosis results and proposed fix
        """
        print(f"🔍 Processing PR #{pr_number} in {owner}/{repo}")
        
        # Step 1: Get PR information
        pr_info = await self.github.get_pr_info(owner, repo, pr_number)
        print(f"📋 PR Title: {pr_info.get('title', 'N/A')}")
        
        # Step 2: Get failed CI checks
        check_runs = await self.github.get_pr_checks(owner, repo, pr_number)
        failed_checks = [c for c in check_runs if c.get('conclusion') == 'failure']
        
        if not failed_checks:
            return {"status": "no_failures", "message": "No failed CI checks found"}
        
        print(f"❌ Found {len(failed_checks)} failed check(s)")
        
        # Step 3: Analyze first failed check
        check = failed_checks[0]
        check_id = check['id']
        check_name = check['name']
        
        print(f"🔬 Analyzing check: {check_name}")
        logs = await self.github.get_check_logs(owner, repo, check_id)
        
        # Step 4: Diagnose failure
        diagnosis = self.analyzer.analyze(logs)
        print(f"🎯 Diagnosis: {diagnosis['failure_type'].value} (confidence: {diagnosis['confidence']:.0%})")
        
        if diagnosis['confidence'] < self.confidence_threshold:
            return {
                "status": "low_confidence",
                "diagnosis": diagnosis,
                "message": "Unable to confidently diagnose the failure"
            }
        
        # Step 5: Locate root cause file
        affected_file = await self._locate_affected_file(
            owner, repo, pr_number, diagnosis
        )
        
        if not affected_file:
            return {
                "status": "file_not_found",
                "diagnosis": diagnosis,
                "message": "Could not locate the affected file"
            }
        
        print(f"📁 Affected file: {affected_file}")
        
        # Step 6: Get file content
        pr_head_ref = pr_info['head']['ref']
        file_content = await self.github.get_file_content(
            owner, repo, affected_file, pr_head_ref
        )
        
        # Step 7: Generate fix
        fix = await self.fix_generator.generate_fix(
            diagnosis['failure_type'],
            diagnosis['details'],
            file_content,
            affected_file
        )
        
        print(f"🔧 Generated fix: {fix['fix_type']} (confidence: {fix['confidence']:.0%})")
        
        # Step 8: Post fix as PR comment
        comment_body = self._format_fix_comment(diagnosis, fix, check_name)
        await self.github.post_comment(owner, repo, pr_number, comment_body)
        
        print("💬 Posted fix comment to PR")
        
        return {
            "status": "success",
            "diagnosis": diagnosis,
            "fix": fix,
            "affected_file": affected_file
        }
    
    async def _locate_affected_file(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        diagnosis: Dict
    ) -> Optional[str]:
        """Locate the file that caused the failure"""
        # Extract file from stack trace or error details
        if 'missing_module' in diagnosis['details']:
            # For import errors, check PR diff for related files
            diff = await self.github.get_pr_diff(owner, repo, pr_number)
            
            # Parse diff to find Python files
            files = re.findall(r'\+\+\+ b/(.+\.py)', diff)
            
            if files:
                return files[0]  # Return first Python file
        
        # Check stack trace for file paths
        stack_trace = diagnosis.get('log_snippet', '')
        file_match = re.search(r'File "([^"]+\.py)"', stack_trace)
        if file_match:
            return file_match.group(1).lstrip('./')
        
        return None
    
    def _format_fix_comment(
        self,
        diagnosis: Dict,
        fix: Dict,
        check_name: str
    ) -> str:
        """Format the fix as a PR comment"""
        failure_type = diagnosis['failure_type'].value
        error_msg = diagnosis['error_message']
        
        changes_text = "\n".join([
            f"- **{c['file']}** (line {c.get('line_number', 'N/A')}): {c['action']}"
            for c in fix['changes']
        ])
        
        comment = f"""## 🤖 DietCode CI Fix Suggestion

**CI Check Failed:** `{check_name}`

### 📊 Diagnosis
- **Failure Type:** `{failure_type}`
- **Error:** `{error_msg}`
- **Confidence:** {diagnosis['confidence']:.0%}

### 🔧 Proposed Fix
{fix['explanation']}

**Changes:**
{changes_text}

**Fix Confidence:** {fix['confidence']:.0%}

### ✅ Approval
To apply this fix, reply with: `/dietcode apply`
To reject this fix, reply with: `/dietcode reject`

---
<details>
<summary>View detailed changes</summary>
```python
{self._format_changes_detail(fix['changes'])}
```
</details>

*This is an automated fix generated by DietCode. Please review carefully before applying.*
"""
        return comment
    
    def _format_changes_detail(self, changes: List[Dict]) -> str:
        """Format detailed change diff"""
        details = []
        for change in changes:
            if change['action'] == 'insert':
                details.append(f"+ {change['new_content']}")
            elif change['action'] == 'replace':
                details.append(f"- {change['old_content']}")
                details.append(f"+ {change['new_content']}")
            elif change['action'] == 'delete':
                details.append(f"- {change['old_content']}")
        
        return "\n".join(details)
    
    async def close(self):
        """Cleanup resources"""
        await self.mcp_client.close()