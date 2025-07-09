/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <gtest/gtest.h>
#include <gmock/gmock.h>
#include <mockcpp/mockcpp.hpp>
#include "msServiceProfiler/DbBuffer.h"
#include "stubs.h"

using namespace ::testing;
using namespace ::mockcpp;
using namespace msServiceProfiler;

class GlobalStub {
public:
    static GlobalStub &GetInstance()
    {
        static GlobalStub gstub;
        return gstub;
    }

public:
    MockStubFunc stubs;

private:
    GlobalStub() = default;
};

// Test fixture
class TestDbBuffer : public ::testing::Test {
protected:
    void SetUp() override
    {}

    void TearDown() override
    {}
};

TEST_F(TestDbBuffer, CallPushWhenOneNullExceptFalse)
{
    // 传入Null
    DbBuffer buffer;
    EXPECT_FALSE(buffer.Push(nullptr));
}

TEST_F(TestDbBuffer, CallPushWhenOneExceptSuccess)
{
    // 正常push，正常 pop
    DbBuffer buffer;
    DbActivityMarker *pMarker = nullptr;
    EXPECT_TRUE(buffer.Push((DbActivityMarker *)1));

    EXPECT_EQ(buffer.Pop(1, &pMarker), 1);
    EXPECT_EQ(pMarker, (DbActivityMarker *)1);
}

TEST_F(TestDbBuffer, CallPushWhenOverLineSizeExceptFalse)
{
    // 正常push超量的数据
    DbBuffer buffer;
    DbActivityMarker *pMarker = nullptr;
    size_t times = PTR_ARRAY_SIZE * PTR_ARRAY_PRE_SIZE + 1;
    while (--times) {
        buffer.Push((DbActivityMarker *)1);
    };
    EXPECT_FALSE(buffer.Push((DbActivityMarker *)1));

    EXPECT_EQ(buffer.PushCnt(), PTR_ARRAY_SIZE * PTR_ARRAY_PRE_SIZE + 1);
    EXPECT_EQ(buffer.Size(), PTR_ARRAY_SIZE * PTR_ARRAY_PRE_SIZE - 1);
    while (buffer.Pop(1, &pMarker)) {
    }
    EXPECT_EQ(buffer.MaxCntInBuffer(), PTR_ARRAY_SIZE * PTR_ARRAY_PRE_SIZE - 1);
}

TEST_F(TestDbBuffer, CallPopWhen300ItemsExceptEq)
{
    // 正常push 和pop 出来的数据一样
    DbBuffer buffer;
    DbActivityMarkerPtr pMarkers[400] = {nullptr};
    const size_t PUSH_TIEMS = 300;
    size_t times = PUSH_TIEMS + 1;
    while (--times) {
        buffer.Push((DbActivityMarker *)times);
    };
    EXPECT_EQ(buffer.Pop(400, pMarkers), PUSH_TIEMS);
    EXPECT_EQ(buffer.PopCnt(), PUSH_TIEMS);
    times = PUSH_TIEMS + 1;
    int index = 0;
    while (--times) {
        EXPECT_EQ(pMarkers[index], times);
        ++index;
    };
}

TEST_F(TestDbBuffer, CallAutoDestructionExceptOK)
{
    // 传入正常数据
    DbBuffer buffer;
    DbActivityMarkerPtr pMarker = new DbActivityMarker();
    EXPECT_TRUE(buffer.Push(pMarker));
    // 自动析构没有异常
}
