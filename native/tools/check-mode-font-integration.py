#!/usr/bin/env python3
"""Regression checks for Expert Mode, care labels and native-workspace font fallbacks."""
from __future__ import annotations
import base64
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/concepts/ps5hs_generated.cpp'
source = SOURCE.read_text(encoding='utf-8')

# The code the IDE injects must be exactly the checked-in canonical generated screen.
for name in ('TallerColadaPS5-Principal.ps5vproj', 'ps5hs-model.json'):
    model = json.loads((ROOT / name).read_text(encoding='utf-8'))
    if model.get('customCode') != source:
        raise SystemExit(f'FAIL: {name} customCode is not byte-for-byte synchronized with C++')

# R3 is mapped by the core input layer and is not among the actions consumed by the shell.
input_h = (ROOT / 'src/core/input.hpp').read_text(encoding='utf-8')
shell = (ROOT / 'src/app/shell.cpp').read_text(encoding='utf-8')
if '    r3,' not in input_h:
    raise SystemExit('FAIL: Action::r3 is absent from the input API')
mask = re.search(r'kShellActions\s*=\s*(.*?);', shell, re.S)
if not mask or 'Action::touch' not in mask.group(1) or 'Action::r3' in mask.group(1):
    raise SystemExit('FAIL: expected shell touchpad interception / forwarded R3 contract changed')
if 'if (screen_ == Screen::play && input.is_pressed(hui::Action::r3)) open_care_label();' not in source:
    raise SystemExit('FAIL: care label does not open on forwarded R3')
if 'input.is_pressed(hui::Action::r3)) {' not in source:
    raise SystemExit('FAIL: care label cannot close on R3')
if 'Button::right_stick,ui_text(UiText::care_label)' not in source or 'Button::right_stick,ui_text(UiText::care_label_close)' not in source:
    raise SystemExit('FAIL: UI hints do not indicate the R3 control')
if 'input.is_pressed(hui::Action::touch)) open_care_label()' in source:
    raise SystemExit('FAIL: care-label opening still depends on touchpad')

# R1/L1 are shell-reserved. Square is forwarded and now toggles the modes.
if 'switch_mission_mode(!expert_mode_view_)' not in source:
    raise SystemExit('FAIL: Square does not toggle the mission modes')
if re.search(r'Action::page_(?:next|prev)\)\) switch_mission_mode', source):
    raise SystemExit('FAIL: Expert Mode still depends on R1/L1')
if 'Button::square,expert_text(eu_exit_hint)' not in source or 'Button::square,expert_text(eu_enter_hint)' not in source:
    raise SystemExit('FAIL: mode-switch hints use a control other than Square')
expert_table = source[source.index('static constexpr const char *kExpertUiStrings'):source.index('static constexpr const char *kLocalizedFaultLabels')]
if re.search(r'R1|L1', expert_table):
    raise SystemExit('FAIL: old R1/L1 mode hint remains in localized Expert Mode strings')

# Completion, result-return, and save-load all enter Expert Mode automatically at 20/20.
if 'void return_to_mission_menu()' not in source:
    raise SystemExit('FAIL: central mission-menu transition is absent')
helper = source[source.index('void return_to_mission_menu()'):source.index('void switch_mission_mode(bool to_expert)')]
for required in ('all_missions_complete()', 'expert_mode_view_ = true', 'next_unlocked_expert_mission()', 'selected_mission_ = kMissionCount + expert_selected_mission_'):
    if required not in helper:
        raise SystemExit(f'FAIL: auto Expert Mode transition misses {required}')
activate_start = source.find('void activate()')
activate_end = source.find('void interact_basket(', activate_start)
activate_block = source[activate_start:activate_end] if activate_start >= 0 and activate_end > activate_start else ''
result_handler = re.search(r'if \(screen_ == Screen::result\) \{(.*?)\n        \}', activate_block, re.S)
if not result_handler or 'return_to_mission_menu();' not in result_handler.group(1):
    raise SystemExit('FAIL: standard result screen does not transition automatically to unlocked Expert Mode')
if 'if (simulation_active_) { start_random_simulation_case(); return; }' not in result_handler.group(1):
    raise SystemExit('FAIL: simulation result screen does not offer a new randomized case')
# Saved games with 20/20 standard missions must also enter the expert board without an R1 press.
load_start = source.find('bool load_progress_from_disk()')
load_end = source.find('void clear_progress_memory()', load_start)
if load_start < 0 or load_end < 0:
    raise SystemExit('FAIL: cannot locate save-load transition')
load_block = source[load_start:load_end]
if not re.search(r'else\s*\{\s*expert_mode_view_\s*=\s*true;\s*expert_selected_mission_\s*=\s*next_unlocked_expert_mission\(\);\s*selected_mission_\s*=\s*kMissionCount\s*\+\s*expert_selected_mission_;', load_block):
    raise SystemExit('FAIL: loading a 20/20 save does not open Expert Mode automatically')

# Embedded pre-baked faces must match the binary assets shipped alongside the project.
embedded = {
    'kEmbeddedLatinFontBase64': 'inter-latin-fallback.huifont',
    'kEmbeddedJapaneseFontBase64': 'noto-sans-jp-cjk.huifont',
    'kEmbeddedChineseFontBase64': 'noto-sans-sc-cjk.huifont',
}
for symbol, filename in embedded.items():
    m = re.search(rf'static constexpr char {symbol}\[\]\s*=\s*((?:"[A-Za-z0-9+/=]+"\s*)+);', source, re.S)
    if not m:
        raise SystemExit(f'FAIL: embedded font data {symbol} missing')
    encoded = ''.join(re.findall(r'"([A-Za-z0-9+/=]+)"', m.group(1)))
    decoded = base64.b64decode(encoded, validate=True)
    on_disk = (ROOT / 'assets/fonts' / filename).read_bytes()
    if decoded != on_disk:
        raise SystemExit(f'FAIL: embedded {filename} differs from the shipped asset')
    print(f'OK: {symbol} -> {filename}, {len(decoded)} bytes, SHA-256 {hashlib.sha256(decoded).hexdigest()}')
if 'decode_base64(std::string_view encoded)' not in source or 'loaded = !bytes.empty() && font.load(bytes);' not in source:
    raise SystemExit('FAIL: runtime font decoder/fallback path is not wired into the loader')

print('OK: care labels use R3; Expert Mode auto-unlocks and uses Square; fonts and models are synchronized.')
