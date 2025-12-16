set(PROTOBUF_DIR ${CMAKE_CURRENT_SOURCE_DIR}/protobuf)
set(PROTOBUF_BUILD_DIR ${PROTOBUF_DIR}/build)
set(SECUREC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/securec)
set(ASCEND_DIR ${CMAKE_CURRENT_SOURCE_DIR}/ascend)

include(FetchContent)

FetchContent_Declare(
    protobuf_external
    URL "https://cmc.cloudartifact.szv.dragon.tools.huawei.com/artifactory/opensource_general/protobuf/3.21.9/package/protobuf-3.21.9.zip"

    DOWNLOAD_DIR ${PROTOBUF_DIR}
    SOURCE_DIR ${PROTOBUF_DIR}
    TLS_VERIFY OFF
)
FetchContent_Declare(
    securec_external
    GIT_REPOSITORY "https://codehub-dg-y.huawei.com/hwsecurec_group/huawei_secure_c.git"
    GIT_TAG "tag_Huawei_Secure_C_V100R001C01SPC012B002_00001"
    GIT_SHALLOW TRUE
    GIT_PROGRESS TRUE
    TLS_VERIFY OFF

    DOWNLOAD_DIR ${SECUREC_DIR}
    SOURCE_DIR ${SECUREC_DIR}
)

message(STATUS "Preparing securec")
FetchContent_GetProperties(securec_external)
if(NOT securec_external_POPULATED)
    FetchContent_Populate(securec_external)
endif()
message(STATUS "Preparing securec - done")

message(STATUS "Preparing protobuf")
FetchContent_GetProperties(protobuf_external)
if(NOT protobuf_external_POPULATED)
    FetchContent_Populate(protobuf_external)

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

if(ms_service_profiler_BUILD_TESTS)
    set(GOOGLETEST_DIR ${CMAKE_CURRENT_SOURCE_DIR}/googletest)
    set(BOOST_DIR ${CMAKE_CURRENT_SOURCE_DIR}/boost)
    set(MOCK_CPP_DIR ${CMAKE_CURRENT_SOURCE_DIR}/mock_cpp)

    FetchContent_Declare(
        googletest_external
        GIT_REPOSITORY https://codehub-dg-y.huawei.com/OpenSourceCenter/googletest.git
        GIT_TAG release-1.12.1
        GIT_SHALLOW TRUE
        GIT_PROGRESS TRUE
    	TLS_VERIFY OFF

        DOWNLOAD_DIR ${GOOGLETEST_DIR}
        SOURCE_DIR ${GOOGLETEST_DIR}
    )
    FetchContent_Declare(
        boost_external
        GIT_REPOSITORY https://codehub-dg-y.huawei.com/OpenSourceCenter/boostorg/boost.git
        GIT_TAG 1.72.0-h1
        GIT_SHALLOW TRUE
        GIT_PROGRESS TRUE
    	TLS_VERIFY OFF

        DOWNLOAD_DIR ${BOOST_DIR}
        SOURCE_DIR ${BOOST_DIR}
    )
    FetchContent_Declare(
        mock_cpp_external
        GIT_REPOSITORY https://szv-y.codehub.huawei.com/mindstudio/MindStudio_Opensource/mock_cpp.git
        GIT_TAG msprof
        GIT_SHALLOW TRUE
        GIT_PROGRESS TRUE

        DOWNLOAD_DIR ${MOCK_CPP_DIR}
        SOURCE_DIR ${MOCK_CPP_DIR}
    )

    message(STATUS "Preparing googletest")
    FetchContent_MakeAvailable(googletest_external)
    message(STATUS "Preparing googletest - done")

    message(STATUS "Preparing boost")
    if(EXISTS ${BOOST_DIR})
        message(STATUS "Found boost - ${BOOST_DIR}")
    else()
        FetchContent_GetProperties(boost_external)
        if(NOT boost_external_POPULATED)
            FetchContent_Populate(boost_external)
        endif()
    endif()
    message(STATUS "Preparing boost - done")

    message(STATUS "Preparing mock_cpp")
    if(EXISTS ${MOCK_CPP_DIR})
        message(STATUS "Found mock_cpp - ${MOCK_CPP_DIR}")
        add_subdirectory(${MOCK_CPP_DIR})
    else()
        FetchContent_MakeAvailable(mock_cpp_external)
    endif()
    target_include_directories(mockcpp PUBLIC
        ${BOOST_DIR}
    )
    message(STATUS "Preparing mock_cpp - done")
endif()

add_subdirectory(${ASCEND_DIR})

# -- dependency in build steps
file(GLOB SECUREC_SRC "${SECUREC_DIR}/src/*.c")
file(GLOB_RECURSE OPENTELEMETRY_SRC "${THIRD_PARTY_DIR}/opentelemetry/include/*.cc")

add_library(securec OBJECT
    ${SECUREC_SRC}
)
target_include_directories(securec PUBLIC
    ${SECUREC_DIR}/include
)
target_compile_options(securec PRIVATE
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


include(ExternalProject)
ExternalProject_Add(
    json_external
    URL "https://cmc-szver-artifactory.cmc.tools.huawei.com/artifactory/cmc-software-release/Baize%20C/AscendTransformerBoost/1.0.0/asdops_dependency/common/nlohmannjson-v3.11.2.tar.gz"
    SOURCE_DIR "${THIRD_PARTY_DIR}/json"
    DOWNLOAD_DIR "nlohmann-json"
    TLS_VERIFY OFF

    DOWNLOAD_NO_PROGRESS
    TLS_VERIFY FALSE

    CONFIGURE_COMMAND ""
    BUILD_COMMAND ""
    INSTALL_COMMAND ""
)

