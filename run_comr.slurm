#!/bin/bash
#SBATCH -A uppmax2026-1-284
#SBATCH -p pelle
#SBATCH -c 16
#SBATCH -t 04:00:00
#SBATCH -J comr
#SBATCH --mail-type=ALL
#SBATCH -o /proj/uppmax2026-1-284/private/dip/CoMR-dip/log/%x.%j.out
#SBATCH -e /proj/uppmax2026-1-284/private/dip/CoMR-dip/log/%x.%j.err

# Run CoMR (NR disabled). RUN_ID/INPUT/OUTPUT are set in utils/config.sh.
# Submit: sbatch run_comr.slurm

cd /proj/uppmax2026-1-284/private/dip/CoMR-dip
source utils/config.sh

CORES=16

mkdir -p "${OUTPUT}" .inline_cache
echo "[$(current_time)] CoMR started: ${INPUT} ($(grep -c '^>' "${INPUT}") sequences) -> ${OUTPUT}"
T0=$(date +%s)

# Full paths inside the container: CoMR runs some tools from inside the output folder.
RC=0
comr_exec snakemake --cores "${CORES}" \
    --configfile config/config_runtime.yaml \
    --config fasta="/opt/CoMR/${INPUT}" output_dir="/opt/CoMR/${OUTPUT}" enable_nr=false \
    || RC=$?
echo "[$(current_time)] snakemake finished, exit code ${RC} ($(elapsed_time "${T0}"))"

# Keep this run's Snakemake log next to the results, then summarise timings.
cp "$(ls -t .snakemake/log/*.snakemake.log | head -n 1)" "${OUTPUT}/snakemake_${RUN_ID}.log" || true
comr_exec python utils/timing_report.py \
    --bench-dir "${OUTPUT}"/benchmarks_* \
    --snakemake-log "${OUTPUT}/snakemake_${RUN_ID}.log" \
    --out-dir "${OUTPUT}" || true

echo "[$(current_time)] total job time: $(elapsed_time "${T0}")"
exit "${RC}"
