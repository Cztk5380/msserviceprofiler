/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.
 * Description: wrapper header
 * Author: Huawei Technologies Co., Ltd.
 * Create: 2024-12-16
 */
#include <cstdint>
#include "acl/acl.h"
#include "acl/acl_prof.h"

aclError aclprofInit(const char *profilerResultPath, size_t length)
{
    return 0;
}

aclError aclprofFinalize()
{
    return 0;
}

aclprofConfig *aclprofCreateConfig(uint32_t *deviceIdList, uint32_t deviceNums, aclprofAicoreMetrics aicoreMetrics,
                                   aclprofAicoreEvents *aicoreEvents, uint64_t dataTypeConfig)
{
    return nullptr;
}
aclError aclprofDestroyConfig(const aclprofConfig *profilerConfig)
{
    return 0;
}
aclError aclprofSetConfig(aclprofConfigType configType, const char *config, size_t configLength)
{
    return 0;
}

aclError aclprofStart(const aclprofConfig *profilerConfig)
{
    return 0;
}

aclError aclprofStop(const aclprofConfig *profilerConfig)
{
    return 0;
}
