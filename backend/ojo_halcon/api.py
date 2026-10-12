from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .calibration import CalibrationBusyError, CalibrationManager
from .config import AppConfig, ConfigError
from .schemas import (
    ApiInfo,
    CalibrationProcessStatus,
    HealthResponse,
    HistoryResponse,
    ResetResponse,
    SystemState,
)
from .service import VisionRuntime


BACKEND_DIR = Path(__file__).resolve().parent.parent


def create_app(
    runtime: VisionRuntime,
    start_runtime: bool = True,
    calibration_manager: CalibrationManager | None = None,
) -> FastAPI:
    manager = calibration_manager or CalibrationManager(runtime, runtime.config_path)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        runtime.broadcaster.attach_loop(asyncio.get_running_loop())
        if start_runtime:
            runtime.start()
        try:
            yield
        finally:
            manager.shutdown()
            if start_runtime:
                runtime.stop()

    app = FastAPI(
        title="Ojo de Halcón API",
        version=__version__,
        description="Estado, historial y control del detector escolar de gol.",
        lifespan=lifespan,
    )
    app.state.runtime = runtime
    app.state.calibration_manager = manager
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/", response_model=ApiInfo)
    async def api_info() -> ApiInfo:
        return ApiInfo(
            version=__version__,
            endpoints=[
                "/api/health",
                "/api/state",
                "/api/plays",
                "/api/config",
                "/api/snapshot.jpg",
                "/api/result-snapshot.jpg?play_id=1",
                "/api/reset",
                "/api/admin/calibration/status",
                "/api/admin/calibration/start",
            ],
        )

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return runtime.get_health()

    @app.get("/api/state", response_model=SystemState)
    async def state() -> SystemState:
        return runtime.get_state()

    @app.get("/api/plays", response_model=HistoryResponse)
    async def plays(
        limit: int = Query(default=20, ge=1, le=500),
    ) -> HistoryResponse:
        return HistoryResponse(
            plays=runtime.history.recent(limit),
            total=runtime.history.total,
        )

    @app.get("/api/config")
    async def configuration() -> dict[str, Any]:
        return runtime.get_configuration()

    @app.get("/api/snapshot.jpg")
    async def snapshot() -> Response:
        jpeg = runtime.get_latest_jpeg()
        if jpeg is None:
            raise HTTPException(
                status_code=503,
                detail="Todavia no hay una imagen disponible de la webcam",
            )
        return Response(
            content=jpeg,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/result-snapshot.jpg")
    async def result_snapshot(
        play_id: int = Query(ge=1),
    ) -> Response:
        jpeg = runtime.get_result_jpeg(play_id)
        if jpeg is None:
            raise HTTPException(
                status_code=404,
                detail="No hay una captura disponible para esa jugada",
            )
        return Response(
            content=jpeg,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/reset", response_model=ResetResponse, status_code=202)
    async def reset() -> ResetResponse:
        runtime.request_reset()
        return ResetResponse()

    @app.get(
        "/api/admin/calibration/status",
        response_model=CalibrationProcessStatus,
    )
    async def calibration_status() -> CalibrationProcessStatus:
        return manager.get_status()

    @app.post(
        "/api/admin/calibration/start",
        response_model=CalibrationProcessStatus,
        status_code=202,
    )
    async def start_calibration() -> CalibrationProcessStatus:
        try:
            return manager.start()
        except CalibrationBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.websocket("/ws")
    async def websocket_state(websocket: WebSocket) -> None:
        await websocket.accept()
        queue = runtime.broadcaster.subscribe()
        try:
            await websocket.send_json(runtime.get_state().model_dump(mode="json"))
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=10.0)
                except TimeoutError:
                    # Mantiene viva la conexión incluso si la cámara está reintentando.
                    payload = runtime.get_state().model_dump(mode="json")
                await websocket.send_json(payload)
        except WebSocketDisconnect:
            pass
        finally:
            runtime.broadcaster.unsubscribe(queue)

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="API del sistema Ojo de Halcon")
    parser.add_argument("--camera", type=int, default=0, help="Indice de la webcam")
    parser.add_argument(
        "--config",
        type=Path,
        default=BACKEND_DIR / "config" / "default.json",
        help="Archivo JSON de calibracion",
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=BACKEND_DIR / "data" / "plays.jsonl",
        help="Archivo persistente de jugadas",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Direccion del servidor")
    parser.add_argument("--port", type=int, default=8000, help="Puerto HTTP")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        config = AppConfig.load(args.config, require_exists=True)
    except ConfigError as error:
        raise SystemExit(f"Configuración inválida: {error}") from error
    runtime = VisionRuntime(
        config=config,
        camera_index=args.camera,
        history_path=args.history,
        config_path=args.config,
    )
    app = create_app(runtime)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
