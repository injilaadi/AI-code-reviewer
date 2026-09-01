from app.llm.client import _extract_json, review_diff, Finding
from unittest.mock import patch


def test_extract_json_plain():
    text = '[{"file": "a.py", "line": 3, "severity": "high", "comment": "bug"}]'
    assert _extract_json(text) == [{"file": "a.py", "line": 3, "severity": "high", "comment": "bug"}]


def test_extract_json_with_markdown_fence():
    text = '```json\n[{"file": "a.py", "line": 1, "severity": "low", "comment": "nit"}]\n```'
    result = _extract_json(text)
    assert result == [{"file": "a.py", "line": 1, "severity": "low", "comment": "nit"}]


def test_extract_json_malformed_returns_empty():
    assert _extract_json("not json at all") == []


def test_extract_json_non_list_returns_empty():
    assert _extract_json('{"file": "a.py"}') == []


def test_review_diff_skips_malformed_findings():
    with patch("app.llm.client._call_openai", return_value=(
        '[{"file": "a.py", "line": 1, "severity": "high", "comment": "real bug"}, '
        '{"file": "b.py"}]',  # missing required fields -- should be skipped
        10, 5,
    )):
        with patch.dict("os.environ", {"LLM_PROVIDER": "openai"}):
            result = review_diff("diff --git a/a.py b/a.py")
    assert result.findings == [Finding(file="a.py", line=1, severity="high", comment="real bug")]
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5
