import { readonly, ref } from "vue";

import { getHealth, getState, websocketUrl } from "../services/api.js";
import { createStateSocket } from "../services/websocket.js";

const systemState = ref(null);
const health = ref(null);
const connection = ref("connecting");
const error = ref("");
let started = false;
let healthTimer = null;

async function refreshHealth() {
  try {
    health.value = await getHealth();
    if (health.value.status === "ok") error.value = "";
  } catch (requestError) {
    health.value = null;
    error.value = requestError.message;
  }
}

async function refreshState() {
  try {
    systemState.value = await getState();
  } catch (requestError) {
    error.value = requestError.message;
  }
}

function connect() {
  if (started) return;
  started = true;
  refreshHealth();
  refreshState();
  healthTimer = window.setInterval(refreshHealth, 2000);
  createStateSocket(websocketUrl(), {
    onStatus: (status) => {
      connection.value = status;
      if (status === "connected") error.value = "";
    },
    onMessage: (message) => {
      systemState.value = message;
    },
    onError: (message) => {
      error.value = message;
    },
  });
}

export function useOjoHalcon() {
  connect();
  return {
    systemState: readonly(systemState),
    health: readonly(health),
    connection: readonly(connection),
    error: readonly(error),
    refreshHealth,
    refreshState,
  };
}
