#!/usr/bin/env bash
# Create and verify the PS5-compatible exFAT-wrapped .ffpfsc from the signed app folder.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
param="$root/sce_sys/param.json"
title_id=$(python3 - "$param" <<'PY'
import json,sys
with open(sys.argv[1],encoding='utf-8') as f: print(json.load(f)['titleId'])
PY
)
app="$root/dist/$title_id"
out="$root/dist/$title_id.ffpfsc"
tmp="$out.tmp"
[[ -d "$app" && -f "$app/eboot.bin" && -f "$app/sce_sys/param.json" ]] || { echo "missing signed app folder: $app" >&2; exit 2; }
verify_dir=$(mktemp -d "$root/dist/.${title_id}-verify-XXXXXX")
trap 'rm -rf -- "$verify_dir"; rm -f -- "$tmp"' EXIT
python3 -m venv "$root/.deps/mkpfs-venv"
py="$root/.deps/mkpfs-venv/bin/python"
"$py" -m pip install --disable-pip-version-check -r "$root/tools/requirements-packaging.txt"
rm -f -- "$tmp"
"$py" -m mkpfs pack folder --version PS5 --require-game-files --verify --no-adjust-output-file-extension "$app" "$tmp"
"$py" -m mkpfs verify "$tmp"
"$py" -m mkpfs unpack "$tmp" "$verify_dir" --deep --no-progress --overwrite
diff -qr -- "$app" "$verify_dir"
printf 'exFAT payload matches app folder: %s\n' "$app"
mv -f -- "$tmp" "$out"
sha256sum "$out" | awk '{print $1 "  " $2}' > "$out.sha256"
printf 'Verified package: %s\n' "$out"
printf 'SHA-256: %s\n' "$(cut -d ' ' -f1 "$out.sha256")"
