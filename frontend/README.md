# Frontend de Ojo de Halcón

Interfaz local Vue para presentar decisiones y administrar la cámara.

## Desarrollo

Primero inicia FastAPI en `127.0.0.1:8000`. Después:

```powershell
cd frontend
pnpm install
pnpm dev
```

- Marcador: <http://127.0.0.1:5173/>
- Administración: <http://127.0.0.1:5173/admin>

La ruta administrativa no tiene autenticación y está pensada únicamente para
uso local. El backend debe conservar su host predeterminado `127.0.0.1`.

Variables opcionales:

```text
VITE_API_BASE=http://127.0.0.1:8000
VITE_WS_URL=ws://127.0.0.1:8000/ws
```

## Verificación

```powershell
pnpm test
pnpm build
```
