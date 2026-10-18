# Taller de Colada PS5

Proyecto nativo C++20/OpenGL para Visual-PS5. El proyecto importable principal es `TallerColadaPS5-Principal.ps5vproj`; el código canónico de la pantalla está en `src/concepts/ps5hs_generated.cpp`. Se conserva el Title ID de esta base: `PPSA19918`.

## Compilar

1. Extrae el directorio completo `TALLERDECOLADAPS-OpenGL-UI` en una ruta escribible.
2. Abre `TallerColadaPS5-Principal.ps5vproj` en Visual-PS5 y usa la generación/compilación nativa del IDE.
3. Para compilar el árbol fuente del paquete de forma independiente, abre PowerShell en el directorio raíz y ejecuta:

   ```powershell
   .\build.ps1
   ```

   En Windows se necesitan WSL y las dependencias fijadas por el proyecto.

El código de pantalla y los valores `customCode` de `TallerColadaPS5-Principal.ps5vproj` y `ps5hs-model.json` son idénticos. El fallback de fuentes está incluido dentro del código inyectado porque el workspace nativo generado por el IDE no garantiza copiar los archivos `.huifont` sueltos.

## Modo experto

El modo experto se desbloquea al completar las **20 misiones originales**. La pantalla de resultados muestra el aviso de desbloqueo; al confirmar la salida de ese resultado, el juego abre automáticamente el tablero experto. Las partidas guardadas con las 20 misiones originales completadas también abren directamente ese tablero al cargarse. Una vez desbloqueado, **Cuadrado** alterna entre el tablero normal y el experto. No se usan R1 ni L1 para ese cambio porque el shell de Visual-PS5 reserva esas acciones para navegación global.

El modo experto conserva cinco misiones nuevas con la máquina **Girbau HS-6008 / LOGI PRO**. El progreso experto se guarda por separado para mantener la compatibilidad con las partidas anteriores.

## Modo Simulación

El menú principal incluye **Simulación** para la Girbau HS-6008, tratada en este proyecto como la equivalencia extranjera del EH020 según la indicación del usuario. Cada caso elige cuatro de cinco familias de alarma y no ofrece pistas. Antes de cerrarlo, el jugador debe leer la sección de seguridad y las páginas del manual breve que corresponden a los códigos activos; las acciones se resuelven con los estados del simulador.

La guía distingue comprobaciones externas seguras de fallos reservados al servicio autorizado y no instruye a abrir paneles, intervenir cableado ni reparar componentes eléctricos. Los casos no modifican el progreso ni los guardados de las misiones normales o expertas. El atlas de estado está en `assets/simulation-alarm-atlas.png` y su recurso RGBA se registra en `assets/ps5hs/manifest.json`.

Las alarmas y los límites de servicio se contrastaron con el manual operativo LOGI PRO y la tabla de códigos Girbau adjuntos. El Parts Handbook EH020/HS-6008 aporta contexto de piezas y equivalencia, no se usa como procedimiento de reparación.

## Etiquetas de cuidado

Durante una misión de lavado, **R3 (pulsar el stick derecho)** abre la etiqueta de cuidado de la prenda seleccionada; R3, Confirmar o Atrás la cierra. El panel táctil no se usa para abrir etiquetas porque el shell del IDE intercepta esa acción antes de enviarla a la pantalla del juego.

## Idiomas y fuentes

La aplicación conserva ocho idiomas: español, inglés, francés, ruso, alemán, japonés, chino simplificado e italiano. Para evitar que los caracteres acentuados o CJK se conviertan en `?`, el fuente contiene fallbacks `.huifont` embebidos para Latin ampliado, Noto Sans CJK JP y Noto Sans CJK SC. El runtime intenta cargar los archivos de `assets/fonts/` y utiliza los bytes embebidos si el generador del IDE no los ha copiado al workspace nativo. La licencia OFL de los archivos Noto está en `assets/fonts/Noto-CJK-OFL.txt`.

## Validaciones reproducibles

Desde el directorio raíz:

```bash
python tools/check-localization.py --require-fonts
python tools/check-mode-font-integration.py
```

Estas pruebas comprueban las 38 tablas de localización, la cobertura tipográfica requerida, la sincronización entre fuente y modelos del IDE, los controles no interceptados, el desbloqueo experto y que los fallbacks embebidos coinciden con los archivos `.huifont`. La validación de traducciones también detecta términos inequívocamente italianos en todas las tablas españolas.

El 18-10-2026 se compiló y firmó la aplicación con el pipeline PS5/WSL. `dist/PPSA19918/` contiene la carpeta resultante; `dist/PPSA19918.zip` conserva esa carpeta y `dist/PPSA19918.ffpfsc` contiene la imagen PFS comprimida. El `.ffpfsc` se verificó y su extracción profunda coincide byte por byte con los 113 archivos de la carpeta compilada. Esto confirma el build y el contenedor, no una prueba de ejecución en consola física.

## Misiones expertas

Las misiones se inspiran en el manual *Operating Instructions Manual for LOGI CONTROL / LOGI PRO CONTROL* de Girbau (código 523340, revisión 11b/1218). El manual documenta el control de desequilibrio, la dosificación por compartimentos y recomendaciones de carga para algodón, sintéticos y prendas delicadas. Las temperaturas y rpm concretas de las misiones son reglas de simulación, no una afirmación de compatibilidad para todos los modelos físicos.

## Contenido

El ZIP conserva el código nativo, recursos RGBA, fuentes horneadas, música, efectos, scripts de build, manifests, licencias y herramientas de validación. No distribuye carpetas temporales de compilación ni cachés locales.

## Expert-mode / HS-6008 revision

The expert missions now use the documented LOGI PRO HS-6008 program slots: P-2 for heavy-soil whites (56 min / 7 phases), P-7 for synthetics (30 min / 5 phases), P-1 for extra-heavy soil (66 min / 8 phases, including an 80 °C phase in the program table), and P-8 for wool/delicates (31 min / 5 phases). The fifth mission is a separate spin-only imbalance diagnosis. These timings and phase counts follow the supplied LOGI PRO operating manual; exact phase vectors are simplified in gameplay. The 800/600 rpm limits are explicitly game rules, not manufacturer-specified values. Mission temperatures follow the strictest care label in each required load: the current P-1 load is capped at 30 °C despite the 80 °C phase listed for that program.

The expert mission summary, objective, load and duration strings have been separated cleanly by language; `tools/check-localization.py` rejects known Italian strings in Spanish mission rows. `tools/validate-expert-mode.py` checks mission metadata, font/resource integration, project/model/source synchronization, and the machine texture payload before packaging.

The in-game HS-6008 image is a transparent generated recreation based on the user-supplied product reference; it is not a copied manufacturer photograph. The front machine texture is also used in the active washer view while game-specific controls are overlaid on the LOGI PRO fascia.
