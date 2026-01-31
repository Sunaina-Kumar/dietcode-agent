import pytest
from src.agent.analyzer import CILogAnalyzer, FailureType


def test_module_not_found():
    """Test detection of ModuleNotFoundError"""
    log = """
    Traceback (most recent call last):
      File "test_api.py", line 5, in test_api_call
        import requests
    ModuleNotFoundError: No module named 'requests'
    """
    
    analyzer = CILogAnalyzer()
    result = analyzer.analyze(log)
    
    assert result['failure_type'] == FailureType.MODULE_NOT_FOUND
    assert result['details']['missing_module'] == 'requests'
    assert result['confidence'] > 0.8


def test_missing_dependency():
    """Test detection of missing package in requirements"""
    log = """
    ERROR: Could not find a version that satisfies the requirement numpy
    ERROR: No matching distribution found for numpy
    """
    
    analyzer = CILogAnalyzer()
    result = analyzer.analyze(log)
    
    assert result['failure_type'] == FailureType.MISSING_DEPENDENCY


def test_broken_path():
    """Test detection of file not found errors"""
    log = """
    Traceback (most recent call last):
      File "app.py", line 10, in main
        with open('config/settings.json') as f:
    FileNotFoundError: [Errno 2] No such file or directory: 'config/settings.json'
    """
    
    analyzer = CILogAnalyzer()
    result = analyzer.analyze(log)
    
    assert result['failure_type'] == FailureType.BROKEN_PATH
    assert 'config/settings.json' in result['details']['missing_path']