import pytest
import os
from src.agent.fix_generator import FixGenerator
from src.agent.analyzer import FailureType


@pytest.fixture
def fix_generator():
    """Create fix generator with test API key"""
    api_key = os.getenv('OPENAI_API_KEY', 'test-key')
    return FixGenerator(api_key)


@pytest.mark.asyncio
async def test_fix_missing_dependency(fix_generator):
    """Test fix for missing dependency"""
    
    error_details = {'package_name': 'numpy'}
    
    fix = await fix_generator.generate_fix(
        FailureType.MISSING_DEPENDENCY,
        error_details,
        '',
        'requirements.txt'
    )
    
    assert fix['fix_type'] == 'add_dependency'
    assert any('requirements.txt' in c['file'] for c in fix['changes'])
    assert any('numpy' in str(c) for c in fix['changes'])