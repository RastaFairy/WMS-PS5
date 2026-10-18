# Requisitos y compilación

- Windows 10/11 con PowerShell y WSL, o Linux/WSL directamente.
- En Linux/WSL: `bash`, `make`, `ninja`, `clang-18`, `python3`, `wget`, `unzip`, `tar`, `sha256sum` y `ccache` (o compilar con `USE_CCACHE=0`).
- Espacio libre para los SDKs y la caché en `.deps/`, además de los artefactos temporales `build/` y `dist/`.

Desde PowerShell, en la raíz del proyecto, ejecuta `./build.ps1`. Desde Linux/WSL, ejecuta `make app`. El proceso prepara el runtime y el SDK fijado mediante las herramientas incluidas. La primera compilación requiere conexión a Internet para descargar las dependencias.

El proyecto mantiene un único archivo importable para Visual-PS5: `TallerColadaPS5-Principal.ps5vproj`.
