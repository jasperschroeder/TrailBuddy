"""
Quick security validation tests for the improved SQL injection protection.
Run this to verify the security improvements work correctly.
"""
import re
import json

# Replicate the validation functions for testing
_ALLOWED_SQL = re.compile(r"^\s*SELECT\b", re.IGNORECASE)

_DANGEROUS_SQL_KEYWORDS = [
    'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE',
    'PRAGMA', 'ATTACH', 'DETACH', 'EXEC', 'EXECUTE',
    'REPLACE', 'TRUNCATE', 'GRANT', 'REVOKE'
]


def _validate_sql_query(sql: str) -> tuple[bool, str]:
    """Validate SQL query for security. Returns (is_valid, error_message)."""
    # Remove comments to prevent hidden commands
    sql_no_comments = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    sql_no_comments = re.sub(r'/\*.*?\*/', '', sql_no_comments, flags=re.DOTALL)

    # Check for multiple statements (semicolon-separated)
    if ';' in sql_no_comments.rstrip(';'):
        return False, "Error: multiple statements not allowed"

    # Check it starts with SELECT
    if not _ALLOWED_SQL.match(sql_no_comments.strip()):
        return False, "Error: only SELECT queries are permitted"

    # Check for dangerous keywords
    sql_upper = sql_no_comments.upper()
    for keyword in _DANGEROUS_SQL_KEYWORDS:
        if re.search(rf'\b{keyword}\b', sql_upper):
            return False, f"Error: dangerous keyword '{keyword}' not allowed"

    # Ensure only querying the 'hikes' table or using it in joins
    if 'FROM' in sql_upper:
        from_pattern = re.compile(
            r'\bFROM\s+([\w,\s]+?)(?:\s+WHERE|\s+GROUP|\s+ORDER|\s+LIMIT|\s+JOIN|$)',
            re.IGNORECASE
        )
        from_match = from_pattern.search(sql_no_comments)
        if from_match:
            tables = [t.strip().split()[0] for t in from_match.group(1).split(',')]
            for table in tables:
                if table.lower() not in ['hikes', 'ranking']:
                    return False, f"Error: access to table '{table}' not allowed"

    return True, ""


def _extract_json_from_llm_response(content: str, expected_schema: dict = None) -> dict | None:
    """Robustly extract and validate JSON from LLM response."""
    if not content:
        return None

    content = content.strip()

    # Strategy 1: Try to extract JSON from markdown code blocks
    json_patterns = [
        r'```json\s*\n(.+?)\n```',
        r'```\s*\n(.+?)\n```',
        r'`([{\[].*?[}\]])`',
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, content, re.DOTALL)
        for match in matches:
            try:
                result = json.loads(match.strip())
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                continue

    # Strategy 2: Find first valid JSON object in the text
    json_obj_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_obj_pattern, content)

    for match in matches:
        try:
            result = json.loads(match)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            continue

    # Strategy 3: Try parsing the entire content as JSON
    try:
        result = json.loads(content)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    return None


print("Testing SQL Injection Protection")
print("=" * 50)

# Test cases: (query, should_pass, description)
test_cases = [
    ("SELECT * FROM hikes", True, "Simple SELECT"),
    ("SELECT id, title FROM hikes WHERE distance > 5", True, "SELECT with WHERE"),
    ("SELECT * FROM hikes; DROP TABLE hikes;", False, "SQL injection attempt"),
    ("SELECT * FROM hikes -- comment", True, "Comment at end"),
    ("SELECT * FROM sqlite_master", False, "System table access"),
    ("DELETE FROM hikes WHERE id=1", False, "DELETE attempt"),
    ("INSERT INTO hikes VALUES (1,2,3)", False, "INSERT attempt"),
    ("SELECT * FROM hikes WHERE id IN (SELECT id FROM ranking)", True, "Subquery allowed table"),
    ("PRAGMA table_info(hikes)", False, "PRAGMA attempt"),
    ("SELECT * FROM hikes/*comment*/WHERE id=1", True, "Inline comment"),
]

passed = 0
failed = 0

for query, should_pass, description in test_cases:
    is_valid, error = _validate_sql_query(query)

    if is_valid == should_pass:
        print(f"✓ {description}")
        passed += 1
    else:
        print(f"✗ {description}")
        print(f"  Query: {query}")
        print(f"  Expected: {'PASS' if should_pass else 'BLOCK'}, Got: {'PASS' if is_valid else 'BLOCK'}")
        if error:
            print(f"  Error: {error}")
        failed += 1

print()
print("Testing JSON Extraction")
print("=" * 50)

# Test JSON extraction
json_tests = [
    ('{"score": 25, "level": "Moderate"}', {"score": 25, "level": "Moderate"}),
    ('```json\n{"score": 30}\n```', {"score": 30}),
    ('Here is the result: {"score": 15, "level": "Easy"} as requested', {"score": 15, "level": "Easy"}),
    ('```\n{"score": 40, "level": "Hard"}\n```', {"score": 40, "level": "Hard"}),
    ('The difficulty is moderate. {"score": 25, "level": "Moderate"}', {"score": 25, "level": "Moderate"}),
]

for content, expected in json_tests:
    result = _extract_json_from_llm_response(content)
    if result and all(result.get(k) == v for k, v in expected.items()):
        print(f"✓ Extracted from: {content[:50]}...")
        passed += 1
    else:
        print(f"✗ Failed to extract from: {content[:50]}...")
        print(f"  Expected: {expected}, Got: {result}")
        failed += 1

print()
print("=" * 50)
print(f"Results: {passed} passed, {failed} failed")

if failed == 0:
    print("🎉 All security tests passed!")
else:
    print("⚠️  Some tests failed")
