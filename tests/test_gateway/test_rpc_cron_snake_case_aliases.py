"""Regression tests for snake_case and camelCase parameter aliases in cron RPC methods."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from agentos.gateway.rpc import RpcContext
from agentos.gateway.rpc_cron import (
    _handle_cron_add,
    _handle_cron_list,
    _handle_cron_remove,
    _handle_cron_run,
    _handle_cron_run_output,
    _handle_cron_runs,
    _handle_cron_status,
    _handle_cron_update,
    _job_to_wire,
)
from agentos.scheduler.types import (
    CronJob,
    JobExecution,
    ManualRunResult,
    ManualRunStatus,
    ScheduleKind,
    SessionTarget,
)


class _FakeCronScheduler:
    def __init__(self, jobs: list[CronJob] | None = None) -> None:
        self.jobs: dict[str, CronJob] = {j.id: j for j in (jobs or [])}
        self.runs: list[JobExecution] = []
        self.ran: list[str] = []
        self.removed: list[str] = []
        self.last_added: dict[str, Any] | None = None
        self.last_updated: dict[str, Any] | None = None

    async def list_jobs(self) -> list[CronJob]:
        return list(self.jobs.values())

    async def get_job(self, job_id: str) -> CronJob | None:
        return self.jobs.get(job_id)

    async def add_job(self, **kwargs: Any) -> CronJob:
        self.last_added = kwargs
        job_id = kwargs.get("id") or f"job-{len(self.jobs) + 1}"
        job = CronJob(
            id=job_id,
            name=kwargs.get("name", "test"),
            cron_expr=kwargs.get("cron_expr", "0 9 * * *"),
            schedule_raw=kwargs.get("schedule_raw", "0 9 * * *"),
            schedule_kind=kwargs.get("schedule_kind", ScheduleKind.CRON),
            payload=kwargs.get("payload", {}),
            handler_key=kwargs.get("handler_key", "agent_run"),
            session_target=kwargs.get("session_target", SessionTarget.ISOLATED),
            session_key=kwargs.get("session_key", ""),
            origin_session_key=kwargs.get("origin_session_key", ""),
        )
        self.jobs[job_id] = job
        return job

    async def update_job(self, job_id: str, **patch: Any) -> CronJob | None:
        self.last_updated = patch
        job = self.jobs.get(job_id)
        if not job:
            return None
        for k, v in patch.items():
            if hasattr(job, k):
                setattr(job, k, v)
        return job

    async def remove_job(self, job_id: str) -> bool:
        self.removed.append(job_id)
        return self.jobs.pop(job_id, None) is not None

    async def run_job_now(self, job_id: str) -> ManualRunResult:
        self.ran.append(job_id)
        now = datetime.now(UTC)
        execution = JobExecution(
            id=f"run-{job_id}",
            job_id=job_id,
            started_at=now,
            finished_at=now,
            success=True,
            summary="output",
        )
        self.runs.append(execution)
        return ManualRunResult(
            status=ManualRunStatus.ACCEPTED,
            execution=execution,
        )

    async def get_runs(self, job_id: str, limit: int = 20) -> list[JobExecution]:
        return [r for r in self.runs if r.job_id == job_id][:limit]

    async def get_run(self, job_id: str, run_id: str | None = None) -> JobExecution | None:
        matching = [r for r in self.runs if r.job_id == job_id]
        if not matching:
            return None
        if run_id:
            for r in matching:
                if r.id == run_id:
                    return r
            return None
        return matching[-1]


def _make_job(
    job_id: str,
    *,
    agent_id: str = "main",
    session_target: SessionTarget = SessionTarget.ISOLATED,
) -> CronJob:
    return CronJob(
        id=job_id,
        name="test job",
        cron_expr="0 9 * * *",
        schedule_raw="0 9 * * *",
        schedule_kind=ScheduleKind.CRON,
        handler_key="agent_run",
        payload={"kind": "reminder", "text": "ping", "agent_id": agent_id},
        session_target=session_target,
    )


@pytest.mark.asyncio
async def test_cron_status_accepts_job_id_and_job_id_camel() -> None:
    job = _make_job("job-123")
    scheduler = _FakeCronScheduler([job])
    ctx = RpcContext(conn_id="test", cron_scheduler=scheduler)

    # 1. snake_case job_id
    res_snake = await _handle_cron_status({"job_id": "job-123"}, ctx)
    assert res_snake["id"] == "job-123"
    assert res_snake["job_id"] == "job-123"

    # 2. camelCase jobId
    res_camel = await _handle_cron_status({"jobId": "job-123"}, ctx)
    assert res_camel["id"] == "job-123"
    assert res_camel["jobId"] == "job-123"


@pytest.mark.asyncio
async def test_cron_remove_accepts_job_id_aliases() -> None:
    job1 = _make_job("job-1")
    job2 = _make_job("job-2")
    scheduler = _FakeCronScheduler([job1, job2])
    ctx = RpcContext(conn_id="test", cron_scheduler=scheduler)

    await _handle_cron_remove({"job_id": "job-1"}, ctx)
    assert scheduler.removed == ["job-1"]
    assert "job-1" not in scheduler.jobs

    await _handle_cron_remove({"jobId": "job-2"}, ctx)
    assert scheduler.removed == ["job-1", "job-2"]
    assert "job-2" not in scheduler.jobs


@pytest.mark.asyncio
async def test_cron_run_accepts_job_id_aliases() -> None:
    job = _make_job("job-run")
    scheduler = _FakeCronScheduler([job])
    ctx = RpcContext(conn_id="test", cron_scheduler=scheduler)

    res1 = await _handle_cron_run({"job_id": "job-run"}, ctx)
    assert res1["status"] == "accepted"
    assert scheduler.ran == ["job-run"]

    res2 = await _handle_cron_run({"jobId": "job-run"}, ctx)
    assert res2["status"] == "accepted"
    assert scheduler.ran == ["job-run", "job-run"]


@pytest.mark.asyncio
async def test_cron_runs_and_output_accept_job_id_and_run_id_aliases() -> None:
    job = _make_job("job-runs")
    scheduler = _FakeCronScheduler([job])
    ctx = RpcContext(conn_id="test", cron_scheduler=scheduler)

    await _handle_cron_run({"id": "job-runs"}, ctx)

    # cron.runs with jobId
    runs = await _handle_cron_runs({"jobId": "job-runs"}, ctx)
    assert len(runs) == 1
    assert runs[0]["id"] == "run-job-runs"

    # cron.runOutput with job_id and run_id
    output = await _handle_cron_run_output(
        {"job_id": "job-runs", "run_id": "run-job-runs"},
        ctx,
    )
    assert output["jobId"] == "job-runs"
    assert output["runId"] == "run-job-runs"
    assert output["output"] == "output"


@pytest.mark.asyncio
async def test_cron_list_filters_by_agent_id_snake_case() -> None:
    job1 = _make_job("job-a", agent_id="researcher")
    job2 = _make_job("job-b", agent_id="coder")
    scheduler = _FakeCronScheduler([job1, job2])
    ctx = RpcContext(conn_id="test", cron_scheduler=scheduler)

    # Filter with snake_case agent_id
    res_researcher = await _handle_cron_list({"agent_id": "researcher"}, ctx)
    assert len(res_researcher) == 1
    assert res_researcher[0]["id"] == "job-a"
    assert res_researcher[0]["agent_id"] == "researcher"

    res_coder = await _handle_cron_list({"agent_id": "coder"}, ctx)
    assert len(res_coder) == 1
    assert res_coder[0]["id"] == "job-b"
    assert res_coder[0]["agent_id"] == "coder"


@pytest.mark.asyncio
async def test_cron_add_accepts_snake_case_parameters() -> None:
    scheduler = _FakeCronScheduler()
    ctx = RpcContext(conn_id="test", cron_scheduler=scheduler)

    # Add job with agent_id and session_target
    res = await _handle_cron_add(
        {
            "schedule": {"kind": "cron", "expr": "0 9 * * *"},
            "message": "check stock",
            "agent_id": "finance",
            "payload_kind": "reminder",
            "session_target": "isolated",
            "origin_session_key": "sess-123",
        },
        ctx,
    )

    assert scheduler.last_added is not None
    payload = scheduler.last_added["payload"]
    assert payload["agent_id"] == "finance"
    assert scheduler.last_added["session_target"] == SessionTarget.ISOLATED
    assert scheduler.last_added["origin_session_key"] == "sess-123"

    # Check wire output exposes both camelCase and snake_case
    assert res["agentId"] == "finance"
    assert res["agent_id"] == "finance"
    assert res["payloadKind"] == "reminder"
    assert res["payload_kind"] == "reminder"
    assert res["sessionTarget"] == "isolated"
    assert res["session_target"] == "isolated"
    assert res["jobId"] is not None
    assert res["job_id"] is not None


@pytest.mark.asyncio
async def test_cron_update_accepts_job_id_and_snake_case_aliases() -> None:
    job = _make_job("job-update", agent_id="orig_agent")
    scheduler = _FakeCronScheduler([job])
    ctx = RpcContext(conn_id="test", cron_scheduler=scheduler)

    # Update job using job_id and snake_case payload params
    res = await _handle_cron_update(
        {
            "job_id": "job-update",
            "agent_id": "new_agent",
            "text": "new text",
        },
        ctx,
    )

    assert scheduler.last_updated is not None
    assert scheduler.last_updated["payload"]["agent_id"] == "new_agent"
    assert scheduler.last_updated["payload"]["text"] == "new text"
    assert res["agent_id"] == "new_agent"
    assert res["agentId"] == "new_agent"


def test_job_to_wire_provides_symmetric_snake_and_camel_keys() -> None:
    job = _make_job("job-sym", agent_id="analyst")
    wire = _job_to_wire(job)

    assert wire["id"] == "job-sym"
    assert wire["job_id"] == "job-sym"
    assert wire["jobId"] == "job-sym"
    assert wire["agent_id"] == "analyst"
    assert wire["agentId"] == "analyst"
    assert wire["payload_kind"] == "reminder"
    assert wire["payloadKind"] == "reminder"
    assert wire["session_target"] == "isolated"
    assert wire["sessionTarget"] == "isolated"
    assert wire["wake_mode"] == "now"
    assert wire["wakeMode"] == "now"
