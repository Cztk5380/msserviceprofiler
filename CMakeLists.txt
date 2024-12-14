cmake_minimum_required(VERSION 3.10)
project(ms_server_profiler)

# mkdir -p build
# cd build
# cmake ..
# make
# cmake --install . --prefix ../../server_profiler
set(CMAKE_CXX_STANDARD 11)
add_definitions(-D_GLIBCXX_USE_CXX11_ABI=0)

if(NOT DEFINED ENV{ASCEND_TOOLKIT_HOME})
    message(FATAL_ERROR "no env $ASCEND_TOOLKIT_HOME")
endif()

set(TOOLKIT_BASE_PATH $ENV{ASCEND_TOOLKIT_HOME})

include_directories(
    ${TOOLKIT_BASE_PATH}/include
    ${TOOLKIT_BASE_PATH}/aarch64-linux/include
    ${TOOLKIT_BASE_PATH}/x86_64-linux/include
)

link_directories(
    ${TOOLKIT_BASE_PATH}/lib64
    ${TOOLKIT_BASE_PATH}/aarch64-linux/devlib
    ${TOOLKIT_BASE_PATH}/x86_64-linux/devlib
)

add_library(ms_server_profiler
    SHARED
    src/msServerProfiler.cpp
    src/msServerProfilerMarker.cpp
)

add_executable(test_server_profiler test/ut/cpp_test/test.cpp
    src/msServerProfiler.cpp
    src/msServerProfilerMarker.cpp
)

target_link_libraries(ms_server_profiler
    ascendcl
    msprofiler
    dl
)

target_link_libraries(test_server_profiler
    ascendcl
    msprofiler
    dl
)

install(TARGETS ms_server_profiler
    LIBRARY DESTINATION lib
)

install(DIRECTORY ${CMAKE_SOURCE_DIR}/include DESTINATION .
    FILES_MATCHING PATTERN "*.h")

install(DIRECTORY ${CMAKE_SOURCE_DIR}/scripts DESTINATION .
    FILES_MATCHING PATTERN "*.sh")

install(DIRECTORY ${CMAKE_SOURCE_DIR}/ms_server_profiler DESTINATION ./python
    FILES_MATCHING PATTERN "*.py")
