# Taller de Colada PS5

Interfaz nativa C++20/OpenGL para PS5. El menú principal 2D abre Maestro Lavandero, un juego de cuidado textil con veinte niveles, pantallas dibujadas con el motor y navegación por mando.

## Estado actual

El juego presenta clasificación de prendas, lectura obligatoria de etiquetas, preparación de carga, panel de lavadora, ciclo animado e informe por nivel. Incluye ropa válida y distractores de clasificación a lo largo de veinte niveles.

Las reglas de carga usan una lavadora de 8 kg: 2 kg se reservan para el agua y la ropa seca no puede superar los 6 kg. Cada etiqueta muestra el peso orientativo, el tejido, sus máximos de temperatura y centrifugado, el permiso de lejía y las protecciones necesarias. La carga adopta por separado el menor máximo de temperatura y de centrifugado entre las prendas cargadas.

La selección de programa y detergente se evalúa por misión y por compatibilidad con cada tejido. También se comprueban suavizantes, lejías, atrapacolor, pretratamientos de manchas y bolsas de malla. El ciclo anima llenado, lavado, aclarado y centrifugado en la lavadora 2D.

Cada nivel reinicia toda su sesión: prendas en cesta, etiquetas, tratamientos, puerta, ajustes y animación. Solo persiste el progreso entre niveles: desbloqueos, niveles completados y mejores puntuaciones/estrellas, usando el contenedor de guardado existente con CRC y escritura atómica.

Los pesos incorporados son valores orientativos de la simulación, no datos de una etiqueta real; prevalece siempre la etiqueta de la prenda física.

Los ajustes generales mantienen volumen de interfaz, movimiento reducido, vibración y botón de confirmación. La aplicación también permite salir desde el menú principal.

## Archivos principales

- Proyecto Visual-PS5: `TallerColadaPS5-Principal.ps5vproj`
- Modelo del proyecto: `ps5hs-model.json`
- Flujo de menú y juego 2D: `src/concepts/taller_menu.cpp`
- Reglas, sesiones, animación y guardado: `src/game/laundry_game.cpp` y `src/game/laundry_game.hpp`
- Catálogo de niveles y prendas: `src/game/laundry_levels.cpp`
- Registro de pantalla: `src/concepts/registry.cpp`
- Sonidos de interfaz: `src/audio/cues.cpp` y `assets/audio/sfx/`

`ps5hs-model.json` y `TallerColadaPS5-Principal.ps5vproj` son referencias visuales coordinadas para importar los once estados del juego. Se dejan sin widgets, flujos ni código manual porque la interfaz ejecutable y sus reglas viven en C++; así el generador del IDE no sustituye el juego por una pantalla paralela incompleta. El pipeline valida formato, pantallas, destino y manifiesto antes de compilar.

## Compilar y empaquetar

Cuando se autorice una compilación, ejecuta desde PowerShell en la raíz:

```powershell
.\build.ps1
```
