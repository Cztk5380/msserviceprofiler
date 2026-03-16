find_package(Threads REQUIRED)
find_package(SQLite3 REQUIRED)
find_package(Protobuf REQUIRED
    PATHS
        ${THIRD_PARTY_DIR}/protobuf/build
    NO_DEFAULT_PATH
)

set(CMAKE_SKIP_RPATH TRUE)

file(GLOB_RECURSE PROFILER_SRC "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp")
add_library(ms_service_profiler SHARED
    ${PROFILER_SRC}
)

target_include_directories(ms_service_profiler PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${THIRD_PARTY_DIR}/json/include
)

target_compile_options(ms_service_profiler PRIVATE
    -fvisibility-inlines-hidden
    -fPIC
    -fstack-protector-all
    -fno-strict-aliasing
    -fno-common
    -Wfloat-equal
    -Wextra
    -D_FORTIFY_SOURCE=2
    -DENABLE_PROF
    -O2
)

if(ms_service_profiler_BUILD_TESTS)
    target_compile_options(ms_service_profiler PRIVATE
        -fvisibility=default
    )
else()
    target_compile_options(ms_service_profiler PRIVATE
        -fvisibility=hidden
    )
endif()

target_link_libraries(ms_service_profiler PUBLIC
    # ascend related
    ascendcl
    msprofiler
    ms_tools_ext
    mspti
    # 3rd parties
    sqlite3
    boundscheck
    opentelemetry
    protobuf::libprotobuf
    # system related
    dl
    pthread
    rt
)

if (DEFINED ENV{ASCEND_TOOLKIT_HOME})
    set(TOOLKIT_BASE_PATH $ENV{ASCEND_TOOLKIT_HOME})
    message(STATUS ${TOOLKIT_BASE_PATH})
    target_include_directories(ms_service_profiler PRIVATE
        ${TOOLKIT_BASE_PATH}/include
        ${TOOLKIT_BASE_PATH}/aarch64-linux/include
        ${TOOLKIT_BASE_PATH}/x86_64-linux/include
    )
    target_link_directories(ms_service_profiler PRIVATE
        ${TOOLKIT_BASE_PATH}/lib64
        ${TOOLKIT_BASE_PATH}/aarch64-linux/devlib
        ${TOOLKIT_BASE_PATH}/x86_64-linux/devlib
    )
endif ()


target_link_options(ms_service_profiler PRIVATE
    -Wl,-z,relro,-z,now,-z,noexecstack
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
    $<$<NOT:$<STREQUAL:${CMAKE_BUILD_TYPE},Debug>>:-s>
)

install(TARGETS ms_service_profiler
        LIBRARY DESTINATION ${CMAKE_INSTALL_PREFIX}/ms_service_profiler
)