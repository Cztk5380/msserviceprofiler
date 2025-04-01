/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <gtest/gtest.h>
#include <gmock/gmock.h>
#include <mockcpp/mockcpp.hpp>
#include "msServiceProfiler/msServiceProfiler.h"

using namespace ::testing;
using namespace ::mockcpp;
using namespace msServiceProfilerCompatible;
using namespace msServiceProfiler;

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
    MOCKER(StartSpanWithName).expects(never());
    MOCKER(dlopen).stubs().will(returnValue((void *)nullptr));
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.OpenLib();
    EXPECT_EQ(spi.CallStartSpanWithName("TestSpan"), 0);
    GlobalMockObject::verify();
    GlobalMockObject::reset();
}

TEST_F(TestServiceProfilerInterface, CallStartSpanWithNameFoundLib)
{
    SpanHandle mockSpanHandle = 100;
    const char* mockPath = "/home/usr/Ascend/ascend-toolkit/latest";
    MOCKER(MyGetEnv)
        .stubs()
        .with(eq(static_cast<const char*>("ASCEND_HOME_PATH")))
        .will(returnValue(const_cast<char*>(mockPath)));
    MOCKER(dlopen)
        .stubs()
        .with(any(), eq(RTLD_LAZY))
        .will(returnValue(reinterpret_cast<void*>(&mockSpanHandle)));
    MOCKER(StartSpanWithName).stubs().will(returnValue(mockSpanHandle));
    MOCKER(dlopen).stubs().will(returnValue((void *)&mockSpanHandle));
    MOCKER(dlsym).stubs().will(returnValue((void *)StartSpanWithName));
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.OpenLib();
    EXPECT_EQ(spi.CallStartSpanWithName("TestSpan"), mockSpanHandle);
    EXPECT_EQ(spi.CallStartSpanWithName(nullptr), mockSpanHandle);
    GlobalMockObject::verify();
    GlobalMockObject::reset();
}

TEST_F(TestServiceProfilerInterface, CallMarkSpanAttrNotFoundLib)
{
    MOCKER(MarkSpanAttr).expects(never());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrMarkSpanAttr_ = nullptr;
    spi.CallMarkSpanAttr("TestMarkSpanAttr", 0);
    GlobalMockObject::verify();
}

TEST_F(TestServiceProfilerInterface, CallMarkSpanAttrFoundLib)
{
    MOCKER(MarkSpanAttr).expects(once());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrMarkSpanAttr_ = MarkSpanAttr;
    spi.CallMarkSpanAttr("TestMarkSpanAttr", 0);
    GlobalMockObject::verify();
}

TEST_F(TestServiceProfilerInterface, CallEndSpanNotFoundLib)
{
    MOCKER(MarkSpanAttr).expects(never());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrEndSpan_ = nullptr;
    spi.CallEndSpan(0);
    GlobalMockObject::verify();
}

TEST_F(TestServiceProfilerInterface, CallEndSpanFoundLib)
{
    MOCKER(EndSpan).expects(once());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrEndSpan_ = EndSpan;
    spi.CallEndSpan(0);
    GlobalMockObject::verify();
}

TEST_F(TestServiceProfilerInterface, CallMarkEventNotFoundLib)
{
    MOCKER(MarkSpanAttr).expects(never());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrMarkEvent_ = nullptr;
    spi.CallMarkEvent(0);
    GlobalMockObject::verify();
}

TEST_F(TestServiceProfilerInterface, CallMarkEventFoundLib)
{
    MOCKER(MarkEvent).expects(once());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrMarkEvent_ = MarkEvent;
    spi.CallMarkEvent(0);
    GlobalMockObject::verify();
}

TEST_F(TestServiceProfilerInterface, CallIsEnableNotFoundLib)
{
    MOCKER(MarkSpanAttr).expects(never());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrIsEnable_ = nullptr;
    spi.CallIsEnable(Level::INFO);
    GlobalMockObject::verify();
}

TEST_F(TestServiceProfilerInterface, CallIsEnableFoundLib)
{
    GlobalMockObject::reset();
    // mockcpp not support: MOCKER(IsEnable).expects(atLeast(1));
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrIsEnable_ = IsEnable;
    spi.CallIsEnable(Level::INFO);
    spi.CallIsEnable(Level::DETAILED);
    GlobalMockObject::verify();
}