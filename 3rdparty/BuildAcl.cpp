/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.
 * Description: wrapper header
 * Author: Huawei Technologies Co., Ltd.
 * Create: 2024-12-16
 */

#ifndef MS_SERVICE_PROFILER_BUILD_ACL_FUNCTIONS_H
#define MS_SERVICE_PROFILER_BUILD_ACL_FUNCTIONS_H
#include "acl/acl.h"

aclError aclInit(const char *configPath)
{
    return 0;
}

aclError aclrtSetDevice(int32_t deviceId)
{
    return 0;
}

aclError aclrtCreateContext(aclrtContext *context, int32_t deviceId)
{
    return 0;
}

aclError aclrtCreateStream(aclrtStream *stream)
{
    return 0;
}

#endif  //_BUILD_ACL_FUNCTIONS_H
