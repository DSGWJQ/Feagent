"""HTTP request tool for LangChain agents."""

from __future__ import annotations

import json
from typing import Any

import requests
from langchain_core.tools import tool


def _parse_headers(raw_headers: str | None) -> dict[str, str]:
    if not raw_headers:
        return {}
    try:
        parsed = json.loads(raw_headers)
    except json.JSONDecodeError as exc:
        raise ValueError("Headers must be a JSON object.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Headers must be provided as a JSON object.")
    return {str(key): str(value) for key, value in parsed.items()}


def _parse_body(raw_body: str | None) -> tuple[Any | None, Any | None]:
    if not raw_body:
        return None, None
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body, None

    if isinstance(parsed, dict | list):
        return None, parsed
    return str(parsed), None


@tool("http_request")
def http_request(
    url: str,
    method: str = "GET",
    headers: str | None = None,
    body: str | None = None,
) -> str:
    """Send an HTTP request and return a textual summary of the response."""

    allowed_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
    method = method.upper()
    if method not in allowed_methods:
        return f"Error: HTTP method {method} is not supported."

    try:
        header_dict = _parse_headers(headers)
        data_payload, json_payload = _parse_body(body)
    except ValueError as exc:
        return f"Error: {exc}"

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=header_dict,
            data=data_payload,
            json=json_payload,
            timeout=30,
        )
    except requests.exceptions.Timeout:
        return "Error: Request timed out after 30 seconds."
    except requests.exceptions.ConnectionError:
        return "Error: Unable to connect to the server."
    except requests.exceptions.RequestException as exc:
        return f"Error: Request failed ({exc})."

    content = response.text
    if len(content) > 10_000:
        content = f"{content[:10_000]}\n...\n(truncated)"

    if response.status_code >= 400:
        return f"HTTP {response.status_code} error:\n{content}"

    return f"HTTP {response.status_code}\n{content}"


def get_http_request_tool() -> Any:
    """Return the LangChain tool instance."""

    return http_request
