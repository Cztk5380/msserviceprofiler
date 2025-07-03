/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#include "FuzzDefs.h"

GTEST_API_ int main(int argc, char **argv)
{
    int singleCaseTimeout = 60; // second
    // 设置报告路径
    DT_Set_Report_Path(REPORT_PATH.c_str());
    // 设置使能fork模式，每个测试用例单独在子进程运行
    DT_SetEnableFork(1);
    // 检测大内存使用，超过2048M使用或者1024M分配则当做bug报错
    DT_SetCheckOutOfMemory(1024, 2048);
    // 是能内存泄漏单次执行检测，默认也开启
    DT_Enable_Leak_Check(0, 0);
    // 设置用例单次执行多久超时
    DT_Set_TimeOut_Second(singleCaseTimeout);
    testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}