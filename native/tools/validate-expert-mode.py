#!/usr/bin/env python3
"""Static regression checks for the HS-6008/LOGI PRO expert-mode integration."""
from __future__ import annotations
import base64, hashlib, json, re, struct, sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/concepts/ps5hs_generated.cpp'
MODEL = ROOT / 'ps5hs-model.json'
PROJECT = ROOT / 'TallerColadaPS5-Principal.ps5vproj'
MANIFEST = ROOT / 'assets/ps5hs/manifest.json'
errors: list[str] = []

def require(ok: bool, msg: str) -> None:
    if not ok: errors.append(msg)

source = SOURCE.read_text(encoding='utf-8')
model = json.loads(MODEL.read_text(encoding='utf-8'))
project = json.loads(PROJECT.read_text(encoding='utf-8'))
require(model.get('customCode') == source, 'ps5hs-model.json customCode differs from canonical C++ source')
require(project.get('customCode') == source, '.ps5vproj customCode differs from canonical C++ source')
require('static constexpr const char *kExpertLogiPrograms[8][8]' in source, 'localized LOGI PRO P-1..P-8 table is missing')
require('P-2: 56 min and 7 phases' in source or 'P-2 · Blancos muy sucios' in source, 'real P-2 expert mission definition is missing')
require('P-1 · Suciedad extrema' in source and '66 min · 8 fases' in source, 'P-1 duration/phase definition is missing')
require('P-7 · Sintéticos' in source and '30 min · 5 fases' in source, 'P-7 duration/phase definition is missing')
require('P-8 · Lana y delicados' in source and '31 min · 5 fases' in source, 'P-8 duration/phase definition is missing')
require('static constexpr int temps[] = {0,20,30,40,60,80,90};' in source, '80 °C is not selectable')
require('program_has_heating(program_) ? temps[pos] : 0' in source, 'temperature controls are not context-aware for LOGI PRO programs')
require('wrapped_text_box' in source and 'right_text' in source, 'measured-width/edge-aligned text helpers are missing')
require('image_resource(draw,0,Rect{122,201,470,714})' in source.replace(' ',''), 'realistic machine texture is not used in the active washer view')
# Strictly validate machine image + RGBA payload.
manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
entries = [x for x in manifest if x.get('id') == 'asset-machine']
require(len(entries) == 1, 'manifest must contain exactly one machine texture')
if entries:
    entry=entries[0]
    raw_path=ROOT/'assets/ps5hs/asset-machine.rgba'
    raw=raw_path.read_bytes()
    require(len(raw)>=8, 'machine RGBA payload is truncated')
    if len(raw)>=8:
        w,h=struct.unpack('<II',raw[:8])
        require((w,h)==(340,512), f'machine RGBA dimensions are {(w,h)}, expected (340,512)')
        require(len(raw)==8+w*h*4, 'machine RGBA payload size does not match dimensions')
        require(hashlib.sha256(raw).hexdigest()==entry.get('sha256'), 'machine RGBA SHA-256 mismatches manifest')
        require(w==entry.get('width') and h==entry.get('height'), 'machine RGBA dimensions mismatch manifest')
img_path=ROOT/'assets/machine.png'
img=Image.open(img_path).convert('RGBA')
require(img.size==(340,512), f'machine PNG dimensions are {img.size}, expected (340,512)')
require(img.getchannel('A').getextrema()[0] == 0, 'machine PNG has no transparent cutout background')
png_bytes=img_path.read_bytes()
asset_model=[a for a in model.get('assets',[]) if a.get('id')=='asset-machine']
asset_proj=[a for a in project.get('assets',[]) if a.get('id')=='asset-machine']
require(len(asset_model)==1 and asset_model[0].get('size')==len(png_bytes), 'model PNG asset metadata is stale')
require(len(asset_proj)==1 and asset_proj[0].get('size')==len(png_bytes), 'project PNG asset metadata is stale')
if asset_proj:
    url=asset_proj[0].get('dataUrl','')
    require(url.startswith('data:image/png;base64,'), 'project machine image is not embedded as PNG data URL')
    if url.startswith('data:image/png;base64,'):
        try: require(base64.b64decode(url.split(',',1)[1])==png_bytes, 'embedded machine PNG differs from assets/machine.png')
        except Exception as e: errors.append(f'embedded machine PNG could not be decoded: {e}')
# Ensure the expert selector maps only in expert wash missions and keeps standalone spin semantics.
require('expert_index(selected_mission_) < 4' in source, 'expert-only LOGI PRO program mapping is missing')
require('if (expert == 4) { load_mask_ = 0x3u;' in source, 'spin-only balancing mission setup missing')
# Translation regression: Spanish UI must not contain the former Italian expert strings.
for array_name in ['kExpertMissionSummaries','kExpertMissionGoals','kExpertMissionLoads','kExpertMissionDurations']:
    start=source.find(array_name)
    require(start>=0, f'{array_name} missing')
    if start>=0:
        end=source.find('\n};',start)
        es_row=source[start:end if end>=0 else start+3000].split('{',2)[-1].split('}',1)[0].casefold()
        for bad in ['prepara cotone','carico nominale','ammorbidente','ridistribuisci']:
            require(bad not in es_row, f'{array_name} Spanish row still contains Italian fragment {bad!r}')
if errors:
    print('EXPERT-MODE VALIDATION FAILED')
    for e in errors: print(' -',e)
    sys.exit(1)
print('Expert mode, source/model synchronization, P-1..P-8 timing metadata, temperature controls, machine PNG/RGBA and Spanish regression: OK')
