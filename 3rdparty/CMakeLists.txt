# ------------------------------------------------------------------------------
# prepare
# ------------------------------------------------------------------------------
find_package(Git)
if (NOT GIT_FOUND)
    message(FATAL_ERROR "Git is required to clone protobuf")
endif ()

set(ASCEND_DIR ${CMAKE_CURRENT_SOURCE_DIR}/ascend)
set(BOUNDSCHECK_DIR ${CMAKE_CURRENT_SOURCE_DIR}/boundscheck)
set(PROTOBUF_DIR ${CMAKE_CURRENT_SOURCE_DIR}/protobuf)
set(PROTOBUF_BUILD_DIR ${PROTOBUF_DIR}/build)
set(JSON_DIR ${CMAKE_CURRENT_SOURCE_DIR}/json)

include(FetchContent)

# ------------------------------------------------------------------------------
# boundscheck
# ------------------------------------------------------------------------------
message(STATUS "Preparing boundscheck")
if(NOT EXISTS ${BOUNDSCHECK_DIR})
    FetchContent_Declare(
        boundscheck_external
        GIT_REPOSITORY https://gitcode.com/openeuler/libboundscheck
        GIT_SHALLOW TRUE

        DOWNLOAD_DIR ${BOUNDSCHECK_DIR}
        SOURCE_DIR ${BOUNDSCHECK_DIR}
    )
    FetchContent_Populate(boundscheck_external)
else()
    message(STATUS "boundscheck already exists, skipping download")
endif()
message(STATUS "Preparing boundscheck - done")

# ------------------------------------------------------------------------------
# json
# ------------------------------------------------------------------------------
message(STATUS "Preparing json")
if(NOT EXISTS ${JSON_DIR})
    FetchContent_Declare(
        json_external
        GIT_REPOSITORY https://gitcode.com/GitHub_Trending/js/json.git
        GIT_TAG v3.11.2
        GIT_SHALLOW TRUE

        DOWNLOAD_DIR ${JSON_DIR}
        SOURCE_DIR ${JSON_DIR}
    )
    FetchContent_Populate(json_external)
else()
    message(STATUS "json already exists, skipping download")
endif()
message(STATUS "Preparing json - done")

# ------------------------------------------------------------------------------
# protobuf
# ------------------------------------------------------------------------------
message(STATUS "Preparing protobuf")

set(PROTOC_CMD ${PROTOBUF_BUILD_DIR}/protoc)

if(NOT EXISTS ${PROTOBUF_DIR})
    message(STATUS "Cloning protobuf v3.21.9 ...")
    execute_process(
        COMMAND git clone https://gitcode.com/gh_mirrors/pro/protobuf.git
                --depth 1 -b v3.21.9 ${PROTOBUF_DIR}
        RESULT_VARIABLE _clone_result
        OUTPUT_VARIABLE _clone_output
        ERROR_VARIABLE  _clone_error
    )
    if(NOT _clone_result EQUAL 0)
        message(FATAL_ERROR "Failed to clone protobuf:\n${_clone_output}\n${_clone_error}")
    endif()
endif()

if(NOT EXISTS ${PROTOC_CMD})
    message(STATUS "protoc not found, building protobuf from source ...")

    execute_process(
        COMMAND ${CMAKE_COMMAND}
            -S ${PROTOBUF_DIR}
            -B ${PROTOBUF_BUILD_DIR}
            -Dprotobuf_BUILD_TESTS=OFF
            -Dprotobuf_BUILD_SHARED_LIBS=OFF
            -DCMAKE_CXX_FLAGS=-D_GLIBCXX_USE_CXX11_ABI=0
            -DCMAKE_POSITION_INDEPENDENT_CODE=ON
        RESULT_VARIABLE _configure_result
        OUTPUT_VARIABLE _configure_output
        ERROR_VARIABLE  _configure_error
    )
    if(NOT _configure_result EQUAL 0)
        message(FATAL_ERROR "Failed to configure protobuf:\n${_configure_output}\n${_configure_error}")
    endif()

    execute_process(
        COMMAND ${CMAKE_COMMAND} --build ${PROTOBUF_BUILD_DIR} -j ${NPROC}
        RESULT_VARIABLE _build_result
        OUTPUT_VARIABLE _build_output
        ERROR_VARIABLE  _build_error
    )
    if(NOT _build_result EQUAL 0)
        message(FATAL_ERROR "Failed to build protobuf:\n${_build_output}\n${_build_error}")
    endif()

    if(NOT EXISTS ${PROTOC_CMD})
        message(FATAL_ERROR "protobuf build succeeded but protoc not found at: ${PROTOC_CMD}")
    endif()
else()
    message(STATUS "protoc already exists at ${PROTOC_CMD}, skipping build")
endif()

message(STATUS "Preparing protobuf - done")

# ------------------------------------------------------------------------------
# opentelemetry protoc generating code
# ------------------------------------------------------------------------------
message(STATUS "Preparing opentelemetry")

set(PROTOC_INCLUDE_DIR ${THIRD_PARTY_DIR})
set(PROTOC_OUT_DIR ${THIRD_PARTY_DIR}/opentelemetry/include)

set(OPENTELEMETRY_PROTOS
    opentelemetry/proto/trace/v1/trace.proto
    opentelemetry/proto/resource/v1/resource.proto
    opentelemetry/proto/common/v1/common.proto
    opentelemetry/proto/collector/trace/v1/trace_service.proto
)

foreach(PROTO_FILE ${OPENTELEMETRY_PROTOS})
    if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/${PROTO_FILE}")
        message(FATAL_ERROR "Proto file not found: ${CMAKE_CURRENT_SOURCE_DIR}/${PROTO_FILE}")
    endif()

    execute_process(
        COMMAND ${PROTOC_CMD} ${PROTO_FILE}
                -I ${PROTOC_INCLUDE_DIR}
                --cpp_out=${PROTOC_OUT_DIR}
        RESULT_VARIABLE _protoc_result
        OUTPUT_VARIABLE _protoc_output
        ERROR_VARIABLE  _protoc_error
    )
    if(NOT _protoc_result EQUAL 0)
        message(FATAL_ERROR "Failed to compile proto [${PROTO_FILE}]:\n${_protoc_output}\n${_protoc_error}")
    endif()
endforeach()

message(STATUS "Preparing opentelemetry - done")

# ------------------------------------------------------------------------------
# googletest
# ------------------------------------------------------------------------------
if(ms_service_profiler_BUILD_TESTS)
    set(GOOGLETEST_DIR ${CMAKE_CURRENT_SOURCE_DIR}/googletest)

    if(NOT EXISTS ${GOOGLETEST_DIR})
        message(STATUS "Preparing googletest")
        FetchContent_Declare(
            googletest_external
            GIT_REPOSITORY https://gitcode.com/GitHub_Trending/go/googletest.git
            GIT_TAG release-1.12.1
            GIT_SHALLOW TRUE

            DOWNLOAD_DIR ${GOOGLETEST_DIR}
            SOURCE_DIR ${GOOGLETEST_DIR}
        )
        FetchContent_MakeAvailable(googletest_external)
        message(STATUS "Preparing googletest - done")
    else()
        message(STATUS "googletest already exists, skipping download")
        add_subdirectory(${GOOGLETEST_DIR} ${CMAKE_BINARY_DIR}/googletest)
    endif()
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
