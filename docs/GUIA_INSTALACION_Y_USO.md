# Guía de instalación y uso

Esta guía explica cómo preparar y ejecutar **Ojo de Halcón escolar** en Windows.
Está escrita para una persona sin experiencia previa en Python, Vue u OpenCV.

## 1. Recursos físicos

Antes de instalar programas, prepara:

1. Una computadora con Windows 10 u 11 de 64 bits.
2. Una webcam USB compatible con Windows.
3. Un trípode o soporte que mantenga la webcam completamente inmóvil.
4. La portería, su línea negra y la superficie que representa la zona de gol.
5. Un balón de color uniforme y con buen contraste respecto al suelo.
6. Iluminación estable, sin sombras fuertes ni cambios durante las jugadas.

La cámara, la portería y la iluminación no deben moverse después de calibrar.

## 2. Programas que se deben instalar

Instala los siguientes programas:

1. **[Python 3.14 de 64 bits](https://www.python.org/downloads/windows/)**.
   El proyecto fue validado con Python 3.14.7.
2. **[Node.js 24 LTS](https://nodejs.org/en/download)**, que también instala
   `npm`.
3. **[pnpm 11.25.0](https://pnpm.io/installation/)**, utilizando `npm` después
   de instalar Node.js.
4. Un navegador moderno, preferiblemente Google Chrome o Microsoft Edge.
5. Visual Studio Code es opcional, pero facilita la apertura de terminales.

Después de instalar Python y Node.js, cierra y vuelve a abrir Visual Studio Code
o PowerShell para que Windows actualice las rutas de los comandos.

## 3. Comprobar las instalaciones

Abre PowerShell y ejecuta:

```powershell
py --version
node --version
npm --version
```

Los tres comandos deben mostrar una versión y no un mensaje de error.

Instala la versión de pnpm usada para validar el proyecto:

```powershell
npm install --global pnpm@11.25.0
pnpm --version
```

El último comando debe mostrar `11.25.0`.

## 4. Copiar el proyecto

1. Copia o descomprime la carpeta completa `Ojo_Halcon`.
2. Colócala en una ruta fácil de localizar, por ejemplo:

```text
C:\Proyectos\Ojo_Halcon
```

No copies un entorno `.venv` creado en otra computadora. Tampoco es necesario
entregar `frontend/node_modules` ni `frontend/dist`, porque se regeneran durante
la instalación.

## 5. Preparar el backend

Abre PowerShell dentro de la carpeta del proyecto y ejecuta, una línea a la vez:

```powershell
cd C:\Proyectos\Ojo_Halcon\backend
py -3.14 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Este proceso instala:

- OpenCV para cámara, detección y dibujo;
- NumPy para operaciones con imágenes;
- FastAPI para la API local;
- Uvicorn para ejecutar el servidor;
- WebSockets para actualizaciones en tiempo real;
- pytest y httpx2 para las pruebas automáticas.

La instalación inicial requiere conexión a Internet.

## 6. Preparar el frontend

En otra terminal de PowerShell ejecuta:

```powershell
cd C:\Proyectos\Ojo_Halcon\frontend
pnpm install --frozen-lockfile
```

Este proceso instala Vue 3, Vue Router, Vite y Vitest. También requiere conexión
a Internet la primera vez.

## 7. Preparar la webcam

1. Conecta la webcam antes de iniciar el backend.
2. Comprueba la imagen con la aplicación Cámara de Windows.
3. Cierra completamente Cámara, Teams, Zoom y cualquier programa que pueda usarla.
4. Coloca la webcam en su posición definitiva.

Windows asigna un índice numérico a cada cámara. En este proyecto normalmente se
usa `--camera 1`. Si no abre, prueba `--camera 0`.

## 8. Iniciar el backend

Abre la primera terminal y ejecuta:

```powershell
cd C:\Proyectos\Ojo_Halcon\backend
& .\.venv\Scripts\python.exe -m ojo_halcon.api --camera 1
```

Si aparece `No se pudo abrir la webcam 1`, detén el comando con `Ctrl+C` y prueba:

```powershell
& .\.venv\Scripts\python.exe -m ojo_halcon.api --camera 0
```

Deja esta terminal abierta. El mismo proceso inicia:

- API: `http://127.0.0.1:8000`;
- salud: `http://127.0.0.1:8000/api/health`;
- documentación: `http://127.0.0.1:8000/docs`;
- WebSocket: `ws://127.0.0.1:8000/ws`.

No se necesita una terminal adicional para el WebSocket.

## 9. Iniciar el frontend

Abre una segunda terminal y ejecuta:

```powershell
cd C:\Proyectos\Ojo_Halcon\frontend
pnpm dev
```

Deja también esta terminal abierta. Después abre en el navegador:

- marcador: `http://127.0.0.1:5173/`;
- administración: `http://127.0.0.1:5173/admin`.

La dirección `/admin` se escribe manualmente y no requiere usuario o contraseña.

## 10. Calibrar por primera vez

1. Abre `http://127.0.0.1:5173/admin`.
2. Presiona **Abrir calibración**.
3. Espera a que aparezca la ventana de OpenCV.
4. Usa las teclas siguientes:

   - `B`: seleccionar el color del balón y hacer clic en su centro.
   - `L`: marcar los dos extremos de la línea de gol.
   - `G`: marcar un punto dentro de la portería.
   - `P`: marcar cuatro puntos de la zona de análisis.
   - `M`: mostrar u ocultar la máscara de color.
   - `N`: reiniciar la jugada actual.
   - `S`: guardar la calibración.
   - `Q` o `Esc`: cerrar el calibrador.

5. Antes de guardar, comprueba que:

   - el balón tenga un círculo estable;
   - la máscara muestre una mancha blanca compacta sobre el balón;
   - la línea amarilla coincida con la línea física;
   - el punto `INTERIOR` esté detrás de la línea;
   - el contorno cian incluya todo el recorrido del balón;
   - un balón dentro de la boca indique `entre postes=SI`.

6. Presiona `S` y luego `Q`.
7. El backend recuperará la cámara y continuará automáticamente.

La calibración queda guardada en `backend/config/default.json`. Si se mueve la
cámara, la portería o la iluminación cambia significativamente, debe calibrarse
de nuevo.

## 11. Probar una jugada

1. Abre `http://127.0.0.1:5173/`.
2. Confirma que aparezca **Cámara activa**.
3. Presiona la imagen **INICIAR**.
4. Coloca el balón completamente antes de la línea.
5. Hazlo avanzar hacia la portería.
6. Espera cuatro segundos mientras aparece la cámara de análisis.
7. Comprueba que aparezca `GOAL` o `NO GOAL` junto con la evidencia ampliada.
8. Retira completamente el balón antes de iniciar otra jugada.

Prueba al menos estos casos:

1. El balón cruza completamente entre los postes: debe producir `GOAL`.
2. El balón queda tocando o parcialmente sobre la línea: debe producir `NO GOAL`.
3. El balón se detiene antes de la línea: debe producir `NO GOAL`.
4. El balón cruza por fuera de un poste: debe producir `NO GOAL`.
5. El balón se aproxima y retrocede: debe producir `NO GOAL`.

## 12. Detener el sistema

1. Ve a la terminal del frontend y presiona `Ctrl+C`.
2. Ve a la terminal del backend y presiona `Ctrl+C`.
3. Espera a que ambos comandos regresen al indicador de PowerShell.
4. Después puedes desconectar la webcam.

## 13. Ejecutar las pruebas automáticas

Backend:

```powershell
cd C:\Proyectos\Ojo_Halcon\backend
& .\.venv\Scripts\python.exe -m pytest -q
```

Frontend:

```powershell
cd C:\Proyectos\Ojo_Halcon\frontend
pnpm test
pnpm build
```

## 14. Archivos importantes

- `backend/config/default.json`: calibración activa.
- `backend/data/plays.jsonl`: historial de decisiones.
- `backend/requirements.txt`: librerías necesarias para ejecutar el backend.
- `backend/requirements-dev.txt`: librerías de ejecución y pruebas.
- `frontend/package.json`: tecnologías y comandos del frontend.
- `frontend/pnpm-lock.yaml`: versiones reproducibles de las dependencias.
- `docs/API.md`: endpoints HTTP y WebSocket.

Haz una copia de seguridad de `backend/config/default.json` cuando la calibración
funcione correctamente.

## 15. Errores frecuentes

### `py` o `python` no se reconoce

Instala Python de 64 bits, cierra todas las terminales y vuelve a abrirlas.

### `pnpm` no se reconoce

Ejecuta:

```powershell
npm install --global pnpm@11.25.0
```

Después cierra y vuelve a abrir Visual Studio Code.

### La página indica que rechazó la conexión

El servicio correspondiente no está ejecutándose. Comprueba que el backend siga
abierto para el puerto 8000 y el frontend para el puerto 5173.

### No se puede abrir la cámara

1. Cierra Cámara, Teams, Zoom y navegadores que estén usando la webcam.
2. Prueba primero `--camera 1` y después `--camera 0`.
3. Desconecta y vuelve a conectar la webcam.
4. Comprueba los permisos de cámara de Windows.

### El puerto ya está en uso

Probablemente quedó otra instancia abierta. Busca la terminal anterior y
presiona `Ctrl+C` antes de volver a ejecutar el comando.

### El balón aparece como `SIN BALÓN`

Revisa iluminación, sombras, contraste, máscara y calibración HSV. Evita que el
balón tenga el mismo color que el suelo.

### Aparece `FUERA DE LOS POSTES` cuando está dentro

Verifica los extremos marcados con `L`. Extiende solamente unos pocos píxeles
los dos extremos siguiendo la misma dirección de la línea, guarda con `S` y
vuelve a probar.

## 16. Tecnologías utilizadas

Backend:

- Python 3.14;
- OpenCV 4.14;
- NumPy 2.5;
- FastAPI;
- Uvicorn;
- HTTP, JSON y WebSocket;
- archivo JSONL para historial, sin base de datos externa.

Frontend:

- Vue 3;
- Vue Router;
- Vite 8;
- JavaScript;
- HTML y CSS;
- pnpm como administrador de dependencias.

No se requiere Docker, una base de datos, una cuenta en la nube ni conexión a
Internet después de instalar las dependencias. El backend, frontend, WebSocket y
webcam funcionan localmente en la misma computadora.
