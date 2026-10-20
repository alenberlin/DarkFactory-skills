"""Loopback administrative API and a dashboard backed by actual factory records."""

import hmac
import json
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from darkfactory.discovery import Discovery
from darkfactory.domain import Blueprint, InferenceSpec, Limits, Policy
from darkfactory.execution import BoundaryError
from darkfactory.profiles import Profile
from darkfactory.security import redact
from darkfactory.services import Factory
from darkfactory.storage import StateError, Store


class ImportRequest(BaseModel):
    """Human-submitted proposed blueprint, policy and local source path."""

    model_config = ConfigDict(extra="forbid")
    blueprint: Blueprint
    policy: Policy = Field(default_factory=Policy)
    source: str


class ApprovalRequest(BaseModel):
    """Exact blueprint digest; callers cannot supply their own approval identity."""

    model_config = ConfigDict(extra="forbid")
    digest: str = Field(min_length=64, max_length=64)


class AcceptanceRequest(BaseModel):
    """Exact delivery digest and optional human rejection feedback."""

    model_config = ConfigDict(extra="forbid")
    revision: str = Field(min_length=64, max_length=64)
    reason: str = Field(default="", max_length=16000)
    criteria: list[str] | None = None


class DiscoveryRequest(BaseModel):
    """Explicit human authorization for planning inference, without implementation approval."""

    model_config = ConfigDict(extra="forbid")
    goal: str = Field(min_length=1, max_length=16000)
    inference: InferenceSpec
    limits: Limits
    source: str
    adapter: str = Field(pattern=r"^(claude|codex)$")
    profile: Profile | None = None


class AnswerRequest(BaseModel):
    """Human answers to the pending discovery questions."""

    model_config = ConfigDict(extra="forbid")
    answers: list[str] = Field(min_length=1, max_length=100)


class RevisionRequest(BaseModel):
    """A new proposed version that cannot inherit an earlier approval."""

    model_config = ConfigDict(extra="forbid")
    blueprint: Blueprint
    policy: Policy


class UsageRequest(BaseModel):
    """Human accounting values for an unknown inference charge, with an audit reference."""

    model_config = ConfigDict(extra="forbid")
    tokens: int = Field(ge=0)
    cost_microusd: int | None = Field(default=None, ge=0)
    reference: str = Field(min_length=1, max_length=1000)


class FindingExceptionRequest(BaseModel):
    """Explicit human justification bound to one immutable source revision."""

    model_config = ConfigDict(extra="forbid")
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    reason: str = Field(min_length=1, max_length=16000)


def create_app(store: Store, admin_token: str, factory: Factory | None = None) -> FastAPI:
    """Create a local administrative application with a separately provisioned bearer identity.

    Args:
        store: Protected controller storage.
        admin_token: Operator-provisioned credential, never returned by this API.
        factory: Optional shared service used for deterministic integration tests.

    Returns:
        An authenticated API and public static dashboard shell.

    Raises:
        ValueError: The administrator credential is too short.
    """
    if len(admin_token) < 32:
        raise ValueError("administrator credential must contain at least 32 characters")
    app = FastAPI(title="DarkFactory Autopilot", version="0.3.0")
    service = factory or Factory(store)
    security = HTTPBearer(auto_error=False)

    def human(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    ) -> str:
        if credentials is None or not hmac.compare_digest(credentials.credentials, admin_token):
            raise HTTPException(status_code=401, detail="administrator authentication required")
        return "human:local-operator"

    @app.middleware("http")
    async def guard(request: Request, call_next: object) -> Response:
        from collections.abc import Awaitable, Callable
        from typing import cast

        host = request.headers.get("host", "").split(":")[0]
        origin = request.headers.get("origin")
        allowed_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if host not in ("127.0.0.1", "localhost") or (origin and origin != allowed_origin):
            return JSONResponse(status_code=403, content={"detail": "local Host/Origin required"})
        response = await cast(Callable[[Request], Awaitable[Response]], call_next)(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(StateError)
    async def state_error(request: Request, error: StateError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": redact(str(error))})

    @app.exception_handler(BoundaryError)
    async def boundary_error(request: Request, error: BoundaryError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": redact(str(error))})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
                    for item in error.errors()
                ]
            },
        )

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return Path(__file__).with_name("web").joinpath("index.html").read_text()

    @app.get("/assets/{name}")
    def asset(name: str) -> Response:
        if name not in ("app.js", "style.css"):
            raise HTTPException(status_code=404)
        kind = "text/javascript" if name.endswith("js") else "text/css"
        return Response(Path(__file__).with_name("web").joinpath(name).read_text(), media_type=kind)

    @app.get("/v1/projects")
    def projects(actor: Annotated[str, Depends(human)]) -> list[dict[str, object]]:
        return [
            {key: row[key] for key in ("id", "name", "state", "error", "updated")}
            for row in store.projects()
        ]

    @app.post("/v1/projects", status_code=201)
    def propose(body: ImportRequest, actor: Annotated[str, Depends(human)]) -> dict[str, str]:
        project = service.propose(body.blueprint, body.policy, Path(body.source))
        return {"id": project, "digest": store.project(project)["blueprint_hash"]}

    @app.get("/v1/projects/{project}")
    def project_report(project: str, actor: Annotated[str, Depends(human)]) -> dict[str, object]:
        return service.report(project)

    @app.post("/v1/discovery", status_code=201)
    def discover(
        body: DiscoveryRequest, actor: Annotated[str, Depends(human)]
    ) -> dict[str, object]:
        discovery = Discovery(store, service.engine)
        project = discovery.begin(
            body.goal,
            body.inference,
            body.limits,
            Path(body.source),
            body.adapter,
            profile=body.profile,
        )
        return {"id": project, **discovery.advance(project)}

    @app.post("/v1/discovery/{project}/answer")
    def answer(
        project: str, body: AnswerRequest, actor: Annotated[str, Depends(human)]
    ) -> dict[str, object]:
        return Discovery(store, service.engine).advance(project, body.answers)

    @app.post("/v1/projects/{project}/revise", status_code=201)
    def revise(
        project: str, body: RevisionRequest, actor: Annotated[str, Depends(human)]
    ) -> dict[str, str]:
        proposed = service.revise(project, body.blueprint, body.policy)
        return {"id": proposed, "digest": store.project(proposed)["blueprint_hash"]}

    @app.post("/v1/projects/{project}/retry")
    def retry(project: str, actor: Annotated[str, Depends(human)]) -> dict[str, object]:
        service.retry(project, actor)
        return {"state": store.project(project)["state"]}

    @app.post("/v1/projects/{project}/review")
    def review(project: str, actor: Annotated[str, Depends(human)]) -> dict[str, bool]:
        return {"reviewed": service.review(project)}

    @app.post("/v1/projects/{project}/usage/{usage}/reconcile")
    def reconcile_usage(
        project: str, usage: str, body: UsageRequest, actor: Annotated[str, Depends(human)]
    ) -> dict[str, str]:
        service.reconcile_usage(
            project, usage, body.tokens, body.cost_microusd, body.reference, actor
        )
        return {"state": store.project(project)["state"]}

    @app.post("/v1/projects/{project}/approve")
    def approve(
        project: str, body: ApprovalRequest, actor: Annotated[str, Depends(human)]
    ) -> dict[str, str]:
        store.approve(project, body.digest, actor)
        return {"state": store.project(project)["state"]}

    @app.post("/v1/projects/{project}/findings/{finding}/exception", status_code=201)
    def grant_exception(
        project: str,
        finding: str,
        body: FindingExceptionRequest,
        actor: Annotated[str, Depends(human)],
    ) -> dict[str, str]:
        return {"id": service.grant_exception(project, finding, body.revision, body.reason, actor)}

    @app.post("/v1/projects/{project}/exceptions/{exception}/revoke")
    def revoke_exception(
        project: str,
        exception: str,
        actor: Annotated[str, Depends(human)],
    ) -> dict[str, str]:
        service.revoke_exception(project, exception, actor)
        return {"state": store.project(project)["state"]}

    @app.post("/v1/projects/{project}/{action}")
    def control(
        project: str, action: str, actor: Annotated[str, Depends(human)]
    ) -> dict[str, object]:
        if action in ("start", "resume"):
            service.start(project)
        elif action in ("pause", "cancel"):
            service.control(project, action, actor)
        else:
            raise HTTPException(status_code=404, detail="unknown operation")
        return {"state": store.project(project)["state"]}

    @app.post("/v1/deliveries/{project}/accept")
    def accept(
        project: str, body: AcceptanceRequest, actor: Annotated[str, Depends(human)]
    ) -> dict[str, str]:
        service.accept(project, body.revision, actor)
        return {"state": store.project(project)["state"]}

    @app.post("/v1/deliveries/{project}/reject")
    def reject(
        project: str, body: AcceptanceRequest, actor: Annotated[str, Depends(human)]
    ) -> dict[str, str]:
        service.reject(project, body.revision, body.reason, actor, body.criteria)
        return {"state": store.project(project)["state"]}

    @app.get("/v1/projects/{project}/export")
    def export_report(project: str, actor: Annotated[str, Depends(human)]) -> Response:
        return Response(
            json.dumps(service.report(project), indent=2), media_type="application/json"
        )

    return app
