MSSERVICE_RUN_NAME="mindstudio-msserviceprofiler"

function print_log() {
    if [ ! -f "$log_file" ]; then
        echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2"
    else
        echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2" | tee -a $log_file
    fi
}

function delete_msserviceprofiler() {
    local install_path="$1"
    if [ -z "$install_path" ]; then
        echo "用法: $0 <install_path>"
        exit 1
    fi
    rm -rf "${install_path%/}/ascend-toolkit/latest/python/site-packages/ms_service_profiler"*
    print_log "INFO" "$MSSERVICE_RUN_NAME uninstalled successfully."
}

delete_msserviceprofiler "$1"