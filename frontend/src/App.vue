<script setup>
import { RouterView } from "vue-router";

import studentLogo from "./images/logo-kids.jpg";
</script>

<template>
  <img
    class="global-student-logo"
    :src="studentLogo"
    alt="Los Hackers del Futuro"
  />
  <RouterView />
</template>
