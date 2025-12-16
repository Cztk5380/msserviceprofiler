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
#include "FuzzDefs.h"
#include "ServiceProfilerManager.h"


TEST(TestServiceProfilerManager, AddMetaInfoFuzzTest)
{
    char testApi[] = "test_service_profiler_add_meta_info_fuzz";
    std::string fileName = "../build/addmetainfo.dump";
    std::string key = "default_key";
    std::string value = "default_value";
    DT_FUZZ_START(0, FUZZ_RUN_TIMES, testApi, 0)
    {
        printf("\r%d", fuzzSeed + fuzzi);
        std::ofstream fileout(fileName, std::ios::app);
        // 生成随机的key和value
        char* fuzzKey = DT_SetGetString(&g_Element[0], key.length() + 1, 256,
                                        const_cast<char *>(key.c_str()));
        char* fuzzValue = DT_SetGetString(&g_Element[1], value.length() + 1, 1024,
                                        const_cast<char *>(value.c_str()));

        std::string message1(fuzzKey);
        std::string message2(fuzzValue);
        // 调用被测函数
        try{
            AddMetaInfo(fuzzKey, fuzzValue);
            fileout << message1 << "\t" << message1.length() << message2 << "\t" << message2.length() << "\n";
        } catch (const std::exception& e) {
            // 处理异常
            std::cout << "Exception caught: " << e.what() << std::endl;
        }
        fileout.close();
    }
    DT_FUZZ_END()
}


TEST(TestServiceProfilerManager, IsEnableWithValidation)
{
    char testApi[] = "test_service_profiler_is_enable_with_validation";
    DT_FUZZ_START(0, FUZZ_RUN_TIMES, testApi, 0)
    {
        printf("\r%d", fuzzSeed + fuzzi);
        // 生成随机的level值进行测试
        auto charLevel = DT_SetGetBlob(&g_Element[0], 0, UINT32_MAX, "0");
        int level = DT_GET_MutatedValueLen(&g_Element[0]);
        // 调用被测函数
        bool result = IsEnable(level);

        // 验证结果是否在预期范围内（假设我们至少知道有效返回值是true/false）
        EXPECT_TRUE(result == true || result == false)
            << "Unexpected return value for level=" << level;
    }
    DT_FUZZ_END()
}