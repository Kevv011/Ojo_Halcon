# API y WebSocket

## Iniciar el backend

Cierra primero el calibrador OpenCV para liberar la webcam. Desde la carpeta
`backend` ejecuta:

```powershell
& .\.venv\Scripts\python.exe -m ojo_halcon.api --camera 1
```

Si la cámara correcta es la cero, cambia el final por `--camera 0`. El servidor
escucha únicamente en `127.0.0.1:8000` de forma predeterminada, por lo que no
queda expuesto a otros equipos de la red.

Direcciones útiles:

- documentación interactiva: <http://127.0.0.1:8000/docs>
- estado actual: <http://127.0.0.1:8000/api/state>
- salud del servicio: <http://127.0.0.1:8000/api/health>
- última captura procesada: <http://127.0.0.1:8000/api/snapshot.jpg>
- captura de una decisión: `http://127.0.0.1:8000/api/result-snapshot.jpg?play_id=1`
- WebSocket: `ws://127.0.0.1:8000/ws`

## Endpoints

| Método | Ruta | Función |
|---|---|---|
| `GET` | `/api/health` | Verifica cámara, frames recientes, calibración, resolución e historial. |
| `GET` | `/api/state` | Devuelve cámara, detección, geometría y jugada actual. |
| `GET` | `/api/plays?limit=20` | Devuelve las decisiones más recientes. |
| `GET` | `/api/config` | Devuelve la calibración activa. |
| `GET` | `/api/snapshot.jpg` | Devuelve el último frame con diagnósticos. |
| `GET` | `/api/result-snapshot.jpg?play_id=1` | Devuelve el frame exacto de una decisión en memoria. |
| `POST` | `/api/reset` | Solicita cancelar la jugada y rearmar el sistema. |
| `GET` | `/api/admin/calibration/status` | Informa el ciclo del calibrador. |
| `POST` | `/api/admin/calibration/start` | Libera la cámara y abre el calibrador local. |
| `WS` | `/ws` | Publica el estado actualizado en tiempo real. |

## Ejemplos desde PowerShell

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/state
Invoke-RestMethod http://127.0.0.1:8000/api/plays?limit=10
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/reset
```

## Mensaje WebSocket

Cada mensaje contiene una fotografía lógica completa del sistema:

```json
{
  "schema_version": "1.0",
  "type": "state",
  "service_mode": "detecting",
  "timestamp": "2026-10-11T20:00:00+00:00",
  "camera": {
    "connected": true,
    "fps": 8.4,
    "index": 1,
    "error": null,
    "width": 1280,
    "height": 720,
    "resolution_matches": true
  },
  "detection": {
    "status": "DETECTADO",
    "center": {"x": 650.2, "y": 418.5},
    "radius_px": 74.1,
    "speed_px_s": 35.0,
    "area_px": 15448.0,
    "circularity": 0.72
  },
  "geometry": {
    "relation": "CRUZADO",
    "signed_distance_px": 112.1,
    "trailing_edge_px": 38.0,
    "inside_posts": true
  },
  "game": {
    "state": "GOAL",
    "play_id": 1,
    "reason": "Cruce completo confirmado",
    "state_elapsed_seconds": 0.1,
    "approach_speed_px_s": 80.0,
    "crossed_observations": 3,
    "waiting_for_removal": false
  },
  "calibration": {
    "ready": true,
    "errors": []
  }
}
```

El frontend debe usar `game.state` como fuente de verdad. No debe volver a
calcular si fue gol usando las coordenadas.

## Historial

Cada `GOAL` o `NO GOAL` se agrega una sola vez a
`backend/data/plays.jsonl`. El archivo se carga al iniciar, permite continuar
la numeración de jugadas y conserva las 500 decisiones más recientes. No se
guarda una entrada para estados intermedios. La escritura es atómica: un fallo
de disco se informa en `/api/health`, pero no oculta la decisión en vivo.

## Interpretar `/api/health`

El estado es `ok` únicamente cuando se cumplen todas estas condiciones:

- la webcam está conectada;
- llegó un frame durante los últimos dos segundos;
- línea, punto interior y zona ROI están calibrados;
- la resolución real coincide con la configurada;
- no hay un error pendiente de procesamiento o historial.

Si la webcam se desconecta, la detección y la captura anterior se limpian,
`/api/health` cambia a `degraded` y el servidor intenta reconectarse cada dos
segundos. Los campos `camera_error`, `processing_error` e `history_error`
permiten distinguir la causa.

## Calibración desde `/admin`

La petición `POST /api/admin/calibration/start` responde `202` y ejecuta el
siguiente ciclo sin cerrar FastAPI:

1. detiene el hilo de detección y libera la webcam;
2. abre el calibrador OpenCV con el mismo índice y archivo JSON;
3. espera que el usuario guarde con `S` y cierre con `Q`;
4. valida y recarga la configuración;
5. reinicia la detección.

El estado pasa por `stopping`, `calibrating`, `restarting` e `idle`. Si OpenCV
termina con error, cambia a `error` y el backend vuelve a usar la configuración
anterior. Solo se permite un proceso de calibración a la vez.

Las capturas de resultado se conservan en memoria para las 20 jugadas más
recientes del proceso actual. El frontend las solicita por `play_id`; después
de reiniciar FastAPI continúa el historial, pero no esas imágenes temporales.
