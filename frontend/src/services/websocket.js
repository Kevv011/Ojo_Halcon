export function createStateSocket(url, handlers = {}) {
  let socket = null;
  let closed = false;
  let reconnectTimer = null;
  let retryMilliseconds = 750;

  function connect() {
    if (closed) return;
    handlers.onStatus?.("connecting");
    socket = new WebSocket(url);

    socket.addEventListener("open", () => {
      retryMilliseconds = 750;
      handlers.onStatus?.("connected");
    });

    socket.addEventListener("message", (event) => {
      try {
        handlers.onMessage?.(JSON.parse(event.data));
      } catch {
        handlers.onError?.("El backend envió un mensaje inválido");
      }
    });

    socket.addEventListener("error", () => {
      handlers.onError?.("No se pudo mantener la conexión en tiempo real");
    });

    socket.addEventListener("close", () => {
      handlers.onStatus?.("disconnected");
      if (closed) return;
      reconnectTimer = window.setTimeout(connect, retryMilliseconds);
      retryMilliseconds = Math.min(retryMilliseconds * 1.7, 5000);
    });
  }

  connect();

  return () => {
    closed = true;
    window.clearTimeout(reconnectTimer);
    socket?.close();
  };
}
