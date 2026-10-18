# Taller de Colada PS5

Repositorio del simulador de lavado, con la versión web existente y el proyecto nativo para PS5.

## Contenido

- `Taller de colada.html`: versión web conservada del repositorio original.
- `native/`: proyecto C++20/OpenGL importable en Visual-PS5. Incluye campaña, modo experto y el modo **Simulación** basado en el modelo Girbau HS-6008, indicado como equivalente extranjero del EH020.
- `artifacts/PPSA19918.ffpfsc`: imagen PFS comprimida construida desde la aplicación compilada, versión `01.000.010`.

El modo Simulación genera casos aleatorios sin pistas y exige consultar el manual de diagnóstico del juego. Las acciones de reparación respetan los límites de seguridad del manual técnico.

## Compilar y validar

En Windows con WSL configurado:

```powershell
cd native
.\build.ps1
```

Las comprobaciones estáticas usan Python 3.13 y Pillow, fijado en `native/tools/requirements-validation.txt` para validar imágenes PNG/RGBA.

Para ejecutarlas:

```powershell
cd native
python -m pip install -r tools/requirements-validation.txt
python tools/check-localization.py --require-fonts
python tools/check-mode-font-integration.py
python tools/validate-expert-mode.py
```

El workflow de GitHub ejecuta esas comprobaciones estáticas. La compilación necesita el entorno WSL y el SDK OpenGL fijado por el proyecto. La salida local del build se guarda en `native/dist/`; los resultados generados y cachés no se versionan.

## Paquete disponible

`artifacts/PPSA19918.ffpfsc` se verificó y se extrajo en profundidad para compararlo con la carpeta compilada: 113 archivos, sin diferencias. SHA-256: `43D89A7152A17DDF59B704EB1FFC890A1A8F4B345ADE0F7757587A3FA1C3B51D`. Es una imagen `.ffpfsc`, no un instalador `.pkg`; no constituye una prueba de ejecución en consola física.

## Créditos de herramientas

- Visual-PS5: edición e integración del proyecto nativo.
- WSL y PS5 OpenGL SDK: entorno de compilación de destino.
- Clang 18 y Ninja: compilación y enlace.
- Python 3: validadores estáticos del proyecto.
- MkPFS.CSharp 2.5.0: creación y verificación de la imagen `.ffpfsc`.

## Licencias

El proyecto nativo mantiene su licencia en `native/LICENSE` y sus avisos de terceros en `native/THIRD_PARTY_NOTICES.md`. Las fuentes Noto conservan su licencia OFL en `native/assets/fonts/Noto-CJK-OFL.txt`. La página HTML preexistente se conserva sin cambios.
