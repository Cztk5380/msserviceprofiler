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
    EXPECT_EQ(buffer.Push(nullptr), nullptr);

    std::unique_ptr<NodeMarkerData> nodeMarker = std::make_unique<NodeMarkerDataPtr<DbActivityMarker>>(nullptr);
    auto nodeRet = buffer.Push(std::move(nodeMarker));
    EXPECT_NE(nodeRet, nullptr);
    EXPECT_TRUE(nodeRet->IsNull());

    auto pMarker = std::make_unique<DbActivityMarker>();
    std::unique_ptr<NodeMarkerData> nodeMarkerNotNull =
        std::make_unique<NodeMarkerDataPtr<DbActivityMarker>>(std::move(pMarker));
    auto nodeRetNotNull = buffer.Push(std::move(nodeMarkerNotNull));
    EXPECT_EQ(nodeRetNotNull, nullptr);
    // 自动析构没有异常
}

TEST_F(TestDbBuffer, CallPushWhenOneExceptSuccess)
{
    // 正常push，正常 pop
    DbBuffer buffer;
    std::unique_ptr<NodeMarkerData> pMarkerPopNode = nullptr;
    auto pMarker = std::make_unique<DbActivityMarker>();
    pMarker->id = 1;
    std::unique_ptr<NodeMarkerData> nodeMarker =
        std::make_unique<NodeMarkerDataPtr<DbActivityMarker>>(std::move(pMarker));
    EXPECT_EQ(buffer.Push(std::move(nodeMarker)), nullptr);

    EXPECT_EQ(buffer.Pop(1, &pMarkerPopNode), 1);
    EXPECT_EQ(pMarkerPopNode->GetType(), GetTypeIndex<DbActivityMarker>());

    auto pMarkerPop = (static_cast<NodeMarkerDataPtr<DbActivityMarker> *>(pMarkerPopNode.get()))->MovePtr();
    EXPECT_EQ(pMarkerPop->id, 1);
}

TEST_F(TestDbBuffer, CallPushWhenOverLineSizeExceptFalse)
{
    // 正常push超量的数据
    DbBuffer buffer;
    std::unique_ptr<NodeMarkerData> pMarkerPop = nullptr;
    size_t times = PTR_ARRAY_SIZE * PTR_ARRAY_PRE_SIZE + 1;
    while (--times) {
        auto pMarker = std::make_unique<DbActivityMarker>();
        std::unique_ptr<NodeMarkerData> nodeMarker =
            std::make_unique<NodeMarkerDataPtr<DbActivityMarker>>(std::move(pMarker));
        auto ret = buffer.Push(std::move(nodeMarker));
        if (times < 2) {
            EXPECT_NE(ret, nullptr);
        }
    };

    EXPECT_EQ(buffer.PushCnt(), PTR_ARRAY_SIZE * PTR_ARRAY_PRE_SIZE);
    EXPECT_EQ(buffer.Size(), PTR_ARRAY_SIZE * PTR_ARRAY_PRE_SIZE - 1);
    while (buffer.Pop(1, &pMarkerPop)) {
        pMarkerPop = nullptr;
    }
    EXPECT_EQ(buffer.MaxCntInBuffer(), PTR_ARRAY_SIZE * PTR_ARRAY_PRE_SIZE - 1);
}

TEST_F(TestDbBuffer, CallPopWhen300ItemsExceptEq)
{
    // 正常push 和pop 出来的数据一样
    DbBuffer buffer;
    std::unique_ptr<NodeMarkerData> pMarkers[400] = {nullptr};
    const size_t PUSH_TIEMS = 300;
    size_t times = PUSH_TIEMS + 1;
    while (--times) {
        auto pMarker = std::make_unique<DbActivityMarker>();
        pMarker->id = times;
        std::unique_ptr<NodeMarkerData> nodeMarker =
            std::make_unique<NodeMarkerDataPtr<DbActivityMarker>>(std::move(pMarker));
        buffer.Push(std::move(nodeMarker));
    };
    EXPECT_EQ(buffer.Pop(400, pMarkers), PUSH_TIEMS);
    EXPECT_EQ(buffer.PopCnt(), PUSH_TIEMS);
    times = PUSH_TIEMS + 1;
    int index = 0;
    while (--times) {
        auto pMarkerPop = (static_cast<NodeMarkerDataPtr<DbActivityMarker> *>(pMarkers[index].get()))->MovePtr();
        EXPECT_EQ(pMarkerPop->id, times);
        ++index;
    };
}