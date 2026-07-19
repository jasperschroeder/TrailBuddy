"""Robust JSON extraction/validation helpers for parsing LLM responses."""
import json
import re


def extract_json_from_llm_response(content: str, expected_schema: dict = None) -> dict | None:  # noqa
    """Robustly extract and validate JSON from LLM response.

    Args:
        content: Raw LLM response text
        expected_schema: Optional dict mapping field names to (type, default_value) tuples

    Returns:
        Parsed and validated JSON dict, or None if extraction fails
    """
    if not content:
        return None

    content = content.strip()

    # Strategy 1: Try to extract JSON from markdown code blocks
    json_patterns = [
        r'```json\s*\n(.+?)\n```',  # ```json ... ```
        r'```\s*\n(.+?)\n```',       # ``` ... ```
        r'`([{\[].*?[}\]])`',         # `{...}` or `[...]`
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, content, re.DOTALL)
        for match in matches:
            try:
                result = json.loads(match.strip())
                if isinstance(result, dict):
                    return _validate_json_schema(result, expected_schema)
            except json.JSONDecodeError:
                continue

    # Strategy 2: Find first valid JSON object or array in the text
    # Look for { ... } or [ ... ] patterns
    json_obj_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_obj_pattern, content)

    for match in matches:
        try:
            result = json.loads(match)
            if isinstance(result, dict):
                return _validate_json_schema(result, expected_schema)
        except json.JSONDecodeError:
            continue

    # Strategy 3: Try parsing the entire content as JSON
    try:
        result = json.loads(content)
        if isinstance(result, dict):
            return _validate_json_schema(result, expected_schema)
    except json.JSONDecodeError:
        pass

    return None


def _validate_json_schema(data: dict, expected_schema: dict = None) -> dict:  # noqa
    """Validate and coerce JSON data to expected schema.

    Args:
        data: Parsed JSON dict
        expected_schema: Dict mapping field names to (type, default_value) tuples

    Returns:
        Validated dict with coerced types
    """
    if not expected_schema:
        return data

    validated = {}
    for field, (expected_type, default_value) in expected_schema.items():
        value = data.get(field, default_value)

        if value is None:
            validated[field] = default_value
            continue

        # Type coercion with error handling
        try:
            if expected_type == float:
                validated[field] = float(value)
            elif expected_type == int:
                validated[field] = int(value)
            elif expected_type == str:
                validated[field] = str(value)
            elif expected_type == bool:
                if isinstance(value, bool):
                    validated[field] = value
                elif isinstance(value, str):
                    validated[field] = value.strip().lower() in {"true", "1", "yes", "y", "on"}
                else:
                    validated[field] = bool(value)
                validated[field] = value
        except (ValueError, TypeError):
            validated[field] = default_value

    return validated
