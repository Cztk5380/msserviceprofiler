set(MOCK_CPP_DIR "${THIRD_PARTY_DIR}/mock_cpp")
set(UT_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/ut/cpp")
set(ST_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/st/cpp")

set(UT_TARGET ms_service_profiler_run_uts)
set(ST_TARGET ms_service_profiler_run_sts)

file(GLOB UT_SRC ${UT_SOURCE_DIR}/*.cpp)
set(ST_SRC ${ST_SOURCE_DIR}/test.cpp)

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -fprofile-arcs -ftest-coverage")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fprofile-arcs -ftest-coverage")

if(CMAKE_C_COMPILER_VERSION VERSION_LESS "9.0.0")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -lgcov")
endif()


add_compile_options(
    -g
    -Og
    -Wall
    --coverage
)

add_executable(${UT_TARGET}
    ${UT_SRC}
    ${CMAKE_SOURCE_DIR}/cpp/src/Tracer.cpp # getResourceProto has no extern header
)
add_executable(${ST_TARGET}
    ${ST_SRC}
    ${CMAKE_SOURCE_DIR}/cpp/src/ServiceProfilerMspti.cpp # 'CallShowApiInfo' has no extern header
)

target_include_directories(${UT_TARGET}
    PRIVATE
    ${MOCK_CPP_DIR}/include
    ${UT_SOURCE_DIR}/include
)

target_link_libraries(${UT_TARGET} PRIVATE
    mockcpp
    gmock_main
    ms_service_profiler
)
target_link_libraries(${ST_TARGET} PRIVATE
    ms_service_profiler
)

target_compile_options(${UT_TARGET} PRIVATE
    -fno-access-control
    -fpermissive
)

target_compile_definitions(${UT_TARGET} PUBLIC
    ENABLE_PROF
    ENABLE_SERVICE_PROF_UNIT_TEST
)
target_compile_definitions(${ST_TARGET} PUBLIC
    ENABLE_PROF
    ENABLE_SERVICE_PROF_UNIT_TEST
)

