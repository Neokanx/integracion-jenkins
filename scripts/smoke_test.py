"""Integration check executed INSIDE the api container by the Jenkins pipeline.

Usage (from the repository root, with the stack already up):
    docker compose exec -T api python - < scripts/smoke_test.py

It proves that the two containers communicate through Docker's DNS using the
Compose SERVICE NAMES (db, api), never localhost or fixed IPs. Every check
raises on failure, so the process exits non-zero and the Jenkins build fails.
"""

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

BASE = "http://api:8000"  # "api" is the service name of this very container.


def call(method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    """Send one HTTP request to the API and return (status code, JSON body)."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def check(name: str, condition: bool, detail: object = "") -> None:
    """Print PASS/FAIL for one check and abort the script on failure."""
    print(f"[{'PASS' if condition else 'FAIL'}] {name} {detail}".rstrip())
    if not condition:
        sys.exit(1)


def main() -> None:
    """Run all checks in order."""
    # 1. The API is configured to reach the database by service name.
    check("DB_HOST is the service name 'db'", os.environ.get("DB_HOST") == "db")

    # 2. Docker DNS resolves both service names to different container IPs.
    db_ip = socket.gethostbyname("db")
    api_ip = socket.gethostbyname("api")
    check("DNS resolves 'db' and 'api' by service name", db_ip != api_ip, f"db={db_ip} api={api_ip}")

    # 3. /health runs SELECT 1 against PostgreSQL: proves api -> db over the network.
    status, body = call("GET", "/health")
    check("GET /health returns 200 with database ok", status == 200 and body.get("database") == "ok", body)

    # 4. Full round trip through both containers (write then read).
    name = f"jenkins-smoke-{int(time.time())}"
    status, project = call("POST", "/projects", {"name": name})
    check("POST /projects creates a project", status == 201, project)

    status, task = call("POST", "/tasks", {"project_id": project["id"], "title": "Task from Jenkins"})
    check("POST /tasks creates a task", status == 201 and task["status"] == "todo", task)

    status, tasks = call("GET", f"/tasks?project_id={project['id']}")
    check("GET /tasks reads it back from PostgreSQL", status == 200 and [t["title"] for t in tasks] == ["Task from Jenkins"])

    status, summary = call("GET", f"/reports/projects/{project['id']}/summary")
    check("GET /reports summary counts 1 task", status == 200 and summary["total_tasks"] == 1, summary)

    # 5. A business rule still holds end to end (blank title is rejected).
    status, _ = call("POST", "/tasks", {"project_id": project["id"], "title": "   "})
    check("Blank task title is rejected with 422", status == 422)

    print("ALL INTEGRATION CHECKS PASSED")


if __name__ == "__main__":
    main()
