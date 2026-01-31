"""Test file with missing import - will fail CI"""

def test_github_api():
    # Missing import: requests module not imported
    response = requests.get('https://api.github.com')
    assert response.status_code == 200

def test_simple():
    assert 1 + 1 == 2
