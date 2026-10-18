#!/usr/bin/env bash
# ps5-native-app-boilerplate - Build in a WSL-native copy and return the result.
# Copyright (C) 2026 BlackBearReloaded
# SPDX-License-Identifier: GPL-3.0-or-later
#
# A project on a Windows drive (/mnt/d, ...) cannot hold the symbolic links the build
# creates unless Windows grants the symlink privilege, and it is slow for compilers.
# This script mirrors the project into the Linux filesystem, runs make there, and copies
# the app folder (dist/) back next to the original sources.
#
# usage: tools/wsl-build.sh <project directory> [make target]
# PS5_WSL_WORKDIR overrides the working copy (default ~/.cache/ps5-native-builds/<name>).

set -euo pipefail

src=$(cd -- "${1:?usage: wsl-build.sh <project directory> [make target]}" && pwd)
target=${2:-app}

# Already on the Linux filesystem: nothing to mirror.
case $src in
    /mnt/*) ;;
    *) exec make -C "$src" "$target" ;;
esac

command -v rsync >/dev/null || {
    echo "rsync is required: sudo apt-get install -y rsync" >&2
    exit 2
}

name=$(printf '%s' "${src##*/}" | tr -c 'A-Za-z0-9._-' '_')
work=${PS5_WSL_WORKDIR:-${XDG_CACHE_HOME:-$HOME/.cache}/ps5-native-builds/$name}
case $work in
    /mnt/*)
        echo "PS5_WSL_WORKDIR must be on the Linux filesystem, not $work" >&2
        exit 2
        ;;
esac
mkdir -p "$work"

# build/, dist/ and .deps/ live only in the working copy, so incremental builds, the
# ccache-friendly object tree and the downloaded SDK survive between runs.
printf '==> [wsl-build] Syncing sources to %s\n' "$work"
rsync -a --delete \
    --exclude='/build/' --exclude='/dist/' --exclude='/.deps/' \
    --exclude='/.git/' --exclude='/.vs/' --exclude='/.idea/' \
    "$src/" "$work/"

printf '==> [wsl-build] make %s (Linux filesystem)\n' "$target"
make -C "$work" "$target"

# Only reached when make succeeded, so a failed build never overwrites a good dist/.
if [[ -d $work/dist ]]; then
    printf '==> [wsl-build] Returning dist/ to %s\n' "$src/dist"
    mkdir -p "$src/dist"
    rsync -rt --delete "$work/dist/" "$src/dist/"
fi
[[ ! -f $work/runtime/libc.prx ]] || cp -f -- "$work/runtime/libc.prx" "$src/runtime/libc.prx"
printf '==> [wsl-build] Done. Result: %s\n' "$src/dist"
