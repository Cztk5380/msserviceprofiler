set(BUILD_ENV_MSPROF_DEPEND_PATH /usr1/slave1/msprof/collector/dvvp/depend/inc)
set(BUILD_ENV_MSPROF_DEPEND_ACL_PATH /usr1/slave1/msprof/collector/dvvp/depend/inc/acl)
set(BUILD_ENV_MSPROF_DEPEND_API_PATH /usr1/slave1/msprof/collector/dvvp/depend/inc/profapi)
set(BUILD_ENV_MSPROF_PATH /usr1/slave1/msprof/collector/inc/external)
set(BUILD_ENV_MSTX_PATH /usr1/slave1/mstx/include)
set(BUILD_INCLUDE_LIST
        ${BUILD_ENV_MSTX_PATH}
        ${BUILD_ENV_MSPROF_PATH}
        ${BUILD_ENV_MSPROF_DEPEND_PATH}
        ${BUILD_ENV_MSPROF_DEPEND_ACL_PATH}
        ${BUILD_ENV_MSPROF_DEPEND_API_PATH}
        PARENT_SCOPE
)

include_directories(
        ${BUILD_INCLUDE_LIST}
        ${CMAKE_CURRENT_SOURCE_DIR}
)

add_library(ascendcl
        SHARED
        ./BuildAcl.cpp
)
add_library(msprofiler
        SHARED
        ./BuildAclProf.cpp
)
add_library(ms_tools_ext
        SHARED
        ./BuildMstx.cpp
)