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

#define ENABLE_SERVICE_PROF_UNIT_TEST

#include <gtest/gtest.h>
#include <string>
#include <dlfcn.h>
#include <unistd.h>

// 包含你项目中的头文件
#include "msServiceProfiler/msServiceProfiler.h"
#include "msServiceProfiler/ServiceProfilerDbWriter.h"

using namespace msServiceProfiler;
// 定义一个全局变量，用于控制 gethostname 返回值
int mock_gethostname_return_value = 0;

// 保存真正的 gethostname 函数指针
static int (*real_gethostname)(char *, size_t) = nullptr;

extern "C" {
// 替换的 gethostname 函数
int gethostname(char *name, size_t len)
{
    if (!real_gethostname) {
        real_gethostname = (int (*)(char *, size_t))dlsym(RTLD_NEXT, "gethostname");
    }

    std::cerr << "nihao" << mock_gethostname_return_value << std::endl;
    if (mock_gethostname_return_value != 0) {
        return mock_gethostname_return_value;  // 模拟失败
    }

    return real_gethostname(name, len);  // 正常调用
}

// 设置 mock 返回值的 API
void SetMockGetHostNameReturnValue(int value)
{
    mock_gethostname_return_value = value;
}

}  // extern "C"

TEST(GetHostNameTest, GetHostName_Success_ReturnsValidHostname)
{
    // 设置 gethostname 返回 0（模拟成功）
    SetMockGetHostNameReturnValue(0);

    // 调用被测函数（使用命名空间）
    std::string result = MsUtils::GetHostName();

    // 验证返回值不为空字符串
    EXPECT_FALSE(result.empty());
}

TEST(WaitForAllDumpTest, WaitForAllDump_Success)
{
    try {
        auto start = std::chrono::steady_clock::now();

        // 直接调用目标函数
        msServiceProfiler::ServiceProfilerThreadWriter<DBFile::SERVICE>::GetWriter().WaitForAllDump();

        auto duration = std::chrono::duration_cast<std::chrono::seconds>(std::chrono::steady_clock::now() - start);

        // 判断函数在合理时间内完成（例如不超过 2s）
        EXPECT_LT(duration.count(), 2) << "WaitForAllDump() took too long, possibly stuck or not configured properly.";

        std::cout << "Test passed, execution time: " << duration.count() << "s" << std::endl;
    } catch (const std::exception &e) {
        FAIL() << "Exception during WaitForAllDump(): " << e.what();
    } catch (...) {
        FAIL() << "Unknown exception during WaitForAllDump().";
    }
}

int main(int argc, char **argv)
{
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}