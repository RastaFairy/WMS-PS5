# Importación en Homebrew Studio

Este directorio es el proyecto canónico y el código del juego vive aquí:

- Interfaz y estados: `src/concepts/taller_menu.cpp`.
- Reglas, prendas, niveles, evaluación y guardado: `src/game/`.
- Entrada de compilación: `build.ps1` y `Makefile`.

## Qué hace cada ruta del IDE

**Abrir el archivo `.ps5vproj`** carga las once pantallas, sus controles y sus
rutas de navegación. El campo `manualCode` está activado y contiene una unidad
C++20 completa que implementa `GeneratedScreen` y la fábrica que exige el
backend OpenGL del IDE. Esa unidad se sincroniza desde el catálogo de niveles,
las reglas y la interfaz nativa del juego; por ello el botón de compilar del
IDE usa la lógica del juego y no sustituye el modelo por una pantalla vacía.

Los controles del lienzo sirven para revisar y ordenar la interfaz. Sus flujos
representan la navegación de referencia; las reglas de carga, desbloqueo,
etiquetas, productos, evaluación, guardado y ciclo están implementadas en el
C++ manual. **Regenerar código** desde el lienzo descarta el C++ manual y crea
una pantalla visual sencilla, así que no lo uses para este proyecto.

`tools/sync-ide-project.py` actualiza el `.ps5vproj`, `ps5hs-model.json` y
`src/ide/ps5hs-screen.cpp` desde los archivos nativos. `tools/build.sh` realiza
esa sincronización y valida cada pantalla, componente, flujo, ID, posición y la
fábrica C++ antes de preparar dependencias o compilar. El puente manual se
contrasta también con los campos expuestos por el `Context` actual del runtime.
Como ese contrato ya no expone `save_root`, la sincronización toma el directorio
de datos persistentes desde `kDataRoot` de `src/main.cpp`; así el progreso del
juego y los ajustes comparten el mismo almacenamiento del título.

**Proyectos nativos** detecta carpetas dentro de
`Documentos/PS5HomebrewStudio/Projects`. El servidor actual del IDE usa esa ruta
fija y no escanea automáticamente `D:\TALLERDECOLADAPS-OpenGL-UI`. No copies el
proyecto para cambiar su ubicación canónica. Al compilar el modelo visual, el
IDE crea su título generado dentro de ese workspace; la carpeta canónica y el
pipeline de entrega siguen siendo `D:\TALLERDECOLADAPS-OpenGL-UI`.

Cuando se autorice compilar, ejecuta `build.ps1` desde la raíz de este
directorio. Ese script construye el título nativo desde `src/`, incluida la
interfaz real del mini juego. El shell de galería del kit no intercepta botones
ni superpone un HUD. Los marcadores del perfil `standalone-native-ui-v1` hacen
que el runtime del IDE reconozca ese trabajo y no reescriba funciones de la
aplicación. `dist/` contiene la salida del pipeline; UltraPack debe recibir esa
salida si se solicita el empaquetado.

## Contraste con Visual-PS5

La importación visual acepta `format: "ps5vproj"`, lee `manualCode` y pasa el
texto de `customCode` al servicio del backend. La ruta OpenGL verifica que el
C++ incluya `GeneratedScreen` y `make_ps5hs_generated`, lo inserta en una
plantilla nativa recién creada y compila esa carpeta bajo el workspace fijo de
Documentos. Este contrato se contrasta con el código y la documentación del IDE:

- [Importador y constructor visual](https://github.com/RastaFairy/Visual-PS5/blob/main/app.js)
- [Detector y constructor de proyectos nativos](https://github.com/RastaFairy/Visual-PS5/blob/main/runtime/server.ps1)
- [Documentación de backends visuales nativos](https://github.com/RastaFairy/Visual-PS5/blob/main/docs/NATIVE_VISUAL_BACKENDS.md)
