cmake_minimum_required(VERSION 3.11)

project(ms_service_profiler VERSION 8.5.0 LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED True)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -D_GLIBCXX_USE_CXX11_ABI=0")

set(THIRD_PARTY_DIR "${CMAKE_CURRENT_SOURCE_DIR}/3rdparty")
set(CPP_DIR "${CMAKE_CURRENT_SOURCE_DIR}/cpp")

option(ms_service_profiler_BUILD_TESTS "build ms_service_profiler uts and sts" OFF)

add_subdirectory("${THIRD_PARTY_DIR}")
add_subdirectory("${CPP_DIR}")

if(ms_service_profiler_BUILD_TESTS)
    add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/test")
endif()
