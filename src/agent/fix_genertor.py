import os
from typing import Dict, List, Optional
from openai import OpenAI
from .analyzer import FailureType


class FixGenerator:
    """Generates fixes for diagnosed CI failures"""
    
    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    async def generate_fix(
        self,
        failure_type: FailureType,
        error_details: Dict,
        file_content: str,
        file_path: str
    ) -> Dict:
        """
        Generate a fix for the diagnosed failure
        
        Returns:
            dict with keys: fix_type, changes, explanation, confidence
        """
        if failure_type == FailureType.MODULE_NOT_FOUND:
            return await self._fix_missing_import(error_details, file_content, file_path)
        elif failure_type == FailureType.MISSING_DEPENDENCY:
            return await self._fix_missing_dependency(error_details)
        elif failure_type == FailureType.BROKEN_PATH:
            return await self._fix_broken_path(error_details, file_content)
        else:
            return await self._generic_fix(failure_type, error_details, file_content)
    
    async def _fix_missing_import(
        self, 
        error_details: Dict, 
        file_content: str,
        file_path: str
    ) -> Dict:
        """Fix missing import errors"""
        missing_module = error_details.get("missing_module", "")
        
        prompt = f"""You are a Python code expert. A CI test failed with a ModuleNotFoundError.

Error: Missing module '{missing_module}'
File: {file_path}

Current file content:
```python
{file_content}
```

Task: Generate the MINIMAL fix to resolve this import error.
- If the module should be imported, add the import statement
- If it's a typo, fix the import name
- If it's a missing package, indicate that in requirements.txt

Respond in JSON format:
{{
  "fix_type": "add_import" | "fix_import" | "add_dependency",
  "changes": [
    {{
      "file": "path/to/file",
      "action": "insert" | "replace" | "delete",
      "line_number": 5,
      "old_content": "...",
      "new_content": "..."
    }}
  ],
  "explanation": "Brief explanation of the fix",
  "confidence": 0.9
}}

Respond ONLY with valid JSON, no other text."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a code repair assistant. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        import json
        return json.loads(response.choices[0].message.content)
    
    async def _fix_missing_dependency(self, error_details: Dict) -> Dict:
        """Fix missing dependency in requirements.txt"""
        package_name = error_details.get("package_name", "")
        
        return {
            "fix_type": "add_dependency",
            "changes": [{
                "file": "requirements.txt",
                "action": "insert",
                "line_number": -1,  # Append
                "old_content": "",
                "new_content": f"{package_name}\n"
            }],
            "explanation": f"Add missing dependency '{package_name}' to requirements.txt",
            "confidence": 0.85
        }
    
    async def _fix_broken_path(self, error_details: Dict, file_content: str) -> Dict:
        """Fix broken file paths"""
        missing_path = error_details.get("missing_path", "")
        
        prompt = f"""You are a Python code expert. A file path error occurred.

Error: File not found '{missing_path}'

File content with the broken path:
```python
{file_content}
```

Task: Suggest the correct path or identify what file needs to be created.

Respond in JSON format:
{{
  "fix_type": "fix_path" | "create_file",
  "changes": [...],
  "explanation": "...",
  "confidence": 0.8
}}"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        import json
        return json.loads(response.choices[0].message.content)
    
    async def _generic_fix(
        self,
        failure_type: FailureType,
        error_details: Dict,
        file_content: str
    ) -> Dict:
        """Generic LLM-based fix generation"""
        prompt = f"""Analyze this CI failure and suggest a minimal fix.

Failure Type: {failure_type.value}
Error Details: {error_details}

File content:
```python
{file_content}
```

Provide a minimal, surgical fix in JSON format."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        import json
        return json.loads(response.choices[0].message.content)