"""Exercise SPEC acceptance scenarios 1, 7 and 9 over a real HTTP connection."""

import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4


def register(relay, name):
    enrollment_secret = os.environ.get("RELAY_TEST_ENROLLMENT_SECRET")
    headers = {"X-Enrollment-Secret": enrollment_secret} if enrollment_secret else {}
    response = relay.post("/api/v1/agents", headers=headers, json={"name": name})
    assert response.status_code == 201, "Agent registration must succeed."
    identity = response.json()
    assert set(identity) == {"agent_id", "token"}
    assert bool(identity["agent_id"]) and bool(identity["token"])
    return identity, {"Authorization": f"Bearer {identity['token']}"}


def test_real_http_task_lifecycle(relay, request):
    # Fresh identities make repeated runs safe even when the server has other data.
    run_id = uuid4().hex[:12]
    sender, sender_headers = register(relay, f"acceptance-sender-{run_id}")
    recipient, recipient_headers = register(relay, f"acceptance-worker-{run_id}")
    outsider, outsider_headers = register(relay, f"acceptance-outsider-{run_id}")
    payload = {"to": recipient["agent_id"], "input": "hello from homework 3"}
    submission_headers = {**sender_headers, "Idempotency-Key": f"acceptance-{run_id}"}

    sent = relay.post("/api/v1/tasks", headers=submission_headers, json=payload)
    assert sent.status_code == 201
    task_id = sent.json()["task_id"]
    task_path = f"/api/v1/tasks/{task_id}"
    assert sent.json() == {"task_id": task_id, "status": "queued"}
    duplicate = relay.post("/api/v1/tasks", headers=submission_headers, json=payload)
    assert duplicate.status_code == 201
    assert duplicate.json() == sent.json()
    conflict = relay.post(
        "/api/v1/tasks", headers=submission_headers, json={**payload, "input": "different"}
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"

    queued = relay.get(task_path, headers=sender_headers)
    assert queued.status_code == 200
    assert queued.json()["status"] == "queued"
    assert queued.json()["attempt_count"] == 0
    assert relay.get(task_path).status_code == 401
    for path in (task_path, f"{task_path}/attempts"):
        denied = relay.get(path, headers=outsider_headers)
        assert denied.status_code == 404
        assert "input" not in denied.json()
    # Claim requests address the authenticated inbox, even if the worker label matches.
    worker_id = f"acceptance-process-{run_id}"
    assert relay.post(
        "/api/v1/tasks/claim", headers=outsider_headers,
        json={"worker_id": worker_id, "wait_seconds": 0},
    ).status_code == 204

    claimed = relay.post(
        "/api/v1/tasks/claim", headers=recipient_headers,
        json={"worker_id": worker_id, "wait_seconds": 0},
    )
    assert claimed.status_code == 200
    claim = claimed.json()
    assert claim["task_id"] == task_id
    assert claim["from"] == sender["agent_id"]
    assert claim["input"] == payload["input"]
    assert claim["attempt"] == 1
    assert bool(claim["lease_expires_at"]) and bool(claim["claim_token"])
    processing = relay.get(task_path, headers=sender_headers)
    assert processing.status_code == 200
    assert processing.json()["status"] == "processing"
    assert relay.post(
        "/api/v1/tasks/claim", headers=recipient_headers,
        json={"worker_id": f"second-{run_id}", "wait_seconds": 0},
    ).status_code == 204

    completion = {"claim_token": claim["claim_token"], "output": claim["input"].upper()}
    # Knowing a claim token alone does not authorize the sender to finish work.
    assert relay.post(
        f"{task_path}/complete", headers=sender_headers, json=completion,
    ).status_code == 404
    heartbeat = relay.post(
        f"{task_path}/heartbeat", headers=recipient_headers,
        json={"claim_token": claim["claim_token"]},
    )
    assert heartbeat.status_code == 200
    assert bool(heartbeat.json()["lease_expires_at"])
    completed = relay.post(f"{task_path}/complete", headers=recipient_headers, json=completion)
    assert completed.status_code == 200
    assert completed.json() == {"task_id": task_id, "status": "completed"}
    retry = relay.post(f"{task_path}/complete", headers=recipient_headers, json=completion)
    assert retry.status_code == 200
    assert retry.json() == completed.json()
    assert relay.post(
        f"{task_path}/complete", headers=recipient_headers,
        json={**completion, "output": "conflicting result"},
    ).status_code == 409

    result = relay.get(task_path, headers=sender_headers)
    assert result.status_code == 200
    task = result.json()
    assert task["status"] == "completed"
    assert task["from"] == sender["agent_id"]
    assert task["to"] == recipient["agent_id"]
    assert task["input"] == payload["input"]
    assert task["output"] == "HELLO FROM HOMEWORK 3"
    assert task["error"] is None
    assert task["attempt_count"] == 1
    assert task["created_at"] and task["finished_at"]
    for headers, direction in ((sender_headers, "sent"), (recipient_headers, "received")):
        listing = relay.get(
            "/api/v1/tasks", headers=headers,
            params={"direction": direction, "status": "completed"},
        )
        assert listing.status_code == 200
        assert [item["task_id"] for item in listing.json()["items"]] == [task_id]
        history = relay.get(f"{task_path}/attempts", headers=headers)
        assert history.status_code == 200
        attempts = history.json()["items"]
        assert len(attempts) == 1
        assert attempts[0]["attempt"] == 1
        assert attempts[0]["worker_id"] == worker_id
        assert attempts[0]["outcome"] == "completed"
        assert attempts[0]["finished_at"]
        assert not any("token" in key for key in attempts[0])
    directory = relay.get("/api/v1/agents", headers=sender_headers)
    assert directory.status_code == 200
    assert not any("token" in key for item in directory.json()["items"] for key in item)
    assert not any("token" in key for key in task)

    if request.config.getoption("--save-demo-credentials"):
        artifact_dir = Path(os.environ.get("RELAY_TEST_ARTIFACT_DIR") or tempfile.gettempdir()).resolve()
        project_dir = Path(__file__).resolve().parents[1]
        assert not artifact_dir.is_relative_to(project_dir), (
            "Credential files must stay outside the repository. "
            "Set RELAY_TEST_ARTIFACT_DIR to a writable external directory."
        )
        # NamedTemporaryFile creates mode 0600. Never save tokens in the repository.
        with tempfile.NamedTemporaryFile(
            mode="w", prefix="relay-acceptance-", suffix=".json", delete=False, dir=artifact_dir,
        ) as file:
            json.dump({"base_url": str(relay.base_url), "task_id": task_id,
                       "sender": sender, "recipient": recipient}, file)
        print(f"Dashboard credentials saved privately to {file.name}; task {task_id}.")
