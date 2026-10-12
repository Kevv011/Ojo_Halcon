from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CameraStatus(BaseModel):
    connected: bool = False
    fps: float = 0.0
    index: int = 0
    error: str | None = None
    width: int | None = None
    height: int | None = None
    resolution_matches: bool | None = None


class PointData(BaseModel):
    x: float
    y: float


class DetectionStatus(BaseModel):
    status: Literal["DETECTADO", "RECUPERANDO", "SIN BALON"] = "SIN BALON"
    center: PointData | None = None
    radius_px: float | None = None
    speed_px_s: float = 0.0
    area_px: float | None = None
    circularity: float | None = None


class GeometryStatus(BaseModel):
    relation: Literal[
        "SIN CALIBRAR",
        "FUERA DE LOS POSTES",
        "ANTES",
        "TOCANDO",
        "PARCIAL",
        "CRUZADO",
    ]
    signed_distance_px: float
    trailing_edge_px: float
    inside_posts: bool


class GameStatus(BaseModel):
    state: Literal["ESPERANDO JUGADA", "ANALIZANDO", "GOAL", "NO GOAL"] = (
        "ESPERANDO JUGADA"
    )
    play_id: int = 0
    reason: str = "Servicio iniciando"
    state_elapsed_seconds: float = 0.0
    approach_speed_px_s: float = 0.0
    crossed_observations: int = 0
    waiting_for_removal: bool = False


class CalibrationStatus(BaseModel):
    ready: bool = False
    errors: list[str] = Field(default_factory=list)


class SystemState(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    type: Literal["state"] = "state"
    service_mode: Literal["detecting", "calibrating"] = "detecting"
    timestamp: str
    camera: CameraStatus
    detection: DetectionStatus
    geometry: GeometryStatus | None = None
    game: GameStatus
    calibration: CalibrationStatus = Field(default_factory=CalibrationStatus)


class PlayRecord(BaseModel):
    play_id: int
    result: Literal["GOAL", "NO GOAL"]
    reason: str
    decided_at: str
    approach_speed_px_s: float = 0.0
    crossed_observations: int = 0


class HistoryResponse(BaseModel):
    plays: list[PlayRecord]
    total: int


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service_mode: Literal["detecting", "calibrating"] = "detecting"
    camera_connected: bool
    calibration_ready: bool
    processing_alive: bool
    last_frame_age_seconds: float | None = None
    camera_error: str | None = None
    processing_error: str | None = None
    history_error: str | None = None
    resolution_matches: bool | None = None


class CalibrationProcessStatus(BaseModel):
    status: Literal["idle", "stopping", "calibrating", "restarting", "error"]
    active: bool
    message: str
    error: str | None = None
    started_at: str | None = None


class ResetResponse(BaseModel):
    accepted: bool = True
    message: str = "Reinicio solicitado"


class ApiInfo(BaseModel):
    name: str = "Ojo de Halcon API"
    version: str
    docs: str = "/docs"
    websocket: str = "/ws"
    endpoints: list[str] = Field(default_factory=list)
