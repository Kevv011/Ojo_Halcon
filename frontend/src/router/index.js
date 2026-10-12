import { createRouter, createWebHistory } from "vue-router";

import AdminView from "../views/AdminView.vue";
import ScoreboardView from "../views/ScoreboardView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "scoreboard",
      component: ScoreboardView,
    },
    {
      path: "/admin",
      name: "admin",
      component: AdminView,
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/",
    },
  ],
});

export default router;
