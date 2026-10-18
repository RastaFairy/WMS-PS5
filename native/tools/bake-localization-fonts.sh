#!/usr/bin/env bash
# ps5-homebrew-ui - Build and validate localized fallback font atlases.
# Copyright (C) 2026 BlackBearReloaded
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Source TTFs are fetched at an immutable upstream commit only when the bundled
# atlases lack a required glyph. Generated .huifont atlases ship as app resources.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cache="$root/.deps/localization-fonts/noto-cjk-523d033d6cb47f4a80c58a35753646f5c3608a78"
source_url="https://raw.githubusercontent.com/notofonts/noto-cjk/523d033d6cb47f4a80c58a35753646f5c3608a78"
jp_ttf="$cache/NotoSansJP-VF.ttf"
sc_ttf="$cache/NotoSansSC-VF.ttf"
license="$cache/LICENSE"
mkdir -p "$cache" "$root/build/host" "$root/assets/fonts"

# Always derive the exact code-point lists from the current eight locale tables.
# Projects ship pre-baked .huifont atlases, so normal builds remain offline. Only
# fetch the pinned source TTFs if those atlases cannot cover the current strings.
python3 "$root/tools/collect-cjk-glyphs.py" \
    --source "$root/src/concepts/ps5hs_generated.cpp" \
    --japanese "$root/build/cjk-glyphs-jp.txt" \
    --chinese "$root/build/cjk-glyphs-sc.txt"
if [[ -s "$root/assets/fonts/noto-sans-jp-cjk.huifont" && -s "$root/assets/fonts/noto-sans-sc-cjk.huifont" ]]; then
    if python3 "$root/tools/check-localization.py" --require-fonts; then
        echo '==> Bundled font atlases cover all localized glyphs; skipping network downloads'
        exit 0
    fi
    echo '==> Existing font atlases are stale or incomplete; rebuilding pinned CJK fallbacks'
fi

fetch_pinned() {
    local url=$1 dest=$2 min_size=$3
    if [[ ! -s $dest ]] || [[ $(wc -c <"$dest") -lt $min_size ]]; then
        local temp="$dest.tmp.$$"
        rm -f -- "$temp"
        echo "==> Downloading pinned source: ${dest##*/}"
        curl --fail --location --retry 3 --retry-delay 1 --silent --show-error "$url" -o "$temp"
        [[ -s $temp ]] || { rm -f -- "$temp"; echo "empty download: $url" >&2; exit 2; }
        [[ $(wc -c <"$temp") -ge $min_size ]] || { rm -f -- "$temp"; echo "download too small: $url" >&2; exit 2; }
        mv -f -- "$temp" "$dest"
    fi
}
fetch_pinned "$source_url/Sans/Variable/TTF/Subset/NotoSansJP-VF.ttf" "$jp_ttf" 1000000
fetch_pinned "$source_url/Sans/Variable/TTF/Subset/NotoSansSC-VF.ttf" "$sc_ttf" 1000000
fetch_pinned "$source_url/LICENSE" "$license" 1000
cp -f -- "$license" "$root/assets/fonts/Noto-CJK-OFL.txt"

if [[ ! -x "$root/build/host/bake_font" || "$root/tools/font-baker/bake_font.cpp" -nt "$root/build/host/bake_font" || "$root/third_party/stb/stb_truetype.h" -nt "$root/build/host/bake_font" ]]; then
    cxx=$(command -v "${HOST_CXX:-clang++}")
    echo '==> Building the host-only font baker with strict code-point-list support'
    "$cxx" -std=c++20 -O2 -w "$root/tools/font-baker/bake_font.cpp" -o "$root/build/host/bake_font"
fi

# Cache by the exact font sources, glyph lists, baker, and UI source. We do not
# skip coverage validation even when the fingerprints match.
fpfile="$root/assets/fonts/.cjk-fonts-fingerprint"
fingerprint=$(
    sha256sum "$jp_ttf" "$sc_ttf" "$root/build/cjk-glyphs-jp.txt" "$root/build/cjk-glyphs-sc.txt" \
        "$root/tools/font-baker/bake_font.cpp" "$root/src/concepts/ps5hs_generated.cpp" \
        "$root/src/gfx/font_format.hpp" | sha256sum | cut -d' ' -f1
)
if [[ ! -s "$root/assets/fonts/noto-sans-jp-cjk.huifont" || \
      ! -s "$root/assets/fonts/noto-sans-sc-cjk.huifont" || \
      ! -s "$fpfile" || $(cat "$fpfile") != "$fingerprint" ]]; then
    echo '==> Baking the exact Japanese CJK fallback glyph set'
    "$root/build/host/bake_font" "$jp_ttf" "$root/assets/fonts/noto-sans-jp-cjk.huifont" \
        40 8 2048 list "$root/build/cjk-glyphs-jp.txt"
    echo '==> Baking the exact Simplified Chinese CJK fallback glyph set'
    "$root/build/host/bake_font" "$sc_ttf" "$root/assets/fonts/noto-sans-sc-cjk.huifont" \
        40 8 2048 list "$root/build/cjk-glyphs-sc.txt"
    printf '%s\n' "$fingerprint" >"$fpfile"
else
    echo '==> CJK fallback font outputs match current sources; reusing cached atlases'
fi

python3 "$root/tools/check-localization.py" --require-fonts
