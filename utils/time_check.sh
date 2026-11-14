# Time helpers for log lines.

# "2026-11-14 17:30:01"
current_time() {
    date '+%Y-%m-%d %H:%M:%S'
}

# elapsed_time <start_epoch_seconds>  ->  "01h:02m:03s"
elapsed_time() {
    local s=$(( $(date +%s) - $1 ))
    printf '%02dh:%02dm:%02ds' $(( s / 3600 )) $(( s % 3600 / 60 )) $(( s % 60 ))
}
