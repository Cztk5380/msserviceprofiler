/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.
 */

#include <fstream>
#include <string>
#include "FuzzDefs.h"
#include "ServiceProfilerManager.h"
#include "ServiceProfilerDbWriter.h"


TEST(TestServiceProfilerManager, MarkEventTest)
{
    char testApi[] = "test_service_profiler_mark_event_fuzz";
    std::string fileName = "../build/markevent.dump";
    std::string context = "default_context";
    DT_FUZZ_START(0, FUZZ_RUN_TIMES, testApi, 0)
    {
        printf("\r%d", fuzzSeed + fuzzi);
        std::ofstream fileout(fileName, std::ios::app);

        char* msg = DT_SetGetString(&g_Element[0], context.length() + 1, 10000,
                                    const_cast<char *>(context.c_str()));
        std::string message(msg);
        fileout << message << "\t" << message.length() << "\n";
        // 调用被测函数
        try {
            MarkEvent(msg);
        } catch(const std::exception& e) {
            // 处理异常
            std::cout << "Exception caught: " << e.what() << std::endl;
        }
        fileout.close();
    }
    DT_FUZZ_END()
}


TEST(TestServiceProfilerManager, MarkSpanAttrTest)
{
    char testApi[] = "test_service_profiler_mark_span_Attr";
    std::string fileName = "../build/markspanattr.dump";
    std::string context = "default_context";
    DT_FUZZ_START(0, FUZZ_RUN_TIMES, testApi, 0)
    {
        printf("\r%d", fuzzSeed + fuzzi);
        std::ofstream fileout(fileName, std::ios::app);

        char* msg = DT_SetGetString(&g_Element[0], context.length() + 1, 10000,
                                    const_cast<char *>(context.c_str()));
        std::string message(msg);
        fileout << message << "\t" << message.length() << "\n";
        try {
            auto span = StartSpan();
            MarkSpanAttr(msg, span);
            EndSpan(span);
        } catch(const std::exception& e) {
            // 处理异常
            std::cout << "Exception caught: " << e.what() << std::endl;
        }
        fileout.close();
    }
    DT_FUZZ_END()
}