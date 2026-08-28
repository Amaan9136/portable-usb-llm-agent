"""API-level tests. These do NOT require a running llama-server —
LLM calls are mocked so the test suite runs offline and fast, matching
the project's own no-network-during-operation principle."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

import app as app_module
import tools


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    artifacts = tmp_path / "artifacts"
    workspace.mkdir()
    artifacts.mkdir()

    monkeypatch.setattr(tools, "WORKSPACE", workspace)
    monkeypatch.setattr(tools, "ARTIFACTS", artifacts)
    monkeypatch.setattr(app_module, "ARTIFACTS", artifacts)

    yield workspace, artifacts


@pytest.fixture
def client():
    return TestClient(app_module.app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "model_endpoint" in body


def test_list_artifacts_empty(client):
    response = client.get("/artifacts")
    assert response.status_code == 200
    assert response.json()["artifacts"] == []


def test_list_artifacts_lists_zip_files(client, isolated_dirs):
    _, artifacts = isolated_dirs
    (artifacts / "a.zip").write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    (artifacts / "notes.txt").write_text("ignore me")

    response = client.get("/artifacts")
    assert response.json()["artifacts"] == ["a.zip"]


def test_download_artifact_success(client, isolated_dirs):
    _, artifacts = isolated_dirs
    (artifacts / "out.zip").write_bytes(b"PK\x05\x06" + b"\x00" * 18)

    response = client.get("/artifacts/out.zip")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"


def test_download_artifact_rejects_traversal(client):
    response = client.get("/artifacts/..%2F..%2Fsecret.zip")
    assert response.status_code in (400, 404)


def test_download_artifact_rejects_non_zip(client, isolated_dirs):
    _, artifacts = isolated_dirs
    (artifacts / "notes.txt").write_text("hi")
    response = client.get("/artifacts/notes.txt")
    assert response.status_code == 400


def test_download_artifact_missing_file(client):
    response = client.get("/artifacts/ghost.zip")
    assert response.status_code == 404


def test_agent_endpoint_rejects_short_task(client):
    response = client.post("/agent", json={"task": "hi"})
    assert response.status_code == 422


def test_agent_endpoint_runs_native_loop_with_mocked_llm(client, monkeypatch, isolated_dirs):
    """Simulate the model calling write_file once, then finishing with a
    plain text final answer, without ever hitting a real server."""

    call_count = {"n": 0}

    def fake_create(*, model, messages, tools=None, tool_choice=None, temperature=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            tool_call = SimpleNamespace(
                id="call_1",
                function=SimpleNamespace(
                    name="write_file",
                    arguments='{"relative_path": "hello.py", "content": "print(1)"}',
                ),
            )
            message = SimpleNamespace(
                tool_calls=[tool_call],
                content=None,
                model_dump=lambda exclude_none=True: {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": '{"relative_path": "hello.py", "content": "print(1)"}',
                            },
                        }
                    ],
                },
            )
        else:
            message = SimpleNamespace(
                tool_calls=None,
                content="Created hello.py. No tests run. No artifact created.",
                model_dump=lambda exclude_none=True: {
                    "role": "assistant",
                    "content": "Created hello.py. No tests run. No artifact created.",
                },
            )
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(app_module.client.chat.completions, "create", fake_create)

    response = client.post("/agent", json={"task": "Create a hello world script."})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "hello.py" in body["changed_files"]
    assert "Created hello.py" in body["final_answer"]


def test_agent_endpoint_reports_turn_limit(client, monkeypatch, isolated_dirs):
    """If the model only ever emits tool calls and never finishes, the
    loop must stop at MAX_AGENT_TURNS rather than looping forever."""

    def fake_create(*, model, messages, tools=None, tool_choice=None, temperature=None):
        tool_call = SimpleNamespace(
            id="call_x",
            function=SimpleNamespace(
                name="list_files",
                arguments='{"relative_path": "."}',
            ),
        )
        message = SimpleNamespace(
            tool_calls=[tool_call],
            content=None,
            model_dump=lambda exclude_none=True: {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_x",
                        "type": "function",
                        "function": {"name": "list_files", "arguments": '{"relative_path": "."}'},
                    }
                ],
            },
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(app_module.client.chat.completions, "create", fake_create)

    response = client.post("/agent", json={"task": "Never finish this task please."})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert any("turn limit" in w.lower() for w in body["warnings"])