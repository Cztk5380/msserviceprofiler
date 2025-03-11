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
class ServiceProfilerInterfaceTest : public ::testing::Test {
protected:
    void SetUp() override
    {}

    void TearDown() override
    {}
};

TEST_F(ServiceProfilerInterfaceTest, CallStartSpanWithNameNotFoundLib)
{
    MOCKER(StartSpanWithName).expects(never());
    MOCKER(dlopen).stubs().will(returnValue((void *)nullptr));
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.OpenLib();
    EXPECT_EQ(spi.CallStartSpanWithName("TestSpan"), 0);
    GlobalMockObject::verify();
    GlobalMockObject::reset();
}

TEST_F(ServiceProfilerInterfaceTest, CallStartSpanWithNameFoundLib)
{
    SpanHandle mockSpanHandle = 100;
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

TEST_F(ServiceProfilerInterfaceTest, CallMarkSpanAttrNotFoundLib)
{
    MOCKER(MarkSpanAttr).expects(never());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrMarkSpanAttr_ = nullptr;
    spi.CallMarkSpanAttr("TestMarkSpanAttr", 0);
    GlobalMockObject::verify();
}

TEST_F(ServiceProfilerInterfaceTest, CallMarkSpanAttrFoundLib)
{
    MOCKER(MarkSpanAttr).expects(once());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrMarkSpanAttr_ = MarkSpanAttr;
    spi.CallMarkSpanAttr("TestMarkSpanAttr", 0);
    GlobalMockObject::verify();
}

TEST_F(ServiceProfilerInterfaceTest, CallEndSpanNotFoundLib)
{
    MOCKER(MarkSpanAttr).expects(never());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrEndSpan_ = nullptr;
    spi.CallEndSpan(0);
    GlobalMockObject::verify();
}

TEST_F(ServiceProfilerInterfaceTest, CallEndSpanFoundLib)
{
    MOCKER(EndSpan).expects(once());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrEndSpan_ = EndSpan;
    spi.CallEndSpan(0);
    GlobalMockObject::verify();
}

TEST_F(ServiceProfilerInterfaceTest, CallMarkEventNotFoundLib)
{
    MOCKER(MarkSpanAttr).expects(never());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrMarkEvent_ = nullptr;
    spi.CallMarkEvent(0);
    GlobalMockObject::verify();
}

TEST_F(ServiceProfilerInterfaceTest, CallMarkEventFoundLib)
{
    MOCKER(MarkEvent).expects(once());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrMarkEvent_ = MarkEvent;
    spi.CallMarkEvent(0);
    GlobalMockObject::verify();
}

TEST_F(ServiceProfilerInterfaceTest, CallIsEnableNotFoundLib)
{
    MOCKER(MarkSpanAttr).expects(never());
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrIsEnable_ = nullptr;
    spi.CallIsEnable(Level::INFO);
    GlobalMockObject::verify();
}

TEST_F(ServiceProfilerInterfaceTest, CallIsEnableFoundLib)
{
    GlobalMockObject::reset();
    // mockcpp not support: MOCKER(IsEnable).expects(atLeast(1));
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrIsEnable_ = IsEnable;
    spi.CallIsEnable(Level::INFO);
    spi.CallIsEnable(Level::DETAILED);
    GlobalMockObject::verify();
}