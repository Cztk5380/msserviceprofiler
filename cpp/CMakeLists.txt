find_package(Threads REQUIRED)
find_package(SQLite3 REQUIRED)
find_package(Protobuf REQUIRED
    PATHS
        ${THIRD_PARTY_DIR}/protobuf/build
    NO_DEFAULT_PATH
)

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

target_link_options(ms_service_profiler PRIVATE
    -Wl,-z,relro,-z,now,-z,noexecstack
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
    $<$<NOT:$<STREQUAL:${CMAKE_BUILD_TYPE},Debug>>:-s>
)

install(TARGETS ms_service_profiler
        LIBRARY DESTINATION ${CMAKE_INSTALL_PREFIX}/ms_service_profiler
)

