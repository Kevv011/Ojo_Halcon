# Ojo de Halcón escolar

Prototipo educativo de visión por computadora para detectar un balón y, en
fases posteriores, decidir si cruzó completamente una línea de gol.

Para preparar una computadora nueva desde cero, consulta la
[guía de instalación y uso](docs/GUIA_INSTALACION_Y_USO.md).

Después de instalar Python, Node.js y pnpm, también puedes iniciar y restaurar
automáticamente todo el proyecto con doble clic en `INICIAR_OJO_HALCON.cmd`.

## Alcance actual: fase 5 (presentación)

La aplicación permite:

- abrir una webcam;
- comprobar que la imagen es estable;
- seleccionar el color del balón con un clic;
- detectar el balón por color y contorno;
- marcar la línea de gol con dos clics;
- definir una zona poligonal de análisis con cuatro clics;
- rechazar regiones poco circulares;
- suavizar el centro y radio detectados;
- mostrar la trayectoria y velocidad aproximada;
- conservar brevemente la pista ante pérdidas de hasta tres frames o 0.5 s;
- mostrar FPS y datos de diagnóstico;
- decidir una jugada mediante estados temporales `GOAL` / `NO GOAL`;
- conservar el resultado y exigir retirar el balón antes de rearmarse;
- publicar el estado mediante FastAPI y WebSocket;
- guardar un historial persistente de jugadas;
- permitir consultar una captura procesada y reiniciar remotamente;
- guardar la calibración en un archivo JSON;
- presentar cada decisión en una pantalla Vue;
- conservar la captura exacta asociada a cada resultado;
- abrir el calibrador desde `/admin` y reactivar el backend al cerrarlo.

El backend y el frontend local están disponibles. La pantalla pública solamente
presenta la jugada; los diagnósticos y controles permanecen en `/admin`.

## Preparación

Se recomienda Python 3.11 o posterior. Este repositorio se validó localmente
con Python 3.14 y OpenCV 4.14.

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

## Uso

1. Coloca la webcam fija, preferiblemente arriba o con poca inclinación.
2. Usa un balón de color saturado que contraste con el fondo.
3. Evita sombras fuertes y cambios automáticos de iluminación.
4. Ejecuta:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m ojo_halcon --camera 0
```

Controles de la ventana:

- `b`: entrar en modo de muestra del balón; luego haz clic en el centro del balón.
- `l`: entrar en modo de línea; haz clic en sus dos extremos.
- `g`: indicar el interior; haz clic dentro de la zona verde, lejos de la línea.
- `p`: marcar la zona de análisis con cuatro clics consecutivos alrededor del suelo.
- `s`: guardar toda la calibración.
- `r`: borrar solamente la línea marcada.
- `x`: borrar solamente la zona de análisis.
- `m`: mostrar u ocultar la miniatura de la máscara.
- `n`: cancelar la jugada actual y volver a `ESPERANDO JUGADA`.
- `q` o `Esc`: salir.

Los mensajes de confirmación duran cuatro segundos. Después, la barra superior
regresa automáticamente al menú de teclas. Las letras funcionan en mayúscula o
minúscula.

La imagen muestra la máscara en blanco y negro junto a la vista de la cámara.
Una detección buena produce una sola mancha blanca compacta sobre el balón y
un círculo verde estable en la vista principal.

### Zona de análisis

Presiona `p` y marca cuatro puntos en orden alrededor de todo el suelo por el
que puede pasar el balón. Una secuencia recomendada es: exterior izquierda,
exterior derecha, fondo derecha y fondo izquierda. El contorno cian debe incluir
la aproximación, la línea negra y la zona verde, pero excluir muebles y paredes.

El seguimiento muestra una trayectoria celeste. Si falta una detección durante
pocos frames, el círculo se vuelve amarillo y aparece `RECUPERANDO`; si la
pérdida continúa, la pista se descarta.

### Geometría de la línea

Presiona `g`, haz clic dentro del suelo verde y guarda con `s`. El punto magenta
y su flecha indican qué lado de la línea corresponde al interior. La aplicación
clasifica el balón como `ANTES`, `TOCANDO`, `PARCIAL`, `CRUZADO` o
`FUERA DE LOS POSTES`. Esta clasificación geométrica alimenta la máquina de
estados que produce la decisión temporal final.

### Decisión temporal

La máquina de estados muestra `ESPERANDO JUGADA`, `ANALIZANDO`, `GOAL` o
`NO GOAL`. Usa segundos reales, exige varias detecciones completas para un gol
y mantiene el resultado un mínimo de cuatro segundos. Después solicita retirar
el balón antes de aceptar una nueva jugada. `n` permite un reinicio manual.

Para usar otro archivo de configuración:

```powershell
python -m ojo_halcon --config config/mi_escena.json --camera 1
```

## Servidor FastAPI y WebSocket

Si abriste el calibrador manualmente desde una terminal, ciérralo antes de
iniciar el servidor para que ambos no intenten usar la misma webcam. El botón
de `/admin` sí es seguro: el servidor libera y recupera la cámara de forma
automática. Para iniciar FastAPI, ejecuta:

```powershell
cd backend
& .\.venv\Scripts\python.exe -m ojo_halcon.api --camera 1
```

Luego abre <http://127.0.0.1:8000/docs> para probar la API. El estado en tiempo
real se publica en `ws://127.0.0.1:8000/ws`. Las decisiones se conservan en
`backend/data/plays.jsonl`; al reiniciar el servidor, la numeración continúa a
partir de la última jugada guardada. El archivo conserva como máximo las 500
decisiones más recientes para no crecer indefinidamente.

`/api/health` solo devuelve `ok` cuando la cámara entrega frames recientes, la
calibración está completa, la resolución coincide y no existen fallos de
procesamiento o persistencia. Un estado `degraded` incluye el campo concreto
que explica qué falta o qué falló.

Para ejecutar las pruebas automáticas:

```powershell
cd backend
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m pytest -q
```

Consulta [docs/API.md](docs/API.md) para ver todos los endpoints y ejemplos.

## Frontend Vue

Con el backend abierto, inicia otra terminal:

```powershell
cd frontend
pnpm install
pnpm dev
```

Abre el marcador en <http://127.0.0.1:5173/>. El panel administrativo se abre
escribiendo manualmente <http://127.0.0.1:5173/admin>; no existe un enlace hacia
él desde el marcador. Desde allí puedes reiniciar una jugada o abrir el
calibrador. FastAPI libera la cámara, espera que cierres OpenCV con `Q`, recarga
la configuración y reactiva la detección automáticamente.

Pruebas y compilación del frontend:

```powershell
cd frontend
pnpm test
pnpm build
```

## Criterio de validación integral

Para aprobar la demostración completa conviene comprobar:

- detección continua mientras el balón se mueve;
- pocos o ningún falso positivo cuando no hay balón;
- centro y radio razonablemente estables;
- línea visible y bien alineada con la marca física;
- una sola decisión por jugada y sin goles duplicados;
- resultados correctos al cruzar, detenerse, retroceder y salir por un poste;
- cámara inmóvil durante toda la prueba.
- `/api/state` actualizado y eventos recibidos mediante `/ws`;
- una entrada en el historial por cada decisión final;
- espera visual de cuatro segundos antes de revelar el resultado;
- captura y decisión correspondientes al mismo `play_id`;
- calibrador administrado desde `/admin` sin cerrar FastAPI.

Consulta [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) para el diseño completo y
el orden de las siguientes fases.

Las pruebas físicas de esta fase están en
[docs/PRUEBAS_FASE_3.md](docs/PRUEBAS_FASE_3.md).
