# Pruebas físicas de la fase 3

Estas pruebas validan la decisión temporal antes de conectar el sistema con
Vue. La máquina puede trabajar con los aproximadamente 8 FPS de la webcam porque
los umbrales usan segundos reales.

## Preparación

1. Deja fija la cámara y la portería en la posición usada al calibrar.
2. Ejecuta la aplicación y comprueba que aparecen la línea amarilla, el punto
   magenta interior y la zona cian.
3. Retira el balón. El panel inferior debe indicar `ESPERANDO JUGADA`.
4. Si quedó una jugada anterior activa, presiona `n` para reiniciarla.

Haz cada caso al menos cinco veces. Con 8 FPS, mueve el balón de forma moderada
y, al probar un gol, déjalo completamente dentro durante al menos 0.3 segundos.

## Casos esperados

### 1. Gol válido

Mueve el balón desde fuera, entre los postes, hasta que cruce completamente la
línea. Debe verse:

```text
ESPERANDO JUGADA -> ANALIZANDO -> GOAL
```

El resultado debe mantenerse al menos cuatro segundos. No debe contar otro gol
mientras el balón siga dentro. Después retíralo; el sistema debe volver a
`ESPERANDO JUGADA`.

### 2. Balón detenido antes de cruzar

Acerca el balón a la línea y déjalo inmóvil sin cruzarla completamente. Después
de aproximadamente un segundo debe aparecer `NO GOAL` con la razón `Balon
detenido sin cruzar`.

### 3. Balón parcial sobre la línea

Deja una parte del balón sobre la línea, pero mantén otra parte fuera. La
geometría puede mostrar `PARCIAL`; después de detenerse debe terminar en
`NO GOAL`, no en `GOAL`.

### 4. Balón que retrocede

Haz que el balón toque o invada parcialmente la línea y luego retíralo hacia el
exterior. Debe aparecer `NO GOAL` con la razón `Balon retrocedio sin cruzar`.

### 5. Paso por fuera de los postes

Mueve el balón hacia la línea, pero haz que la cruce por fuera de uno de los
extremos. Debe aparecer `NO GOAL` con la razón `Cruzo por fuera de los postes`.

### 6. Pérdida de detección

Mientras el panel muestre `ANALIZANDO`, tapa el balón o sácalo rápidamente de la
zona cian durante más de medio segundo. Debe aparecer `NO GOAL` con la razón
`Balon perdido antes del cruce`.

### 7. Rearme y reinicio manual

Después de cualquier resultado, deja el balón visible: el panel debe pedir
`Retira el balon para continuar`. Al retirarlo debe rearmarse. También verifica
que la tecla `n` cancele cualquier jugada y vuelva inmediatamente a
`ESPERANDO JUGADA`.

## Qué registrar

Para cada intento anota: caso probado, resultado esperado, resultado obtenido y
si la detección fue estable. Si un fallo ocurre por máscara inestable, primero se
ajusta detección; si la geometría es correcta pero falla el resultado, se ajustan
los parámetros `game` de `backend/config/default.json`.
