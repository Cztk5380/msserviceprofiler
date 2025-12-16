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