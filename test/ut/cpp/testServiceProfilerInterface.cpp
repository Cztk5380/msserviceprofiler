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

TEST_F(TestServiceProfilerInterface, CallStartSpanWithNameFoundLib)
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

TEST_F(TestServiceProfilerInterface, CallStartSpanWithNameNotFoundLib)
{
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.OpenLib();
    spi.ptrStartSpanWithName_ = nullptr;
    EXPECT_EQ(spi.CallStartSpanWithName("TestSpan"), 0);
    GlobalMockObject::verify();
}

TEST_F(TestServiceProfilerInterface, CallStartSpanWithNameInputNull)
{
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.OpenLib();
    EXPECT_GE(spi.CallStartSpanWithName(nullptr), 0);
    GlobalMockObject::verify();
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


void MockedIsValidDomain(const char* domain)
{
    GlobalStub::GetInstance().stubs.IsValidDomain(domain);
}
TEST_F(TestServiceProfilerInterface, CallIsDomainEnableIsValidDomainNonNull)
{
    GlobalMockObject::reset();
    EXPECT_CALL(GlobalStub::GetInstance().stubs, IsValidDomain(::testing::_)).Times(AtLeast(1));
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.ptrIsValidDomain_ = MockedIsValidDomain;
    spi.CallIsDomainEnable("domain");
    GlobalMockObject::verify();
}

extern "C" {
bool MockedGetEnableDomainFilter()
{
    return true;
}
const std::set<std::string> &MockedGetValidDomain()
{
    // 返回正确的domain
    static const std::set<std::string> enableDomain = {"domain", "otherDomain"};
    return enableDomain;
}
const std::set<std::string> &MockedGetValidDomain2()
{
    // 返回不是正确的domain
    static const std::set<std::string> enableDomain = {"domain2"};
    return enableDomain;
}
}
TEST_F(TestServiceProfilerInterface, CallIsDomainEnableIsValidDomainIsNull)
{
    GlobalMockObject::reset();
    ServiceProfilerInterface &spi = ServiceProfilerInterface::GetInstance();
    spi.OpenLib();
    // ptrIsValidDomain_ 为null ，其他接口为正常值
    spi.ptrIsValidDomain_ = nullptr;
    spi.ptrEnableDomainFilter_ = MockedGetEnableDomainFilter;
    spi.ptrValidDomain_ = MockedGetValidDomain;
    EXPECT_TRUE(spi.CallIsDomainEnable("domain"));

    // ptrIsValidDomain_ 为null ，其他接口有为空的
    spi.ptrEnableDomainFilter_ = MockedGetEnableDomainFilter;
    spi.ptrValidDomain_ = nullptr;
    EXPECT_TRUE(spi.CallIsDomainEnable("domain"));

    spi.ptrEnableDomainFilter_ = nullptr;
    spi.ptrValidDomain_ = MockedGetValidDomain;
    EXPECT_TRUE(spi.CallIsDomainEnable("domain"));

    // ptrIsValidDomain_ 为null ，其他接口返回不是正确的domain
    spi.ptrEnableDomainFilter_ = MockedGetEnableDomainFilter;
    spi.ptrValidDomain_ = MockedGetValidDomain2;
    EXPECT_FALSE(spi.CallIsDomainEnable("domain"));

    GlobalMockObject::verify();
}

