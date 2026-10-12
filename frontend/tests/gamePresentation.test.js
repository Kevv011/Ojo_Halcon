import { describe, expect, it } from "vitest";

import { GamePresentationController } from "../src/logic/gamePresentation.js";

function game(state, playId = 1, reason = "") {
  return { game: { state, play_id: playId, reason } };
}

describe("GamePresentationController", () => {
  it("waits four seconds before revealing a received result", () => {
    let finishWaiting;
    const controller = new GamePresentationController({
      schedule: (callback) => {
        finishWaiting = callback;
        return 1;
      },
      cancel: () => {},
    });

    controller.handle(game("ANALIZANDO", 3));
    controller.handle(game("GOAL", 3, "Cruce completo confirmado"));

    expect(controller.snapshot().phase).toBe("waiting");
    finishWaiting();
    expect(controller.snapshot()).toMatchObject({
      phase: "result",
      playId: 3,
      result: "GOAL",
    });
  });

  it("keeps confirming when the timer ends before the decision", () => {
    let finishWaiting;
    const controller = new GamePresentationController({
      schedule: (callback) => {
        finishWaiting = callback;
        return 1;
      },
      cancel: () => {},
    });

    controller.handle(game("ANALIZANDO", 8));
    finishWaiting();
    expect(controller.snapshot().phase).toBe("confirming");

    controller.handle(game("NO GOAL", 8, "Balón detenido"));
    expect(controller.snapshot()).toMatchObject({
      phase: "result",
      result: "NO GOAL",
      reason: "Balón detenido",
    });
  });

  it("keeps the result until a different play begins", () => {
    let finishWaiting;
    const controller = new GamePresentationController({
      schedule: (callback) => {
        finishWaiting = callback;
        return 1;
      },
      cancel: () => {},
    });

    controller.handle(game("ANALIZANDO", 1));
    controller.handle(game("GOAL", 1));
    finishWaiting();
    controller.handle(game("ESPERANDO JUGADA", 1));
    expect(controller.snapshot().phase).toBe("result");

    controller.handle(game("ANALIZANDO", 2));
    expect(controller.snapshot()).toMatchObject({ phase: "waiting", playId: 2 });
  });

  it("returns to ready when a new play is started manually", () => {
    let finishWaiting;
    const controller = new GamePresentationController({
      schedule: (callback) => {
        finishWaiting = callback;
        return 1;
      },
      cancel: () => {},
    });

    controller.handle(game("ANALIZANDO", 4));
    controller.handle(game("GOAL", 4));
    finishWaiting();
    controller.reset();

    expect(controller.snapshot()).toEqual({
      phase: "ready",
      playId: 4,
      result: null,
      reason: "",
    });
  });
});
