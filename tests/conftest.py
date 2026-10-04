"""Shared fixtures: one full offline pipeline run per test session (about 5 seconds)."""

from __future__ import annotations

import pytest

from fabricbi.pipeline import run_all
from fabricbi.serve.access import resolve
from fabricbi.serve.mcp_server import DataAgentTools


@pytest.fixture(scope="session")
def run(tmp_path_factory):
    return run_all(tmp_path_factory.mktemp("fabricbi"))


@pytest.fixture(scope="session")
def lake(run):
    return run.lake


@pytest.fixture(scope="session")
def tools(run):
    return DataAgentTools(run.lake, run.ctx.lineage)


@pytest.fixture(scope="session")
def agent(tools):
    return tools.agent


@pytest.fixture
def who():
    return lambda name: resolve(f"{name}@fernhill.example")
