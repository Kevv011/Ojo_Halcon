# Pruebas de geometría de la línea

Esta prueba permite revisar la geometría que utiliza la máquina de estados para
emitir posteriormente `GOAL` o `NO GOAL`.

## Calibrar el lado interior

1. Inicia la aplicación con la cámara y porteria inmóviles.
2. Presiona `g`.
3. Haz clic cerca del centro del suelo verde, lejos de la línea y los postes.
4. Confirma que aparece un punto magenta `INTERIOR` y una flecha desde la línea.
5. Presiona `s` para guardarlo.

La flecha debe apuntar desde la línea hacia el fondo de la porteria. Si apunta
al exterior, repite `g` y selecciona claramente el suelo verde.

## Clasificaciones esperadas

- `ANTES`: ninguna parte del balón ha tocado la línea.
- `TOCANDO`: el borde delantero está dentro de la tolerancia de la línea.
- `PARCIAL`: una parte cruzó, pero el borde posterior todavía no la superó.
- `CRUZADO`: todo el balón está detrás de la línea más la tolerancia.
- `FUERA DE LOS POSTES`: el balón no está completamente entre los postes.

## Prueba estática

Con 8 FPS, empieza colocando el balón manualmente y manteniéndolo quieto dos
segundos en cada caso:

1. completamente antes de la línea;
2. apenas tocando el borde exterior;
3. centrado sobre la línea;
4. casi completamente dentro, pero aún tocando;
5. completamente dentro del suelo verde;
6. cerca del poste izquierdo;
7. cerca del poste derecho.

Observa `distancia`, `borde posterior` y `entre postes`. El borde posterior debe
ser positivo y mayor que la tolerancia para obtener `CRUZADO`.

## Prueba en movimiento

Haz rodar el balón lentamente por el centro. La secuencia normal es:

```text
ANTES -> TOCANDO -> PARCIAL -> CRUZADO
```

A 8 FPS es posible que una categoría intermedia no aparezca en un lanzamiento;
por eso la validación principal se realiza primero con posiciones estáticas.

## Ajustes

- Si declara `CRUZADO` demasiado pronto, aumenta `line_tolerance_px`.
- Si tarda demasiado en declarar `CRUZADO`, reduce ligeramente la tolerancia.
- Si siempre muestra `FUERA DE LOS POSTES`, comprueba los extremos de la línea y el
  radio detectado.
- Si el orden aparece invertido, vuelve a marcar el punto interior con `g`.

El valor inicial de tolerancia es 3 píxeles. No lo ajustes antes de completar
las posiciones estáticas.
