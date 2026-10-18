#!/usr/bin/env python3
# ps5-homebrew-ui - Collect exact CJK glyphs required by localized UI tables.
# Copyright (C) 2026 BlackBearReloaded
# SPDX-License-Identifier: GPL-3.0-or-later
"""Collect exact Japanese and Simplified Chinese code points used by the UI tables.

The font baker consumes one hexadecimal code point per line. This deliberately
uses only actual language rows, not random comments or the other translations.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')
ARRAY_RE = re.compile(r'static constexpr const char\s+\*k(?P<name>\w+)\b(?P<dims>(?:\[[^\]]+\])+)[^=]*=\s*\{')
RANGES = (
    (0x2E80, 0x2EFF), (0x2F00, 0x2FDF), (0x3000, 0x303F),
    (0x3040, 0x30FF), (0x31F0, 0x31FF), (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0xFF00, 0xFFEF),
)

def is_cjk(cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in RANGES)

def cpp_string(token: str) -> str:
    # All UI table literals use JSON-compatible C++ escaping. Fail closed otherwise.
    return json.loads(token)

def find_initializer_end(text: str, open_pos: int) -> int:
    depth = 0
    in_string = False
    escape = False
    for pos in range(open_pos, len(text)):
        ch = text[pos]
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return pos + 1
    raise ValueError('unterminated array initializer')

def split_nested_rows(initializer: str) -> list[str] | None:
    # initialiser includes outer braces. Split nested `{ ... }` rows at depth 2.
    depth = 0
    in_string = False
    escape = False
    row_start = None
    rows: list[str] = []
    for pos, ch in enumerate(initializer):
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == '{':
            depth += 1
            if depth == 2:
                row_start = pos
        elif ch == '}':
            if depth == 2 and row_start is not None:
                rows.append(initializer[row_start:pos + 1])
                row_start = None
            depth -= 1
    return rows if rows else None

def row_strings(row: str) -> list[str]:
    return [cpp_string(m.group(0)) for m in STRING_RE.finditer(row)]

def collect(source: str, language_index: int) -> set[int]:
    found: set[int] = set()
    for m in ARRAY_RE.finditer(source):
        dims = re.findall(r'\[([^\]]+)\]', m.group('dims'))
        if not dims or dims[0].strip() != '8':
            continue
        end = find_initializer_end(source, m.end() - 1)
        initializer = source[m.end() - 1:end]
        rows = split_nested_rows(initializer)
        if rows:
            if len(rows) != 8:
                # Some non-language arrays may share the same spelling; ignore only if
                # the declaration is not eight locale rows, otherwise fail loudly.
                continue
            values = row_strings(rows[language_index])
        else:
            flat = row_strings(initializer)
            if len(flat) != 8:
                continue
            values = [flat[language_index]]
        for value in values:
            found.update(ord(ch) for ch in value if is_cjk(ord(ch)))
    return found

def write_list(path: Path, codepoints: set[int]) -> None:
    if len(codepoints) < 30:
        raise SystemExit(f'implausibly small CJK glyph set for {path}: {len(codepoints)}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(f'{cp:04X}\n' for cp in sorted(codepoints)), encoding='ascii', newline='\n')
    print(f'{path}: {len(codepoints)} unique CJK glyphs')

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path, default=Path('src/concepts/ps5hs_generated.cpp'))
    ap.add_argument('--japanese', type=Path, default=Path('build/cjk-glyphs-jp.txt'))
    ap.add_argument('--chinese', type=Path, default=Path('build/cjk-glyphs-sc.txt'))
    args = ap.parse_args()
    text = args.source.read_text(encoding='utf-8', errors='strict')
    jp = collect(text, 5)
    sc = collect(text, 6)
    if not jp or not sc:
        raise SystemExit('CJK glyph collection returned an empty set; check the locale tables')
    write_list(args.japanese, jp)
    write_list(args.chinese, sc)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
