# Shared setup for CoMR run scripts. Source from the repo folder.

set -euo pipefail

# ---- input / output (paths relative to the repo) ----
RUN_ID="paratrimastix_pilot"
INPUT="test_input/paratrimastix_pilot/pilot_100.fasta"
OUTPUT="test_output/paratrimastix_pilot"
# RUN_ID="paratrimastix_full"
# INPUT="test_input/paratrimastix_full/Paratrimastix_pyriformis_predicted_proteome_benchmark.fasta"
# OUTPUT="test_output/paratrimastix_full"
source utils/time_check.sh

trap 'echo "[$(current_time)] ERROR: script exited unexpectedly (exit code $?, line ${LINENO})"' ERR
trap 'echo "[$(current_time)] script finished (exit code $?)"' EXIT

# Run a command inside the CoMR container, from the repo folder (mounted at /opt/CoMR).
# NR is not mounted: runs use enable_nr=false.
comr_exec() {
    apptainer exec \
        --pwd /opt/CoMR \
        --bind "${PWD}:/opt/CoMR" \
        --bind "${PWD}/extra_download/CoMR_DB_hmm:/mnt/databases:ro" \
        --bind "${PWD}/extra_download/targetp-2.0:/mnt/software/targetp-2.0:ro" \
        --bind "${PWD}/.inline_cache:/opt/software/MitoFates/bin/modules/_Inline" \
        extra_download/CoMR.sif \
        "$@"
}
