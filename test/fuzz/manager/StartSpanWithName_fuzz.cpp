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

#include <string>
#include "FuzzDefs.h"
#include "msServiceProfiler/ServiceProfilerManager.h"


TEST(TestServiceProfilerManager, StartSpanWithName)
{
    char testApi[] = "test_service_profiler_manager_start_span_with_name";
    DT_FUZZ_START(0, FUZZ_RUN_TIMES, testApi, 0)
    {
        printf("\r%d", fuzzSeed + fuzzi);
        // 生成随机字符串作为输入
        char* spanName = DT_SetGetString(&g_Element[0], 5, UINT32_MAX, "span_name");

        try {
            // 调用StartSpanWithName函数
            StartSpanWithName(spanName);
        } catch (const std::exception& e) {
            // 捕获异常，继续测试
        }
    }
    DT_FUZZ_END()
}