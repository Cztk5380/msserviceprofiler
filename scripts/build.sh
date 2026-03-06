#!/bin/bash
# This script is used to build msserviceprofiler&&libms_service_profiler.so
# Copyright Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
set -ueo pipefail
CUR_DIR=$(dirname $(readlink -f $0))
TOP_DIR=$(realpath "${CUR_DIR}/..")

MSSERVICE_TEMP_DIR=${TOP_DIR}/build/msservice_tmp
rm -rf ${MSSERVICE_TEMP_DIR}
mkdir -p ${MSSERVICE_TEMP_DIR}
OUTPUT_DIR=${TOP_DIR}/output
RUN_SCRIPT_DIR=${TOP_DIR}/scripts
chmod -R 755 ${RUN_SCRIPT_DIR}
FILTER_PARAM_SCRIPT=${RUN_SCRIPT_DIR}/help.conf
mkdir -p "${OUTPUT_DIR}"
VERSION="26.0.0"
MAKESELF_DIR=${TOP_DIR}/opensource/makeself
CREATE_RUN_SCRIPT=${MAKESELF_DIR}/makeself.sh
CONTROL_PARAM_SCRIPT=${MAKESELF_DIR}/makeself-header.sh
MSSERVICE_RUN_NAME="mindstudio-service-profiler"
MAIN_SCRIPT=main.sh
INSTALL_SCRIPT=install.sh
UN_INSTALL_SCRIPT=uninstall.sh
UPGRADE_SCRIPT=upgrade.sh
VERSION_INFO=version.info

PKG_LIMIT_SIZE=524288000 # 500M

# 编python的whl包
cd ${TOP_DIR}/
python3 -m build --wheel . --outdir ${TOP_DIR}/build/output_whl_dir

# 打包成run包（main.sh、install.sh）
function parse_script_args() {
    if [ $# -gt 1 ]; then
        echo "[ERROR] Too many arguments. Only one arguments are allowed."
        exit 1
    elif [ $# -eq 1 ]; then
        VERSION="$1"
    fi
}

function create_temp_dir() {
    local temp_dir=${1}

    # cp whl包
    cp ${TOP_DIR}/build/output_whl_dir/ms_service_profiler-*.whl ${temp_dir}

    # cp libms_service_profiler.so (from cmake build output)
    local so_file
    so_file=$(find ${TOP_DIR}/build -name "libms_service_profiler.so" -type f 2>/dev/null | head -1)
    if [ -n "$so_file" ] && [ -f "$so_file" ]; then
        cp "$so_file" ${temp_dir}/
    fi

    # cp include/msServiceProfiler (header files for upgrade)
    if [ -d "${TOP_DIR}/cpp/include/msServiceProfiler" ]; then
        mkdir -p ${temp_dir}/include
        cp -r ${TOP_DIR}/cpp/include/msServiceProfiler ${temp_dir}/include/
    fi

    cd ${TOP_DIR}/
    copy_script ${MAIN_SCRIPT} ${temp_dir}
    copy_script ${INSTALL_SCRIPT} ${temp_dir}
    copy_script ${UN_INSTALL_SCRIPT} ${temp_dir}
    copy_script ${UPGRADE_SCRIPT} ${temp_dir}
    copy_script ${VERSION_INFO} ${temp_dir}
}

function copy_script() {
    local script_name=${1}
    local temp_dir=${2}

    if [ -f "${temp_dir}/${script_name}" ]; then
        rm -f "${temp_dir}/${script_name}"
    fi

    cp ${RUN_SCRIPT_DIR}/${script_name} ${temp_dir}/${script_name}
    chmod 500 "${temp_dir}/${script_name}"
}

function get_version() {
    # 如果 VERSION 不是 "none"，直接返回 VERSION
    if [ "${VERSION}" != "none" ]; then
        echo "${VERSION}"
        return
    fi

    # 定义配置文件路径
    local path="${TOP_DIR}/../manifest/dependency/config.ini"

    # 检查配置文件是否存在
    if [ ! -f "${path}" ]; then
        echo "none"
        return
    fi

    # 从配置文件中读取 version
    local version=$(grep -m 1 "^version=" "${path}" | cut -d"=" -f2)

    # 检查读取到的 version 是否为空
    if [ -z "${version}" ]; then
        echo "none"
    else
        echo "${version}"
    fi
}

function get_package_name() {
    local name=${MSSERVICE_RUN_NAME}

    local version=$(echo $(get_version) | cut -d '.' -f 1,2,3)
    local os_arch=$(arch)
    echo "${name}_${version}_${os_arch}.run"
}

function create_run_package() {
    local run_name=${1}
    local temp_dir=${2}
    local main_script=${3}
    local file_param=${4}
    local package_name=$(get_package_name)

    ${CREATE_RUN_SCRIPT} \
    --header ${CONTROL_PARAM_SCRIPT} \
    --help-header ${file_param} \
    --gzip \
    --tar-quietly \
    --complevel 4 \
    --nomd5 \
    --sha256 \
    --chown \
    ${temp_dir} \
    ${OUTPUT_DIR}/${package_name} \
    ${run_name} \
    ./${main_script}
}

function check_file_exist() {
    local temp_dir=${1}

    check_package ${temp_dir}/ms_service_profiler-*.whl ${PKG_LIMIT_SIZE}
    check_package ${temp_dir}/${MAIN_SCRIPT} ${PKG_LIMIT_SIZE}
    check_package ${temp_dir}/${INSTALL_SCRIPT} ${PKG_LIMIT_SIZE}
    check_package ${temp_dir}/${UN_INSTALL_SCRIPT} ${PKG_LIMIT_SIZE}
    check_package ${temp_dir}/${UPGRADE_SCRIPT} ${PKG_LIMIT_SIZE}
    check_package ${temp_dir}/${VERSION_INFO} ${PKG_LIMIT_SIZE}
}

function check_package() {
    local _path="$1"
    local _limit_size=$2
    echo "check ${_path} exists"
    # 检查路径是否存在
    if [ ! -e "${_path}" ]; then
        echo "${_path} does not exist."
        exit 1
    fi

    # 检查路径是否为文件
    if [ -f "${_path}" ]; then
        local _file_size=$(stat -c%s "${_path}")
        # 检查文件大小是否超过限制
        if [ "${_file_size}" -gt "${_limit_size}" ] || [ "${_file_size}" -eq 0 ]; then
            echo "package size exceeds limit:${_limit_size}"
            exit 1
        fi
    fi
}

function main() {
	local main_script=${1}
	local file=${2}

	create_temp_dir ${MSSERVICE_TEMP_DIR}
	check_file_exist ${MSSERVICE_TEMP_DIR}
	create_run_package ${MSSERVICE_RUN_NAME} ${MSSERVICE_TEMP_DIR} ${main_script} ${file}
	check_package ${OUTPUT_DIR}/$(get_package_name) ${PKG_LIMIT_SIZE}
}

cleanup() {
    if [ -n "${MSSERVICE_TEMP_DIR}" ] && [ -d "${MSSERVICE_TEMP_DIR}" ]; then
        rm -rf "${MSSERVICE_TEMP_DIR}"
    fi
}

parse_script_args $*
main ${MAIN_SCRIPT} ${FILTER_PARAM_SCRIPT}
trap cleanup EXIT INT TERM