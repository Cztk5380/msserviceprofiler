add_library(ascendcl
    SHARED
    ${CMAKE_CURRENT_SOURCE_DIR}/src/BuildAcl.cpp
)
add_library(msprofiler
    SHARED
    ${CMAKE_CURRENT_SOURCE_DIR}/src/BuildAclProf.cpp
)
add_library(ms_tools_ext
    SHARED
    ${CMAKE_CURRENT_SOURCE_DIR}/src/BuildMstx.cpp
)
add_library(mspti
    SHARED
    ${CMAKE_CURRENT_SOURCE_DIR}/src/Buildmspti.cpp
)

target_include_directories(ascendcl
    PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_include_directories(msprofiler
    PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_include_directories(ms_tools_ext
    PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_include_directories(mspti
    PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

