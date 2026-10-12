<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";

import { useOjoHalcon } from "../composables/useOjoHalcon.js";
import cameraImage from "../images/camera.png";
import goalImage from "../images/goal.png";
import noGoalImage from "../images/no-goal.png";
import refereeImage from "../images/referee.png";
import startButtonImage from "../images/start-btn.png";
import { GamePresentationController } from "../logic/gamePresentation.js";
import { resetPlay, resultSnapshotUrl } from "../services/api.js";

const { systemState, health, connection } = useOjoHalcon();
const imageFailed = ref(false);
const gameStarted = ref(false);
const starting = ref(false);
const startError = ref("");
const presentation = reactive({
  phase: "ready",
  playId: 0,
  result: null,
  reason: "",
});

const controller = new GamePresentationController({
  onChange: (next) => {
    if (next.playId !== presentation.playId) imageFailed.value = false;
    Object.assign(presentation, next);
    if (next.phase === "result") gameStarted.value = false;
  },
});

watch(
  systemState,
  (value) => {
    if (gameStarted.value) controller.handle(value);
  },
  { immediate: true },
);

onBeforeUnmount(() => controller.dispose());

const calibrating = computed(
  () => systemState.value?.service_mode === "calibrating",
);
const connected = computed(
  () => connection.value === "connected" && health.value?.camera_connected,
);
const realtimeConnected = computed(() => connection.value === "connected");
const connectionLabel = computed(() => {
  if (!realtimeConnected.value) return "Sin conexión";
  if (!health.value?.camera_connected) return "Cámara no disponible";
  return `Cámara activa · ${fps.value} FPS`;
});
const resultIsGoal = computed(() => presentation.result === "GOAL");
const resultImage = computed(() => resultSnapshotUrl(presentation.playId));
const decisionImage = computed(() => (resultIsGoal.value ? goalImage : noGoalImage));
const fps = computed(() => systemState.value?.camera?.fps?.toFixed(1) || "—");

async function startGame() {
  if (!connected.value) {
    startError.value = "La cámara debe estar conectada antes de iniciar.";
    return;
  }

  starting.value = true;
  startError.value = "";
  try {
    await resetPlay();
    controller.reset();
    gameStarted.value = true;
  } catch (error) {
    startError.value = error.message;
  } finally {
    starting.value = false;
  }
}
</script>

<template>
  <main
    class="scoreboard"
    :class="{
      'is-goal': resultIsGoal,
      'is-no-goal': presentation.result === 'NO GOAL',
    }"
  >
    <header class="scoreboard__header">
      <div class="brand">
        <span class="brand__mark" aria-hidden="true">◎</span>
        <div>
          <p class="eyebrow">Sistema de decisión</p>
          <h1>Ojo de Halcón</h1>
        </div>
      </div>
      <div
        class="connection-pill"
        :class="{ online: connected, warning: realtimeConnected && !connected }"
      >
        <span class="connection-pill__dot"></span>
        {{ connectionLabel }}
      </div>
    </header>

    <section v-if="calibrating" class="stage stage--notice" aria-live="polite">
      <div class="radar-loader" aria-hidden="true"></div>
      <p class="eyebrow">Mantenimiento</p>
      <h2>Calibración en curso</h2>
      <p>La detección continuará cuando se cierre la ventana con Q.</p>
    </section>

    <section v-else-if="presentation.phase === 'ready'" class="stage" aria-live="polite">
      <template v-if="!gameStarted">
        <p class="eyebrow">Sistema preparado</p>
        <h2>Ojo de Halcón</h2>
        <button
          class="start-image-button"
          :disabled="starting || !connected"
          type="button"
          @click="startGame"
        >
          <img :src="startButtonImage" alt="Iniciar jugada" />
        </button>
        <p v-if="startError" class="stage-error">{{ startError }}</p>
        <p v-else>
          {{ connected ? "Presiona iniciar para preparar la jugada." : "Esperando conexión con la cámara." }}
        </p>
      </template>
      <template v-else>
        <div class="ready-signal" aria-hidden="true"><span></span></div>
        <p class="eyebrow">Jugada preparada</p>
        <h2>¡Adelante!</h2>
        <p>Realiza el tiro. El análisis comenzará automáticamente.</p>
      </template>
    </section>

    <section
      v-else-if="presentation.phase === 'waiting' || presentation.phase === 'confirming'"
      class="stage stage--waiting"
      aria-live="assertive"
    >
      <img class="state-art state-art--camera" :src="cameraImage" alt="Cámara analizando la jugada" />
      <p class="eyebrow">Jugada {{ presentation.playId }}</p>
      <h2>
        {{ presentation.phase === "waiting" ? "Esperando resultado..." : "Confirmando resultado..." }}
      </h2>
      <p>El sistema está analizando el cruce completo del balón.</p>
      <div v-if="presentation.phase === 'waiting'" class="wait-track" aria-hidden="true">
        <span></span>
      </div>
    </section>

    <section v-else class="result-layout" aria-live="assertive">
      <div class="result-referee">
        <img :src="refereeImage" alt="Árbitro señalando la decisión" />
      </div>

      <div class="result-decision">
        <figure class="result-frame">
          <img
            v-if="!imageFailed"
            :src="resultImage"
            :alt="`Captura ampliada de la jugada ${presentation.playId}`"
            @error="imageFailed = true"
          />
          <div v-else class="result-frame__fallback">
            <span aria-hidden="true">◉</span>
            <p>La decisión fue recibida, pero la captura ya no está disponible.</p>
          </div>
          <figcaption>
            Evidencia de la jugada · Captura tomada al confirmar la decisión
          </figcaption>
        </figure>

        <aside class="result-summary">
          <img
            class="decision-art"
            :src="decisionImage"
            :alt="resultIsGoal ? 'Decisión: gol' : 'Decisión: no es gol'"
          />
          <div class="result-copy">
            <p class="eyebrow">Jugada {{ presentation.playId }}</p>
            <h2>{{ resultIsGoal ? "¡GOAL!" : "NO GOAL" }}</h2>
            <p>{{ presentation.reason }}</p>
            <button
              class="start-image-button start-image-button--compact"
              :disabled="starting || !connected"
              type="button"
              @click="startGame"
            >
              <img :src="startButtonImage" alt="Iniciar una nueva jugada" />
            </button>
            <p v-if="startError" class="stage-error">{{ startError }}</p>
          </div>
        </aside>
      </div>
    </section>

    <footer class="scoreboard__footer">
      <span>Decisión asistida por visión por computadora</span>
      <span v-if="systemState?.detection">{{ systemState.detection.status }}</span>
    </footer>
  </main>
</template>
