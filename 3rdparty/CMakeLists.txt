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

message(STATUS "Preparing boundscheck")
FetchContent_GetProperties(boundscheck_external)
if(NOT boundscheck_external_POPULATED)
    FetchContent_Populate(boundscheck_external)
endif()
message(STATUS "Preparing boundscheck - done")

message(STATUS "Preparing protobuf")
if(NOT EXISTS ${PROTOBUF_DIR})
    execute_process(
        COMMAND git clone https://gitcode.com/gh_mirrors/pro/protobuf.git --depth 1 -b v3.21.9 ${PROTOBUF_DIR}
        RESULT_VARIABLE GIT_RESULT
        OUTPUT_VARIABLE GIT_OUTPUT
        ERROR_VARIABLE GIT_ERROR
    )
    if(NOT ${GIT_RESULT} EQUAL 0)
        message(FATAL_ERROR "Failed to download protobuf: ${GIT_OUTPUT} ${GIT_ERROR}")
    endif()

    execute_process(
        COMMAND ${CMAKE_COMMAND} -S ${PROTOBUF_DIR} -B ${PROTOBUF_BUILD_DIR} -Dprotobuf_BUILD_TESTS=OFF -Dprotobuf_BUILD_SHARED_LIBS=OFF -DCMAKE_CXX_FLAGS=-D_GLIBCXX_USE_CXX11_ABI=0 -DCMAKE_POSITION_INDEPENDENT_CODE=ON
        RESULT_VARIABLE PROTOBUF_RESULT
        OUTPUT_VARIABLE PROTBUF_OUTPUT
        ERROR_VARIABLE PROTOBUF_ERROR
    )
    if(NOT PROTOBUF_RESULT EQUAL 0)
        message(FATAL_ERROR "Failed to configure protobuf: ${PROTOBUF_OUTPUT} ${PROTOBUF_ERROR}")
    endif()

    execute_process(
        COMMAND ${CMAKE_COMMAND} --build "${PROTOBUF_BUILD_DIR}" -j ${NPROC}
        RESULT_VARIABLE PROTOBUF_RESULT
        OUTPUT_VARIABLE PROTBUF_OUTPUT
        ERROR_VARIABLE PROTOBUF_ERROR
    )
    if(NOT PROTOBUF_RESULT EQUAL 0)
        message(FATAL_ERROR "Failed to build protobuf: ${PROTOBUF_OUTPUT} ${PROTOBUF_ERROR}")
    endif()
endif()
message(STATUS "Preparing protobuf - done")

message(STATUS "Preparing opentelemtry")
execute_process(
    COMMAND ${PROTOBUF_BUILD_DIR}/protoc opentelemetry/proto/trace/v1/trace.proto -I ${THIRD_PARTY_DIR} --cpp_out=${THIRD_PARTY_DIR}/opentelemetry/include
    COMMAND ${PROTOBUF_BUILD_DIR}/protoc opentelemetry/proto/resource/v1/resource.proto -I ${THIRD_PARTY_DIR} --cpp_out=${THIRD_PARTY_DIR}/opentelemetry/include
    COMMAND ${PROTOBUF_BUILD_DIR}/protoc opentelemetry/proto/common/v1/common.proto -I ${THIRD_PARTY_DIR} --cpp_out=${THIRD_PARTY_DIR}/opentelemetry/include
    COMMAND ${PROTOBUF_BUILD_DIR}/protoc opentelemetry/proto/collector/trace/v1/trace_service.proto -I ${THIRD_PARTY_DIR} --cpp_out=${THIRD_PARTY_DIR}/opentelemetry/include
    OUTPUT_VARIABLE PROTOC_OUTPUT
    ERROR_VARIABLE PROTOC_ERROR
    RESULT_VARIABLE PROTOC_RESULT
)
if(NOT PROTOC_RESULT EQUAL 0)
    message(FATAL_ERROR "Failed to prepare opentelemtry: ${PROTOC_OUTPUT} ${PROTOC_ERROR}")
endif()
message(STATUS "Preparing opentelemtry - done")
message(STATUS "Preparing json")
FetchContent_GetProperties(json_external)
if(NOT json_external_POPULATED)
    FetchContent_Populate(json_external)
endif()
message(STATUS "Preparing json - done")

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

add_subdirectory(${ASCEND_DIR})

# -- dependency in build steps
file(GLOB BOUNDSCHECK_SRC "${BOUNDSCHECK_DIR}/src/*.c")
file(GLOB_RECURSE OPENTELEMETRY_SRC "${THIRD_PARTY_DIR}/opentelemetry/include/*.cc")

add_library(boundscheck OBJECT
    ${BOUNDSCHECK_SRC}
)
target_include_directories(boundscheck PUBLIC
    ${BOUNDSCHECK_DIR}/include
)
target_compile_options(boundscheck PRIVATE
    -fPIC
)

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

