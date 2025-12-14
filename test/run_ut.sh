#!/bin/bash
# This script is used to run ut and st testcase.
# Copyright Huawei Technologies Co., Ltd. 2021-2022. All rights reserved.

set -e

export _GLIBCXX_USE_CXX11_ABI=0
unset ASCEND_TOOLKIT_HOME
CUR_DIR=$(dirname $(readlink -f $0))
PROJECT_DIR=$(readlink -f ${CUR_DIR}/..)
TEST_LANG=$1
ENABLE_CACHE=$2
ret=0

clean() {
  cd ${TEST_DIR}
  if [ -e ${TEST_DIR}/coverage.xml ]; then
    rm coverage.xml
    echo "remove last coverage.xml success"
  fi
  cd -
}

run_test_cpp() {
    local BUILD_DIR=${PROJECT_DIR}/build
    local BUILD_TEST_DIR=${BUILD_DIR}/test

    local UT_BUILD_CACHE_DIR=${BUILD_TEST_DIR}/CMakeFiles/ms_service_profiler_run_uts.dir
    local ST_BUILD_CACHE_DIR=${BUILD_TEST_DIR}/CMakeFiles/ms_service_profiler_run_sts.dir
    local COV_DIR=${CUR_DIR}/coverage

    if [ "$ENABLE_CACHE" != "1" ]; then
        [ -d "${BUILD_DIR}" ] && rm -rf "${BUILD_DIR}"
        cmake -S ${PROJECT_DIR}/ . -B ${BUILD_DIR} && cmake --build ${BUILD_DIR} -j$(nproc)
    fi
    if [ $? -ne 0 ]; then
        echo "build ut or st failed"
        exit 1
    fi

    ${BUILD_TEST_DIR}/ms_service_profiler_run_uts
    if [ $? -ne 0 ]; then
        echo "failed to run uts"
        exit 1
    fi
    ${BUILD_TEST_DIR}/ms_service_profiler_run_sts
    if [ $? -ne 0 ]; then
        echo "failed to run sts"
        exit 1
    fi

    if [ ! -d ${COV_DIR} ]; then
        mkdir -p ${COV_DIR}
    else
        rm -rf ${COV_DIR}/*
    fi

    lcov_opt="--rc lcov_branch_coverage=1 --rc geninfo_no_exception_branch=1"
    lcov -c -d ${UT_BUILD_CACHE_DIR} -o ${COV_DIR}/ut_server_profiler.info -b ${COV_DIR} $lcov_opt
    lcov -c -d ${ST_BUILD_CACHE_DIR} -o ${COV_DIR}/st_server_profiler.info -b ${COV_DIR} $lcov_opt
    if [ -f "${COV_DIR}/st_server_profiler.info " ]; then
        lcov -a ${COV_DIR}/ut_server_profiler.info  -a ${COV_DIR}/st_server_profiler.info  -o ${COV_DIR}/test_server_profiler.info  $lcov_opt
    else
        lcov -a ${COV_DIR}/ut_server_profiler.info  -o ${COV_DIR}/test_server_profiler.info  $lcov_opt
    fi

    lcov -r ${COV_DIR}/test_server_profiler.info '*cpp*' -o ${COV_DIR}/test_server_profiler.info $lcov_opt -q
    lcov -r ${COV_DIR}/test_server_profiler.info '*c++*' -o ${COV_DIR}/test_server_profiler.info $lcov_opt -q
    lcov -r ${COV_DIR}/test_server_profiler.info '/usr/include/*' -o ${COV_DIR}/test_server_profiler.info $lcov_opt -q
    lcov -r ${COV_DIR}/test_server_profiler.info '*nlohmann*' -o ${COV_DIR}/test_server_profiler.info $lcov_opt -q
    lcov -r ${COV_DIR}/test_server_profiler.info '*mockcpp*' -o ${COV_DIR}/test_server_profiler.info $lcov_opt -q
    lcov -r ${COV_DIR}/test_server_profiler.info '*googletest*' -o ${COV_DIR}/test_server_profiler.info $lcov_opt -q

    genhtml ${COV_DIR}/test_server_profiler.info -o ${COV_DIR}/report --branch-coverage
    tar -zcf ${COV_DIR}/report.tar.gz ${COV_DIR}/report
    echo show report using cmd: python -m http.server -d ${COV_DIR}/report
}

run_test_python() {
    pip3 install -r "${CUR_DIR}/requirements.txt" --default-timeout=20
    export PYTHONPATH=${PROJECT_DIR}:${PYTHONPATH}
    python3 -m coverage run --branch --source ${PROJECT_DIR}/'ms_service_profiler' -m pytest ${CUR_DIR}/ut/python

    if [ $? -ne 0 ]; then
        echo "UT Failure"
        exit 1
    fi

    python3 -m coverage report -m
    python3 -m coverage xml -o ${TEST_DIR}/coverage.xml
}

main() {
    export VERBOSE=1
    cd ${TEST_DIR}

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
