cmake_minimum_required(VERSION 3.16)
project(msserviceprofiler)

# 设置 C++ 标准为 C++14
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# 设置 FUZZ_HOME_DIR 为当前目录
set(FUZZ_HOME_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

message("fuzz start")
message(STATUS "[fuzz dir is] ${FUZZ_HOME_DIR}")

# 启用 AddressSanitizer
add_compile_options(-fsanitize=address)
add_link_options(-fsanitize=address)

# 启用代码覆盖
add_compile_options(-fprofile-generate )

# 添加新的测试文件

# 检查文件是否存在

# 添加测试文件列表

# 构建可执行文件


# 添加头文件路径
target_include_directories(msserviceprofiler PUBLIC
        "${FUZZ_HOME_DIR}/secodefuzz/Secodefuzz"
)

# 编译选项
target_compile_options(msserviceprofiler PRIVATE
        -g
        -fPIC
        -Wall
        -Winvalid-pch
        -fms-extensions
        -std=c++14
        -O0
        -fno-omit-frame-pointer
        -ftest-coverage
        -fprofile-arcs
        -fdump-rtl-expand
        -Wno-pmf-conversions
        -fsanitize=address
        -fsanitize=undefined
        -fsanitize-coverage=trace-cmp,trace-pc
)

# 链接选项
target_link_options(msserviceprofiler PRIVATE
        -fsanitize=address
        -fsanitize=undefined
        -fsanitize-coverage=trace-cmp,trace-pc
)

target_link_libraries(msserviceprofiler PRIVATE
		gtest gtest_main gmock_main
        pthread dl z Secodefuzz stdc++fs gcov
)

target_link_directories(msserviceprofiler PUBLIC
        ${FUZZ_HOME_DIR}/secodefuzz/release/lib/Secodefuzz
        ${FUZZ_HOME_DIR}/secodefuzz/examples/out-bin-x64/
)

target_include_directories(msserviceprofiler PUBLIC
        ${FUZZ_HOME_DIR}/secodefuzz/Secodefuzz
)

# 安装配置
install(TARGETS msserviceprofiler
       RUNTIME DESTINATION "${FUZZ_HOME_DIR}/../build"
)

