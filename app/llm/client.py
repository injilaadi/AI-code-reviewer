"""LLM client for generating structured review findings from a diff.

Supports OpenAI and Gemini behind LLM_PROVIDER. Both providers are asked for
JSON-only output, but LLMs don't always obey that instruction perfectly
(markdown code fences, stray prose) -- _extract_json defends against the
common cases rather than trusting the raw response.
"""
import json
import os
import re
from dataclasses import dataclass

from app.llm.prompts import REVIEW_SYSTEM_PROMPT, build_review_prompt

MAX_DIFF_CHARS = 20_000  # keep prompts bounded; a huge diff gets truncated rather than rejected


@dataclass
class Finding:
    file: str
    line: int
    severity: str
    comment: str


@dataclass
class ReviewResult:
    findings: list[Finding]
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def _extract_json(text: str) -> list:
    """Strip markdown code fences if present, then parse JSON. Returns []
    (rather than raising) if the model didn't return valid/parseable JSON --
    a malformed LLM response should degrade to "no findings", not crash the worker."""
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _call_openai(diff: str) -> tuple[str, int | None, int | None]:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["LLM_API_KEY"])
    resp = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
            {"role": "user", "content": build_review_prompt(diff)},
        ],
        temperature=0,
    )
    usage = resp.usage
    return (
        resp.choices[0].message.content or "[]",
        usage.prompt_tokens if usage else None,
        usage.completion_tokens if usage else None,
    )


def _call_gemini(diff: str) -> tuple[str, int | None, int | None]:
    import google.generativeai as genai

    genai.configure(api_key=os.environ["LLM_API_KEY"])
    model = genai.GenerativeModel(
        os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        system_instruction=REVIEW_SYSTEM_PROMPT,
    )
    resp = model.generate_content(build_review_prompt(diff))
    usage = getattr(resp, "usage_metadata", None)
    return (
        resp.text or "[]",
        getattr(usage, "prompt_token_count", None) if usage else None,
        getattr(usage, "candidates_token_count", None) if usage else None,
    )


def review_diff(diff: str) -> ReviewResult:
    """Call the configured LLM provider and return structured findings."""
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n... [diff truncated]"

    provider = os.environ.get("LLM_PROVIDER", "openai").lower()
    if provider == "openai":
        raw_text, prompt_tokens, completion_tokens = _call_openai(diff)
    elif provider == "gemini":
        raw_text, prompt_tokens, completion_tokens = _call_gemini(diff)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")

    items = _extract_json(raw_text)
    findings = []
    for item in items:
        try:
            findings.append(Finding(
                file=str(item["file"]),
                line=int(item["line"]),
                severity=str(item.get("severity", "medium")),
                comment=str(item["comment"]),
            ))
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed individual findings rather than failing the whole review

    return ReviewResult(findings=findings, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
