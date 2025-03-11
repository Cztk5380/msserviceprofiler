/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <iostream>
#include <string>
#include <gtest/gtest.h>
#include <gmock/gmock.h>
#include <mockcpp/mockcpp.hpp>
#include "msServiceProfiler/msServiceProfiler.h"

using namespace testing;
using namespace msServiceProfilerCompatible;
using namespace msServiceProfiler;

namespace msServiceProfiler {

bool MockedIsEnable(uint32_t itemLevel)
{
    return itemLevel <= msServiceProfiler::Level::INFO;
}

class ProfilerTest : public ::testing::Test {
protected:
    void SetUp() override
    {
        ServiceProfilerInterface::GetInstance().ptrIsEnable_ = MockedIsEnable;
        ServiceProfilerInterface::GetInstance().ptrStartSpanWithName_ = StartSpanWithName;
        ServiceProfilerInterface::GetInstance().ptrMarkSpanAttr_ = MarkSpanAttr;
        ServiceProfilerInterface::GetInstance().ptrEndSpan_ = EndSpan;
        ServiceProfilerInterface::GetInstance().ptrMarkEvent_ = MarkEvent;
        ServiceProfilerInterface::GetInstance().ptrStartServerProfiler_ = StartServerProfiler;
        ServiceProfilerInterface::GetInstance().ptrStopServerProfiler_ = StopServerProfiler;
    }

    void TearDown() override
    {
        GlobalMockObject::reset();
    }
};

TEST_F(ProfilerTest, Construction)
{
    ResID ridInt(123);
    EXPECT_EQ(ridInt.resValue.rid, 123);
    EXPECT_EQ(ridInt.type, ResType::UINT64);

    ResID ridUint32(123U);
    EXPECT_EQ(ridUint32.resValue.rid, 123U);
    EXPECT_EQ(ridUint32.type, ResType::UINT64);

    ResID ridStr("abc");
    EXPECT_STREQ(ridStr.resValue.strRid, "abc");
    EXPECT_EQ(ridStr.type, ResType::STRING);

    ResID ridStrEmpty("");
    EXPECT_STREQ(ridStrEmpty.resValue.strRid, "");
    EXPECT_EQ(ridStr.type, ResType::STRING);

    std::string dRidStr129("d", 129);
    std::string dRidStr128("d", 128);
    ResID ridStrStd(dRidStr129.c_str());
    EXPECT_STREQ(ridStrStd.resValue.strRid, dRidStr128.c_str());
    EXPECT_EQ(ridStrStd.type, ResType::STRING);
}

TEST_F(ProfilerTest, IsIllegal)
{
    ResID illegalRid = ResID::IllegalResource();
    EXPECT_TRUE(illegalRid.IsIllegal());

    ResID validRid(123);
    EXPECT_FALSE(validRid.IsIllegal());

    ResID validRidStr("abc");
    EXPECT_FALSE(validRidStr.IsIllegal());
}

TEST_F(ProfilerTest, NumArrayAttrProfEnable)
{
    int array[2] = {1, 2};
    int *pArray = array;
    auto prof = PROF(INFO, NumArrayAttr("key", pArray, pArray + 2));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:[1,2],");
}

TEST_F(ProfilerTest, NumArrayAttrProfEnableEmptyArray)
{
    int array[2] = {1, 2};
    int *pArray = array;
    auto prof = PROF(INFO, NumArrayAttr("key", pArray, pArray + 0));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:[],");
}

TEST_F(ProfilerTest, NumArrayAttrProfDisable)
{
    int array[2] = {1, 2};
    int *pArray = array;
    auto prof_detailed = PROF(DETAILED, NumArrayAttr("key", pArray, pArray + 2));
    EXPECT_STREQ(prof_detailed.GetMsg().c_str(), "");
    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = nullptr;
    auto prof_null_info = PROF(INFO, NumArrayAttr("key", pArray, pArray + 2));
    EXPECT_STREQ(prof_null_info.GetMsg().c_str(), "");
    auto prof_null_detailed = PROF(DETAILED, NumArrayAttr("key", pArray, pArray + 2));
    EXPECT_STREQ(prof_null_detailed.GetMsg().c_str(), "");
    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = MockedIsEnable;
}

TEST_F(ProfilerTest, ArrayAttrProfEnable)
{
    int array[2] = {1, 2};
    int *pArray = array;
    auto prof = PROF(INFO, Domain("test"));

    prof.ArrayAttr("key", pArray, pArray + 2, [](decltype(prof) *x, int *y) -> void {
        if (*y == 1) {
            x->Attr("value", *y);
        }
    });
    EXPECT_STREQ(prof.GetMsg().c_str(), "^domain^:^test^,^key^:[{^value^:1},{}],");

    auto prof2 = PROF(INFO, ArrayAttr("key", pArray, pArray + 2, [](decltype(prof) *x, int *y) -> void {
        if (*y == 1) {
            x->Attr("value", *y);
        }
    }));
    EXPECT_STREQ(prof2.GetMsg().c_str(), "^key^:[{^value^:1},{}],");
}

TEST_F(ProfilerTest, ArrayAttrProfEnableEmptyArray)
{
    int array[2] = {1, 2};
    int *pArray = array;
    auto prof = PROF(INFO, Domain("test"));

    prof.ArrayAttr("key", pArray, pArray + 0, [](decltype(prof) *x, int *y) -> void { x->Attr("value", *y); });
    EXPECT_STREQ(prof.GetMsg().c_str(), "^domain^:^test^,^key^:[],");
}

TEST_F(ProfilerTest, ArrayAttrProfDisable)
{
    int array[2] = {1, 2};
    int *pArray = array;
    auto prof = PROF(DETAILED, Domain("test"));

    prof.ArrayAttr("key", pArray, pArray + 2, [](decltype(prof) *x, int y) -> void { x->Attr("value", y); });
    EXPECT_STREQ(prof.GetMsg().c_str(), "");

    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = nullptr;

    auto prof_null_info = PROF(INFO, Domain("test"));
    prof_null_info.ArrayAttr("key", pArray, pArray + 2, [](decltype(prof) *x, int y) -> void { x->Attr("value", y); });
    EXPECT_STREQ(prof_null_info.GetMsg().c_str(), "");

    auto prof_null_detailed = PROF(DETAILED, Domain("test"));
    prof_null_detailed.ArrayAttr(
        "key", pArray, pArray + 2, [](decltype(prof) *x, int y) -> void { x->Attr("value", y); });
    EXPECT_STREQ(prof_null_detailed.GetMsg().c_str(), "");
    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = MockedIsEnable;
}

TEST_F(ProfilerTest, AttrProfEnableString)
{
    auto prof = PROF(INFO, Attr("key", "value"));

    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:^value^,");
}

TEST_F(ProfilerTest, AttrProfEnableStdString)
{
    std::string value = "value";
    auto prof = PROF(INFO, Attr("key", value));

    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:^value^,");
}

TEST_F(ProfilerTest, AttrProfDisableStdString)
{
    std::string value = "value";
    auto prof = PROF(DETAILED, Attr("key", value));

    EXPECT_STREQ(prof.GetMsg().c_str(), "");
}

TEST_F(ProfilerTest, AttrProfEnableNumber)
{
    auto prof = PROF(INFO, Attr("key", 6));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:6,");
}

TEST_F(ProfilerTest, AttrProfEnableUint)
{
    auto prof = PROF(INFO, Attr("key", 6U));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:6,");
}

TEST_F(ProfilerTest, AttrProfEnableUlong)
{
    auto prof = PROF(INFO, Attr("key", 6UL));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:6,");
}

TEST_F(ProfilerTest, AttrProfEnableFloat)
{
    auto prof = PROF(INFO, Attr("key", 0.6));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:0.600000,");
}

TEST_F(ProfilerTest, AttrProfDisableNumber)
{

    auto prof = PROF(INFO, Attr("key", 0.6));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:0.600000,");

    auto prof_info_detailed = PROF(INFO, Attr<Level::DETAILED>("key", 0.6));
    EXPECT_STREQ(prof_info_detailed.GetMsg().c_str(), "");

    auto prof_info_info = PROF(INFO, Attr<Level::INFO>("key", 0.6));
    EXPECT_STREQ(prof_info_info.GetMsg().c_str(), "^key^:0.600000,");

    auto prof_detailed = PROF(DETAILED, Attr("key", 0.6));
    EXPECT_STREQ(prof_detailed.GetMsg().c_str(), "");

    auto prof_detailed_detailed = PROF(DETAILED, Attr<Level::DETAILED>("key", 0.6));
    EXPECT_STREQ(prof_detailed_detailed.GetMsg().c_str(), "");

    auto prof_detailed_info = PROF(DETAILED, Attr<Level::INFO>("key", 0.6));
    EXPECT_STREQ(prof_detailed_info.GetMsg().c_str(), "^key^:0.600000,");
}

TEST_F(ProfilerTest, AttrProfDisableNull)
{
    auto prof_detailed = PROF(DETAILED, Attr("key", 0.6));
    EXPECT_STREQ(prof_detailed.GetMsg().c_str(), "");

    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = nullptr;

    auto prof_null_info = PROF(INFO, Attr("key", 0.6));
    EXPECT_STREQ(prof_null_info.GetMsg().c_str(), "");

    auto prof_null_info_detailed = PROF(INFO, Attr<Level::DETAILED>("key", 0.6));
    EXPECT_STREQ(prof_null_info_detailed.GetMsg().c_str(), "");

    auto prof_null_info_info = PROF(INFO, Attr<Level::INFO>("key", 0.6));
    EXPECT_STREQ(prof_null_info_info.GetMsg().c_str(), "");

    auto prof_null_detailed = PROF(DETAILED, Attr("key", 0.6));
    EXPECT_STREQ(prof_null_detailed.GetMsg().c_str(), "");

    auto prof_null_detailed_detailed = PROF(DETAILED, Attr<Level::DETAILED>("key", 0.6));
    EXPECT_STREQ(prof_null_detailed_detailed.GetMsg().c_str(), "");

    auto prof_null_detailed_info = PROF(DETAILED, Attr<Level::INFO>("key", 0.6));
    EXPECT_STREQ(prof_null_detailed_info.GetMsg().c_str(), "");

    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = MockedIsEnable;
}

TEST_F(ProfilerTest, AttrProfEnableResID)
{
    auto prof = PROF(INFO, Attr("key", ResID((int)2)));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:2,");
}

TEST_F(ProfilerTest, AttrProfEnableResIDStr)
{
    auto prof = PROF(INFO, Attr("key", ResID("2")));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:^2^,");
}
TEST_F(ProfilerTest, AttrProfDisAbleResID)
{
    auto prof = PROF(DETAILED, Attr("key", ResID((int)2)));
    EXPECT_STREQ(prof.GetMsg().c_str(), "");
}

TEST_F(ProfilerTest, SpanStartProfDisable)
{
    auto prof = PROF(DETAILED, SpanStart("key"));
    EXPECT_STREQ(prof.GetMsg().c_str(), "");
}

TEST_F(ProfilerTest, SpanStartProfEnable)
{
    auto prof = PROF(INFO, SpanStart("key"));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^name^:^key^,^type^:2,");
    EXPECT_TRUE(prof.autoEnd_);
}

TEST_F(ProfilerTest, SpanStartProfEnableNotAutoEnd)
{
    auto prof = PROF(INFO, SpanStart("key", false));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^name^:^key^,^type^:2,");
    EXPECT_FALSE(prof.autoEnd_);
}

TEST_F(ProfilerTest, SpanEndProfDisable)
{
    auto prof = PROF(DETAILED, SpanStart("key"));
    prof.SpanEnd();
}

TEST_F(ProfilerTest, SpanEndProfEnable)
{
    auto prof = PROF(INFO, SpanStart("key"));
    prof.SpanEnd();
}

TEST_F(ProfilerTest, MetricProfDisable)
{
    auto prof = PROF(DETAILED, Metric("key", 12));
    EXPECT_STREQ(prof.GetMsg().c_str(), "");

    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = nullptr;
    auto prof_null_info = PROF(INFO, Metric("key", 12));
    EXPECT_STREQ(prof_null_info.GetMsg().c_str(), "");
    auto prof_null_detailed = PROF(DETAILED, Metric("key", 12));
    EXPECT_STREQ(prof_null_detailed.GetMsg().c_str(), "");
    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = MockedIsEnable;
}

TEST_F(ProfilerTest, MetricProfEnable)
{
    auto prof = PROF(INFO, Metric("key", 12));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key=^:12,");
}

TEST_F(ProfilerTest, MetricScopeProfDisable)
{
    auto prof = PROF(DETAILED, MetricScope("key", 12));
    EXPECT_STREQ(prof.GetMsg().c_str(), "");
    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = nullptr;
    auto prof_null_info = PROF(INFO, MetricScope("key", 12));
    EXPECT_STREQ(prof_null_info.GetMsg().c_str(), "");
    auto prof_null_detailed = PROF(DETAILED, MetricScope("key", 12));
    EXPECT_STREQ(prof_null_detailed.GetMsg().c_str(), "");
    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = MockedIsEnable;
}

TEST_F(ProfilerTest, MetricScopeProfEnable)
{
    auto prof = PROF(INFO, MetricScope("key", 12));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^scope#key^:12,");
}

TEST_F(ProfilerTest, Launch)
{
    PROF(DETAILED, Launch());
    PROF(INFO, Launch());

    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = nullptr;
    PROF(DETAILED, Launch());
    PROF(INFO, Launch());
    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = MockedIsEnable;
}

TEST_F(ProfilerTest, EventProfEnable)
{
    auto prof = PROF(INFO, Domain("test"));
    prof.Event("12");
    EXPECT_STREQ(prof.GetMsg().c_str(), "^domain^:^test^,^name^:^12^,^type^:0,");
}

TEST_F(ProfilerTest, EventProfDisable)
{
    auto prof = PROF(DETAILED, Domain("test"));
    prof.Event("12");
    EXPECT_STREQ(prof.GetMsg().c_str(), "");

    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = nullptr;

    auto prof_null_info = PROF(INFO, Domain("test"));
    prof_null_info.Event("12");
    EXPECT_STREQ(prof_null_info.GetMsg().c_str(), "");

    auto prof_null_detailed = PROF(DETAILED, Domain("test"));
    prof_null_info.Event("12");
    EXPECT_STREQ(prof_null_detailed.GetMsg().c_str(), "");

    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = MockedIsEnable;
}

TEST_F(ProfilerTest, LinkProfEnable)
{
    auto prof = PROF(INFO, Domain("test"));
    prof.Link("key", "key2");
    EXPECT_STREQ(prof.GetMsg().c_str(), "^domain^:^test^,^type^:3,^from^:^key^,^to^:^key2^,");
}

TEST_F(ProfilerTest, LinkProfDisable)
{
    auto prof = PROF(DETAILED, Domain("test"));
    prof.Link("key", "key2");
    EXPECT_STREQ(prof.GetMsg().c_str(), "");

    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = nullptr;

    auto prof_null_info = PROF(INFO, Domain("test"));
    prof_null_info.Link("key", "key2");
    EXPECT_STREQ(prof_null_info.GetMsg().c_str(), "");

    auto prof_null_detailed = PROF(DETAILED, Domain("test"));
    prof_null_detailed.Link("key", "key2");
    EXPECT_STREQ(prof_null_detailed.GetMsg().c_str(), "");

    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = MockedIsEnable;
}

}  // namespace msServiceProfiler