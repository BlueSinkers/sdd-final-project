"""The log line is a contract with infra/monitoring: every query parses it with one
KQL `parse` expression. If this service's line and those queries ever disagree, the
dashboard and the SLO go quietly blank. These tests read the pattern out of the .kql
files themselves, so a change on either side fails here, before it reaches Azure.

No database is needed: the requests below fail to reach one, which is fine, because the
request line is written either way.
"""

import logging
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

SERVICE = "swaps"
MONITORING = Path(__file__).resolve().parents[2] / "infra" / "monitoring"
PARSE = re.compile(r"\| parse Log_s with (.+)")
TOKEN = re.compile(r'"([^"]*)"|(\w+)(?::(\w+))?')
TYPES = {None: r".*?", "int": r"-?\d+", "real": r"-?\d+(?:\.\d+)?"}


def kql_parse_expressions() -> dict[str, str]:
    found = {}
    for path in sorted(MONITORING.glob("*.kql")):
        for line in path.read_text().splitlines():
            match = PARSE.match(line.strip())
            if match:
                found[path.name] = match.group(1).strip()
    return found


def to_regex(expression: str) -> re.Pattern:
    """Turn a KQL parse expression into an anchored regex with one group per column."""
    parts = []
    for literal, name, kind in TOKEN.findall(expression):
        if literal:
            parts.append(re.escape(literal))
        else:
            parts.append(f"(?P<{name}>{TYPES[kind or None]})")
    return re.compile("^" + "".join(parts) + "$")


@pytest.fixture
def request_lines(caplog):
    # Nothing listens on port 1, so every database call fails at once and cleanly.
    settings = Settings(database_url="mssql://nobody:nothing@127.0.0.1:1/none")
    client = TestClient(create_app(settings), raise_server_exceptions=False)  # no lifespan: no migrations

    def send(method: str, path: str, **kwargs):
        caplog.clear()
        with caplog.at_level(logging.INFO, logger=SERVICE):
            client.request(method, path, **kwargs)
        return [r.getMessage() for r in caplog.records if r.name == SERVICE and r.getMessage().startswith("service=")]

    return send


def test_the_queries_all_use_the_same_parse_expression():
    expressions = kql_parse_expressions()
    assert expressions, "no parse expression found in infra/monitoring"
    assert len(set(expressions.values())) == 1, expressions


def test_every_request_line_parses_with_the_query_pattern(request_lines):
    pattern = to_regex(next(iter(kql_parse_expressions().values())))
    for method, path in [("GET", "/health"), ("GET", "/nope"), ("POST", "/swaps")]:
        lines = request_lines(method, path, json={})
        assert len(lines) == 1, f"expected exactly one request line for {method} {path}, got {lines}"
        parsed = pattern.match(lines[0])
        assert parsed, f"the KQL pattern does not parse: {lines[0]!r}"
        assert parsed["service"] == SERVICE
        assert parsed["method"] == method
        assert parsed["path"] == path
        assert 100 <= int(parsed["status"]) <= 599
        assert float(parsed["duration_ms"]) >= 0


def test_the_service_name_matches_the_slo_filter(request_lines):
    # slo_swaps*.kql keep only lines that start with "service=swaps ".
    (line,) = request_lines("GET", "/health")
    assert line.startswith(f"service={SERVICE} ")


def test_a_crafted_path_cannot_write_a_second_log_line(request_lines):
    lines = request_lines("GET", "/health%0Aservice=swaps%20method=POST%20path=/swaps%20status=200%20duration_ms=1.0")
    assert len(lines) == 1
    assert "\n" not in lines[0]
