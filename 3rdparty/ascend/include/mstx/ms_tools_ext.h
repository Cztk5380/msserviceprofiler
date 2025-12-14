/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.
 * Description: wrapper header
 * Author: Huawei Technologies Co., Ltd.
 * Create: 2024-12-16
 */

#ifndef MS_SERVICE_PROFILER_MS_TOOLS_EXT_H
#define MS_SERVICE_PROFILER_MS_TOOLS_EXT_H

#include <cstdint>
#include <acl/acl.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MSTX_INVALID_ID 0

typedef uint64_t  mstxRangeId;

void mstxMarkA(const char* message, aclrtStream stream);
mstxRangeId mstxRangeStartA(const char* message, aclrtStream stream);
void mstxRangeEnd(mstxRangeId id);

#ifdef __cplusplus
}
#endif

#endif //_MS_TOOLS_EXT_H
