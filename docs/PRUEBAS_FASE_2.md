# Pruebas de zona y seguimiento

## 1. Confirmar la calibración existente

Inicia la aplicación y confirma que la línea amarilla y el color del balón se
cargan sin volver a presionar `b` o `l`.

## 2. Marcar la zona de análisis

Presiona `p` y realiza cuatro clics consecutivos, siempre alrededor del suelo y
en orden, sin cruzar lados:

1. esquina exterior izquierda de la zona de aproximación;
2. esquina exterior derecha de la zona de aproximación;
3. esquina derecha del fondo de la zona verde;
4. esquina izquierda del fondo de la zona verde.

El polígono cian debe incluir toda posición posible del balón, incluida la línea,
pero excluir paredes, estantes y objetos del fondo. Presiona `s` para guardarlo.
Si queda mal, presiona `x` y repite.

## 3. Prueba sin balón

Retira el balón durante 30 segundos. Debe mostrarse `SIN BALON` y no debe
aparecer ningún círculo dentro de la zona.

## 4. Prueba estática

Deja el balón durante tres segundos en cada punto:

- exterior cercano y exterior lejano;
- antes, sobre y después de la línea;
- centro y fondo de la zona verde;
- zonas iluminada y sombreada;
- cerca de ambos postes.

El centro y el radio deben estabilizarse. Una oscilación pequeña es normal.

## 5. Prueba de trayectoria

Haz rodar el balón lentamente diez veces por el centro y cinco veces por cada
lado. La línea celeste debe seguir una ruta continua, sin saltar hacia el fondo.

## 6. Prueba de pérdida breve

Pasa una mano rápidamente frente al balón o cúbrelo durante uno o dos frames. El
círculo debe cambiar momentáneamente a amarillo con `RECUPERANDO` y volver a
verde cuando reaparece. Si permanece oculto, la pista debe desaparecer tras
tres frames para no inventar una posición.

## 7. Prueba de rendimiento

Observa `FPS` durante el movimiento. El objetivo es mantener al menos 20 FPS y,
preferiblemente, cerca de 30 FPS. Cierra otras aplicaciones que usen la cámara
o consuman muchos recursos si el valor es menor.

## Criterio para avanzar

La fase se considera aprobada si:

- no hay falsos positivos durante 30 segundos sin balón;
- al menos 18 de 20 recorridos mantienen una pista utilizable;
- una pérdida de hasta tres frames no provoca un salto a otro objeto;
- la trayectoria sigue al balón y permanece dentro del polígono;
- el procesamiento se mantiene en 20 FPS o más.
