#!/bin/bash
# install constant
install_path=${1}
package_arch=${2}
install_for_all_flag=${3}
pylocal=y
MSSERVICE_RUN_NAME="mindstudio-msserviceprofiler"

function print_log() {
    if [ ! -f "$log_file" ]; then
        echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2"
    else
        echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2" | tee -a $log_file
    fi
}

function install_whl_package() {
    local _pylocal=$1
    local _package=$2
    local _pythonlocalpath=$3

    print_log "INFO" "Start to install ${_package}."
    if [ ! -f "${_package}" ]; then
        print_log "ERROR" "Install whl The ${_package} does not exist."
        return 1
    fi
    if [ "-${_pylocal}" = "-y" ]; then
        pip3 install --upgrade --no-deps --force-reinstall --disable-pip-version-check "${_package}" -t "${_pythonlocalpath}" > /dev/null 2>&1
    else
        if [ "$(id -u)" -ne 0 ]; then
            pip3 install --upgrade --no-deps --force-reinstall --disable-pip-version-check "${_package}" --user > /dev/null 2>&1
        else
            pip3 install --upgrade --no-deps --force-reinstall --disable-pip-version-check "${_package}" > /dev/null 2>&1
        fi
    fi
    if [ $? -ne 0 ]; then
        print_log "ERROR" "Install ${_package} failed."
        return 1
    fi
    chmod -R u+rwx,go+rx,go-w "${_pythonlocalpath}"
    print_log "INFO" "Install ${_package} success."
    return 0
}

function implement_install() {
	# install whl
  install_whl_package $pylocal ms_service_profiler-*.whl ${install_path%/}/python/site-packages
  if [ $? -ne 0 ]; then
      print_log "ERROR" "Install msserviceprofiler whl failed."
      return 1
  fi
}

function delete_msserviceprofiler() {
    rm -rf ${install_path%/}/python/site-packages/ms_service_profiler*
}

function copy_file() {
	local filename=${1}
	local target_file=$(readlink -f ${2})

	if [ ! -f "$filename" ] && [ ! -d "$filename" ]; then
		return
	fi

	if [ -f "$target_file" ] || [ -d "$target_file" ]; then
		local parent_dir=$(dirname ${target_file})
		local parent_right=$(stat -c '%a' ${parent_dir})

		chmod u+w ${parent_dir}
		chmod -R u+w ${target_file}
		rm -r ${target_file}

		cp -r ${filename} ${target_file}
		chmod -R ${parent_right} ${target_file}
		chmod ${parent_right} ${parent_dir}

		print_log "INFO" "$filename is replaced."
		return
	fi
	print_log "WARNING" "target $filename is non-existent."
}

arch_name="${package_arch}-linux"
delete_msserviceprofiler
implement_install