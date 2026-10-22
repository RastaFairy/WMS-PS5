# Requisitos y compilación

- Windows 10/11 con PowerShell y WSL, o Linux/WSL directamente.
- En Linux/WSL: `bash`, `make`, `ninja`, `clang-18`, `python3`, `wget`, `unzip`, `tar`, `sha256sum` y `ccache` (o compilar con `USE_CCACHE=0`).
- Espacio libre para los SDKs y la caché en `.deps/`, además de los artefactos temporales `build/` y `dist/`.

Desde PowerShell, en la raíz del proyecto, ejecuta `./build.ps1`. Desde Linux/WSL, ejecuta `make app`. El proceso prepara el runtime y el SDK fijado mediante las herramientas incluidas. La primera compilación requiere conexión a Internet para descargar las dependencias.

El archivo `TallerColadaPS5-Principal.ps5vproj` se abre en Visual-PS5 con once pantallas, 133 componentes y 51 flujos de navegación de referencia. Lleva el código C++ manual completo del mini juego para que el backend OpenGL use el contrato `GeneratedScreen` requerido por el IDE. No pulses «Regenerar código»: el generador visual sustituiría la lógica completa por una pantalla básica.

Homebrew Studio coloca los títulos que crea desde el lienzo en `Documentos/PS5HomebrewStudio/Projects`; el proyecto y el pipeline canónicos siguen en `D:\TALLERDECOLADAPS-OpenGL-UI`. Consulta [`IDE_BUILD.md`](IDE_BUILD.md) antes de compilar desde el IDE.
