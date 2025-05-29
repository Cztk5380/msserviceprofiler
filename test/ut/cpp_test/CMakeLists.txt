cmake_minimum_required(VERSION 3.13)
project(ms_service_profiler_test)
message("building test of msServiceProfiler")

set(CMAKE_SKIP_RPATH TRUE)
set(CMAKE_CXX_STANDARD 14)
set(PROJECT_TOP_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../..)
set(TOOLKIT_BASE_PATH $ENV{ASCEND_TOOLKIT_HOME})
set(CMAKE_CXX_FLAGS "-fprofile-arcs -ftest-coverage -lgcov")
set(CMAKE_C_FLAGS "-fprofile-arcs -ftest-coverage -lgcov")

add_compile_definitions(
        ENABLE_PROF
)

add_compile_options(
        -fvisibility=default
        -fprofile-arcs
        -ftest-coverage
        -g
        -Wall
        -fpermissive
)
if (NOT DEFINED ENV{ASCEND_TOOLKIT_HOME})
    message(AUTHOR_WARNING "no env $ASCEND_TOOLKIT_HOME")
    set(BUILD_INCLUDE_LIST )
    add_subdirectory(${PROJECT_TOP_DIR}/3rdparty 3rdparty)
    message("${BUILD_INCLUDE_LIST}")
    include_directories(
            ${PROJECT_TOP_DIR}/3rdparty
    )
endif ()

include_directories(
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${PROJECT_TOP_DIR}/include
        ${PROJECT_TOP_DIR}/include/msServiceProfiler
        ${PROJECT_TOP_DIR}/opensource/googletest/googletest-1.12.1/include
        ${PROJECT_TOP_DIR}/opensource/mock_cpp/mockcpp/include
        ${PROJECT_TOP_DIR}/opensource/json/include
        ${PROJECT_TOP_DIR}/platform/securec/include
        ${TOOLKIT_BASE_PATH}/include
        ${TOOLKIT_BASE_PATH}/aarch64-linux/include
        ${TOOLKIT_BASE_PATH}/x86_64-linux/include
)

link_directories(
        ${PROJECT_TOP_DIR}/opensource/googletest/googletest-1.12.1/lib
        ${PROJECT_TOP_DIR}/opensource/mock_cpp/mockcpp/lib
        ${TOOLKIT_BASE_PATH}/lib64
        ${TOOLKIT_BASE_PATH}/aarch64-linux/devlib
        ${TOOLKIT_BASE_PATH}/x86_64-linux/devlib
)

set(TEST_LIBS
        ascendcl
        msprofiler
        ms_tools_ext
        dl
        pthread
        rt
        securec
        mspti
        -lsqlite3
        libgtest.a
        libgtest_main.a
        libgmock.a
        libgmock_main.a
        libmockcpp.a
)

add_link_options(
        -lgcov
        --coverage
)

aux_source_directory(${PROJECT_TOP_DIR}/src/ PROFILER_SRC)
add_subdirectory(${PROJECT_TOP_DIR}/platform platform)

add_executable(ut_server_profiler
        ${PROFILER_SRC}
        testNpuMemoryUsage.cpp
        testServiceProfilerInterface.cpp
        testServiceProfilerManager.cpp
        testProfiler.cpp
)

target_link_libraries(ut_server_profiler
        ${TEST_LIBS}
)

target_compile_options(ut_server_profiler PRIVATE
        -fno-access-control
)

add_executable(st_server_profiler
        test.cpp
        ${PROFILER_SRC}
)

target_link_libraries(st_server_profiler
        ${TEST_LIBS}
)

target_compile_definitions(st_server_profiler PUBLIC
        ENABLE_SERVICE_PROF_UNIT_TEST
)