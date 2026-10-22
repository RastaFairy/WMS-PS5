#!/usr/bin/env python3
"""Validate Visual-PS5's imported canvas and complete native gameplay source."""

from __future__ import annotations

import json
import importlib.util
import base64
import binascii
import math
import re
import struct
import sys
from pathlib import Path

_sync_path = Path(__file__).resolve().with_name("sync-ide-project.py")
_sync_spec = importlib.util.spec_from_file_location("ps5hs_ide_sync", _sync_path)
if _sync_spec is None or _sync_spec.loader is None:
    raise SystemExit("tools/sync-ide-project.py is missing or cannot be loaded")
_sync_module = importlib.util.module_from_spec(_sync_spec)
_sync_spec.loader.exec_module(_sync_module)
IDE_TYPES = _sync_module.IDE_TYPES
build_project = _sync_module.build_project


EXPECTED_SCREEN_IDS = (
    "screen-main",
    "screen-settings",
    "screen-levels",
    "screen-sorting",
    "screen-label",
    "screen-treatment",
    "screen-machine",
    "screen-manual",
    "screen-running",
    "screen-report",
    "screen-pause",
)
SHARED_FIELDS = (
    "format",
    "formatVersion",
    "name",
    "backend",
    "resolution",
    "theme",
    "components",
    "flows",
    "assets",
    "fontAssetId",
    "screens",
    "currentScreen",
    "settings",
    "customCode",
    "manualCode",
    "portingNotes",
)
INTERACTIVE_TYPES = {
    "button", "toggle", "slider", "stepper", "select", "carousel", "list", "input"
}
VALID_FLOW_ACTIONS = {"navigate", "notify"}
EXPECTED_POLICY = {
    "gallerySwitcher": False,
    "touchpadInfoPanel": False,
    "shellHud": False,
    "forwardUnmappedControllerActions": True,
    "defaultL1Action": False,
    "defaultR1Action": False,
    "defaultTouchpadAction": False,
}
IDE_CONTEXT_FIELDS = {"fonts", "catalog", "telemetry", "settings", "settings_changed"}
UNICODE_FONT_ASSET_ID = "taller-font-inter-regular"
UNICODE_FONT_PATH = Path("third_party/fonts/Inter-Regular.ttf")


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{path.name}: cannot read valid UTF-8 JSON ({exc})") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{path.name}: project root must be a JSON object")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def validate_spanish_text_and_fonts(root: Path, project: dict) -> None:
    native_source = project.get("customCode", "")
    source_path = root / "src/concepts/taller_menu.cpp"
    catalog_path = root / "src/game/laundry_levels.cpp"
    for path in (source_path, catalog_path):
        try:
            path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeError) as exc:
            raise SystemExit(f"{path.relative_to(root)}: source is not valid UTF-8 ({exc})") from exc

    literals = re.findall(r'"((?:\\.|[^"\\])*)"', native_source)
    ui_text = "\n".join(literals + [
        str(component.get("label", "")) for component in project.get("components", [])
    ])
    require("\ufffd" not in ui_text,
            "Spanish UI source contains the Unicode replacement character U+FFFD")
    require(not re.search(r"(?:Ã[À-ÿ]|Â[À-ÿ]|â€|ï¿)", ui_text),
            "Spanish UI contains text decoded with the wrong character encoding")
    require(not re.search(r"[A-Za-zÀ-ÿ]\?[A-Za-zÀ-ÿ]", ui_text),
            "Spanish UI contains a question mark in the middle of a word")

    required = set("áéíóúüñÁÉÍÓÚÜÑ¿¡.:,;_'-?+*][")
    required.update(character for character in ui_text if ord(character) > 127)
    for font_name in (
        "inter-regular.huifont", "inter-semibold.huifont",
        "montserrat-medium.huifont", "dejavu-sans-mono.huifont",
        "press-start-2p.huifont", "patrick-hand.huifont",
    ):
        path = root / "assets/fonts" / font_name
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise SystemExit(f"Spanish UI font is missing: {path.relative_to(root)} ({exc})") from exc
        require(len(data) >= 40, f"{font_name}: truncated SDF font file")
        magic, version, atlas_width, atlas_height, *_metrics, glyph_count, kern_count = struct.unpack_from(
            "<IIHHfffffII", data, 0
        )
        require(magic == 0x46505A50 and version == 1 and atlas_width > 0 and atlas_height > 0,
                f"{font_name}: invalid SDF font header")
        glyph_end = 40 + glyph_count * 24
        require(glyph_end <= len(data), f"{font_name}: glyph table is truncated")
        require(len(data) == glyph_end + kern_count * 12 + atlas_width * atlas_height,
                f"{font_name}: font atlas payload size does not match its header")
        glyph_list = [struct.unpack_from("<I", data, 40 + index * 24)[0]
                      for index in range(glyph_count)]
        require(glyph_list == sorted(set(glyph_list)),
                f"{font_name}: glyph table is not sorted and unique for runtime lookup")
        glyphs = set(glyph_list)
        missing = sorted(ord(character) for character in required if ord(character) not in glyphs)
        require(not missing,
                f"{font_name}: missing Spanish or used UI glyphs: "
                + ", ".join(f"U+{codepoint:04X}" for codepoint in missing))


def validate_visual_model(path: Path, project: dict, expected: dict) -> None:
    require(
        project.get("format") == "ps5vproj" and project.get("formatVersion") == 1,
        f"{path.name}: unsupported Visual-PS5 format or version",
    )
    require(project.get("backend") == "opengl-ui", f"{path.name}: backend must be opengl-ui")
    screens = project.get("screens")
    require(isinstance(screens, list), f"{path.name}: screens must be an array")
    ids = [screen.get("id") for screen in screens if isinstance(screen, dict)]
    require(
        len(ids) == len(screens) and tuple(ids) == EXPECTED_SCREEN_IDS,
        f"{path.name}: screen IDs are missing, duplicated, or out of order",
    )
    screen_ids = set(ids)
    require(project.get("currentScreen") in screen_ids, f"{path.name}: currentScreen is unknown")
    require(project.get("settings", {}).get("titleId") == "PPSA19918",
            f"{path.name}: titleId does not match the native title")
    require(project.get("manualCode") is True,
            f"{path.name}: gameplay must use Visual-PS5's manual C++ source path")
    require(project.get("customCode") == expected["customCode"],
            f"{path.name}: manual C++ source is missing or stale")
    require(project.get("fontAssetId") == UNICODE_FONT_ASSET_ID,
            f"{path.name}: a Unicode TTF must be selected for native compilation")
    require(project.get("portingNotes", {}).get("nativeSource") == "src/concepts/taller_menu.cpp",
            f"{path.name}: canonical game source reference is missing")
    require(project.get("portingNotes", {}).get("manualSource") == "src/ide/ps5hs-screen.cpp",
            f"{path.name}: IDE manual source reference is missing")

    components = project.get("components")
    flows = project.get("flows")
    require(isinstance(components, list) and components,
            f"{path.name}: canvas has no screen components")
    require(isinstance(flows, list) and flows,
            f"{path.name}: visual navigation map is missing")
    assets = project.get("assets")
    require(isinstance(assets, list) and len(assets) == 7,
            f"{path.name}: six garment atlases and one Unicode font must be embedded")
    atlas_assets = [asset for asset in assets
                    if isinstance(asset, dict) and asset.get("mime") == "image/png"]
    asset_ids = [asset.get("id") for asset in atlas_assets]
    require(len(atlas_assets) == 6 and len(asset_ids) == 6 and len(set(asset_ids)) == 6,
            f"{path.name}: garment atlas asset IDs are missing or duplicated")
    for asset in atlas_assets:
        require(isinstance(asset, dict), f"{path.name}: image asset must be an object")
        require(asset.get("mime") == "image/png"
                and str(asset.get("fileName", "")).lower().endswith(".png"),
                f"{path.name}: garment atlas must be a PNG resource")
        data_url = asset.get("dataUrl", "")
        require(isinstance(data_url, str) and data_url.startswith("data:image/png;base64,"),
                f"{path.name}: garment atlas has no embedded PNG data")
        try:
            png = base64.b64decode(data_url.partition(",")[2], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise SystemExit(f"{path.name}: invalid embedded PNG data: {exc}") from exc
        require(len(png) == asset.get("size") and png[:8] == b"\x89PNG\r\n\x1a\n",
                f"{path.name}: garment atlas PNG is truncated or has the wrong size")
        require(len(png) >= 24 and struct.unpack_from(">II", png, 16) == (512, 512),
                f"{path.name}: native atlas dimensions must be 512x512")

    font_assets = [asset for asset in assets
                   if isinstance(asset, dict) and asset.get("id") == UNICODE_FONT_ASSET_ID]
    require(len(font_assets) == 1, f"{path.name}: the selected Unicode font asset is missing")
    font_asset = font_assets[0]
    require(font_asset.get("mime") == "font/ttf"
            and str(font_asset.get("fileName", "")).lower().endswith(".ttf"),
            f"{path.name}: selected Unicode font must be a TTF resource")
    font_url = font_asset.get("dataUrl", "")
    require(isinstance(font_url, str) and font_url.startswith("data:font/ttf;base64,"),
            f"{path.name}: selected Unicode TTF is not embedded")
    try:
        font_data = base64.b64decode(font_url.partition(",")[2], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise SystemExit(f"{path.name}: invalid embedded Unicode TTF: {exc}") from exc
    font_path = path.parent / UNICODE_FONT_PATH
    require(len(font_data) == font_asset.get("size") and font_data[:4] in (b"\x00\x01\x00\x00", b"OTTO"),
            f"{path.name}: selected font is truncated or is not a TrueType/OpenType font")
    require(font_data == font_path.read_bytes(),
            f"{path.name}: embedded Unicode font differs from the licensed project font")

    component_ids: set[str] = set()
    components_by_id: dict[str, dict] = {}
    for component in components:
        require(isinstance(component, dict), f"{path.name}: component must be an object")
        component_id = component.get("id")
        require(
            isinstance(component_id, str)
            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{1,63}", component_id),
            f"{path.name}: component has an invalid technical ID",
        )
        require(component_id not in component_ids,
                f"{path.name}: duplicate component ID {component_id!r}")
        component_ids.add(component_id)
        components_by_id[component_id] = component
        require(component.get("screenId") in screen_ids,
                f"{path.name}: component {component_id!r} targets an unknown screen")
        require(component.get("type") in IDE_TYPES,
                f"{path.name}: component {component_id!r} uses an unsupported IDE type")
        for dimension in ("x", "y", "w", "h", "font", "opacity", "value", "min", "max", "step"):
            value = component.get(dimension)
            require(
                isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value),
                f"{path.name}: {component_id!r} has an invalid {dimension}",
            )
        require(
            0 <= component["x"] < 1920 and 0 <= component["y"] < 1080
            and 0 < component["w"] <= 1920 and 0 < component["h"] <= 1080
            and component["x"] + component["w"] <= 1920
            and component["y"] + component["h"] <= 1080,
            f"{path.name}: {component_id!r} extends outside the 1920x1080 canvas",
        )
        if component["type"] in {"select", "carousel", "list"}:
            require(isinstance(component.get("items"), list) and component["items"],
                    f"{path.name}: {component_id!r} needs selectable items")

    image_components = [component for component in components if component.get("type") == "image"]
    require(len(image_components) == 6,
            f"{path.name}: each garment atlas needs exactly one linked hidden image component")
    require({component.get("assetId") for component in image_components} == set(asset_ids),
            f"{path.name}: an atlas is missing a linked image component")
    require(all(component.get("visible") is False and component.get("opacity") == 0
                for component in image_components),
            f"{path.name}: source atlas components must remain invisible in the design canvas")

    for screen_id in screen_ids:
        require(any(component.get("screenId") == screen_id for component in components),
                f"{path.name}: {screen_id!r} has no visual components")

    flow_ids: set[str] = set()
    for flow in flows:
        require(isinstance(flow, dict), f"{path.name}: flow must be an object")
        flow_id = flow.get("id")
        require(isinstance(flow_id, str) and flow_id and flow_id not in flow_ids,
                f"{path.name}: flow ID is empty or duplicated")
        flow_ids.add(flow_id)
        require(flow.get("event") in {"activate", "change", "start", "any"},
                f"{path.name}: {flow_id!r} has an unsupported event")
        require(flow.get("action") in VALID_FLOW_ACTIONS,
                f"{path.name}: {flow_id!r} has an unsupported or unimplemented action")
        source = components_by_id.get(flow.get("componentId"))
        require(source is not None, f"{path.name}: {flow_id!r} has no live component trigger")
        require(source.get("type") in INTERACTIVE_TYPES,
                f"{path.name}: {flow_id!r} is triggered by a non-interactive component")
        if flow["action"] == "navigate":
            require(flow.get("targetScreen") in screen_ids,
                    f"{path.name}: {flow_id!r} navigates to an unknown screen")

    by_id = {component["id"]: component for component in components}

    def follows(first: str, second: str, description: str) -> None:
        upper = by_id[first]
        lower = by_id[second]
        require(upper["y"] + upper["h"] <= lower["y"],
                f"{path.name}: {description} overlap vertically")

    follows("screen-sorting-subtitle", "sorting-basket", "sorting heading and basket")
    follows("screen-machine-subtitle", "machine-illustration", "machine heading and drawing")
    follows("screen-machine-subtitle", "machine-capacity", "machine heading and capacity")
    follows("machine-capacity", "machine-setting-1", "machine capacity and controls")
    follows("machine-setting-7", "machine-start", "machine controls and start action")
    follows("screen-running-subtitle", "running-machine", "running heading and drum")
    follows("screen-report-subtitle", "report-score", "report heading and score")
    follows("report-score", "report-feedback", "report score and feedback")


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent).resolve()
    model_path = root / "ps5hs-model.json"
    import_path = root / "TallerColadaPS5-Principal.ps5vproj"
    native_manifest_path = root / ".ps5hs-project.json"
    runtime_manifest_path = root / ".ps5hs-native-runtime.json"
    model = load_json(model_path)
    imported = load_json(import_path)
    native_manifest = load_json(native_manifest_path)
    runtime_manifest = load_json(runtime_manifest_path)
    garment_manifest = load_json(root / "artwork/garments/manifest.json")

    expected = build_project(root, imported.get("updatedAt"))
    generated_source_path = root / "src/ide/ps5hs-screen.cpp"
    generated_source = generated_source_path.read_text(encoding="utf-8") if generated_source_path.is_file() else ""
    require(generated_source == expected["customCode"],
            "src/ide/ps5hs-screen.cpp is stale; run tools/sync-ide-project.py")
    for field in (
        "format", "formatVersion", "name", "backend", "resolution", "theme",
        "components", "flows", "assets", "fontAssetId", "screens", "currentScreen",
        "settings", "customCode", "manualCode", "updatedAt", "portingNotes",
    ):
        require(model.get(field) == imported.get(field), f"Visual-PS5 files disagree in {field!r}")
        require(model.get(field) == expected.get(field),
                f"Visual-PS5 field {field!r} is stale; run tools/sync-ide-project.py")

    validate_visual_model(model_path, model, expected)
    validate_visual_model(import_path, imported, expected)
    validate_spanish_text_and_fonts(root, model)
    garment_items = garment_manifest.get("items")
    garment_ids = [item.get("id") for item in garment_items if isinstance(item, dict)] \
        if isinstance(garment_items, list) else []
    require(garment_manifest.get("schema") == "taller-colada-garment-art-v1"
            and len(garment_ids) == 92 and len(set(garment_ids)) == 92,
            "Generated garment art manifest must contain 92 unique catalog entries")
    require("find_garment_sprite" in generated_source
            and "draw_garment_image" in generated_source
            and "draw_garment_icon" not in generated_source,
            "Native game must draw the garment-specific atlas cells, without generic icon fallback")
    require('"/app0/assets/ps5hs/garment-atlas-%02u.rgba"' in generated_source,
            "IDE source must load its linked RGBA garment atlas resources from the native asset folder")
    require("draw_drum_water(draw" in generated_source
            and "draw.polygon(boundary.data(), vertex" in generated_source
            and "draw.rounded_rect(Rect{cx - half_width" not in generated_source,
            "Cycle water must follow the drum circle and may not use an unclipped rectangle")
    require("input.is_pressed(Action::page_prev)" in generated_source
            and "input.is_pressed(Action::page_next)" in generated_source
            and "input.is_pressed(Action::touch)" in generated_source,
            "L1/R1 and touchpad actions must be consumed by the game screens")
    require("return_screen_ == Screen::running" in generated_source
            and "else if (return_screen_ == Screen::running)" in generated_source,
            "The manual opened during the wash must render and return to the live cycle screen")
    for index in range(1, 7):
        raw_path = root / "assets/garments" / f"garment-atlas-{index:02d}.rgba"
        try:
            raw = raw_path.read_bytes()
        except OSError as exc:
            raise SystemExit(f"Missing native garment atlas {raw_path.relative_to(root)}: {exc}") from exc
        require(len(raw) == 8 + 512 * 512 * 4
                and struct.unpack_from("<II", raw, 0) == (512, 512),
                f"{raw_path.relative_to(root)}: invalid RGBA8 dimensions or byte count")

    context_fields = set(re.findall(r"\bcontext_?\.(\w+)\b", generated_source))
    require(context_fields <= IDE_CONTEXT_FIELDS,
            "IDE manual source reads Context fields missing from the current runtime: "
            + ", ".join(sorted(context_fields - IDE_CONTEXT_FIELDS)))
    runtime_entry = (root / "src/main.cpp").read_text(encoding="utf-8")
    data_roots = re.findall(
        r'^\s*constexpr\s+const\s+char\s*\*\s*kDataRoot\s*=\s*"([^"]+)"\s*;',
        runtime_entry,
        re.MULTILINE,
    )
    require(len(data_roots) == 1 and data_roots[0].startswith("/"),
            "src/main.cpp must expose one absolute persistent data root")
    save_path = f'game::load_progress("{data_roots[0]}")'
    write_path = f'game::save_progress("{data_roots[0]}", progress_)'
    require(generated_source.count(save_path) == 1 and generated_source.count(write_path) == 1,
            "IDE source must load and save game progress in the runtime's persistent data root")
    require("context.save_root" not in generated_source and "context_.save_root" not in generated_source,
            "IDE source uses save_root, which the current runtime Context does not expose")

    require(
        native_manifest.get("schema") == "ps5hs-native-project"
        and native_manifest.get("template") == "hui-gl"
        and native_manifest.get("visualBackend") == "opengl-ui",
        ".ps5hs-project.json: native OpenGL project identity is invalid",
    )
    require(native_manifest.get("titleId") == "PPSA19918", ".ps5hs-project.json: titleId mismatch")
    require(
        native_manifest.get("visualModel") == model_path.name
        and native_manifest.get("nativeSource") == "src/concepts/taller_menu.cpp",
        ".ps5hs-project.json: canonical model or native game source path is wrong",
    )
    require(
        native_manifest.get("ideManualSource") == "src/ide/ps5hs-screen.cpp"
        and native_manifest.get("visualImportProject") == import_path.name,
        ".ps5hs-project.json: Visual-PS5 source or import path is wrong",
    )
    require(
        native_manifest.get("generatedFromStudio") is True
        and native_manifest.get("nativeRuntimeProfile") == "standalone-native-ui-v1",
        ".ps5hs-project.json: the IDE standalone runtime profile is not selected",
    )
    require(
        runtime_manifest.get("schema") == "ps5hs-native-runtime"
        and runtime_manifest.get("profile") == "standalone-native-ui-v1"
        and runtime_manifest.get("policy") == EXPECTED_POLICY,
        ".ps5hs-native-runtime.json: standalone input and HUD policy is invalid",
    )
    require(
        runtime_manifest.get("managedFiles") == ["src/app/shell.cpp", "src/app/shell_render.cpp"],
        ".ps5hs-native-runtime.json: managed source list is invalid",
    )

    source_path = root / native_manifest["nativeSource"]
    require(source_path.is_file(), f"native game source is missing: {source_path}")
    require("GeneratedScreen final : public app::Concept" in generated_source
            and "explicit GeneratedScreen(app::Context &context)" in generated_source
            and "TallerMenu" not in generated_source
            and "make_ps5hs_generated(app::Context &context)" in generated_source,
            "IDE source does not implement its required OpenGL Concept/factory contract")
    shell_path = root / "src/app/shell.cpp"
    render_path = root / "src/app/shell_render.cpp"
    require(shell_path.is_file() and render_path.is_file(), "native shell source is incomplete")
    shell = shell_path.read_text(encoding="utf-8")
    render = render_path.read_text(encoding="utf-8")
    for marker in (
        "PS5HS_STANDALONE_RUNTIME_ACTIONS_V1",
        "PS5HS_STANDALONE_RUNTIME_UPDATE_V1",
        "PS5HS_STANDALONE_RUNTIME_CHROME_V1",
        "concepts_[current_]->update(input, dt, feedback_);",
    ):
        require(marker in shell, f"native shell is missing the IDE runtime marker {marker!r}")
    for forbidden in (
        "kShellActions",
        "input.is_pressed(Action::page_prev)",
        "input.is_pressed(Action::page_next)",
        "input.is_pressed(Action::touch)",
        "concepts_[current_]->update(forwarded, dt, feedback_)",
        "void Shell::draw_chrome()",
    ):
        require(forbidden not in shell, f"native shell still contains IDE-conflicting code {forbidden!r}")
    require(
        "PS5HS_STANDALONE_RUNTIME_RENDER_V1" in render
        and "draw_chrome();" not in render
        and "renderer.draw(chrome_)" not in render,
        "native renderer still contains the gallery HUD composition",
    )

    param = load_json(root / "sce_sys/param.json")
    require(param.get("titleId") == native_manifest["titleId"], "sce_sys/param.json titleId mismatch")
    print(
        f"Visual-PS5 import contract: valid ({len(model['screens'])} screens, "
        f"{len(model['components'])} components, {len(model['flows'])} flows, "
        "complete manual C++ gameplay source). Standalone native runtime: valid"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
