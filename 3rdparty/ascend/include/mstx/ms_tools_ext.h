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
