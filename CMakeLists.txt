cmake_minimum_required(VERSION 3.13)
project(ms_service_profiler)

# mkdir -p build
# cd build
# cmake ..
# make
# cmake --install . --prefix ../../ms_service_profiler

set(CMAKE_SKIP_RPATH TRUE)
set(CMAKE_CXX_STANDARD 11)
add_definitions(-D_GLIBCXX_USE_CXX11_ABI=0)


if (NOT DEFINED ENV{ASCEND_TOOLKIT_HOME})
    message(AUTHOR_WARNING "no env $ASCEND_TOOLKIT_HOME")
    set(BUILD_ENV_MSPROF_DEPEND_PATH /usr1/slave1/msprof/collector/dvvp/depend/inc)
    set(BUILD_ENV_MSPROF_DEPEND_ACL_PATH /usr1/slave1/msprof/collector/dvvp/depend/inc/acl)
    set(BUILD_ENV_MSPROF_DEPEND_API_PATH /usr1/slave1/msprof/collector/dvvp/depend/inc/profapi)
    set(BUILD_ENV_MSPROF_PATH /usr1/slave1/msprof/collector/inc/external)
    set(BUILD_ENV_MSTX_PATH /usr1/slave1/mstx/include)

    add_library(ascendcl
            SHARED
            3rdparty/BuildAcl.cpp
    )
    add_library(msprofiler
            SHARED
            3rdparty/BuildAclProf.cpp
    )
    add_library(ms_tools_ext
            SHARED
            3rdparty/BuildMstx.cpp
    )
    include_directories(
            ${BUILD_ENV_MSTX_PATH}
            ${BUILD_ENV_MSPROF_PATH}
            ${BUILD_ENV_MSPROF_DEPEND_PATH}
            ${BUILD_ENV_MSPROF_DEPEND_ACL_PATH}
            ${BUILD_ENV_MSPROF_DEPEND_API_PATH}
            3rdparty
            opensource/json/include
    )
else ()
    set(TOOLKIT_BASE_PATH $ENV{ASCEND_TOOLKIT_HOME})
    include_directories(
            ${TOOLKIT_BASE_PATH}/include
            ${TOOLKIT_BASE_PATH}/aarch64-linux/include
            ${TOOLKIT_BASE_PATH}/x86_64-linux/include
            opensource/json/include
    )

    link_directories(
            ${TOOLKIT_BASE_PATH}/lib64
            ${TOOLKIT_BASE_PATH}/aarch64-linux/devlib
            ${TOOLKIT_BASE_PATH}/x86_64-linux/devlib
    )
endif ()

add_library(ms_service_profiler
        SHARED
        src/Profiler.cpp
        src/ServiceProfilerManager.cpp
        src/GetNpuMemoryUsage.cpp
)

add_executable(test_server_profiler test/ut/cpp_test/test.cpp
        src/Profiler.cpp
        src/ServiceProfilerManager.cpp
        src/GetNpuMemoryUsage.cpp
)

target_compile_options(ms_service_profiler PRIVATE
        -std=c++11
        -fPIC
        -fstack-protector-all
        -fno-strict-aliasing
        -fno-common
        -fvisibility=hidden
        -fvisibility-inlines-hidden
        -Wfloat-equal
        -Wextra
        -D_FORTIFY_SOURCE=2 -O2
)

target_link_options(ms_service_profiler PRIVATE
        -Wl,-z,relro,-z,now,-z,noexecstack
        -Wl,-Bsymbolic
        -Wl,--exclude-libs=ALL
        $<$<NOT:$<STREQUAL:${CMAKE_BUILD_TYPE},Debug>>:-s>
)


target_link_libraries(ms_service_profiler
        ascendcl
        msprofiler
        ms_tools_ext
        dl
        pthread
)


target_link_libraries(test_server_profiler
        ascendcl
        msprofiler
        dl
        pthread
)

target_compile_definitions(test_server_profiler PUBLIC -DENABLE_PROF)

install(TARGETS ms_service_profiler
        LIBRARY DESTINATION lib
)

install(DIRECTORY ${CMAKE_SOURCE_DIR}/include DESTINATION .
        FILES_MATCHING PATTERN "*.h")

install(DIRECTORY ${CMAKE_SOURCE_DIR}/scripts DESTINATION .
        FILES_MATCHING PATTERN "*.sh")

install(DIRECTORY ${CMAKE_SOURCE_DIR}/ms_service_profiler DESTINATION ./python
        FILES_MATCHING PATTERN "*.py")
