#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-screenshots/ui}"
mkdir -p "$out_dir"
export UV_CACHE_DIR="${UV_CACHE_DIR:-.cache/uv}"
export KIVY_HOME="${KIVY_HOME:-.cache/kivy}"

modes=(menu setup tutorial play)

for mode in "${modes[@]}"; do
    uv run python main.py --dev-state "$mode" --window-size 1200x800 --screenshot "$out_dir/desktop-$mode.png" --exit-after 0.2
    uv run python main.py --dev-state "$mode" --window-size 603x1311 --screenshot "$out_dir/iphone17-$mode.png" --exit-after 0.2
done

printf 'Wrote UI screenshots to %s\n' "$out_dir"
