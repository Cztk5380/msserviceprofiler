#!/bin/bash

CANN_UNINSTALL_SCRIPT="cann_uninstall.sh"
MSSERVICE_RUN_NAME="mindstudio-msserviceprofiler"

CUR_DIR=$(dirname $(readlink -f $0))
CANN_INSTALL_PATH=$(readlink -f "${CUR_DIR}/../../..")
if [ -z "${1}" ]; then
    install_path=${CANN_INSTALL_PATH}
else
 	  install_path=${1}
fi

function print_log() {
     if [ ! -f "$log_file" ]; then
         echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2"
     else
         echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2" | tee -a $log_file
     fi
}

function delete_register_uninstall() {
    if [ ! -f "${install_path}/${CANN_UNINSTALL_SCRIPT}" ]; then
 	  	  print_log "ERROR" "Failed to delete_register_uninstall, no such file: ${install_path}/${CANN_UNINSTALL_SCRIPT}"
 	  	  return 1
 	  fi
 	  local script_right=$(stat -c '%a' "${install_path}/${CANN_UNINSTALL_SCRIPT}")
 	  chmod u+w "${install_path}/${CANN_UNINSTALL_SCRIPT}"
 	  sed -i "/uninstall_package \"share\/info\/msserviceprofiler\"/d" "${install_path}/${CANN_UNINSTALL_SCRIPT}"
 	  chmod ${script_right} "${install_path}/${CANN_UNINSTALL_SCRIPT}"
}

rm -rf ${install_path%/}/ascend-toolkit/latest/python/site-packages/ms_service_profiler*
rm -rf ${install_path%/}/share/info/msserviceprofiler
delete_register_uninstall