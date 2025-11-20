cmake_minimum_required(VERSION 3.13)
project(ms_service_profiler)

# mkdir -p build
# cd build
# cmake ..
# make
# cmake --install . --prefix ../../ms_service_profiler

set(CMAKE_SKIP_RPATH TRUE)
set(CMAKE_CXX_STANDARD 14)
add_definitions(-D_GLIBCXX_USE_CXX11_ABI=0)
add_definitions(-DENABLE_PROF)

include_directories(
        include
        opensource/json/include
        platform/securec/include
        opensource
        opensource/protobuf/include
)

if (NOT DEFINED ENV{ASCEND_TOOLKIT_HOME})
    message(AUTHOR_WARNING "no env $ASCEND_TOOLKIT_HOME")
    set(BUILD_INCLUDE_LIST )
    add_subdirectory(3rdparty)
    message("${BUILD_INCLUDE_LIST}")
    include_directories(
            ${BUILD_INCLUDE_LIST}
            3rdparty
    )
else ()
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
endif ()

link_directories(
        opensource/protobuf/lib
)

add_compile_options(
        -fPIC
        -fstack-protector-all
        -fno-strict-aliasing
        -fno-common
        -fvisibility=hidden
        -Wfloat-equal
        -Wextra
        -D_FORTIFY_SOURCE=2 -O2
)

add_link_options(
        -Wl,-z,relro,-z,now,-z,noexecstack
        -Wl,-Bsymbolic
        -Wl,--exclude-libs=ALL
        $<$<NOT:$<STREQUAL:${CMAKE_BUILD_TYPE},Debug>>:-s>
)

aux_source_directory(${CMAKE_CURRENT_SOURCE_DIR}/src/ PROFILER_SRC)
add_subdirectory(platform)

add_library(ms_service_profiler
        SHARED
        ${PROFILER_SRC}
        opensource/opentelemetry/proto/common/v1/common.pb.cc
        opensource/opentelemetry/proto/resource/v1/resource.pb.cc
        opensource/opentelemetry/proto/trace/v1/trace.pb.cc
        opensource/opentelemetry/proto/collector/trace/v1/trace_service.pb.cc
)

target_compile_options(ms_service_profiler PRIVATE
        -fvisibility-inlines-hidden
)


target_link_libraries(ms_service_profiler
        ascendcl
        msprofiler
        ms_tools_ext
        dl
        pthread
        rt
        securec
        mspti
        sqlite3
        libprotobuf.a
)

install(TARGETS ms_service_profiler
        LIBRARY DESTINATION lib
)

install(DIRECTORY ${CMAKE_SOURCE_DIR}/include DESTINATION .
        FILES_MATCHING PATTERN "*.h")

install(DIRECTORY ${CMAKE_SOURCE_DIR}/scripts DESTINATION .
        FILES_MATCHING PATTERN "*.sh")

install(DIRECTORY ${CMAKE_SOURCE_DIR}/ms_service_profiler DESTINATION ./python
        FILES_MATCHING PATTERN "*.py")

install(DIRECTORY ${CMAKE_SOURCE_DIR}/ms_service_profiler DESTINATION ./python
        FILES_MATCHING PATTERN "*.json")
