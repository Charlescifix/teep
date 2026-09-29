# app/request_log.py
"""
One-line descriptions of rejected requests, for the logs.

A 422 used to leave no trace beyond uvicorn's access line, so a flood of them
read the same whether it was a scanner guessing field names or a partner
shipping a broken integration. What distinguishes those is the content type,
the shape of the body and the User-Agent, so that is what gets recorded.
"""

from typing import Optional

from fastapi import Request

# Enough body to recognise a shape - a wrong field name, a JSON syntax error -
# without copying whole payloads into the logs on every probe.
BODY_SNIPPET = 200
HEADER_SNIPPET = 120
# Pydantic echoes the whole offending input back in its error list, so this is
# the one value here not already bounded by the caller's own request size.
ERRORS_SNIPPET = 400


def clip(value: Optional[str], limit: int) -> str:
    """
    Truncate and escape one caller-supplied value.

    repr() rather than the bare string on purpose: every value here is chosen
    by the caller, and an embedded newline would otherwise let them append
    convincing fake lines to this log.
    """
    if not value:
        return "-"
    clipped = value[:limit]
    return repr(clipped) + ("..." if len(value) > limit else "")


def describe_request(request: Request, body: bytes = b"") -> str:
    """
    Summarise a request as a single log-safe line.

    Deliberately not the full body or every header: this runs on traffic that
    is already unwanted, so it should stay cheap and bounded.
    """
    headers = request.headers
    return " ".join(
        (
            f"{request.method} {request.url.path}",
            f"query={clip(request.url.query, HEADER_SNIPPET)}",
            f"content-type={clip(headers.get('content-type'), HEADER_SNIPPET)}",
            f"origin={clip(headers.get('origin'), HEADER_SNIPPET)}",
            f"ua={clip(headers.get('user-agent'), HEADER_SNIPPET)}",
            f"body={clip(body.decode('utf-8', 'replace'), BODY_SNIPPET)}",
        )
    )
