/* -------------------------------------------------------------------------
 * This file is part of the MindStudio project.
 * Copyright (c) 2025 Huawei Technologies Co.,Ltd.
 *
 * MindStudio is licensed under Mulan PSL v2.
 * You can use this software according to the terms and conditions of the Mulan PSL v2.
 * You may obtain a copy of Mulan PSL v2 at:
 *
 *          http://license.coscl.org.cn/MulanPSL2
 *
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
 * EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
 * MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
 * See the Mulan PSL v2 for more details.
 * -------------------------------------------------------------------------
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
