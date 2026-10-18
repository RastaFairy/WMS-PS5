#!/usr/bin/env python3
# ps5-homebrew-ui - Localized string and baked-font coverage validation.
# Copyright (C) 2026 BlackBearReloaded
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail the build if localized UI strings cannot be represented by baked fonts.

This is a source/asset consistency test, not a translation-quality oracle. It verifies
UTF-8 NFC, all eight locale rows, native JP/SC strings, font-file integrity and glyph coverage.
"""
from __future__ import annotations
import argparse
import json
import re
import struct
import sys
import unicodedata
from pathlib import Path

STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')
ARRAY_RE = re.compile(r'static constexpr const char\s+\*k(?P<name>\w+)\b(?P<dims>(?:\[[^\]]+\])+)[^=]*=\s*\{')
CJK_RANGES = (
    (0x2E80,0x2EFF),(0x2F00,0x2FDF),(0x3000,0x303F),(0x3040,0x30FF),
    (0x31F0,0x31FF),(0x3400,0x4DBF),(0x4E00,0x9FFF),(0xF900,0xFAFF),(0xFF00,0xFFEF),
)
LANGUAGES = ['es','en','fr','ru','de','ja','zh','it']
# Expected number of entries in every localized table, per locale. UiStrings is
# checked against the UiText enum below so adding a key requires updating every row.
EXPECTED_ROW_COUNTS = {
    'UtilityTextureLabels': 9, 'AdditionalTextureLabels': 9,
    'CareTitle': 1, 'CareDisclaimer': 1, 'CareFieldLabels': 6,
    'CareWashModes': 5, 'CareBleach': 3, 'CareTumble': 3, 'CareIron': 4,
    'CareDry': 3, 'CareProfessional': 3, 'CareMaterials': 7, 'CareNotes': 8,
    'LanguageNames': 1, 'MissionTitles': 20, 'MissionSummaries': 20,
    'MissionGoals': 20, 'MissionLoads': 20, 'MissionDurations': 20,
    'LocalizedFaultLabels': 4, 'LocalizedPrograms': 8, 'DifficultyLabels': 3,
    'ManualTitles': 6, 'ManualPages': 6, 'TextureLabels': 7,
    'TextureSpecials': 6, 'PhysicalButtonLabels': 5,
    'ExpertMissionTitles': 5, 'ExpertMissionSummaries': 5, 'ExpertMissionGoals': 5,
    'ExpertMissionLoads': 5, 'ExpertMissionDurations': 5, 'ExpertUiStrings': 11,
    'ExpertLogiPrograms': 8,
    'SimulationUiStrings': 23, 'SimulationManualTitles': 4, 'SimulationManualPages': 4,
}
SPANISH_ACCENT_ERRORS = {
    'accion','cajon','demas','repitelo','puntuacion','todavia','menu','diagnostico',
    'mision','seleccion','energia','pagina','maximo','maxima','minimo','minima','basico',
    'basica','numero','titulo','presion','instruccion','informacion','configuracion',
    'opcion','operacion','reparacion','revision','interaccion','codigo','simbolo','electrico',
    'electrica','electricos','electricas','tambien','despues','facil','util','estandar','limite',
    'limites','cancion','musica','clasificacion','seccion','atencion','preparacion','recomendacion',
    'opcion','sustitucion','sustituciones','visualmente','rapidamente',
    'frio','fria','calido','humedo','humeda','oxigeno','plastico','desague','vacio','vacia',
    'obstaculo','maquina','maquinas','rapido','rapida','algodon','sinteticos','tecnica','tecnico',
    'tecnicos','averia','averias','gestion','automatico','automaticamente','podras','centrifugacion',
    'rotacion','proximo','proxima','comun','comunmente','alimentacion','situacion','conexion','desconexion','limpiala','retirala','conectala','desconectala',
}
FRENCH_ACCENT_ERRORS = {
    'luminosite','selectionner','selection','debloquee','debloquer','debloquent','terminees','desactive',
    'desactivee','desactiver','deja','etre','tres','regle','regler','reinitialiser','echelle','necessaire',
    'necessaires','apres','controle','controlez','eleve','elevee','eleves','elevees','securite','securise',
    'securisee','etiquette','etiquettes','reference','reponse','reponses','verifie','verifier','verifiez',
    'terminee','demarre','demarrer','prelavage','debranche','debranchez','temperatures',
    'vetement','vetements','selectionne','selectionnee','reinitialise','reinitialisee',
    'reparateur','reparation','reglable','reglables','electrique','electriques','evitez',
    'desequilibre','residu','residus','seche','secher','sechage','eteint','eteinte','rincage','deverrouillee','verrouillee',
    'temperature','separe','separer','ameliorer','probleme','problemes','qualite','humidite','libere',
    'liberee','duree','pret','prets','pretee','pretees','sauvegardee','fermee','deverrouille',
}
ITALIAN_ACCENT_ERRORS = {
    'piu','perche','finche','cosi','gia','abilita','qualita','quantita','umidita','elettricita',
    'modalita','priorita','velocita','difficolta','menu','lunedi','martedi','mercoledi','giovedi','venerdi',
}
FALLBACK_MARKERS = (
    'english fallback','use english','remain in english','stays in english',
    'remain English','use English','文本使用英语','仍为英文','英語のまま','英語を使用',
    'japonés y chino usan textos en inglés','日本語と中国語は英語','japonais et chinois restent en anglais',
    'japanisch und chinesisch bleiben englisch','giapponese e cinese restano in inglese',
)

def is_cjk(cp: int) -> bool:
    return any(a <= cp <= b for a,b in CJK_RANGES)

def cpp_string(token: str) -> str:
    return json.loads(token)

def initializer_end(text: str, open_pos: int) -> int:
    depth=0; quoted=False; escape=False
    for i in range(open_pos,len(text)):
        ch=text[i]
        if quoted:
            if escape: escape=False
            elif ch=='\\': escape=True
            elif ch=='"': quoted=False
            continue
        if ch=='"': quoted=True
        elif ch=='{': depth+=1
        elif ch=='}':
            depth-=1
            if depth==0: return i+1
    raise ValueError('unterminated initializer')

def nested_rows(initializer: str) -> list[str]:
    depth=0; quoted=False; escape=False; start=None; result=[]
    for i,ch in enumerate(initializer):
        if quoted:
            if escape: escape=False
            elif ch=='\\': escape=True
            elif ch=='"': quoted=False
            continue
        if ch=='"': quoted=True
        elif ch=='{':
            depth+=1
            if depth==2: start=i
        elif ch=='}':
            if depth==2 and start is not None:
                result.append(initializer[start:i+1]); start=None
            depth-=1
    return result

def parse_tables(source: str):
    tables={}
    for m in ARRAY_RE.finditer(source):
        dims=re.findall(r'\[([^\]]+)\]',m.group('dims'))
        if not dims or dims[0].strip()!='8': continue
        start=source.find('{',m.end()-1)
        end=initializer_end(source,start)
        init=source[start:end]
        rows=nested_rows(init)
        if rows and len(rows)==8:
            values=[[cpp_string(tok) for tok in STRING_RE.findall(row)] for row in rows]
        else:
            flat=[cpp_string(tok) for tok in STRING_RE.findall(init)]
            if len(flat)!=8: continue
            values=[[v] for v in flat]
        tables[m.group('name')]=values
    return tables

def font_glyphs(path: Path) -> set[int]:
    data=path.read_bytes()
    if len(data)<40: raise ValueError(f'{path}: font is too small')
    magic,version,width,height,pixels,sdf,ascent,descent,gap,glyph_count,kern_count=struct.unpack_from('<IIHHfffffII',data,0)
    if magic!=0x46505A50 or version!=1: raise ValueError(f'{path}: invalid huifont header')
    glyph_start=40
    glyph_end=glyph_start+glyph_count*24
    kern_end=glyph_end+kern_count*12
    if len(data)!=kern_end+width*height: raise ValueError(f'{path}: invalid huifont length')
    return {struct.unpack_from('<I',data,glyph_start+i*24)[0] for i in range(glyph_count)}

def source_mission_strings(source: str) -> list[str]:
    start=source.find('static const Mission kMissions[] = {')
    if start<0: return []
    end=source.find('\n};',start)
    if end<0: raise ValueError('unterminated kMissions block')
    return [cpp_string(tok) for tok in STRING_RE.findall(source[start:end+3])]

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,default=Path('src/concepts/ps5hs_generated.cpp'))
    ap.add_argument('--screen-copy',type=Path,default=None)
    ap.add_argument('--model',type=Path,default=Path('ps5hs-model.json'))
    ap.add_argument('--font-dir',type=Path,default=Path('assets/fonts'))
    ap.add_argument('--require-fonts',action='store_true')
    args=ap.parse_args()
    errors=[]
    try:
        source=args.source.read_text(encoding='utf-8',errors='strict')
        screen=(args.screen_copy.read_text(encoding='utf-8',errors='strict')
                if args.screen_copy is not None else None)
        model=json.loads(args.model.read_text(encoding='utf-8',errors='strict'))
    except Exception as ex:
        print(f'ERROR: source/model UTF-8 or JSON error: {ex}',file=sys.stderr); return 2
    if screen is not None and source!=screen: errors.append('generated screen and screen source copy differ; sync before Visual-PS5 regeneration')
    if model.get('customCode')!=source: errors.append('ps5hs-model.json customCode is not byte-for-byte synchronized with generated C++')
    for project_path in sorted(args.source.parent.parent.parent.glob('*.ps5vproj')):
        try:
            project_data=json.loads(project_path.read_text(encoding='utf-8',errors='strict'))
            if 'customCode' in project_data and project_data['customCode']!=source:
                errors.append(f'{project_path.name} customCode is not synchronized with generated C++')
        except Exception as ex:
            errors.append(f'{project_path.name} is not valid UTF-8/JSON: {ex}')
    if '\ufffd' in source: errors.append('source contains the Unicode replacement character U+FFFD')
    if any(marker in source for marker in ('Ã¡','Ã©','Ã­','Ã³','Ãº','Ã±','Ã¼','Â¿','Â¡','â€™','â€œ','â€','ï¿½')):
        errors.append('source contains a known UTF-8 mojibake sequence')
    if '¿¿' in source or '¡¡' in source: errors.append('duplicated Spanish opening punctuation found')
    runtime_source = source[source.find('class GeneratedScreen final'):]
    if 'set_message(\"' in runtime_source:
        errors.append('runtime contains a hardcoded string passed directly to set_message; use UiText for all languages')
    validation_match = re.search(r'std::string validation_error\(\) const\s*\{(.*?)\n    \}', runtime_source, re.S)
    if validation_match and re.search(r'\breturn\s+\"', validation_match.group(1)):
        errors.append('validation_error contains a hardcoded message instead of a localized UiText entry')
    if 'English fallback' in source or 'use English until' in source or 'se simplifican' in source:
        errors.append('old language fallback/simplification messaging remains in source')
    tables=parse_tables(source)
    if not unicodedata.is_normalized('NFC', source):
        errors.append('C++ source is not Unicode NFC; normalize source strings before baking fonts')
    expected_tables = set(EXPECTED_ROW_COUNTS) | {'UiStrings'}
    missing_tables = expected_tables - set(tables)
    unexpected_tables = set(tables) - expected_tables
    if missing_tables:
        errors.append(f'missing localized tables: {sorted(missing_tables)}')
    if unexpected_tables:
        errors.append(f'unregistered localized tables: {sorted(unexpected_tables)}; add explicit row-count validation')
    if len(tables) != len(expected_tables):
        errors.append(f'expected {len(expected_tables)} localized tables, parsed {len(tables)}')
    for table_name, expected_count in EXPECTED_ROW_COUNTS.items():
        rows = tables.get(table_name)
        if rows is None:
            errors.append(f'localized table k{table_name} is missing or could not be parsed')
            continue
        for lang, row in enumerate(rows):
            if len(row) != expected_count:
                errors.append(f'k{table_name}[{LANGUAGES[lang]}] has {len(row)} entries; expected {expected_count}')
            for idx, value in enumerate(row):
                if not value.strip():
                    errors.append(f'k{table_name}[{LANGUAGES[lang]}][{idx}] is empty')
    enum=re.search(r'enum class UiText\s*:\s*std::size_t\s*\{(.*?)\bcount\s*\}',source,re.S)
    if not enum: errors.append('UiText enum not found')
    else:
        keys=[x.strip() for x in enum.group(1).replace('\n',' ').split(',') if x.strip()]
        rows=tables.get('UiStrings')
        if rows is None: errors.append('kUiStrings table not parsed')
        else:
            for i,row in enumerate(rows):
                if len(row)!=len(keys): errors.append(f'kUiStrings locale {LANGUAGES[i]} has {len(row)} strings; expected {len(keys)}')
                for idx, value in enumerate(row):
                    if not value.strip(): errors.append(f'kUiStrings[{LANGUAGES[i]}][{idx}] is empty')
    names=tables.get('LanguageNames')
    expected=['Español','English','Français','Русский','Deutsch','日本語','简体中文','Italiano']
    if names and [r[0] for r in names]!=expected: errors.append(f'language selector names mismatch: {[r[0] for r in names]}')
    # Regression guards for Spanish rows that previously leaked Italian strings.
    spanish_care_wash_modes = (
        'Algodón normal', 'Colores / lavar del revés', 'Lana: muy delicado',
        'Sintéticos: delicado', 'Seda: lavado delicado',
    )
    care_wash_modes = tables.get('CareWashModes')
    if care_wash_modes and tuple(care_wash_modes[0]) != spanish_care_wash_modes:
        for index, expected in enumerate(spanish_care_wash_modes):
            actual = care_wash_modes[0][index] if index < len(care_wash_modes[0]) else '<missing>'
            if actual != expected:
                errors.append(f'CareWashModes[es][{index}] should be {expected!r}, got {actual!r}')
    es_expected = {
        'ExpertMissionTitles': 'P-2 · Blancos muy sucios',
        'ExpertMissionSummaries': 'LOGI PRO P-2:',
        'ExpertMissionGoals': 'Selecciona P-2',
        'ExpertMissionLoads': 'Carga blanca nominal',
        'ExpertMissionDurations': '56 min · 7 fases',
    }
    italian_leaks = ('prepara cotone', 'carico nominale', 'ammorbidente', 'ridistribuisci', 'simulato', 'seleziona p-2', 'programma tabellato', 'carico parziale')
    italian_only_terms = re.compile(
        r'(?i)\b(?:detersivo|ammorbidente|prelavaggio|risciacquo|lavatrice|bucato|'
        r'sportello|manutenzione|tessuto|tessuti|guasto|guasti|guarnizione|'
        r'asciugatura|asciugare|vassoio|rubinetto|sciacquare|cestello|'
        r'lavaggio principale|carico nominale|carico parziale|programma tabellato)\b'
    )
    for table_name, expected_prefix in es_expected.items():
        rows = tables.get(table_name)
        if rows and (not rows[0] or not rows[0][0].startswith(expected_prefix)):
            errors.append(f'{table_name}[es][0] should start with {expected_prefix!r}, got {rows[0][0] if rows[0] else "<empty>"!r}')
        if rows and rows[0]:
            for mission_index, spanish_cell in enumerate(rows[0]):
                if any(leak in spanish_cell.casefold() for leak in italian_leaks):
                    errors.append(f'{table_name}[es][{mission_index}] contains a non-Spanish/Italian-language leak')
    # Extend the regression guard beyond Expert Mode: scan every Spanish table for
    # words and phrases that have clear Spanish equivalents and should not leak from Italian.
    for table_name, rows in tables.items():
        if not rows:
            continue
        for index, spanish_cell in enumerate(rows[0]):
            match = italian_only_terms.search(spanish_cell)
            if match:
                errors.append(f'{table_name}[es][{index}] contains Italian-only term {match.group(0)!r}')
    for table_name, rows in tables.items():
        for lang, row in enumerate(rows):
            for idx, value in enumerate(row):
                if not unicodedata.is_normalized('NFC', value):
                    errors.append(f'{table_name}[{LANGUAGES[lang]}][{idx}] is not Unicode NFC: {value!r}')
    # French machine states are adjectives, not unaccented verb stems.
    if 'UiStrings' in tables and enum:
        keys = [x.strip() for x in enum.group(1).replace('\n',' ').split(',') if x.strip()]
        for key, expected_value in (
            ('state_connected','BRANCHÉ'), ('state_disconnected','DÉBRANCHÉ'),
            ('on','Activée'), ('off','Désactivée'),
        ):
            if key in keys:
                actual = tables['UiStrings'][2][keys.index(key)]
                if actual != expected_value:
                    errors.append(f'French UiText::{key} should be {expected_value!r}, found {actual!r}')
    for table_name in ('UiStrings','MissionTitles','MissionSummaries','MissionGoals','ManualTitles','ManualPages','ExpertMissionTitles','ExpertMissionSummaries','ExpertMissionGoals','ExpertMissionLoads','ExpertMissionDurations','ExpertUiStrings'):
        rows=tables.get(table_name)
        if rows:
            if not any(is_cjk(ord(ch)) for value in rows[5] for ch in value):
                errors.append(f'{table_name}[ja] has no Japanese/CJK characters; locale may have fallen back')
            if not any(is_cjk(ord(ch)) for value in rows[6] for ch in value):
                errors.append(f'{table_name}[zh] has no Chinese/CJK characters; locale may have fallen back')
            if rows[5] == rows[1]: errors.append(f'{table_name}[ja] is identical to English')
            if rows[6] == rows[1]: errors.append(f'{table_name}[zh] is identical to English')
    european_error_sets = {0: SPANISH_ACCENT_ERRORS, 2: FRENCH_ACCENT_ERRORS, 7: ITALIAN_ACCENT_ERRORS}
    word_re = re.compile(r"[A-Za-zÀ-ÿ]+")
    for name,rows in tables.items():
        for lang,row in enumerate(rows):
            for value in row:
                low=value.lower()
                if lang in (5,6) and any(marker.lower() in low for marker in FALLBACK_MARKERS):
                    errors.append(f'{name}[{LANGUAGES[lang]}] contains an obsolete language fallback: {value!r}')
                if '\ufffd' in value:
                    errors.append(f'{name}[{LANGUAGES[lang]}] contains U+FFFD replacement character')
                for word in word_re.findall(value):
                    if word.lower() in european_error_sets.get(lang, set()):
                        errors.append(f'{name}[{LANGUAGES[lang]}] likely missing accent in {word!r}: {value!r}')
    rendered=re.search(r'static int rendered_language\(int language\)\s*\{([^}]+)\}',source)
    if not rendered or '(language == 5' in rendered.group(1) or '(language == 6' in rendered.group(1):
        errors.append('rendered_language still routes Japanese or Chinese to another locale')
    for value in source_mission_strings(source):
        for word in word_re.findall(value):
            if word.lower() in SPANISH_ACCENT_ERRORS:
                errors.append(f'kMissions[es] likely missing accent in {word!r}: {value!r}')
    print(f'Parsed {len(tables)} localized tables; UiText count={len(keys) if enum else 0}; languages=8')
    if not args.require_fonts:
        if errors:
            for e in errors: print('ERROR:',e,file=sys.stderr)
            return 1
        print('Source UTF-8, locale rows, language routing and model synchronization: OK (font coverage not requested)')
        return 0
    font_paths={
      'regular':args.font_dir/'inter-regular.huifont',
      'semibold':args.font_dir/'inter-semibold.huifont',
      'latin_fallback':args.font_dir/'inter-latin-fallback.huifont',
      'jp':args.font_dir/'noto-sans-jp-cjk.huifont',
      'zh':args.font_dir/'noto-sans-sc-cjk.huifont',
    }
    try:
        faces={k:font_glyphs(v) for k,v in font_paths.items()}
    except Exception as ex:
        errors.append(f'font coverage check failed: {ex}')
        faces={}
    if faces:
        base=faces['latin_fallback']
        required={i:set() for i in range(8)}
        for rows in tables.values():
            for lang,row in enumerate(rows):
                for value in row:
                    required[lang].update(ord(ch) for ch in value if ord(ch)>=32)
        required[0].update(ord(ch) for v in source_mission_strings(source) for ch in v if ord(ch)>=32)
        for lang in range(8):
            missing_base=set()
            missing_cjk=set()
            for cp in required[lang]:
                if cp<128: continue
                if is_cjk(cp):
                    face=faces['jp'] if lang==5 else faces['zh'] if lang==6 else None
                    if face is None or cp not in face: missing_cjk.add(cp)
                elif cp not in base:
                    missing_base.add(cp)
            for cp in sorted(missing_base)[:20]: errors.append(f'{LANGUAGES[lang]}: required base-font glyph U+{cp:04X} is missing in regular/semibold')
            for cp in sorted(missing_cjk)[:20]: errors.append(f'{LANGUAGES[lang]}: required CJK glyph U+{cp:04X} missing from fallback atlas')
        print('Font coverage:',', '.join(f'{k}={len(v)} glyphs' for k,v in faces.items()))
    if errors:
        for e in errors: print('ERROR:',e,file=sys.stderr)
        return 1
    print('UTF-8, all eight locales, source/model sync, and required glyph coverage: OK')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
