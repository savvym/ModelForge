from fastapi import APIRouter, Header, HTTPException, Query, Request, status

from nta_backend.schemas.probe import (
    ProbeDetail,
    ProbeHeartbeatRequest,
    ProbeHeartbeatResponse,
    ProbeRegistrationRequest,
    ProbeRegistrationResponse,
    ProbeSummary,
    ProbeTaskClaimResponse,
    ProbeTaskCompleteRequest,
    ProbeTaskCreate,
    ProbeTaskDetail,
    ProbeTaskFailRequest,
    ProbeTaskProgressRequest,
    ProbeTaskStartRequest,
    ProbeTaskSummary,
    ProbeTaskTransitionResponse,
)
from nta_backend.services.probe_service import ProbeService

router = APIRouter()
service = ProbeService()


@router.get("/api/v2/probes", response_model=list[ProbeSummary])
async def list_probes() -> list[ProbeSummary]:
    return await service.list_probes()


@router.get("/api/v2/probes/{probe_id}", response_model=ProbeDetail)
async def get_probe(probe_id: str) -> ProbeDetail:
    try:
        return await service.get_probe(probe_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Probe not found",
        ) from exc


@router.post(
    "/api/v2/probe-tasks",
    response_model=ProbeTaskDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_probe_task(payload: ProbeTaskCreate) -> ProbeTaskDetail:
    try:
        return await service.create_task(payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Probe not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/api/v2/probe-tasks", response_model=list[ProbeTaskSummary])
async def list_probe_tasks(
    probe_id: str | None = Query(default=None),
    status_text: str | None = Query(default=None, alias="status"),
) -> list[ProbeTaskSummary]:
    return await service.list_tasks(probe_id=probe_id, status=status_text)


@router.get("/api/v2/probe-tasks/{task_id}", response_model=ProbeTaskDetail)
async def get_probe_task(task_id: str) -> ProbeTaskDetail:
    try:
        return await service.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Probe task not found",
        ) from exc


@router.post("/api/v2/probes/register", response_model=ProbeRegistrationResponse)
async def register_probe(
    payload: ProbeRegistrationRequest,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> ProbeRegistrationResponse:
    try:
        return await service.register_probe(
            payload,
            authorization=authorization,
            client_ip=request.client.host if request.client else None,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/api/v2/probes/{probe_id}/heartbeat", response_model=ProbeHeartbeatResponse)
async def heartbeat_probe(
    probe_id: str,
    payload: ProbeHeartbeatRequest,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> ProbeHeartbeatResponse:
    try:
        return await service.heartbeat(
            probe_id,
            payload,
            authorization=authorization,
            client_ip=request.client.host if request.client else None,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Probe not found",
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/api/v2/probes/{probe_id}/tasks/claim", response_model=ProbeTaskClaimResponse)
async def claim_probe_task(
    probe_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> ProbeTaskClaimResponse:
    try:
        return await service.claim_task(probe_id, authorization=authorization)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Probe not found",
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/api/v2/probes/tasks/{task_id}/start", response_model=ProbeTaskTransitionResponse)
async def start_probe_task(
    task_id: str,
    payload: ProbeTaskStartRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> ProbeTaskTransitionResponse:
    try:
        return await service.start_task(task_id, payload, authorization=authorization)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Probe task not found",
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/api/v2/probes/tasks/{task_id}/progress", response_model=ProbeTaskTransitionResponse)
async def report_probe_task_progress(
    task_id: str,
    payload: ProbeTaskProgressRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> ProbeTaskTransitionResponse:
    try:
        return await service.report_progress(task_id, payload, authorization=authorization)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Probe task not found",
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/api/v2/probes/tasks/{task_id}/complete", response_model=ProbeTaskTransitionResponse)
async def complete_probe_task(
    task_id: str,
    payload: ProbeTaskCompleteRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> ProbeTaskTransitionResponse:
    try:
        return await service.complete_task(task_id, payload, authorization=authorization)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Probe task not found",
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/api/v2/probes/tasks/{task_id}/fail", response_model=ProbeTaskTransitionResponse)
async def fail_probe_task(
    task_id: str,
    payload: ProbeTaskFailRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> ProbeTaskTransitionResponse:
    try:
        return await service.fail_task(task_id, payload, authorization=authorization)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Probe task not found",
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
