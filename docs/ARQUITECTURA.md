# Arquitectura propuesta

## Principio

Python es la fuente de verdad. Captura la cámara, detecta y sigue el balón,
aplica la regla y administra el estado de la jugada. Vue solamente presenta el
estado y envía acciones explícitas como reiniciar.

```text
Webcam -> VisionPipeline -> detector -> seguimiento -> geometría -> estados
                              |                                    |
                         calibrador                           FastAPI/WS
                                                                   |
                                                                  Vue
```

## Estructura objetivo

```text
Ojo_Halcon/
|-- backend/
|   |-- config/              # Calibración de cada escena
|   |-- ojo_halcon/
|   |   |-- vision/          # Cámara, máscara y contornos
|   |   |-- tracking/        # Trayectoria y filtro temporal (fase 2)
|   |   |-- game/            # Regla y estados (fase 3)
|   |   `-- api/             # WebSocket/HTTP (fase 4)
|   `-- tests/
|-- frontend/                # Vue + Vite (fase 4)
`-- docs/
```

Actualmente existen las piezas de visión, seguimiento temporal, diagnóstico
geométrico, máquina de estados, historial persistente, API HTTP, WebSocket y la
interfaz Vue. El panel local coordina el calibrador sin cerrar FastAPI.

## Decisiones técnicas

### Cámara

Una sola webcam fija. La posición superior es preferible porque reduce la
ambigüedad de perspectiva. Resolución inicial: 1280 x 720 a 30 FPS, reducida si
el equipo no procesa de forma fluida.

### Detección inicial

HSV + operaciones morfológicas + contorno de mayor tamaño. HSV suele tolerar
mejor los cambios de brillo que RGB. Un rango de área descarta ruido pequeño y
objetos demasiado grandes.

### Regla de decisión

La línea se representa mediante dos puntos, no como una coordenada vertical
fija. Esto permite una cámara ligeramente inclinada. El detector aproximará el
balón con un círculo de centro `C` y radio `r`.

La decisión no usa solamente el centro. Para que el balón esté
completamente al otro lado, la distancia firmada del centro a la línea debe
superar su radio, más una tolerancia calibrable. También se exigirá una secuencia
temporal: aproximación, cruce y varios fotogramas de confirmación.

La máquina de estados implementada sigue esta secuencia:

```text
ESPERANDO JUGADA -> ANALIZANDO -> GOAL / NO GOAL
        ^                              |
        `--- resultado + retirar balón-'
```

Todos los umbrales temporales se expresan en segundos reales para no depender
de que la webcam alcance los FPS solicitados.

### Comunicación implementada

FastAPI expone consultas HTTP, una captura JPEG y un WebSocket local. El backend
emite mensajes de estado como:

```json
{
  "type": "state",
  "game": {
    "state": "GOAL",
    "play_id": 12,
    "reason": "Cruce completo confirmado"
  }
}
```

Vue no interpretará coordenadas ni decidirá resultados.

El calibrador y el servidor llaman al mismo `VisionPipeline`; por ello una
misma imagen no pasa por dos implementaciones distintas. Al perder la cámara,
el servidor limpia pista, geometría, captura y jugada antes de reintentar. El
endpoint de salud también comprueba calibración, antigüedad del último frame,
resolución real y errores de persistencia.

## Fases y puertas de validación

1. **Visión:** captura, color, contorno y línea estables en la escena real.
2. **Seguimiento:** trayectoria coherente y manejo de pérdidas breves.
3. **Regla:** cruce completo, `GOAL`/`NO GOAL`, temporizadores y una decisión
   por jugada.
4. **Presentación:** API local, WebSocket, marcador Vue y `/admin` completados.
5. **Pruebas:** matriz de casos, ajuste de tolerancias y modo demostración.

Cada fase debe probarse antes de introducir la siguiente; así, si algo falla,
se sabe si el problema está en la imagen, el seguimiento, la regla o la UI.
