#!/bin/bash
# the params for checking
install_args_num=0
install_path_num=0
MSSERVICE_RUN_NAME="mindstudio-msserviceprofiler"
PATH_LENGTH=4096
install_for_all_flag=0

function print_log() {
    if [ ! -f "$log_file" ]; then
        echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2"
    else
        echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2" | tee -a $log_file
    fi
}

function get_log_file() {
    local log_dir
    if [ "$UID" = "0" ]; then
		    log_dir="/var/log/ascend_seclog"
	  else
		    log_dir="${HOME}/var/log/ascend_seclog"
	  fi
	  echo "${log_dir}/ascend_install.log"
}

function log_init() {
    if [ ! -f "$log_file" ]; then
        touch $log_file
        if [ $? -ne 0 ]; then
            print_log "ERROR" "touch $log_file permission denied"
            exit 1
        fi
    fi
    chmod 640 $log_file
}

function check_path() {
    local path_str=${1}
    # check the existence of the path
    if [ ! -e "${path_str}" ]; then
        print_log "ERROR" "The path ${path_str} does not exist, please check."
        exit 1
    fi
    # check the length of path
    if [ ${#path_str} -gt ${PATH_LENGTH} ]; then
        print_log "ERROR" "parameter error $path_str, the length exceeds ${PATH_LENGTH}."
        exit 1
    fi
    # check absolute path
    if [[ ! "${path_str}" =~ ^/.* ]]; then
        print_log "ERROR" "parameter error $path_str, must be an absolute path."
        exit 1
    fi
    # black list
    if echo "${path_str}" | grep -Eq '\/{2,}|\.{3,}'; then
        print_log "ERROR" "The path ${path_str} is invalid, cannot contain the following characters: // ...!"
        exit 1
    fi
    # white list
    if echo "${path_str}" | grep -Eq '^\~?[a-zA-Z0-9./_-]*$'; then
        return
    else
        print_log "ERROR" "The path ${path_str} is invalid, only [a-z,A-Z,0-9,-,_] is support!"
        exit 1
    fi
}

function check_cann_path() {
    local cann_path=${1}
    local current_user=$(whoami)
    local cann_path_owner=$(stat -c '%U' "$cann_path")

    if [ "$current_user" != "root" ]; then
        # 1. Check the current executing user and the installation user of cann_path.
        if [ "$current_user" != "$cann_path_owner" ]; then
            print_log "ERROR" "Current user ($current_user) is not the same as the owner of cann_path ($cann_path_owner)."
            exit 1
        fi

        # 2. Check whether the current cann_path is writable (except for the root user).
        if [ ! -w "$cann_path" ]; then
            print_log "ERROR" "cann_path ($cann_path) is not writable by the current user ($current_user)."
            exit 1
        fi
    fi
}


function parse_script_args() {
    while true; do
        if [ "$3" = "" ]; then
            break
        fi
        case "$3" in
        --install-path=*)
            let "install_path_num+=1"
            raw_path=${3#--install-path=}
            install_path="${raw_path%/}/ascend-toolkit/latest"
            [ ! -d ${install_path} ] && mkdir -p ${install_path}
            check_path ${install_path}
            install_path=$(readlink -f ${install_path})
            check_path ${install_path}
            check_cann_path ${install_path}
            shift
            continue
            ;;
        --quiet)
            shift
            continue
            ;;
        --install)
            let "install_args_num+=1"
            shift
            continue
            ;;
        --install-for-all)
            install_for_all_flag=1
            shift
            continue
            ;;
        *)
            print_log "ERROR" "Input option is invalid. Please try --help."
            exit 1
            ;;
        esac
    done
}

function check_args() {
    if [ ${install_args_num} -eq 0 ]; then
        print_log "ERROR" "Input option is invalid. Please try --help."
        exit 1
    fi

    if [ ${install_path_num} -gt 1 ]; then
        print_log "ERROR" "Do not input --install-path many times. Please try --help."
        exit 1
    fi
}

function execute_run() {
    bash install.sh ${install_path} ${package_arch} ${install_for_all_flag}
}

function get_default_install_path() {
    if [ "$UID" = "0" ]; then
        echo "/usr/local/Ascend/ascend-toolkit/latest"
    else
        echo "${HOME}/Ascend/ascend-toolkit/latest"
    fi
}

# init log file
log_file=$(get_log_file)
log_init
# use utils function and constant
install_path=$(get_default_install_path)
#0, this footnote path;1, path for executing run;2, parents' dir for run package;3, run params
parse_script_args $*
check_args
execute_run
print_log "INFO" "${MSSERVICE_RUN_NAME} package install success, the path is: '${install_path}'."