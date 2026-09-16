#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
freecad_root="/snap/freecad/current/usr/lib"
kf_root="/snap/kf6-core24/current/usr/lib"
run_dir="$(mktemp -d /tmp/arabic-nameplate-gui.XXXXXX)"
result_file="${run_dir}/result.txt"
log_file="${run_dir}/freecad.log"

if [[ ! -x "/snap/freecad/current/usr/bin/FreeCAD" ]]; then
    echo "FreeCAD Snap GUI runtime was not found." >&2
    exit 1
fi

set +e
env \
    ARABIC_NAMEPLATE_GUI_RESULT="${result_file}" \
    FREECAD_USER_HOME="${run_dir}/freecad-home" \
    XDG_CACHE_HOME="${run_dir}/cache" \
    XDG_CONFIG_HOME="${run_dir}/config" \
    XDG_DATA_HOME="${run_dir}/data" \
    PYTHONPATH="${freecad_root}:${freecad_root}/python3/dist-packages:${project_dir}${PYTHONPATH:+:${PYTHONPATH}}" \
    LD_LIBRARY_PATH="${freecad_root}:${freecad_root}/x86_64-linux-gnu:${kf_root}:${kf_root}/x86_64-linux-gnu${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}" \
    QT_QPA_PLATFORM=offscreen \
    QT_PLUGIN_PATH="${kf_root}/x86_64-linux-gnu/qt6/plugins" \
    timeout 60s /snap/freecad/current/usr/bin/FreeCAD \
        -M "${project_dir}" "${project_dir}/tests/freecad_gui.FCMacro" \
        >"${log_file}" 2>&1
freecad_status=$?
set -e

if [[ ${freecad_status} -ne 0 ]]; then
    echo "Native FreeCAD GUI exited with status ${freecad_status}." >&2
    tail -80 "${log_file}" >&2
    [[ -f "${result_file}" ]] && cat "${result_file}" >&2
    exit "${freecad_status}"
fi
if [[ ! -f "${result_file}" ]]; then
    echo "Native FreeCAD GUI produced no result marker." >&2
    exit 1
fi
read -r result_code < "${result_file}"
cat "${result_file}"
echo "FreeCAD GUI log: ${log_file}"
if [[ "${result_code}" != "0" ]]; then
    exit 1
fi
