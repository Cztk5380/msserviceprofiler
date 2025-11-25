#!/bin/bash

set -u


CUR_DIR=$(dirname $(readlink -f $0))
OPEN_SOURCE_DIR="${CUR_DIR}/opensource"
PLATFORM_DIR="${CUR_DIR}/platform"


function log_info() {
    echo "[INFO] [$(date '+%Y/%m/%d %H:%M:%S')] $*" >&2
}


function log_error() {
    echo "[ERROR] [$(date '+%Y/%m/%d %H:%M:%S')] $*" 2>&1
}


function check_system_tools() {
    local -a readonly needed_build_tools=("git" "cmake" "make" "wget" "tar" "unzip")

    for tool in "${needed_build_tools[@]}"; do
        if ! command -v "${tool}" > /dev/null; then
            log_error "缺少构建依赖: ${tool}"
            return 1
        fi
    done
}


function build_dependencies() {
    declare -A task_map

    local -a tasks=("build_nlohmann_json" "build_securec" "build_protobuf")
    local -a pids=()
    local failed_count=0

    for task in "${tasks[@]}"; do
        log_info "build dependency: ${task}"
        ${task} &
        local pid=$!
        task_map["${pid}"]="${task}"
        pids+=($pid)
    done

    for pid in "${pids[@]}"; do
        local task="${task_map[${pid}]}"

        if ! wait "$pid"; then
            log_error "build dependency: ${task} - failed"
            ((failed_count++))
        fi
        log_info "build dependency: ${task} - ok"
    done

    return $failed_count
}


function build_nlohmann_json() {
    local NLOHMANN_DIR="${OPEN_SOURCE_DIR}/json"
    [ -d "${NLOHMANN_DIR}" ] && return $?

    [ ! -d "${OPEN_SOURCE_DIR}" ] && mkdir -p "${OPEN_SOURCE_DIR}"
    wget --no-check-certificate "https://cmc-szver-artifactory.cmc.tools.huawei.com/artifactory/cmc-software-release/Baize%20C/AscendTransformerBoost/1.0.0/asdops_dependency/common/nlohmannjson-v3.11.2.tar.gz" > /dev/null 2>&1
    tar xf "nlohmannjson-v3.11.2.tar.gz" -C "${OPEN_SOURCE_DIR}"
    mv "${OPEN_SOURCE_DIR}/nlohmannJson" "${NLOHMANN_DIR}"

}


function build_securec() {
    local SECUREC_DIR="${PLATFORM_DIR}/securec"
    [ -d "${SECUREC_DIR}" ] && return $?
    [ ! -d "${PLATFORM_DIR}" ] && mkdir -p "${PLATFORM_DIR}"
    [ -d "${SECUREC_DIR}" ] || git clone -b tag_Huawei_Secure_C_V100R001C01SPC012B002_00001 https://codehub-dg-y.huawei.com/hwsecurec_group/huawei_secure_c.git ${SECUREC_DIR} > /dev/null 2>&1
    make -C "${SECUREC_DIR}/src" -j $(nproc) --silent
}


function build_protobuf() {
    PROTOBUF_DIR="${OPEN_SOURCE_DIR}/protobuf"

    [ -d "${PROTOBUF_DIR}" ] && return $?
    wget --no-check-certificate https://cmc.cloudartifact.szv.dragon.tools.huawei.com/artifactory/opensource_general/protobuf/3.21.9/package/protobuf-3.21.9.zip > /dev/null 2>&1
    unzip -q protobuf-3.21.9.zip -d ${OPEN_SOURCE_DIR}
    cmake -S ${OPEN_SOURCE_DIR}/protobuf-3.21.9 -B ${OPEN_SOURCE_DIR}/protobuf-3.21.9/build -DCMAKE_INSTALL_PREFIX=${PROTOBUF_DIR} -DCMAKE_CXX_FLAGS=-D_GLIBCXX_USE_CXX11_ABI=0 -Dprotobuf_BUILD_TESTS=OFF && cmake --build ${OPEN_SOURCE_DIR}/protobuf-3.21.9/build -j $(nproc) > /dev/null && cmake --install ${OPEN_SOURCE_DIR}/protobuf-3.21.9/build > /dev/null

    build_otel_proto
}


function build_otel_proto() {
    OTEL_DIR="${OPEN_SOURCE_DIR}/opentelemetry"
    [ -d "${OTEL_DIR}" ] && return $?

    [ ! -d "${OPEN_SOURCE_DIR}" ] && mkdir -p "${OPEN_SOURCE_DIR}"
    cd ${CUR_DIR}/opensource
    ./protobuf/bin/protoc ../proto/opentelemetry/proto/trace/v1/trace.proto -I ../proto --cpp_out=./ &
    ./protobuf/bin/protoc ../proto/opentelemetry/proto/resource/v1/resource.proto -I ../proto --cpp_out=./ &
    ./protobuf/bin/protoc ../proto/opentelemetry/proto/common/v1/common.proto -I ../proto --cpp_out=./ &
    ./protobuf/bin/protoc ../proto/opentelemetry/proto/collector/trace/v1/trace_service.proto -I ../proto --cpp_out=./ &
    wait
}


function clean_downloads() {
    local -a archives=("nlohmannjson-v3.11.2.tar.gz" "protobuf-3.21.9.zip")

    log_info "clean downloads"
    for archive in "${archives[@]}"; do
        [ -f "${archive}" ] && rm -f "${archive}"
    done
    log_info "clean downloads - ok"
}


trap clean_downloads EXIT ERR INT TERM


function prebuild() {
    log_info "check system tools"
    check_system_tools
    if [ $? -ne 0 ]; then
        log_error "check system tools - failed"
        return 1
    fi
    log_info "check system tools - ok"

    log_info "build dependencies"
    build_dependencies
    if [ $? -ne 0 ]; then
        log_error "build dependencies - failed"
        return 1
    fi
    log_info "build dependencies - ok"
}


function build_ms_service_profiler() {
    local BUILD_DIR=${CUR_DIR}/build

    cmake -S ${CUR_DIR} -B ${BUILD_DIR} && cmake --build ${BUILD_DIR} -j $(nproc) > /dev/null && cmake --install ${BUILD_DIR} --prefix ${BUILD_DIR}/output > /dev/null
}


function add_version() {
    version_str=`git rev-parse --is-inside-work-tree >/dev/null 2>&1 && echo "$(git rev-parse --abbrev-ref HEAD) $(git log -1 --format='%H %cd' --date=iso)" || echo ""`
    version_file=${CUR_DIR}/build/output/python/ms_service_profiler/analyze.py
    if [ -f "$version_file" ]; then
        echo "" >> $version_file
        echo "" >> $version_file
        echo "version='$version_str'" >> $version_file
        echo "" >> $version_file
    fi
}


function main() {
    log_info "pre-build"
    prebuild
    if [ $? -ne 0 ]; then
        log_error "prebuild - failed"
        exit 1
    fi
    log_info "pre-build - ok"

    log_info "build ms_service_profiler"
    build_ms_service_profiler
    if [ $? -ne 0 ]; then
        log_error "build ms_service_profiler - failed"
        exit 1
    fi
    log_info "build ms_service_profiler - ok"

    log_info "post-build: add version to file"
    add_version
    if [ $? -ne 0 ]; then
        log_error "post-build - failed"
        exit 1
    fi
    log_info "post-build - ok"
}

main
