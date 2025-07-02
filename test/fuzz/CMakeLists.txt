cmake_minimum_required(VERSION 3.16)
project(fuzz_msserviceprofiler)

# 设置 C++ 标准为 C++14
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# 设置 FUZZ_HOME_DIR 为当前目录
set(FUZZ_HOME_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
set(PROJECT_TOP_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../..)
set(TOOLKIT_BASE_PATH $ENV{ASCEND_TOOLKIT_HOME})
set(CMAKE_CXX_FLAGS "-fprofile-arcs -ftest-coverage -lgcov")
set(CMAKE_C_FLAGS "-fprofile-arcs -ftest-coverage -lgcov")


message("fuzz start")
message(STATUS "[fuzz dir is] ${FUZZ_HOME_DIR}")

aux_source_directory(${PROJECT_TOP_DIR}/src PROFILER_SRC)


# 启用 AddressSanitizer
add_compile_options(-fsanitize=address)
add_link_options(-fsanitize=address)

# 启用代码覆盖
# add_compile_options(-fprofile-generate )
add_compile_options(
        -fvisibility=default
        -fprofile-arcs
        -ftest-coverage
        -g
        -Og
        -Wall
)

include_directories(
        ${FUZZ_HOME_DIR}
        ${PROJECT_TOP_DIR}/include
        ${PROJECT_TOP_DIR}/include/msServiceProfiler
        ${PROJECT_TOP_DIR}/platform/securec/include
        ${FUZZ_HOME_DIR}/secodefuzz/Secodefuzz
        ${PROJECT_TOP_DIR}/opensource/json/include
        ${TOOLKIT_BASE_PATH}/include
        ${TOOLKIT_BASE_PATH}/aarch64-linux/include
)

link_directories(
        ${TOOLKIT_BASE_PATH}/lib64
        ${TOOLKIT_BASE_PATH}/aarch64-linux/devlib
)

add_link_options(
        -lgcov
        --coverage
)

add_subdirectory(${PROJECT_TOP_DIR}/platform platform)

# 构建可执行文件
add_executable(fuzz_msserviceprofiler
        FuzzMain.cpp
        ${DIC_FUZZ_TEST_LIST}
        ${PROFILER_SRC}
)

# 链接选项
target_link_options(fuzz_msserviceprofiler PRIVATE
        -fsanitize=address
        -fsanitize=undefined
        -fsanitize-coverage=trace-cmp,trace-pc
)

target_link_libraries(fuzz_msserviceprofiler
	gtest
        gtest_main
        gmock_main
        pthread
        sqlite3
        securec
        rt
        dl
        z
        Secodefuzz
        stdc++fs
        gcov
        ascendcl
        msprofiler
        ms_tools_ext
        mspti
)

target_link_directories(fuzz_msserviceprofiler PUBLIC
        ${FUZZ_HOME_DIR}/secodefuzz/release/lib/Secodefuzz
)

target_include_directories(fuzz_msserviceprofiler PUBLIC
        ${FUZZ_HOME_DIR}/secodefuzz/Secodefuzz
)

# 安装配置
install(TARGETS fuzz_msserviceprofiler
       RUNTIME DESTINATION "${FUZZ_HOME_DIR}/../build"
)