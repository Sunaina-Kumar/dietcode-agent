import re
from typing import Dict, List, Optional
from enum import Enum


class FailureType(Enum):
    """Types of CI failures we can diagnose"""
    MODULE_NOT_FOUND = "module_not_found"
    IMPORT_ERROR = "import_error"
    MISSING_DEPENDENCY = "missing_dependency"
    BROKEN_PATH = "broken_path"
    SYNTAX_ERROR = "syntax_error"
    UNKNOWN = "unknown"


class CILogAnalyzer:
    """Analyzes CI logs to diagnose failure types"""
    
    # Regex patterns for different error types
    PATTERNS = {
        FailureType.MODULE_NOT_FOUND: [
            r"ModuleNotFoundError: No module named '([^']+)'",
            r"ImportError: No module named ([^\s]+)",
            r"cannot import name '([^']+)'",
        ],
        FailureType.IMPORT_ERROR: [
            r"ImportError: (.+)",
            r"from ([^\s]+) import .+ failed",
        ],
        FailureType.MISSING_DEPENDENCY: [
            r"error: externally-managed-environment",
            r"Could not find a version that satisfies the requirement ([^\s]+)",
            r"No matching distribution found for ([^\s]+)",
        ],
        FailureType.BROKEN_PATH: [
            r"FileNotFoundError: \[Errno 2\] No such file or directory: '([^']+)'",
            r"IOError: \[Errno 2\] No such file or directory: '([^']+)'",
        ],
        FailureType.SYNTAX_ERROR: [
            r"SyntaxError: (.+)",
            r"IndentationError: (.+)",
        ],
    }
    
    def analyze(self, log_content: str) -> Dict:
        """
        Analyze CI log and extract failure information
        
        Returns:
            dict with keys: failure_type, error_message, details, confidence
        """
        result = {
            "failure_type": FailureType.UNKNOWN,
            "error_message": "",
            "details": {},
            "confidence": 0.0,
            "log_snippet": ""
        }
        
        # Extract error lines
        error_lines = self._extract_error_lines(log_content)
        if not error_lines:
            return result
        
        result["log_snippet"] = "\n".join(error_lines[:10])
        
        # Try to match against known patterns
        for failure_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, log_content, re.MULTILINE)
                if match:
                    result["failure_type"] = failure_type
                    result["error_message"] = match.group(0)
                    result["confidence"] = 0.9
                    
                    # Extract specific details
                    if failure_type == FailureType.MODULE_NOT_FOUND:
                        result["details"]["missing_module"] = match.group(1)
                    elif failure_type == FailureType.BROKEN_PATH:
                        result["details"]["missing_path"] = match.group(1)
                    elif failure_type == FailureType.MISSING_DEPENDENCY:
                        if match.groups():
                            result["details"]["package_name"] = match.group(1)
                    
                    return result
        
        # If no pattern matched
        result["confidence"] = 0.3
        return result
    
    def _extract_error_lines(self, log_content: str) -> List[str]:
        """Extract relevant error lines from log"""
        lines = log_content.split('\n')
        error_lines = []
        
        keywords = ['error', 'failed', 'exception', 'traceback', 'modulenotfounderror']
        
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in keywords):
                # Include context: 2 lines before and 5 lines after
                start = max(0, i - 2)
                end = min(len(lines), i + 6)
                error_lines.extend(lines[start:end])
        
        return error_lines