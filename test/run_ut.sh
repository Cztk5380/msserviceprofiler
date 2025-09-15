#!/bin/bash
# This script is used to run ut and st testcase.
# Copyright Huawei Technologies Co., Ltd. 2021-2022. All rights reserved.

set -e

CUR_DIR=$(dirname $(readlink -f $0))
TOP_DIR=$(readlink -f ${CUR_DIR}/..)
TEST_DIR=${TOP_DIR}/"test"
SRC_DIR=${TOP_DIR}/"src"
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

function fn_build_googletest()
{
    OPENSOURCE_DIR=${CUR_DIR}/../opensource
    if [ ! -d $OPENSOURCE_DIR ]; then
        mkdir -p ${CUR_DIR}/../opensource
    fi

    cd ${OPENSOURCE_DIR}
    GTEST_DIR="${OPENSOURCE_DIR}/googletest"
    if [ ! -d "$GTEST_DIR" ]; then
        git clone https://codehub-dg-y.huawei.com/OpenSourceCenter/googletest.git googletest -b release-1.12.1
    else
        echo "opensource/googletest already exists. no need to download."
    fi
    if [ ! -d "$GTEST_DIR/googletest-1.12.1" ]; then
        cd googletest
        cmake -S . -DCMAKE_INSTALL_PREFIX=$GTEST_DIR/googletest-1.12.1 -B gtest_build
        cmake --build gtest_build -j 20
        cmake --install gtest_build
    fi
}

function fn_build_mock_cpp()
{
  mkdir -p ${CUR_DIR}/../opensource
  cd ${CUR_DIR}/../opensource
  MOCK_CPP_DIR="${CUR_DIR}/../opensource/mock_cpp"
  if [ ! -d "$MOCK_CPP_DIR" ]; then
    git clone https://szv-y.codehub.huawei.com/mindstudio/MindStudio_Opensource/mock_cpp.git mock_cpp -b msprof
  else
      echo "opensource/mock_cpp already exists. no need to download."
  fi

  if [ ! -d "$MOCK_CPP_DIR/mockcpp" ]; then
    cd mock_cpp
    mkdir -p build
    cd build
    cmake -DCMAKE_INSTALL_PREFIX=$MOCK_CPP_DIR/mockcpp -DMOCKCPP_XUNIT=gtest \
      -DMOCKCPP_XUNIT_HOME=${CUR_DIR}/../opensource/googletest ..
    make -j20
    make install
  fi
}

run_test_cpp() {
  cd ${TEST_DIR}/..

  if [ "$ENABLE_CACHE" != "1" ]; then
    bash build.sh
  fi
  if [ $? -ne 0 ]; then
    echo "Build ms_service_profiler failed"
    exit 1
  fi
  cd ${TEST_DIR}

  if [ "$ENABLE_CACHE" != "1" ]; then
    mkdir -p test_build && cd test_build && rm * -rf && cmake ../ut/cpp_test && make -j 50
  else
    mkdir -p test_build && cd test_build && cmake ../ut/cpp_test && make -j 50
  fi
  if [ $? -ne 0 ]; then
    echo "Build test failed"
    exit 1
  fi
  cd ${TEST_DIR}
  echo export LD_LIBRARY_PATH=${TEST_DIR}/test_build/3rdparty:$LD_LIBRARY_PATH
  export LD_LIBRARY_PATH=${TEST_DIR}/test_build/3rdparty:$LD_LIBRARY_PATH
  ./test_build/st_server_profiler & ./test_build/st_server_profiler
  ./test_build/ut_server_profiler

  if [ $? -ne 0 ]; then
    echo "Run test failed"
    exit 1
  fi

  mkdir -p coverage
  rm -rf ./coverage/*

  lcov_opt="--rc lcov_branch_coverage=1 --rc geninfo_no_exception_branch=1"
  lcov -c -d ./test_build/CMakeFiles/st_server_profiler.dir -o ./coverage/st_server_profiler.info -b ./coverage $lcov_opt
  lcov -c -d ./test_build/CMakeFiles/ut_server_profiler.dir -o ./coverage/ut_server_profiler.info -b ./coverage $lcov_opt
  if [ -f "./coverage/st_server_profiler.info " ]; then
    lcov -a ./coverage/ut_server_profiler.info  -a ./coverage/st_server_profiler.info  -o ./coverage/test_server_profiler.info  $lcov_opt
  else
    lcov -a ./coverage/ut_server_profiler.info  -o ./coverage/test_server_profiler.info  $lcov_opt
  fi

  lcov -r ./coverage/test_server_profiler.info '*platform*' -o ./coverage/test_server_profiler.info $lcov_opt -q
  lcov -r ./coverage/test_server_profiler.info '*opensource*' -o ./coverage/test_server_profiler.info $lcov_opt -q
  lcov -r ./coverage/test_server_profiler.info '*cpp_test*' -o ./coverage/test_server_profiler.info $lcov_opt -q
  lcov -r ./coverage/test_server_profiler.info '*c++*' -o ./coverage/test_server_profiler.info $lcov_opt -q
  lcov -r ./coverage/test_server_profiler.info '/usr/include/*' -o ./coverage/test_server_profiler.info $lcov_opt -q
  lcov -r ./coverage/test_server_profiler.info '*nlohmann*' -o ./coverage/test_server_profiler.info $lcov_opt -q
  lcov -r ./coverage/test_server_profiler.info '*mockcpp*' -o ./coverage/test_server_profiler.info $lcov_opt -q
  lcov -r ./coverage/test_server_profiler.info '*googletest*' -o ./coverage/test_server_profiler.info $lcov_opt -q

  genhtml ./coverage/test_server_profiler.info -o ./coverage/report --branch-coverage
  cd coverage
  tar -zcf report.tar.gz ./report
  echo show report using cmd: python -m http.server -d ./coverage/report
}

run_test_python() {
  pip3 install -r "${CUR_DIR}/requirements.txt" --default-timeout=20
  export PYTHONPATH=${TOP_DIR}:${PYTHONPATH}
  python3 -m coverage run --branch --source ${TOP_DIR}/'ms_service_profiler' -m pytest ${TEST_DIR}/ut/python_test

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
        fn_build_googletest
        fn_build_mock_cpp
        run_test_cpp
    fi
    echo "UT Success"
}

main "$@"
