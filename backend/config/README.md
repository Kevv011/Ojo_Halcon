# Parámetros de configuración

JSON no admite comentarios, por eso los parámetros importantes se explican
aquí y junto a sus definiciones en `ojo_halcon/config.py`.

Al cargar o guardar, el programa valida rangos HSV, tamaños, factores de
suavizado y coordenadas. El backend no inicia con un archivo ausente o inválido;
el calibrador sí puede crear uno nuevo y lo escribe de forma atómica.

## `camera`

- `width`, `height`: resolución solicitada; cambiarla invalida coordenadas ya calibradas.
- `fps`: velocidad solicitada a la webcam; la velocidad real puede ser menor.
- `use_mjpg`: solicita video comprimido para reducir carga USB y mejorar FPS.
- `buffer_size`: cantidad de frames pendientes; `1` reduce retraso.

## `ball`

- `hsv_lower`, `hsv_upper`: rango de color aceptado para el balón.
- `min_area`, `max_area`: tamaño permitido del contorno.
- `morphology_kernel`: fuerza de limpieza de ruido en la máscara.
- `min_circularity`: forma mínima aceptada; `1` sería un círculo ideal.

## Geometría

- `goal_line`: dos puntos que representan el borde posterior de la línea.
- `goal_side_point`: un punto dentro del área verde que define el lado de gol.
- `roi`: cuatro puntos que limitan dónde se busca el balón; no decide el gol.

## `geometry`

- `line_tolerance_px`: margen alrededor de la línea para absorber ruido.
- `post_margin_px`: separación extra exigida junto a los postes.

## `tracking`

- `smoothing_alpha`: respuesta del centro y radio; menor produce más suavizado.
- `velocity_alpha`: suavizado de la velocidad.
- `max_lost_frames`: frames que se mantiene la pista sin detección real.
- `max_lost_seconds`: tiempo máximo de esa recuperación aunque bajen los FPS.
- `history_size`: cantidad de posiciones de la trayectoria visible.
- `max_jump_px`: salto máximo permitido hacia una nueva detección.

## `game`

- `activation_distance_px`: cercanía a la línea necesaria para analizar.
- `min_approach_speed_px_s`: movimiento mínimo hacia la portería.
- `before_memory_seconds`: tiempo que recuerda una posición exterior reciente.
- `goal_confirmation_seconds`: tiempo que debe permanecer completamente cruzado.
- `min_goal_observations`: detecciones reales necesarias para confirmar gol.
- `no_goal_stationary_seconds`: espera para declarar un balón detenido.
- `stationary_speed_px_s`: velocidad considerada prácticamente inmóvil.
- `analysis_timeout_seconds`: duración máxima de una jugada.
- `max_detection_gap_seconds`: pérdida máxima tolerada durante el análisis.
- `outside_mouth_seconds`: tiempo requerido para confirmar una salida lateral.
- `result_display_seconds`: duración mínima visible del resultado.
- `rearm_absence_seconds`: ausencia necesaria antes de aceptar otra jugada.
