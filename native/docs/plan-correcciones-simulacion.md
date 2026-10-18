# Plan de correcciones y modo Simulación

## Alcance

Integrar un modo Simulación de diagnóstico para la lavadora Girbau HS-6008, tratada como equivalente extranjera del EH020 según la indicación del usuario. Los manuales adjuntos sirven como referencias técnicas; sus advertencias de servicio autorizado se conservan y no se convierten en instrucciones de reparación eléctrica para el jugador.

## Correcciones y entregables

1. **Diagnóstico de referencia:** contrastar los códigos de alarma LOGI/LOGI PRO/INTELI con el manual operativo. Usar solo fallos y comprobaciones compatibles con las interacciones existentes; marcar explícitamente las averías que requieren servicio autorizado.
2. **Modo de juego completo:** añadir una entrada al menú principal, un panel de preparación de caso y casos aleatorios de dificultad máxima que combinen varias alarmas. Cada caso mostrará los códigos activos sin explicar su causa y no ofrecerá pistas.
3. **Manual obligatorio:** incorporar un manual breve de reparación/diagnóstico dentro del juego. El caso no se puede cerrar hasta haber consultado las secciones de seguridad y las páginas asociadas a todas sus alarmas. Las acciones se validan mediante estados reales del simulador, no con respuestas de texto.
4. **Interfaz y atlas:** crear un atlas RGBA real de alarmas/estados y conectarlo al cargador, manifiesto y proyecto. Ajustar el diseño de la etiqueta de cuidado para separar sus notas inferiores y revisar los límites de texto del panel de misión observados en las capturas.
5. **Aislamiento y persistencia:** mantener los casos aleatorios fuera del progreso y guardado de las 20 misiones y las 5 misiones expertas; al salir o terminar, volver al menú Simulación sin alterar ese progreso.
6. **Cierre estático:** comprobar traducciones en los ocho idiomas, cobertura de glifos, sincronización exacta del código canónico con los dos modelos del IDE, integridad del atlas y rutas/estados de navegación. No compilar ni empaquetar hasta recibir la orden del usuario.

## Restricciones de implementación

- Sin stubs vacíos, funciones huérfanas, texto provisional ni botones sin acción.
- No mostrar pistas durante un caso de Simulación, ni permitir activar las pistas generales con el botón habitual.
- La guía diferencia inspecciones seguras del usuario de fallos que exigen técnico autorizado.
- No afirmar que una comprobación está validada en consola sin una compilación y una prueba física autorizadas.

## Estado

- [x] Fuentes técnicas contrastadas y alcance de alarmas definido.
- [x] Modo, casos, manual obligatorio y atlas integrados.
- [x] Ajustes visuales de los paneles observados.
- [x] Validaciones estáticas y sincronización de artefactos.
- [x] Compilación PS5/WSL y firma completadas; carpeta, ZIP y `.ffpfsc` generados en `dist/` y el contenedor comparado byte por byte tras extracción profunda.
