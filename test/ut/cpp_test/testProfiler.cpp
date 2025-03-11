/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <gtest/gtest.h>
#include <mockcpp/mockcpp.hpp>


int Multi(int paramA, int paramB)
{
    return paramA * paramB;
}

TEST(TestMock, TestMock) {
    MOCKER(Multi).stubs().will(returnValue(100000));

    EXPECT_EQ(100000, Multi(1, 2));
}