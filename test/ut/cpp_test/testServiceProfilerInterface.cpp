/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <gtest/gtest.h>
#include <gmock/gmock.h>
#include <mockcpp/mockcpp.hpp>
#include "msServiceProfiler/msServiceProfiler.h"
#include "stubs.h"

using namespace ::testing;
using namespace ::mockcpp;
using namespace msServiceProfilerCompatible;
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
class TestServiceProfilerInterface : public ::testing::Test {
protected:
    void SetUp() override
    {}

    void TearDown() override
    {}
};

TEST_F(TestServiceProfilerInterface, CallStartSpanWithNameNotFoundLib)
{
    EXPECT_CALL(GlobalStub::GetInstance().stubs, StartSpanWithName(::testing::_)).Times(0);
    EXPECT_CALL(GlobalStub::GetInstance().stubs, dlopen(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(nullptr));
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.OpenLib();
    EXPECT_GE(spi.CallStartSpanWithName("TestSpan"), 0);
    GlobalMockObject::verify();
    GlobalMockObject::reset();
}

TEST_F(TestServiceProfilerInterface, CallMarkSpanAttrNotFoundLib)
{
    EXPECT_CALL(GlobalStub::GetInstance().stubs, MarkSpanAttr(::testing::_, ::testing::_)).Times(0);
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrMarkSpanAttr_ = nullptr;
    spi.CallMarkSpanAttr("TestMarkSpanAttr", 0);
    GlobalMockObject::verify();
}


void MockedMarkSpanAttr(const char* msg, SpanHandle span) {
    GlobalStub::GetInstance().stubs.MarkSpanAttr(msg, span);
}
TEST_F(TestServiceProfilerInterface, CallMarkSpanAttrFoundLib)
{
    EXPECT_CALL(GlobalStub::GetInstance().stubs, MarkSpanAttr(::testing::_, ::testing::_))
        .WillOnce(DoDefault());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrMarkSpanAttr_ = MockedMarkSpanAttr;
    spi.CallMarkSpanAttr("TestMarkSpanAttr", 0);
}

TEST_F(TestServiceProfilerInterface, CallEndSpanNotFoundLib)
{
    EXPECT_CALL(GlobalStub::GetInstance().stubs, MarkSpanAttr(::testing::_, ::testing::_)).Times(0);
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrEndSpan_ = nullptr;
    spi.CallEndSpan(0);
    GlobalMockObject::verify();
}

void MockedEndSpan(SpanHandle span) {
    GlobalStub::GetInstance().stubs.EndSpan(span);
}
TEST_F(TestServiceProfilerInterface, CallEndSpanFoundLib)
{
    EXPECT_CALL(GlobalStub::GetInstance().stubs, EndSpan(::testing::_))
        .WillOnce(DoDefault());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrEndSpan_ = MockedEndSpan;
    spi.CallEndSpan(0);
    GlobalMockObject::verify();
}

TEST_F(TestServiceProfilerInterface, CallMarkEventNotFoundLib)
{
    EXPECT_CALL(GlobalStub::GetInstance().stubs, MarkSpanAttr(::testing::_, ::testing::_)).Times(0);
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrMarkEvent_ = nullptr;
    spi.CallMarkEvent(0);
    GlobalMockObject::verify();
}

void MockedMarkEvent(const char* msg) {
    GlobalStub::GetInstance().stubs.MarkEvent(msg);
}
TEST_F(TestServiceProfilerInterface, CallMarkEventFoundLib)
{
    EXPECT_CALL(GlobalStub::GetInstance().stubs, MarkEvent(::testing::_))
        .Times(AtLeast(1));
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrMarkEvent_ = MockedMarkEvent;
    spi.CallMarkEvent(0);
    GlobalMockObject::verify();
    GlobalMockObject::reset();
}

TEST_F(TestServiceProfilerInterface, CallIsEnableNotFoundLib)
{
    EXPECT_CALL(GlobalStub::GetInstance().stubs, IsEnable(::testing::_)).Times(0);
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrIsEnable_ = nullptr;
    spi.CallIsEnable(Level::INFO);
    GlobalMockObject::verify();
}

void MockedIsEnable(uint32_t level) {
    GlobalStub::GetInstance().stubs.IsEnable(level);
}
TEST_F(TestServiceProfilerInterface, CallIsEnableFoundLib)
{
    GlobalMockObject::reset();
    EXPECT_CALL(GlobalStub::GetInstance().stubs, IsEnable(::testing::_)).Times(AtLeast(1));
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrIsEnable_ = MockedIsEnable;
    spi.CallIsEnable(Level::INFO);
    spi.CallIsEnable(Level::DETAILED);
    GlobalMockObject::verify();
}
