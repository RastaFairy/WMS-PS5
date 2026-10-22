#!/usr/bin/env python3
"""Synchronize Visual-PS5's editable canvas with the complete native game source."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCREENS = (
    ("screen-main", "Menú principal"),
    ("screen-settings", "Opciones"),
    ("screen-levels", "Mapa de misiones"),
    ("screen-sorting", "Clasificación y etiquetas"),
    ("screen-label", "Etiqueta de cuidado"),
    ("screen-treatment", "Pretratamiento y malla"),
    ("screen-machine", "Panel de lavado"),
    ("screen-manual", "Manual breve"),
    ("screen-running", "Ciclo en marcha"),
    ("screen-report", "Informe de lavado"),
    ("screen-pause", "Pausa"),
)

SCREEN_IDS = tuple(screen_id for screen_id, _ in SCREENS)
SOURCE_FILES = (
    "src/game/laundry_game.hpp",
    "src/game/garment_sprites.hpp",
    "src/game/laundry_levels.cpp",
    "src/game/laundry_game.cpp",
    "src/concepts/taller_menu.cpp",
)
FRAMEWORK_INCLUDES = {
    '"game/laundry_game.hpp"',
    '"game/garment_sprites.hpp"',
}
IDE_TYPES = {
    "panel", "title", "text", "button", "toggle", "slider", "stepper",
    "select", "carousel", "list", "progress", "badge", "image", "input",
    "gauge", "separator", "card",
}
UNICODE_FONT_ASSET_ID = "taller-font-inter-regular"
UNICODE_FONT_PATH = "third_party/fonts/Inter-Regular.ttf"


def read_source(root: Path, relative: str) -> str:
    try:
        return (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SystemExit(f"{relative}: cannot read UTF-8 source ({exc})") from exc


def native_source(root: Path) -> str:
    """Build the one-translation-unit source accepted by the IDE's visual build."""
    runtime_entry = read_source(root, "src/main.cpp")
    data_roots = re.findall(
        r'^\s*constexpr\s+const\s+char\s*\*\s*kDataRoot\s*=\s*"([^"]+)"\s*;',
        runtime_entry,
        re.MULTILINE,
    )
    if len(data_roots) != 1 or not data_roots[0].startswith("/"):
        raise SystemExit("The native runtime must define one absolute kDataRoot for persistent saves.")
    save_root = data_roots[0]

    bodies: list[str] = []
    includes: list[str] = []
    seen_includes: set[str] = set()
    for relative in SOURCE_FILES:
        source = read_source(root, relative)
        body: list[str] = []
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#include "):
                include = stripped[len("#include "):]
                if include in FRAMEWORK_INCLUDES:
                    continue
                if include not in seen_includes:
                    seen_includes.add(include)
                    includes.append(include)
                continue
            if stripped == "#pragma once":
                continue
            body.append(line)
        bodies.append("\n".join(body).strip())

    code = "\n".join((
        "// Visual-PS5 manual C++ source, synchronized from the canonical game sources.",
        "// This single translation unit preserves the complete native game logic.",
        *(f"#include {include}" for include in includes),
        "",
        *bodies,
    )).rstrip() + "\n"
    code, class_count = re.subn(r"\bclass TallerMenu final : public app::Concept",
                                "class GeneratedScreen final : public app::Concept", code)
    code = re.sub(r"\bTallerMenu\b", "GeneratedScreen", code)
    code, factory_count = re.subn(r"\bmake_taller_menu\b", "make_ps5hs_generated", code)
    code = code.replace('"src/concepts/taller_menu.cpp"', '"generated/ps5hs-screen.cpp"')
    # The current HUI Context no longer exposes save_root. The game still uses
    # the title's established persistent data directory, which is also the
    # root passed to Shell by the native runtime.
    code = code.replace(
        "game::load_progress(context.save_root)",
        f'game::load_progress("{save_root}")',
    )
    code = code.replace(
        "game::save_progress(context_.save_root, progress_)",
        f'game::save_progress("{save_root}", progress_)',
    )
    code = code.replace('"/app0/assets/garments/', '"/app0/assets/ps5hs/')
    if "context.save_root" in code or "context_.save_root" in code:
        raise SystemExit("The IDE's current Context has no save_root; the game path was not adapted.")
    if class_count != 1 or factory_count != 1:
        raise SystemExit(
            "Native IDE source bridge must find exactly one TallerMenu class and factory."
        )
    if ('#include "game/laundry_game.hpp"' in code
            or '#include "game/garment_sprites.hpp"' in code):
        raise SystemExit("The IDE source cannot depend on uncopied game headers.")
    if "make_ps5hs_generated" not in code or "GeneratedScreen final" not in code:
        raise SystemExit("The source does not satisfy Visual-PS5's OpenGL factory contract.")
    if len(code) < 2000:
        raise SystemExit("The synchronized manual source is unexpectedly incomplete.")
    return code


def catalog_titles(root: Path) -> list[tuple[int, str]]:
    source = read_source(root, "src/game/laundry_levels.cpp")
    titles = [(int(number), title) for number, title in re.findall(
        r'^\s*(\d+),\s*"[^"]+",\s*"([^"\\]*(?:\\.[^"\\]*)*)"',
        source,
        re.MULTILINE,
    )]
    titles = [(number, json.loads('"' + title + '"')) for number, title in titles]
    if [number for number, _ in titles] != list(range(1, 21)):
        raise SystemExit("The 20-level visual map no longer matches laundry_levels.cpp.")
    return titles


def build_project(root: Path, updated_at: str | None = None) -> dict:
    components: list[dict] = []
    flows: list[dict] = []
    per_screen: dict[str, int] = {screen_id: 0 for screen_id in SCREEN_IDS}

    def add(screen_id: str, component_id: str, kind: str, label: str,
            x: float, y: float, w: float, h: float, *, font: int = 18,
            bg: str = "transparent", fg: str = "#183247", value: float = 0,
            minimum: float = 0, maximum: float = 100, step: float = 1,
            checked: bool = False, items: list[str] | None = None,
            action: str = "none", action_message: str = "") -> str:
        if screen_id not in per_screen:
            raise SystemExit(f"Component {component_id} references unknown screen {screen_id}.")
        per_screen[screen_id] += 1
        components.append({
            "id": component_id,
            "screenId": screen_id,
            "type": kind,
            "zIndex": per_screen[screen_id] * 10,
            "label": label,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "bg": bg,
            "fg": fg,
            "font": font,
            "visible": True,
            "opacity": 100,
            "value": value,
            "min": minimum,
            "max": maximum,
            "step": step,
            "checked": checked,
            "items": list(items or []),
            "assetId": None,
            "action": action,
            "actionMessage": action_message,
            "targetId": "",
            "custom": {},
        })
        return component_id

    def flow(component_id: str, action: str, *, target_screen: str = "",
             message: str = "") -> None:
        flow_id = f"flow-{len(flows) + 1:03d}"
        flows.append({
            "id": flow_id,
            "componentId": component_id,
            "event": "activate",
            "action": action,
            "targetId": "",
            "targetScreen": target_screen,
            "message": message,
            "value": "",
            "enabled": True,
        })

    def text(screen_id: str, ident: str, label: str, x: float, y: float,
             w: float, h: float, font: int = 18, color: str = "#183247") -> str:
        return add(screen_id, ident, "text", label, x, y, w, h, font=font, fg=color)

    def button(screen_id: str, ident: str, label: str, x: float, y: float,
               w: float, h: float, *, target: str = "", message: str = "",
               font: int = 16) -> str:
        result = add(screen_id, ident, "button", label, x, y, w, h, font=font,
                     bg="#e3f3f7", fg="#155c78", action="notify",
                     action_message=message or ("Abrir: " + label))
        if target:
            flow(result, "navigate", target_screen=target)
        elif message:
            flow(result, "notify", message=message)
        return result

    def heading(screen_id: str, kicker: str, title: str, subtitle: str = "") -> None:
        text(screen_id, f"{screen_id}-kicker", kicker, 118, 224, 1500, 32, 14, "#155c78")
        text(screen_id, f"{screen_id}-title", title, 118, 263, 1580, 50, 28)
        if subtitle:
            text(screen_id, f"{screen_id}-subtitle", subtitle, 118, 307, 1580, 48, 15, "#718494")

    atlas_paths = sorted((root / "artwork/garments").glob("garment-atlas-*.png"))
    if len(atlas_paths) != 6:
        raise SystemExit("El arte de prendas debe contener exactamente seis atlas PNG generados.")
    atlas_assets = []
    for index, path in enumerate(atlas_paths):
        image_data = base64.b64encode(path.read_bytes()).decode("ascii")
        atlas_assets.append({
            "id": path.stem,
            "name": f"Atlas de prendas {index + 1:02d} · ilustraciones originales",
            "fileName": path.name,
            "mime": "image/png",
            "size": path.stat().st_size,
            "dataUrl": f"data:image/png;base64,{image_data}",
        })
    font_path = root / UNICODE_FONT_PATH
    try:
        font_data = font_path.read_bytes()
    except OSError as exc:
        raise SystemExit(f"Unicode TTF asset is missing: {UNICODE_FONT_PATH} ({exc})") from exc
    font_asset = {
        "id": UNICODE_FONT_ASSET_ID,
        "name": "Inter Regular · Fuente Unicode",
        "fileName": font_path.name,
        "mime": "font/ttf",
        "size": len(font_data),
        "dataUrl": "data:font/ttf;base64," + base64.b64encode(font_data).decode("ascii"),
    }
    project_assets = atlas_assets + [font_asset]

    # Menú principal
    add("screen-main", "main-frame", "panel", "Taller de Colada", 88, 194, 1744, 708,
        font=20, bg="#f9fbfc", fg="#155c78")
    add("screen-main", "main-machine-card", "card", "Lavadora educativa 2D", 132, 232,
        604, 626, font=18, bg="#eaf3f6", fg="#155c78")
    text("screen-main", "main-machine-description",
         "Lee etiquetas, clasifica prendas y prepara cada colada.", 168, 770, 520, 76, 17, "#718494")
    text("screen-main", "main-kicker", "MAESTRO LAVANDERO", 812, 267, 850, 36, 16, "#155c78")
    text("screen-main", "main-title", "Prepara la colada", 812, 315, 850, 58, 36)
    text("screen-main", "main-description",
         "Veinte retos de tejidos, programas, productos y cuidado textil.",
         812, 372, 850, 60, 18, "#718494")
    play = button("screen-main", "main-play", "Jugar / continuar", 812, 468, 890, 78,
                  target="screen-levels")
    options = button("screen-main", "main-options", "Opciones", 812, 570, 890, 78,
                     target="screen-settings")
    close = button("screen-main", "main-close", "Cerrar aplicación", 812, 672, 890, 78,
                   message="La salida real del título se gestiona desde el runtime nativo.")
    del play, options, close

    # Opciones
    add("screen-settings", "settings-frame", "panel", "Opciones del juego", 88, 194,
        1744, 708, font=18, bg="#f9fbfc", fg="#155c78")
    heading("screen-settings", "OPCIONES", "Ajustes del sistema")
    add("screen-settings", "settings-volume", "slider", "Volumen de interfaz",
        148, 350, 1624, 76, font=18, bg="#ffffff", value=7, minimum=0, maximum=10, step=1)
    add("screen-settings", "settings-motion", "toggle", "Reducir movimiento",
        148, 446, 1624, 76, font=18, bg="#ffffff", checked=False)
    add("screen-settings", "settings-haptics", "toggle", "Vibración",
        148, 542, 1624, 76, font=18, bg="#ffffff", checked=True)
    add("screen-settings", "settings-confirm", "toggle", "Botón de confirmar: cruz",
        148, 638, 1624, 76, font=18, bg="#ffffff", checked=False)
    back_settings = button("screen-settings", "settings-back", "Volver al menú", 148, 734,
                           1624, 76, target="screen-main")
    del back_settings

    # Mapa de niveles: los nombres se extraen del catálogo de juego real.
    add("screen-levels", "levels-frame", "panel", "Mapa de misiones", 82, 188,
        1756, 746, font=18, bg="#f9fbfc", fg="#155c78")
    heading("screen-levels", "MAPA DE MISIONES", "Elige un nivel")
    level_titles = catalog_titles(root)
    for number, title in level_titles:
        column = (number - 1) % 4
        row = (number - 1) // 4
        x, y = 125 + column * 425, 328 + row * 108
        label = f"NIVEL {number:02d} · {title}"
        level_id = add("screen-levels", f"level-{number:02d}", "button", label,
                       x, y, 392, 92, font=13, bg="#ffffff", fg="#183247",
                       action="notify", action_message="La lógica nativa valida el desbloqueo del nivel.")
        flow(level_id, "navigate", target_screen="screen-sorting")
    levels_back = button("screen-levels", "levels-back", "Volver al menú", 125, 874,
                         392, 42, target="screen-main", font=13)
    del levels_back

    # Clasificación y lectura de etiquetas
    add("screen-sorting", "sorting-frame", "panel", "Clasificación y etiquetas", 82, 188,
        1756, 746, font=18, bg="#f9fbfc", fg="#155c78")
    heading("screen-sorting", "CLASIFICACIÓN Y ETIQUETAS", "Prepara la carga",
            "Las prendas y su misión actual se cargan desde el catálogo nativo de niveles.")
    add("screen-sorting", "sorting-basket", "card", "Cesta de ropa · prendas del nivel actual",
        112, 368, 802, 506, font=17, bg="#ffffff", fg="#155c78")
    add("screen-sorting", "sorting-machine", "card", "Tambor · carga dinámica",
        940, 368, 862, 506, font=17, bg="#f4f8f9", fg="#155c78")
    text("screen-sorting", "sorting-load-rule",
         "8 kg total · 2 kg agua · hasta 6 kg de prendas",
         1342, 420, 420, 42, 14, "#183247")
    label_button = button("screen-sorting", "sorting-read-label", "Leer etiqueta de la prenda",
                          140, 790, 340, 58, target="screen-label", font=14)
    treatment_button = button("screen-sorting", "sorting-treatment", "Mancha y bolsa de malla",
                              496, 790, 390, 58, target="screen-treatment", font=14)
    machine_button = button("screen-sorting", "sorting-machine-open", "Configurar lavado",
                            964, 790, 370, 58, target="screen-machine", font=14)
    manual_button = button("screen-sorting", "sorting-manual", "Manual breve",
                           1350, 790, 350, 58, target="screen-manual", font=14)
    sorting_map = button("screen-sorting", "sorting-map", "Volver al mapa", 118, 872,
                         300, 44, target="screen-levels", font=13)
    del label_button, treatment_button, machine_button, manual_button, sorting_map

    # Etiqueta de cuidado
    add("screen-label", "label-frame", "panel", "Etiqueta de cuidado", 310, 222,
        1300, 670, font=18, bg="#ffffff", fg="#155c78")
    text("screen-label", "label-kicker", "ETIQUETA DE CUIDADO", 370, 267, 800, 32, 14, "#155c78")
    text("screen-label", "label-garment", "Prenda seleccionada · etiqueta real del nivel",
         370, 309, 1160, 46, 24)
    add("screen-label", "label-weight", "card", "Peso en seco · dato de la prenda",
        700, 368, 850, 48, font=14, bg="#f8fafb")
    add("screen-label", "label-temperature", "card", "Lavado máximo · temperatura de etiqueta",
        700, 422, 850, 48, font=14, bg="#f8fafb")
    add("screen-label", "label-spin", "card", "Centrifugado máximo · velocidad de etiqueta",
        700, 476, 850, 48, font=14, bg="#f8fafb")
    add("screen-label", "label-fabric", "card", "Tejido, color y composición",
        700, 530, 850, 48, font=14, bg="#f8fafb")
    add("screen-label", "label-bleach", "card", "Blanqueador · permitido por la etiqueta",
        700, 584, 850, 48, font=14, bg="#f8fafb")
    add("screen-label", "label-softener", "card", "Suavizante · compatibilidad del tejido",
        700, 638, 850, 48, font=14, bg="#f8fafb")
    add("screen-label", "label-stain", "card", "Mancha y protección de la prenda",
        700, 692, 850, 48, font=14, bg="#f8fafb")
    label_confirm = button("screen-label", "label-confirm", "Confirmar lectura", 700, 780,
                           390, 56, target="screen-sorting", font=14)
    label_manual = button("screen-label", "label-manual", "Abrir manual breve", 1110, 780,
                          390, 56, target="screen-manual", font=14)
    del label_confirm, label_manual

    # Tratamiento y malla
    add("screen-treatment", "treatment-frame", "panel", "Pretratamiento y malla",
        470, 250, 980, 595, font=18, bg="#ffffff", fg="#155c78")
    heading("screen-treatment", "CUIDADO DE PRENDA", "Pretratamiento y protección",
            "Las manchas y necesidades de malla dependen de la prenda elegida.")
    treatments = (
        "Sin tratamiento", "Quitagrasas", "Enzimas en frío", "Cepillado previo",
        "Quitamanchas de oxígeno",
    )
    for index, name in enumerate(treatments):
        treatment_id = button("screen-treatment", f"treatment-choice-{index + 1}", name,
                              530, 420 + index * 61, 860, 52,
                              target="screen-sorting", font=14)
        del treatment_id
    mesh = add("screen-treatment", "treatment-mesh", "toggle", "Preparar bolsa de malla",
               530, 730, 860, 54, font=15, bg="#f8fafb", checked=False)
    flow(mesh, "notify", message="La lógica nativa aplica la malla según la prenda seleccionada.")
    treatment_back = button("screen-treatment", "treatment-back", "Volver a la cesta",
                            530, 790, 860, 48, target="screen-sorting", font=14)
    del treatment_back

    # Panel de la lavadora
    add("screen-machine", "machine-frame", "panel", "Panel de lavado", 82, 188,
        1756, 746, font=18, bg="#f9fbfc", fg="#155c78")
    heading("screen-machine", "PANEL DE LAVADO", "Configura la lavadora",
            "Los límites efectivos son los valores más bajos de todas las prendas cargadas.")
    add("screen-machine", "machine-illustration", "card", "Lavadora estándar · tambor 2D animado",
        120, 360, 340, 442, font=16, bg="#eaf3f6", fg="#155c78")
    text("screen-machine", "machine-capacity", "Capacidad: 8 kg totales · agua: 2 kg · prendas: hasta 6 kg",
         514, 357, 1250, 34, 15)
    settings = (
        ("Puerta", "Abierta / cerrada"),
        ("Programa", "Algodón · sintéticos · delicados · lana · deporte · rápido · eco"),
        ("Temperatura", "20 · 30 · 40 · 60 · 90 °C · nunca superar la prenda más delicada"),
        ("Centrifugado", "0 · 400 · 800 · 1200 · 1400 RPM · nunca superar la prenda más delicada"),
        ("Detergente", "Universal · color · lana · deporte · eco · ninguno"),
        ("Suavizante", "Estándar · hipoalergénico · ninguno"),
        ("Aditivo / lejía", "Oxígeno activo · protector de color · cloro · ninguno"),
    )
    for index, (title, value) in enumerate(settings):
        y = 402 + index * 50
        add("screen-machine", f"machine-setting-{index + 1}", "select",
            f"{title} · {value}", 514, y, 1256, 44, font=13, bg="#ffffff",
            items=[part.strip() for part in value.split("·")])
    start = button("screen-machine", "machine-start", "Iniciar lavado",
                   514, 766, 610, 52, target="screen-running", font=16)
    back_sorting = button("screen-machine", "machine-garments", "Volver a prendas",
                          1160, 766, 610, 52, target="screen-sorting", font=15)
    del start, back_sorting
    machine_manual = button("screen-machine", "machine-manual", "Consultar manual breve",
                            514, 824, 610, 42, target="screen-manual", font=13)
    del machine_manual

    # Manual breve
    add("screen-manual", "manual-frame", "panel", "Manual breve de bolsillo",
        330, 210, 1260, 700, font=18, bg="#ffffff", fg="#155c78")
    text("screen-manual", "manual-kicker", "MANUAL BREVE DE BOLSILLO", 390, 255,
         1080, 34, 14, "#155c78")
    text("screen-manual", "manual-title", "Lee la etiqueta antes de lavar", 390, 296,
         1080, 48, 26)
    manual_sections = (
        ("CAPACIDAD", "8 kg totales. Reserva 2 kg para el agua y carga hasta 6 kg de prendas secas."),
        ("TEMPERATURA Y GIRO", "Cada prenda define su máximo; toda la carga adopta el menor límite."),
        ("DETERGENTE", "Elige un producto compatible con el tejido y el color."),
        ("SUAVIZANTE Y LEJÍA", "Respeta la etiqueta; el cloro no sustituye al oxígeno activo."),
        ("MANCHAS Y MALLA", "Trata la mancha antes del ciclo y prepara la bolsa cuando la prenda lo indique."),
    )
    for index, (title, body) in enumerate(manual_sections):
        y = 362 + index * 84
        text("screen-manual", f"manual-section-{index + 1}", title,
             416, y, 1080, 25, 12, "#155c78")
        text("screen-manual", f"manual-body-{index + 1}", body,
             416, y + 25, 1080, 48, 14, "#718494")
    manual_back = button("screen-manual", "manual-back", "Volver a la misión",
                         390, 800, 1080, 52, target="screen-sorting", font=14)
    del manual_back

    # Ciclo en marcha
    add("screen-running", "running-frame", "panel", "Ciclo en marcha", 82, 188,
        1756, 746, font=18, bg="#f9fbfc", fg="#155c78")
    heading("screen-running", "CICLO EN MARCHA", "Lavado en curso",
            "El tambor y las fases se animan desde el runtime nativo.")
    add("screen-running", "running-machine", "card", "Lavadora · llenado · lavado · aclarado · centrifugado",
        280, 360, 470, 490, font=16, bg="#eaf3f6", fg="#155c78")
    add("screen-running", "running-progress", "progress", "Progreso del ciclo",
        862, 410, 760, 40, font=16, bg="#d4e1e7", fg="#2a8eaa",
        value=0, minimum=0, maximum=100, step=1)
    for index, phase in enumerate(("LLENADO", "LAVADO", "ACLARADO", "CENTRIFUGADO")):
        text("screen-running", f"running-phase-{index + 1}", phase,
             862 + index * 195, 475, 184, 32, 11, "#155c78")
    text("screen-running", "running-cycle-note",
         "La animación nativa avanza por tiempo y abre el informe al finalizar el ciclo.",
         862, 730, 748, 58, 15, "#718494")

    # Informe del ciclo
    add("screen-report", "report-frame", "panel", "Informe de lavado", 88, 194,
        1744, 708, font=18, bg="#f9fbfc", fg="#155c78")
    heading("screen-report", "INFORME DE LAVADO", "Resultado del nivel",
            "Puntuación, estrellas y recomendaciones se calculan al terminar el ciclo.")
    add("screen-report", "report-score", "badge", "Puntuación · hasta 300 puntos",
        140, 360, 460, 50, font=18, bg="#e3f3f7", fg="#155c78")
    add("screen-report", "report-feedback", "card", "Evaluación y recomendaciones de cuidado",
        140, 424, 1640, 231, font=17, bg="#ffffff", fg="#183247")
    report_next = button("screen-report", "report-next", "Siguiente nivel",
                         140, 704, 370, 78, target="screen-levels", font=15)
    report_retry = button("screen-report", "report-retry", "Repetir misión",
                          550, 704, 370, 78, target="screen-sorting", font=15)
    report_map = button("screen-report", "report-map", "Mapa de niveles",
                        960, 704, 370, 78, target="screen-levels", font=15)
    report_home = button("screen-report", "report-home", "Volver al menú",
                         1370, 704, 370, 78, target="screen-main", font=15)
    del report_next, report_retry, report_map, report_home

    # Pausa
    add("screen-pause", "pause-frame", "panel", "Misión en pausa",
        540, 310, 840, 465, font=18, bg="#ffffff", fg="#155c78")
    text("screen-pause", "pause-title", "MISIÓN EN PAUSA", 600, 342,
         720, 38, 15, "#155c78")
    for index, (label, target) in enumerate((
        ("Continuar", "screen-running"),
        ("Reiniciar nivel", "screen-sorting"),
        ("Mapa de niveles", "screen-levels"),
        ("Menú principal", "screen-main"),
    )):
        pause_action = button("screen-pause", f"pause-action-{index + 1}", label,
                              600, 392 + index * 70, 720, 54,
                              target=target, font=15)
        del pause_action

    # The native source draws atlas cells by garment ID. Hidden image widgets
    # keep all six source PNGs linked so Visual-PS5 packages their RGBA assets.
    for index, asset in enumerate(atlas_assets):
        component_id = add(
            "screen-main", f"garment-art-atlas-{index + 1:02d}", "image",
            f"Recurso de juego: {asset['name']}", 1780, 980 + index * 16,
            16, 16, bg="transparent", fg="#183247",
        )
        component = next(item for item in components if item["id"] == component_id)
        component["assetId"] = asset["id"]
        component["visible"] = False
        component["opacity"] = 0

    if any(count == 0 for count in per_screen.values()):
        empty = [screen_id for screen_id, count in per_screen.items() if count == 0]
        raise SystemExit("Visual import contains screens without components: " + ", ".join(empty))

    code = native_source(root)
    digest_input = "\n".join(read_source(root, f) for f in SOURCE_FILES).encode("utf-8")
    digest_input += read_source(root, "tools/generate-garment-art.py").encode("utf-8")
    digest_input += (root / "artwork/garments/manifest.json").read_bytes()
    digest_input += font_data
    digest_input += b"".join(path.read_bytes() for path in atlas_paths)
    digest = hashlib.sha256(digest_input).hexdigest()
    project_name = "Taller de Colada · Juego nativo"
    return {
        "format": "ps5vproj",
        "formatVersion": 1,
        "name": project_name,
        "backend": "opengl-ui",
        "resolution": {"width": 1920, "height": 1080},
        "theme": {"background": "#F0F5F7", "accent": "#2A8EAA", "text": "#183247"},
        "components": components,
        "flows": flows,
        "assets": project_assets,
        "fontAssetId": UNICODE_FONT_ASSET_ID,
        "screens": [{"id": screen_id, "name": name} for screen_id, name in SCREENS],
        "currentScreen": "screen-main",
        "settings": {"titleId": "PPSA19918", "firmware": "12.00", "moduleKind": "app"},
        "manualCode": True,
        "customCode": code,
        "updatedAt": updated_at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "portingNotes": {
            "backend": "opengl-ui",
            "nativeSource": "src/concepts/taller_menu.cpp",
            "manualSource": "src/ide/ps5hs-screen.cpp",
            "sourceDigest": digest,
            "resourceLimit": "Seis atlas RGBA8 con 92 ilustraciones textiles originales; dentro del límite nativo de 16 texturas de 512x512.",
            "note": "Modelo Visual-PS5 con controles distribuidos por las once pantallas. El C++ manual conserva catálogo, reglas, navegación, guardado y ciclo del juego. Regenerar el código desde el lienzo sustituye esa lógica por la pantalla visual básica.",
            "featureSet": "Veinte niveles; carga total de 8 kg con 2 kg de agua y máximo de 6 kg de prendas; lectura de etiquetas; límites mínimos de temperatura y centrifugado; detergentes, suavizantes, aditivos, lejías, tratamientos y malla; ciclo 2D animado; progreso persistente.",
            "locales": "Interfaz en español. Los datos dinámicos de prendas, etiquetas, puntuación y progreso se resuelven en el C++ manual.",
            "canvasRole": "Diseño y navegación de referencia. La implementación ejecutable y las reglas están en manualCode, como admite el contrato C++20 de Visual-PS5.",
        },
    }


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def serialized(project: dict) -> str:
    return json.dumps(project, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--check", action="store_true", help="fail if generated import files are stale")
    args = parser.parse_args()
    root = args.root.resolve()
    art_command = [sys.executable, str(root / "tools/generate-garment-art.py")]
    if args.check:
        art_command.append("--check")
    art_result = subprocess.run(art_command, cwd=root, check=False)
    if art_result.returncode != 0:
        raise SystemExit(art_result.returncode)
    import_path = root / "TallerColadaPS5-Principal.ps5vproj"
    try:
        current = json.loads(import_path.read_text(encoding="utf-8"))
        updated_at = current.get("updatedAt") if isinstance(current, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError):
        updated_at = None
    project = build_project(root, updated_at)
    project_json = serialized(project)
    source_path = root / "src/ide/ps5hs-screen.cpp"
    outputs = {
        root / "ps5hs-model.json": project_json,
        import_path: project_json,
        source_path: project["customCode"],
    }
    stale = [path for path, content in outputs.items()
             if not path.is_file() or path.read_text(encoding="utf-8") != content]
    if args.check:
        if stale:
            raise SystemExit("Visual-PS5 import is stale; run tools/sync-ide-project.py: "
                             + ", ".join(str(path.relative_to(root)) for path in stale))
        print(f"Visual-PS5 import is synchronized: {len(project['screens'])} screens, "
              f"{len(project['components'])} components, {len(project['flows'])} flows.")
        return 0
    for path, content in outputs.items():
        write_atomic(path, content)
    print(f"Synchronized {len(project['screens'])} screens, {len(project['components'])} components, "
          f"{len(project['flows'])} visual flows, and the complete manual C++ game source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
