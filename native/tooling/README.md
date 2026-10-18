# Herramientas nativas de compilación

Las herramientas de `tooling/native/` generan los utilitarios usados por el pipeline de compilación PS5. `make app` usa `tools/build-host-tools.sh`, `tools/rebuild-libc.sh`, `tools/prepare-opengl.sh` y `tools/build.sh`; no necesita GoogleTest ni ejecutables previos.

`make libc` reconstruye el runtime de forma determinista y comprueba su hash. `make clean` elimina `build/`, `dist/` y el runtime generado; `make distclean` también elimina la caché de dependencias `.deps/`.
