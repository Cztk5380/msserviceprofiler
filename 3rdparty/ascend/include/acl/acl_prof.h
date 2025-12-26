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

#ifndef MS_SERVICE_PROFILER_ACL_PROF_H
#define MS_SERVICE_PROFILER_ACL_PROF_H

#include <cstdlib>
#include <cstdint>
#include "acl/acl.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct aclprofAicoreEvents aclprofAicoreEvents;
typedef struct aclprofConfig aclprofConfig;
typedef enum {
    ACL_AICORE_ARITHMETIC_UTILIZATION = 0,
    ACL_AICORE_PIPE_UTILIZATION = 1,
    ACL_AICORE_MEMORY_BANDWIDTH = 2,
    ACL_AICORE_L0B_AND_WIDTH = 3,
    ACL_AICORE_RESOURCE_CONFLICT_RATIO = 4,
    ACL_AICORE_MEMORY_UB = 5,
    ACL_AICORE_L2_CACHE = 6,
    ACL_AICORE_NONE = 0xFF
} aclprofAicoreMetrics;
typedef enum {
    ACL_PROF_ARGS_MIN = 0,
    ACL_PROF_STORAGE_LIMIT,
    ACL_PROF_AIV_METRICS,
    ACL_PROF_SYS_HARDWARE_MEM_FREQ,
    ACL_PROF_LLC_MODE,
    ACL_PROF_SYS_IO_FREQ,
    ACL_PROF_SYS_INTERCONNECTION_FREQ,
    ACL_PROF_DVPP_FREQ,
    ACL_PROF_HOST_SYS,
    ACL_PROF_HOST_SYS_USAGE,
    ACL_PROF_HOST_SYS_USAGE_FREQ,
    ACL_PROF_ARGS_MAX,
} aclprofConfigType;

aclError aclprofInit(const char *profilerResultPath, size_t length);
aclError aclprofFinalize();
aclprofConfig *aclprofCreateConfig(uint32_t *deviceIdList, uint32_t deviceNums,
                                   aclprofAicoreMetrics aicoreMetrics, aclprofAicoreEvents *aicoreEvents,
                                   uint64_t dataTypeConfig);
aclError aclprofDestroyConfig(const aclprofConfig *profilerConfig);
aclError aclprofSetConfig(aclprofConfigType configType, const char *config, size_t configLength);

aclError aclprofStart(const aclprofConfig *profilerConfig);
aclError aclprofStop(const aclprofConfig *profilerConfig);
#ifdef __cplusplus
}
#endif

#endif //_ACL_PROF_H
