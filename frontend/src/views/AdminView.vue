<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { useOjoHalcon } from "../composables/useOjoHalcon.js";
import {
  getCalibrationStatus,
  getPlays,
  liveSnapshotUrl,
  resetPlay,
  startCalibration,
} from "../services/api.js";

const { systemState, health, connection, refreshHealth, refreshState } = useOjoHalcon();
const calibration = ref(null);
const plays = ref([]);
const actionError = ref("");
const actionMessage = ref("");
const previewUrl = ref(liveSnapshotUrl());
const working = ref(false);
let statusTimer = null;
let previewTimer = null;
let playsTimer = null;

const calibrationActive = computed(() => calibration.value?.active === true);
const healthLabel = computed(() => {
  if (calibrationActive.value) return "Calibrando";
  return health.value?.status === "ok" ? "Operativo" : "Revisar sistema";
});

async function refreshCalibration() {
  try {
    calibration.value = await getCalibrationStatus();
    if (calibration.value.error) {
      actionMessage.value = "";
      actionError.value = calibration.value.error;
    }
  } catch (error) {
    actionError.value = error.message;
  }
}

async function refreshPlays() {
  try {
    const response = await getPlays(10);
    plays.value = response.plays;
  } catch (error) {
    actionError.value = error.message;
  }
}

async function openCalibration() {
  working.value = true;
  actionError.value = "";
  actionMessage.value = "";
  try {
    calibration.value = await startCalibration();
    actionMessage.value = "Liberando la cámara. La ventana aparecerá en unos segundos.";
  } catch (error) {
    actionError.value = error.message;
  } finally {
    working.value = false;
  }
}

async function resetCurrentPlay() {
  working.value = true;
  actionError.value = "";
  try {
    const response = await resetPlay();
    actionMessage.value = response.message;
    await refreshState();
  } catch (error) {
    actionError.value = error.message;
  } finally {
    working.value = false;
  }
}

function formatDate(value) {
  return new Intl.DateTimeFormat("es-SV", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

onMounted(() => {
  refreshCalibration();
  refreshPlays();
  statusTimer = window.setInterval(async () => {
    await refreshCalibration();
    await refreshHealth();
  }, 1000);
  previewTimer = window.setInterval(() => {
    if (!calibrationActive.value) previewUrl.value = liveSnapshotUrl();
  }, 1000);
  playsTimer = window.setInterval(refreshPlays, 5000);
});

onBeforeUnmount(() => {
  window.clearInterval(statusTimer);
  window.clearInterval(previewTimer);
  window.clearInterval(playsTimer);
});
</script>

<template>
  <main class="admin-shell">
    <header class="admin-header">
      <div>
        <p class="eyebrow">Panel local</p>
        <h1>Administración</h1>
        <p>Control de cámara, calibración y jugadas.</p>
      </div>
      <RouterLink class="secondary-button" to="/">Ver marcador</RouterLink>
    </header>

    <div v-if="actionError" class="alert alert--error">{{ actionError }}</div>
    <div v-if="actionMessage" class="alert">{{ actionMessage }}</div>

    <section class="status-grid">
      <article class="status-card">
        <span>Estado</span>
        <strong>{{ healthLabel }}</strong>
        <small>WebSocket: {{ connection }}</small>
      </article>
      <article class="status-card">
        <span>Cámara</span>
        <strong>{{ health?.camera_connected ? "Conectada" : "Desconectada" }}</strong>
        <small>{{ systemState?.camera?.fps?.toFixed(1) || "0.0" }} FPS</small>
      </article>
      <article class="status-card">
        <span>Calibración</span>
        <strong>{{ health?.calibration_ready ? "Completa" : "Incompleta" }}</strong>
        <small>
          {{
            health?.resolution_matches == null
              ? "Sin lectura"
              : health.resolution_matches
                ? "Resolución correcta"
                : "Resolución diferente"
          }}
        </small>
      </article>
      <article class="status-card">
        <span>Detección</span>
        <strong>{{ systemState?.detection?.status || "Sin datos" }}</strong>
        <small>{{ systemState?.game?.state || "Iniciando" }}</small>
      </article>
    </section>

    <section class="admin-grid">
      <article class="panel calibration-panel">
        <div class="panel__heading">
          <div>
            <p class="eyebrow">Herramientas</p>
            <h2>Calibración de cámara</h2>
          </div>
          <span class="state-badge" :class="{ active: calibrationActive }">
            {{ calibration?.status || "consultando" }}
          </span>
        </div>

        <p>{{ calibration?.message || "Consultando el estado del calibrador..." }}</p>
        <p v-if="calibrationActive" class="instruction">
          Guarda los cambios con <kbd>S</kbd> y cierra la ventana con <kbd>Q</kbd>.
        </p>
        <p v-if="calibration?.error" class="field-error">{{ calibration.error }}</p>

        <div class="button-row">
          <button
            class="primary-button"
            :disabled="working || calibrationActive"
            @click="openCalibration"
          >
            {{ calibrationActive ? "Calibrador abierto" : "Abrir calibración" }}
          </button>
          <button class="secondary-button" :disabled="working" @click="resetCurrentPlay">
            Reiniciar jugada
          </button>
        </div>
      </article>

      <article class="panel preview-panel">
        <div class="panel__heading">
          <div>
            <p class="eyebrow">Vista actual</p>
            <h2>Cámara</h2>
          </div>
        </div>
        <div class="camera-preview">
          <img
            v-if="health?.camera_connected && !calibrationActive"
            :src="previewUrl"
            alt="Vista procesada de la cámara"
          />
          <div v-else class="camera-preview__empty">
            {{ calibrationActive ? "La cámara está siendo calibrada" : "Esperando imagen de la cámara" }}
          </div>
        </div>
      </article>
    </section>

    <section class="panel history-panel">
      <div class="panel__heading">
        <div>
          <p class="eyebrow">Registro</p>
          <h2>Jugadas recientes</h2>
        </div>
        <button class="text-button" @click="refreshPlays">Actualizar</button>
      </div>

      <div v-if="plays.length" class="history-list">
        <article v-for="play in plays" :key="`${play.play_id}-${play.result}`" class="history-item">
          <span class="history-item__id">#{{ play.play_id }}</span>
          <strong :class="play.result === 'GOAL' ? 'text-goal' : 'text-no-goal'">
            {{ play.result }}
          </strong>
          <span>{{ play.reason }}</span>
          <time>{{ formatDate(play.decided_at) }}</time>
        </article>
      </div>
      <p v-else class="empty-copy">Todavía no hay decisiones guardadas.</p>
    </section>
  </main>
</template>
