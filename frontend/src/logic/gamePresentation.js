export class GamePresentationController {
  constructor({ delay = 4000, onChange = () => {}, schedule, cancel } = {}) {
    this.delay = delay;
    this.onChange = onChange;
    this.schedule = schedule || ((callback, milliseconds) => setTimeout(callback, milliseconds));
    this.cancel = cancel || ((timer) => clearTimeout(timer));
    this.timer = null;
    this.pendingResult = null;
    this.presentation = {
      phase: "ready",
      playId: 0,
      result: null,
      reason: "",
    };
  }

  handle(systemState) {
    const game = systemState?.game;
    if (!game) return;

    if (game.state === "ANALIZANDO") {
      if (game.play_id !== this.presentation.playId || this.presentation.phase === "ready") {
        this.begin(game.play_id);
      }
      return;
    }

    if (game.state === "GOAL" || game.state === "NO GOAL") {
      if (game.play_id !== this.presentation.playId) this.begin(game.play_id);
      this.pendingResult = {
        result: game.state,
        reason: game.reason,
      };
      if (this.presentation.phase === "confirming") this.reveal();
    }
  }

  begin(playId) {
    this.cancel(this.timer);
    this.pendingResult = null;
    this.presentation = {
      phase: "waiting",
      playId,
      result: null,
      reason: "",
    };
    this.emit();
    this.timer = this.schedule(() => {
      this.timer = null;
      if (this.pendingResult) {
        this.reveal();
      } else {
        this.presentation = {
          ...this.presentation,
          phase: "confirming",
        };
        this.emit();
      }
    }, this.delay);
  }

  reveal() {
    if (!this.pendingResult) return;
    this.presentation = {
      ...this.presentation,
      phase: "result",
      ...this.pendingResult,
    };
    this.emit();
  }

  reset() {
    this.cancel(this.timer);
    this.timer = null;
    this.pendingResult = null;
    this.presentation = {
      phase: "ready",
      playId: this.presentation.playId,
      result: null,
      reason: "",
    };
    this.emit();
  }

  snapshot() {
    return { ...this.presentation };
  }

  dispose() {
    this.cancel(this.timer);
  }

  emit() {
    this.onChange(this.snapshot());
  }
}
