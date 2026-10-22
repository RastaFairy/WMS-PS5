# Taller de Colada para PS5

**Versión:** `01.000.010`  
**Title ID:** `PPSA19918`  
**Género:** simulador educativo 2D de cuidado textil  
**Tecnología:** C++20 y OpenGL nativo para PlayStation 5

*Taller de Colada* es un minijuego educativo cuyo modo principal, **Maestro Lavandero**, propone preparar coladas respetando el color, el tejido y las instrucciones de cuidado de cada prenda. La partida combina clasificación, lectura de etiquetas, elección de productos y configuración de una lavadora, y termina con una evaluación del lavado realizado.

La descripción de este README se basa en el código fuente etiquetado como [`01.000.010`](https://github.com/RastaFairy/WMS-PS5/tree/01.000.010), especialmente en el [flujo de pantallas](https://github.com/RastaFairy/WMS-PS5/blob/01.000.010/src/concepts/taller_menu.cpp), las [reglas y la evaluación](https://github.com/RastaFairy/WMS-PS5/blob/01.000.010/src/game/laundry_game.cpp) y el [catálogo de niveles](https://github.com/RastaFairy/WMS-PS5/blob/01.000.010/src/game/laundry_levels.cpp).

## Objetivo del juego

Completa cada misión preparando la carga adecuada y seleccionando un ciclo compatible con las prendas. No basta con poner ropa en el tambor: hay que distinguir las prendas correctas de las que deben quedarse en la cesta, consultar sus etiquetas y evitar ajustes o productos que puedan dañarlas.

## Cómo se juega

1. **Elige una misión.** Hay 20 niveles repartidos en cuatro fases. Los niveles se desbloquean progresivamente al completar las misiones.
2. **Clasifica las prendas.** Selecciona cada prenda e inspecciona su etiqueta: el juego muestra tejido y composición, color, peso orientativo, temperatura máxima, centrifugado máximo, permiso de blanqueador y otras precauciones.
3. **Prepara la ropa cuando sea necesario.** Algunas misiones requieren aplicar un tratamiento previo a las manchas o proteger determinadas prendas con una bolsa de malla.
4. **Carga la lavadora.** La puerta debe estar abierta para introducir o retirar prendas. Es obligatorio haber leído la etiqueta antes de cargar cada una.
5. **Configura el panel.** Selecciona programa, temperatura, velocidad de centrifugado, detergente, suavizante y aditivo. También hay que confirmar explícitamente las opciones que no se van a usar (por ejemplo, «Ninguno»).
6. **Cierra la puerta e inicia el ciclo.** El juego comprueba que haya ropa cargada, que la puerta esté cerrada, que las etiquetas se hayan leído, que no se supere la capacidad disponible y que todos los ajustes estén seleccionados.
7. **Consulta el informe.** Al terminar la animación del ciclo, se calcula la puntuación y se conceden estrellas. Desde el informe puedes continuar, repetir el nivel o volver al mapa.

## Contenido: 20 niveles

### Fase 1 — Clasificación básica

1. **La Colada de Blancos:** separar la ropa blanca de algodón de las prendas oscuras y de color intenso.
2. **Ropa Oscura y Tejanos:** seleccionar ropa oscura y vaqueros, evitando mezclar prendas claras o delicadas.
3. **Ropa de Color Brillante:** preparar una carga de colores vivos sin incluir ropa blanca ni lana.
4. **Símbolos de Cuidado Textil:** identificar prendas que no admiten lavado a máquina y dejarlas fuera del tambor.
5. **Toallas y Lencería de Hogar:** preparar la carga de toallas blancas de algodón y excluir las prendas inadecuadas.

### Fase 2 — Parámetros del panel

6. **Programa Sintéticos y Mixtos:** seleccionar el ciclo apropiado para una carga de tejidos sintéticos y mezclas.
7. **Ajuste Térmico y Centrifugado:** equilibrar temperatura y centrifugado según las etiquetas de las prendas.
8. **Especial Lana y Lavado a Mano:** tratar la lana con un programa y productos suaves, temperatura baja y centrifugado reducido.
9. **Lavado Eco 40-60:** configurar el programa Eco y el detergente indicado para la misión.
10. **Ciclo Rápido 15' / Refresco:** identificar prendas de uso ligero y sin manchas aptas para el ciclo rápido.

### Fase 3 — Protección y tratamientos

11. **La Malla Protectora para Delicados:** colocar en bolsa de malla las prendas que lo requieren.
12. **Pre-Tratamiento de Manchas Grasas:** detectar la mancha de aceite y aplicar el tratamiento previo indicado.
13. **Ropa Deportiva Técnica:** usar el programa y el detergente deportivo, evitando el suavizante.
14. **Manchas Orgánicas (Sangre / Fruta):** elegir el pretratamiento según el origen de la mancha y evitar aplicar calor indebidamente.
15. **Seda Natural y Encajes Finos:** proteger las prendas delicadas y utilizar ajustes y detergente compatibles.

### Fase 4 — Maestría compleja

16. **Control de Sobrecarga del Tambor:** calcular el peso seco de la ropa y respetar la capacidad disponible.
17. **Toallitas Atrapacolor y Mixtos:** prevenir la transferencia de color con el aditivo correspondiente.
18. **Anoraks y Ropa de Plumas:** cuidar las prendas acolchadas con un ciclo suave y un detergente apropiado.
19. **Higiene de ropa de bebé:** atender las necesidades de las prendas sensibles con productos adecuados y sin blanqueadores agresivos.
20. **Examen Final de Maestría:** combinar clasificación, lectura de etiquetas, protección, tratamientos y configuración correcta de la lavadora.

Los nombres y objetivos anteriores proceden del catálogo de niveles incluido en el código de la versión `01.000.010`.

## Reglas de la simulación

### Capacidad de carga

La lavadora tiene una capacidad modelada de **8 kg**. El juego reserva **2 kg para el agua**, por lo que la ropa seca cargada no puede superar **6 kg**. El peso de cada prenda es un dato orientativo de la simulación.

### Programas y ajustes

El panel contempla estos programas:

- Algodón / Estándar
- Sintéticos / Mixto
- Delicados
- Lana / Lavado a mano
- Ropa deportiva
- Rápido 15 / 30 min
- Eco 40-60

Las temperaturas disponibles son **20, 30, 40, 60 y 90 °C**. Las velocidades de centrifugado disponibles son **0, 400, 800, 1.200 y 1.400 RPM**. Que un ajuste aparezca en el selector no significa que sea seguro para la carga: la evaluación contrasta los valores seleccionados con los límites de las etiquetas y del programa.

También se pueden seleccionar detergente universal, para ropa de color, para lana, deportivo o Eco Gel; suavizante estándar o hipoalergénico; y aditivos como lejía de oxígeno activo, lejía con cloro o toallita atrapacolor. «Ninguno» es igualmente una selección válida cuando corresponda a la misión.

### Manchas, tejidos y protección

Según la misión, el sistema evalúa la compatibilidad entre prendas y programa, detergente, suavizante y aditivo. También verifica las prendas no lavables a máquina, el uso de la malla protectora y el tratamiento previo de las manchas. La lógica contempla, entre otros, algodón, tejano, fibras sintéticas, lana, seda, prendas delicadas, ropa deportiva, acolchados y cuero.

### Ciclo, puntuación y progreso

El ciclo se representa mediante una animación de **llenado, lavado, aclarado y centrifugado**. No intenta reproducir en tiempo real la duración física de un programa de lavadora.

Cada misión se evalúa sobre un máximo de **300 puntos**. La versión `01.000.010` asigna:

- **3 estrellas:** 270 puntos o más.
- **2 estrellas:** de 205 a 269 puntos.
- **1 estrella:** menos de 205 puntos.

Un lavado perfecto se marca cuando la evaluación no encuentra incidencias. El juego conserva el progreso de niveles, los niveles completados y la mejor puntuación y número de estrellas de cada uno. La sesión de prendas y ajustes se reinicia al comenzar una misión; el progreso acumulado se guarda por separado.

## Controles (DualSense)

Los mensajes de ayuda que aparecen al pie de cada pantalla indican las acciones disponibles en ese contexto. De forma predeterminada, **la Cruz confirma y el Círculo vuelve o pausa**. Esta asignación puede invertirse en Opciones.

| Control | Acción habitual |
| --- | --- |
| Cruceta / stick izquierdo | Navegar por menús, niveles, prendas y ajustes. |
| Cruz (X) | Confirmar, cargar o retirar una prenda, seleccionar una opción o iniciar el ciclo cuando el foco está en el control de inicio. |
| Círculo (O) | Volver o abrir las opciones de pausa, según la pantalla. |
| L1 / R1 | Cambiar de fila en el mapa de niveles o recorrer prendas y controles del panel. |
| L3 | Abrir o cerrar la puerta desde la pantalla de clasificación. |
| R3 / Touchpad | Consultar la etiqueta de la prenda desde las pantallas compatibles. |
| Cuadrado | Abrir las opciones de mancha o alternar la bolsa de malla, según la prenda seleccionada. |
| Triángulo | Abrir el manual breve. |
| R2 | Pasar al panel de la lavadora desde la clasificación o activar el inicio rápido desde dicho panel. |
| L2 | Volver a la clasificación desde el panel de la lavadora. |
| Options | Pausar o continuar durante el ciclo; también abre la pausa en pantallas de preparación compatibles. |
| Touchpad durante el ciclo | Consultar el manual breve. |

El comportamiento de algunos botones cambia según la pantalla y el foco seleccionado; consulta las indicaciones que muestra el propio juego.

## Opciones

La pantalla de opciones permite modificar el volumen de la interfaz, activar el movimiento reducido, activar o desactivar la respuesta háptica del mando e invertir los botones de confirmar y volver.

## Descargar la versión 01.000.010

El repositorio publica la compilación etiquetada como `01.000.010` en la página de versiones:

**[Descargar / consultar la versión 01.000.010](https://github.com/RastaFairy/WMS-PS5/releases/tag/01.000.010)**

El paquete publicado se llama `PPSA19918.ffpfsc`. El procedimiento para instalarlo y ejecutarlo depende del entorno homebrew compatible con la consola; este repositorio no documenta un método universal de instalación.

## Desarrollo y compilación

El proyecto utiliza **C++20 y OpenGL nativo**. El repositorio también incluye un proyecto importable para [Visual-PS5 / PS5 Homebrew Studio](https://github.com/RastaFairy/Visual-PS5), el IDE utilizado para trabajar con la interfaz.

Archivos principales del juego:

- [`src/concepts/taller_menu.cpp`](https://github.com/RastaFairy/WMS-PS5/blob/01.000.010/src/concepts/taller_menu.cpp): pantallas, navegación, controles y flujo de la partida.
- [`src/game/laundry_game.hpp`](https://github.com/RastaFairy/WMS-PS5/blob/01.000.010/src/game/laundry_game.hpp): modelo y tipos que representan prendas, ajustes, sesión y evaluación.
- [`src/game/laundry_game.cpp`](https://github.com/RastaFairy/WMS-PS5/blob/01.000.010/src/game/laundry_game.cpp): reglas de carga, validaciones, animación del ciclo, puntuación y guardado del progreso.
- [`src/game/laundry_levels.cpp`](https://github.com/RastaFairy/WMS-PS5/blob/01.000.010/src/game/laundry_levels.cpp): catálogo de los 20 niveles y sus prendas.
- [`src/ide/ps5hs-screen.cpp`](https://github.com/RastaFairy/WMS-PS5/blob/01.000.010/src/ide/ps5hs-screen.cpp): unidad C++ manual sincronizada para la integración con el IDE.
- [`TallerColadaPrincipal.ps5vproj`](https://github.com/RastaFairy/WMS-PS5/blob/01.000.010/TallerColadaPrincipal.ps5vproj): proyecto visual para Visual-PS5.

### Requisitos de compilación

La guía del proyecto contempla **Windows 10/11 con PowerShell y WSL**, o Linux/WSL directamente. El entorno Linux/WSL necesita `bash`, `make`, `ninja`, `clang-18`, `python3`, `wget`, `unzip`, `tar` y `sha256sum`; `ccache` es opcional.

Desde PowerShell, en la raíz del repositorio:

```powershell
.\build.ps1
```

Desde Linux/WSL, para compilar la aplicación:

```bash
make app
```

Para generar también el paquete de distribución:

```bash
make release
```

La primera compilación necesita conexión a Internet para obtener las dependencias fijadas por el proyecto. Consulta [`docs/GETTING_STARTED.md`](https://github.com/RastaFairy/WMS-PS5/blob/01.000.010/docs/GETTING_STARTED.md) y [`docs/IDE_BUILD.md`](https://github.com/RastaFairy/WMS-PS5/blob/01.000.010/docs/IDE_BUILD.md) antes de preparar el entorno.

**Nota para editar el proyecto en Visual-PS5:** la lógica jugable completa está implementada en C++ manual, sincronizado desde el código fuente del juego. No uses **«Regenerar código»** sin preservar antes ese código: regenerarlo desde el modelo visual puede sustituir la lógica de la partida por una pantalla básica.

## Nota educativa y estado de validación

Las masas y los datos de las prendas son valores orientativos usados por la simulación, no sustituyen las etiquetas reales. Para lavar prendas físicas, prevalecen siempre las instrucciones del fabricante de cada prenda y del detergente.

El repositorio incluye una compilación para la versión `01.000.010`, pero la documentación de validación de esa versión indica que **no se ha verificado la ejecución en una consola PS5 física**.

## Licencia

Consulta [`LICENSE`](https://github.com/RastaFairy/WMS-PS5/blob/01.000.010/LICENSE) y [`THIRD_PARTY_NOTICES.md`](https://github.com/RastaFairy/WMS-PS5/blob/01.000.010/THIRD_PARTY_NOTICES.md) para la licencia del proyecto y los avisos de componentes y recursos de terceros.
