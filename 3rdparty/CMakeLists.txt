set(ASCEND_DIR ${CMAKE_CURRENT_SOURCE_DIR}/ascend)
set(BOUNDSCHECK_DIR ${CMAKE_CURRENT_SOURCE_DIR}/boundscheck)
set(PROTOBUF_DIR ${CMAKE_CURRENT_SOURCE_DIR}/protobuf)
set(PROTOBUF_BUILD_DIR ${PROTOBUF_DIR}/build)
set(JSON_DIR ${CMAKE_CURRENT_SOURCE_DIR}/json)

include(FetchContent)

FetchContent_Declare(
    boundscheck_external
    GIT_REPOSITORY https://gitcode.com/openeuler/libboundscheck
    GIT_SHALLOW TRUE

    DOWNLOAD_DIR ${BOUNDSCHECK_DIR}
    SOURCE_DIR ${BOUNDSCHECK_DIR}
)
FetchContent_Declare(
    json_external
    GIT_REPOSITORY https://gitcode.com/GitHub_Trending/js/json.git
    GIT_TAG v3.11.2
    GIT_SHALLOW TRUE

    DOWNLOAD_DIR ${JSON_DIR}
    SOURCE_DIR ${JSON_DIR}
)

# ------------------------------------------------------------------------------
# boundscheck
# ------------------------------------------------------------------------------
message(STATUS "Preparing boundscheck")
FetchContent_GetProperties(boundscheck_external)
if(NOT boundscheck_external_POPULATED)
    FetchContent_Populate(boundscheck_external)
endif()
message(STATUS "Preparing boundscheck - done")

# ------------------------------------------------------------------------------
# protobuf
# ------------------------------------------------------------------------------
message(STATUS "Preparing protobuf")
if(NOT EXISTS ${PROTOBUF_DIR})
    execute_process(
        COMMAND git clone https://gitcode.com/gh_mirrors/pro/protobuf.git --depth 1 -b v3.21.9 ${PROTOBUF_DIR}
        RESULT_VARIABLE PROTOBUF_CLONE_RESULT
        OUTPUT_VARIABLE PROTOBUF_CLONE_OUTPUT
        ERROR_VARIABLE  PROTOBUF_CLONE_ERROR
    )
    if(NOT PROTOBUF_CLONE_RESULT EQUAL 0)
        message(FATAL_ERROR "Failed to clone protobuf:\n${PROTOBUF_CLONE_OUTPUT}\n${PROTOBUF_CLONE_ERROR}")
    endif()

    execute_process(
        COMMAND ${CMAKE_COMMAND}
            -S ${PROTOBUF_DIR}
            -B ${PROTOBUF_BUILD_DIR}
            -Dprotobuf_BUILD_TESTS=OFF
            -Dprotobuf_BUILD_SHARED_LIBS=OFF
            -DCMAKE_CXX_FLAGS=-D_GLIBCXX_USE_CXX11_ABI=0
            -DCMAKE_POSITION_INDEPENDENT_CODE=ON
        RESULT_VARIABLE PROTOBUF_CONFIGURE_RESULT
        OUTPUT_VARIABLE PROTOBUF_CONFIGURE_OUTPUT
        ERROR_VARIABLE  PROTOBUF_CONFIGURE_ERROR
    )
    if(NOT PROTOBUF_CONFIGURE_RESULT EQUAL 0)
        message(FATAL_ERROR "Failed to configure protobuf:\n${PROTOBUF_CONFIGURE_OUTPUT}\n${PROTOBUF_CONFIGURE_ERROR}")
    endif()

    execute_process(
        COMMAND ${CMAKE_COMMAND} --build "${PROTOBUF_BUILD_DIR}" -j ${NPROC}
        RESULT_VARIABLE PROTOBUF_BUILD_RESULT
        OUTPUT_VARIABLE PROTOBUF_BUILD_OUTPUT
        ERROR_VARIABLE  PROTOBUF_BUILD_ERROR
    )
    if(NOT PROTOBUF_BUILD_RESULT EQUAL 0)
        message(FATAL_ERROR "Failed to build protobuf:\n${PROTOBUF_BUILD_OUTPUT}\n${PROTOBUF_BUILD_ERROR}")
    endif()
endif()
message(STATUS "Preparing protobuf - done")

# ------------------------------------------------------------------------------
# opentelemetry protoc code generation
# ------------------------------------------------------------------------------
message(STATUS "Preparing opentelemetry")

set(PROTOC_CMD ${PROTOBUF_BUILD_DIR}/protoc)
set(PROTOC_INCLUDE_DIR ${THIRD_PARTY_DIR})
set(PROTOC_OUT_DIR ${THIRD_PARTY_DIR}/opentelemetry/include)

if(NOT EXISTS ${PROTOC_CMD})
    message(FATAL_ERROR "protoc not found at: ${PROTOC_CMD}\n"
        "PROTOBUF_BUILD_DIR = ${PROTOBUF_BUILD_DIR}")
endif()

set(OPENTELEMETRY_PROTOS
    opentelemetry/proto/trace/v1/trace.proto
    opentelemetry/proto/resource/v1/resource.proto
    opentelemetry/proto/common/v1/common.proto
    opentelemetry/proto/collector/trace/v1/trace_service.proto
)

foreach(PROTO_FILE ${OPENTELEMETRY_PROTOS})
    execute_process(
        COMMAND ${PROTOC_CMD} ${PROTO_FILE} -I ${PROTOC_INCLUDE_DIR} --cpp_out=${PROTOC_OUT_DIR}
        RESULT_VARIABLE PROTOC_RESULT
        OUTPUT_VARIABLE PROTOC_OUTPUT
        ERROR_VARIABLE  PROTOC_ERROR
    )
    if(NOT PROTOC_RESULT EQUAL 0)
        message(FATAL_ERROR "Failed to compile proto [${PROTO_FILE}]:\n${PROTOC_OUTPUT}\n${PROTOC_ERROR}")
    endif()
endforeach()

message(STATUS "Preparing opentelemetry - done")

# ------------------------------------------------------------------------------
# json
# ------------------------------------------------------------------------------
message(STATUS "Preparing json")
FetchContent_GetProperties(json_external)
if(NOT json_external_POPULATED)
    FetchContent_Populate(json_external)
endif()
message(STATUS "Preparing json - done")

# ------------------------------------------------------------------------------
# googletest
# ------------------------------------------------------------------------------
if(ms_service_profiler_BUILD_TESTS)
    set(GOOGLETEST_DIR ${CMAKE_CURRENT_SOURCE_DIR}/googletest)

    FetchContent_Declare(
        googletest_external
        GIT_REPOSITORY https://gitcode.com/GitHub_Trending/go/googletest.git
        GIT_TAG release-1.12.1
        GIT_SHALLOW TRUE

        DOWNLOAD_DIR ${GOOGLETEST_DIR}
        SOURCE_DIR ${GOOGLETEST_DIR}
    )
    message(STATUS "Preparing googletest")
    FetchContent_MakeAvailable(googletest_external)
    message(STATUS "Preparing googletest - done")
endif()

# ------------------------------------------------------------------------------
# ascend
# ------------------------------------------------------------------------------
if(NOT DEFINED ENV{ASCEND_TOOLKIT_HOME})
    add_subdirectory(${ASCEND_DIR})
endif()

# ------------------------------------------------------------------------------
# build target: boundscheck
# ------------------------------------------------------------------------------
file(GLOB BOUNDSCHECK_SRC "${BOUNDSCHECK_DIR}/src/*.c")

add_library(boundscheck OBJECT
    ${BOUNDSCHECK_SRC}
)
target_include_directories(boundscheck PUBLIC
    ${BOUNDSCHECK_DIR}/include
)
target_compile_options(boundscheck PRIVATE
    -fPIC
)

# ------------------------------------------------------------------------------
# build target: opentelemetry
# ------------------------------------------------------------------------------
file(GLOB_RECURSE OPENTELEMETRY_SRC "${THIRD_PARTY_DIR}/opentelemetry/include/*.cc")

add_library(opentelemetry OBJECT
    ${OPENTELEMETRY_SRC}
)
target_include_directories(opentelemetry PUBLIC
    ${THIRD_PARTY_DIR}/opentelemetry/include
    ${PROTOBUF_DIR}/src
)
target_compile_options(opentelemetry PRIVATE
    -fPIC
)
