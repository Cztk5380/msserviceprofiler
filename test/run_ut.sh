#!/bin/bash

# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------

# This script is used to run ut and st testcase.

set -eu

CUR_DIR=$(dirname $(readlink -f $0))
COV_DIR=${CUR_DIR}/coverage
UT_PYTHON_DIR=${CUR_DIR}/ut/python
PROJECT_DIR=$(readlink -f ${CUR_DIR}/..)
BUILD_DIR=${PROJECT_DIR}/build
ENABLE_CACHE="${ENABLE_CACHE:-0}"


function clean() {
    [[ "${ENABLE_CACHE}" != "1" && -d "${BUILD_DIR}" ]] && rm -rf "${BUILD_DIR}"

    if [ ! -d ${COV_DIR} ]; then
        mkdir -p ${COV_DIR}
    fi
}


function run_ms_service_profiler_python_ut() {
    local UT_DIR="${UT_PYTHON_DIR}/test_ms_service_profiler"

    pip3 install -e "${PROJECT_DIR}[test]"
    python3 -m coverage run --branch --source "${PROJECT_DIR}/ms_service_profiler" --omit="test/*" -m pytest ${UT_DIR}
    python3 -m coverage report -m
    python3 -m coverage xml -o ${COV_DIR}/coverage.xml
}


function run_ms_service_profiler_cpp_ut() {
    local BUILD_TEST_DIR=${BUILD_DIR}/test
    local UT_TARGET="ms_service_profiler_run_uts"
    local ST_TARGET="ms_service_profiler_run_sts"
    local UT_BUILD_CACHE_DIR=${BUILD_TEST_DIR}/CMakeFiles/${UT_TARGET}.dir
    local ST_BUILD_CACHE_DIR=${BUILD_TEST_DIR}/CMakeFiles/${ST_TARGET}.dir
    local UT_COV_INFO=${COV_DIR}/ut_server_profiler.info
    local ST_COV_INFO=${COV_DIR}/st_server_profiler.info
    local OVERALL_COV_INFO=${COV_DIR}/test_server_profiler.info
    local COV_REPORT_DIR=${COV_DIR}/report

    if [ "$ENABLE_CACHE" != "1" ]; then
        cmake -S ${PROJECT_DIR}/ -B ${BUILD_DIR} -Dms_service_profiler_BUILD_TESTS=ON
        cmake --build ${BUILD_DIR} --target ${UT_TARGET} ${ST_TARGET} -j$(nproc)
    fi

    ${BUILD_TEST_DIR}/${UT_TARGET}
    ${BUILD_TEST_DIR}/${ST_TARGET}
}


function run_modelevalstate_ut() {
    local UT_DIR="${UT_PYTHON_DIR}/test_optimizer"

    if ! pip3 show ms_service_profiler > /dev/null; then
        pip3 install -e "${PROJECT_DIR}[test]"
    fi

    pip3 install -e "${PROJECT_DIR}/modelevalstate[test]"
    PYTHONPATH=$PROJECT_DIR/modelevalstate python3 -m coverage run \
        --branch \
        --source "${PROJECT_DIR}/modelevalstate" \
        --omit="test/*" \
        -m pytest ${UT_DIR}

    python3 -m coverage report -m
    python3 -m coverage xml -o ${COV_DIR}/coverage.xml
}


function run_msservice_advisor_ut() {
    local UT_DIR="${UT_PYTHON_DIR}/test_msservice_advisor"

    if ! pip3 show ms_service_profiler > /dev/null; then
        pip3 install -e "${PROJECT_DIR}[test]"
    fi

    pip3 install -e "${PROJECT_DIR}/msservice_advisor"
    PYTHONPATH=$PROJECT_DIR/msservice_advisor python3 -m coverage run \
        --branch \
        --source "${PROJECT_DIR}/msservice_advisor" \
        --omit="test/*" \
        -m pytest ${UT_DIR}
 
    python3 -m coverage report -m
    python3 -m coverage xml -o ${COV_DIR}/coverage.xml
}


function main() {
    clean

    local -A tests_mapping=(
        ["ms_service_profiler"]="run_ms_service_profiler_python_ut"
        ["cpp"]="run_ms_service_profiler_cpp_ut"
        ["modelevalstate"]="run_modelevalstate_ut"
        ["msservice_advisor"]="run_msservice_advisor_ut"
        
    )

    if [ $# -eq 0 ]; then
        for func in "${tests_mapping[@]}"; do
            $func
        done
        exit 0
    fi

    while [ $# -gt 0 ]; do
        test_name="$1"
        test_fn="${tests_mapping[$test_name]:-}"

        if [ -z "${test_fn}" ]; then
            echo "错误: 未知的测试项 '$test_name'"
            echo "可用选项: ${!tests[*]}"
            exit 1
        fi

        ${test_fn}
        shift
    done
}

main "$@"
