/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
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