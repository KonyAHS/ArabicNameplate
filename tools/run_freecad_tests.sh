#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test_script="${1:-${project_dir}/tests/freecad_feature.py}"
freecad_root="/snap/freecad/current/usr/lib"
kf_root="/snap/kf6-core24/current/usr/lib"

if [[ ! -d "${freecad_root}" ]]; then
    echo "FreeCAD snap runtime was not found at ${freecad_root}." >&2
    exit 1
fi

exec env \
    FREECAD_USER_HOME=/tmp/arabic-nameplate-freecad \
    XDG_CACHE_HOME=/tmp/arabic-nameplate-cache \
    XDG_CONFIG_HOME=/tmp/arabic-nameplate-config \
    XDG_DATA_HOME=/tmp/arabic-nameplate-data \
    PYTHONPATH="${freecad_root}:${freecad_root}/python3/dist-packages:${project_dir}${PYTHONPATH:+:${PYTHONPATH}}" \
    LD_LIBRARY_PATH="${freecad_root}:${freecad_root}/x86_64-linux-gnu:${kf_root}:${kf_root}/x86_64-linux-gnu${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}" \
    QT_QPA_PLATFORM=offscreen \
    QT_PLUGIN_PATH="${kf_root}/x86_64-linux-gnu/qt6/plugins" \
    python3 "${test_script}"
