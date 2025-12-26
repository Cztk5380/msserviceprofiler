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
PROJECT_DIR=$(readlink -f ${CUR_DIR}/..)
BUILD_DIR=${PROJECT_DIR}/build

TEST_LANG="${1:-}"
ENABLE_CACHE="${2:-0}"

clean() {
    [[ "${ENABLE_CACHE}" != "1" && -d "${BUILD_DIR}" ]] && rm -rf "${BUILD_DIR}"

    if [ ! -d ${COV_DIR} ]; then
        mkdir -p ${COV_DIR}
    fi
}

run_test_cpp() {
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

        if [ $? -ne 0 ]; then
            echo "failed to build tests project"
            exit 1
        fi
    fi

    ${BUILD_TEST_DIR}/${UT_TARGET}
    if [ $? -ne 0 ]; then
        echo "failed to run uts"
        exit 1
    fi
    ${BUILD_TEST_DIR}/${ST_TARGET}
    if [ $? -ne 0 ]; then
        echo "failed to run sts"
        exit 1
    fi
}

run_test_python() {
    local UT_PYTHON_DIR=${CUR_DIR}/ut/python

    pip3 install "${PROJECT_DIR}[test]"
    pip3 install "${PROJECT_DIR}/modelevalstate[test]"
    pip3 install "${PROJECT_DIR}/msservice_advisor"
    python3 -m coverage run --branch --source "${PROJECT_DIR}/ms_service_profiler" -m pytest ${UT_PYTHON_DIR}

    if [ $? -ne 0 ]; then
        echo "failed to run python uts"
        exit 1
    fi

    python3 -m coverage report -m
    python3 -m coverage xml -o ${COV_DIR}/coverage.xml
}

main() {
    export VERBOSE=1

    clean
    if [ "$TEST_LANG" != "cpp" ]; then
        run_test_python
    fi
    if [ "$TEST_LANG" != "python" ]; then
        run_test_cpp
    fi
    echo "UT Success"
}

main "$@"
