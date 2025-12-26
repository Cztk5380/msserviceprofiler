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

#include <gtest/gtest.h>
#include <gmock/gmock.h>
#include "msServiceProfiler/DbBuffer.h"
#include "msServiceProfiler/ServiceProfilerDbWriter.h"
#include "stubs.h"

using namespace ::testing;
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

namespace msServiceProfiler {
template <>
class DbExecutor<100> : public DbExecutorInterface {
public:
    DbExecutor(int test_value = 100) : test_value_(test_value)
    {}
    void Execute(ServiceProfilerDbWriter &, sqlite3 *) override{};
    bool Cache() override
    {
        return false;
    };
    virtual ~DbExecutor() = default;
    int test_value_;
};
}  // namespace msServiceProfiler

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
    DbBuffer<DbExecutorInterface> buffer;
    EXPECT_EQ(buffer.Push(nullptr), nullptr);

    std::unique_ptr<DbExecutorInterface> nodeMarker = nullptr;
    auto nodeRet = buffer.Push(std::move(nodeMarker));
    EXPECT_EQ(nodeRet, nullptr);

    auto pMarker = std::make_unique<DbExecutor<100>>();
    const auto nodeRetNotNull = buffer.Push(std::move(pMarker));
    EXPECT_EQ(nodeRetNotNull, nullptr);
    // 自动析构没有异常
}

TEST_F(TestDbBuffer, CallPushWhenOneExceptSuccess)
{
    // 正常push，正常 pop
    DbBuffer<DbExecutorInterface> buffer;
    std::unique_ptr<DbExecutorInterface> pMarkerPopNode = nullptr;
    auto pMarker = std::make_unique<DbExecutor<100>>(1);
    EXPECT_EQ(buffer.Push(std::move(pMarker)), nullptr);

    EXPECT_EQ(buffer.Pop(1, &pMarkerPopNode), 1);

    const DbExecutor<100> *pMarkerPop = static_cast<DbExecutor<100> *>(pMarkerPopNode.get());
    EXPECT_EQ(pMarkerPop->test_value_, 1);
}

TEST_F(TestDbBuffer, CallPushWhenOverLineSizeExceptFalse)
{
    // 正常push超量的数据
    DbBuffer<DbExecutorInterface> buffer;
    std::unique_ptr<DbExecutorInterface> pMarkerPop = nullptr;
    size_t times = 128 * 256 + 1;
    while (--times) {
        auto pMarker = std::make_unique<DbExecutor<100>>();
        auto ret = buffer.Push(std::move(pMarker));
        if (times < 2) {
            EXPECT_NE(ret, nullptr);
        }
    };

    EXPECT_EQ(buffer.PushCnt(), 128 * 256);
    EXPECT_EQ(buffer.Size(), 128 * 256 - 1);
    while (buffer.Pop(1, &pMarkerPop)) {
        pMarkerPop = nullptr;
    }
    EXPECT_EQ(buffer.MaxCntInBuffer(), 128 * 256 - 1);
}

TEST_F(TestDbBuffer, CallPopWhen300ItemsExceptEq)
{
    // 正常push 和pop 出来的数据一样
    DbBuffer<DbExecutorInterface> buffer;
    std::unique_ptr<DbExecutorInterface> pMarkers[400] = {nullptr};
    constexpr size_t PUSH_TIMES = 300;
    size_t times = PUSH_TIMES + 1;
    while (--times) {
        auto pMarker = std::make_unique<DbExecutor<100>>(times);
        buffer.Push(std::move(pMarker));
    };
    EXPECT_EQ(buffer.Pop(400, pMarkers), PUSH_TIMES);
    EXPECT_EQ(buffer.PopCnt(), PUSH_TIMES);
    times = PUSH_TIMES + 1;
    int index = 0;
    while (--times) {
        const auto pMarkerPop = static_cast<DbExecutor<100> *>(pMarkers[index].get());
        EXPECT_EQ(pMarkerPop->test_value_, times);
        ++index;
    };
}