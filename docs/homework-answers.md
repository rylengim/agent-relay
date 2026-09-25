# Homework 3 answers

- Course: AI Dev Tools Zoomcamp, 2026 cohort.
- Assignment: [Homework 3: Containerize and Deploy](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/cohorts/2026/homework/03-deployment/homework.md).
- Starter: [alexeygrigorev/agent-relay](https://github.com/alexeygrigorev/agent-relay).
- Homework repository: [rylengim/agent-relay](https://github.com/rylengim/agent-relay).
- Submit at: [course platform](https://courses.datatalks.club/ai-dev-tools-2026/homework/hw3).

| Question | Selected answer | Basis |
| --- | --- | --- |
| 1. Project architecture | Agents claim tasks from a DB through an HTTP API. | The API persists tasks; recipient processes claim work over HTTP. |
| 2. Sender-visible status after the recipient submits its result | `completed` | The completion endpoint stores the output and completes the task. |
| 3. Docker option that publishes a port | `-p` | Container port 8000 is mapped to a host port. |
| 4. API hostname for the Compose database service | `postgres` | Compose DNS resolves the database service by its configured name. |
| 5. Resource that maintains app replicas and manages updates | `Deployment` | The app Deployment owns replica count and rolling updates. |
| 6. Behavior when a workflow test fails | Keep the existing version running and stop the deployment. | Failed tests prevent later build and deployment steps. |

Protocol reference: [starter SPEC.md](https://github.com/alexeygrigorev/agent-relay/blob/main/SPEC.md).
These match the six multiple-choice questions on the official assignment and
submission page.

## Submission status

Pending. These are prepared answers, not confirmation that the platform accepted
them. At inspection on 25 September 2026, the platform displayed a 25 September, 02:00 Europe/Moscow
deadline (24 September, 23:00 UTC) and said late submissions remained open until scoring closed. The
platform's current status governs whether submission remains possible.

## Verification record

See [docs/verification.md](verification.md) for execution evidence. The main agent
observed 15 starter/storage tests passing against both SQLite and PostgreSQL,
the HTTP acceptance test passing against local, Docker, Compose, and kind
instances, PostgreSQL data surviving a Compose restart, and successful v1/v2
`act` deployments. A deliberately introduced temporary test failure stopped the
workflow before build/deployment and left the running image unchanged; the
temporary failure was removed afterward. The v2 dashboard and a persisted
completed result were inspected in the browser. Submission remains a separate
pending step.
