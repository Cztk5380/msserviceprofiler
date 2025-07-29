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

constexpr int TEST_NUMER_1 = 1;
constexpr int TEST_NUMER_2 = 2;
constexpr int TEST_NUMER_ARRAY_LEN = 2;
constexpr int TEST_NUMER_123 = 123;
constexpr uint32_t TEST_NUMER_1234 = 1234U;
constexpr float TEST_NUMER_6 = 0.6;
const size_t MAX_RES_STR_IZE = 10;

namespace msServiceProfiler {

bool MockedIsEnable(uint32_t itemLevel)
{
    return itemLevel <= msServiceProfiler::Level::INFO;
}

class TestProfiler : public ::testing::Test {
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

TEST_F(TestProfiler, Construction)
{
    ResID ridInt(TEST_NUMER_1);
    EXPECT_EQ(ridInt.resValue.rid, TEST_NUMER_1);
    EXPECT_EQ(ridInt.type, ResType::UINT64);

    ResID ridUint32(TEST_NUMER_2);
    EXPECT_EQ(ridUint32.resValue.rid, TEST_NUMER_2);
    EXPECT_EQ(ridUint32.type, ResType::UINT64);

    ResID ridStr("abc");
    EXPECT_STREQ(ridStr.resValue.strRid, "abc");
    EXPECT_EQ(ridStr.type, ResType::STRING);

    ResID ridStrEmpty("");
    EXPECT_STREQ(ridStrEmpty.resValue.strRid, "");
    EXPECT_EQ(ridStr.type, ResType::STRING);

    std::string dRidStr129("d", MAX_RES_STR_IZE + 1);
    std::string dRidStr128("d", MAX_RES_STR_IZE);
    ResID ridStrStd(dRidStr129.c_str());
    EXPECT_STREQ(ridStrStd.resValue.strRid, dRidStr128.c_str());
    EXPECT_EQ(ridStrStd.type, ResType::STRING);
}

TEST_F(TestProfiler, IsIllegal)
{
    ResID illegalRid = ResID::IllegalResource();
    EXPECT_TRUE(illegalRid.IsIllegal());

    ResID validRid(TEST_NUMER_1);
    EXPECT_FALSE(validRid.IsIllegal());

    ResID validRidStr("abc");
    EXPECT_FALSE(validRidStr.IsIllegal());
}

TEST_F(TestProfiler, NumArrayAttrProfEnable)
{
    int array[TEST_NUMER_ARRAY_LEN] = {TEST_NUMER_1, TEST_NUMER_2};
    int *pArray = array;
    auto prof = PROF(INFO, NumArrayAttr("key", pArray, pArray + TEST_NUMER_ARRAY_LEN));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:[1,2],");
}

TEST_F(TestProfiler, NumArrayAttrProfEnableEmptyArray)
{
    int array[TEST_NUMER_ARRAY_LEN] = {TEST_NUMER_1, TEST_NUMER_2};
    int *pArray = array;
    auto prof = PROF(INFO, NumArrayAttr("key", pArray, pArray + 0));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:[],");
}

TEST_F(TestProfiler, NumArrayAttrProfDisable)
{
    int array[TEST_NUMER_ARRAY_LEN] = {TEST_NUMER_1, TEST_NUMER_2};
    int *pArray = array;
    auto prof_detailed = PROF(DETAILED, NumArrayAttr("key", pArray, pArray + TEST_NUMER_ARRAY_LEN));
    EXPECT_STREQ(prof_detailed.GetMsg().c_str(), "");
    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = nullptr;
    auto prof_null_info = PROF(INFO, NumArrayAttr("key", pArray, pArray + TEST_NUMER_ARRAY_LEN));
    EXPECT_STREQ(prof_null_info.GetMsg().c_str(), "");
    auto prof_null_detailed = PROF(DETAILED, NumArrayAttr("key", pArray, pArray + TEST_NUMER_ARRAY_LEN));
    EXPECT_STREQ(prof_null_detailed.GetMsg().c_str(), "");
    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = MockedIsEnable;
}

TEST_F(TestProfiler, ArrayAttrProfEnable)
{
    int array[TEST_NUMER_ARRAY_LEN] = {TEST_NUMER_1, TEST_NUMER_2};
    int *pArray = array;
    auto prof = PROF(INFO, Domain("test"));

    prof.ArrayAttr("key", pArray, pArray + TEST_NUMER_ARRAY_LEN, [](decltype(prof) *x, int *y) -> void {
        if (*y == 1) {
            x->Attr("value", *y);
        }
    });
    EXPECT_STREQ(prof.GetMsg().c_str(), "^domain^:^test^,^key^:[{^value^:1},{}],");

    auto prof2 =
        PROF(INFO, ArrayAttr("key", pArray, pArray + TEST_NUMER_ARRAY_LEN, [](decltype(prof) *x, int *y) -> void {
            if (*y == 1) {
                x->Attr("value", *y);
            }
        }));
    EXPECT_STREQ(prof2.GetMsg().c_str(), "^key^:[{^value^:1},{}],");
}

TEST_F(TestProfiler, ArrayAttrProfEnableEmptyArray)
{
    int array[TEST_NUMER_ARRAY_LEN] = {TEST_NUMER_1, TEST_NUMER_2};
    int *pArray = array;
    auto prof = PROF(INFO, Domain("test"));

    prof.ArrayAttr("key", pArray, pArray + 0, [](decltype(prof) *x, int *y) -> void { x->Attr("value", *y); });
    EXPECT_STREQ(prof.GetMsg().c_str(), "^domain^:^test^,^key^:[],");
}

TEST_F(TestProfiler, ArrayAttrProfDisable)
{
    int array[TEST_NUMER_ARRAY_LEN] = {TEST_NUMER_1, TEST_NUMER_2};
    int *pArray = array;
    auto prof = PROF(DETAILED, Domain("test"));

    prof.ArrayAttr("key", pArray, pArray + TEST_NUMER_ARRAY_LEN,
                   [](decltype(prof) *x, int y) -> void { x->Attr("value", y); });
    EXPECT_STREQ(prof.GetMsg().c_str(), "");

    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = nullptr;

    auto prof_null_info = PROF(INFO, Domain("test"));
    prof_null_info.ArrayAttr("key", pArray, pArray + TEST_NUMER_ARRAY_LEN,
                             [](decltype(prof) *x, int y) -> void { x->Attr("value", y); });
    EXPECT_STREQ(prof_null_info.GetMsg().c_str(), "");

    auto prof_null_detailed = PROF(DETAILED, Domain("test"));
    prof_null_detailed.ArrayAttr(
        "key", pArray, pArray + TEST_NUMER_ARRAY_LEN,
        [](decltype(prof) *x, int y) -> void { x->Attr("value", y); });
    EXPECT_STREQ(prof_null_detailed.GetMsg().c_str(), "");
    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = MockedIsEnable;
}

TEST_F(TestProfiler, AttrProfEnableString)
{
    auto prof = PROF(INFO, Attr("key", "value"));

    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:^value^,");
}

TEST_F(TestProfiler, AttrProfEnableStdString)
{
    std::string value = "value";
    auto prof = PROF(INFO, Attr("key", value));

    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:^value^,");
}

TEST_F(TestProfiler, AttrProfDisableStdString)
{
    std::string value = "value";
    auto prof = PROF(DETAILED, Attr("key", value));

    EXPECT_STREQ(prof.GetMsg().c_str(), "");
}

TEST_F(TestProfiler, AttrProfEnableNumber)
{
    auto prof = PROF(INFO, Attr("key", 6));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:6,");
}

TEST_F(TestProfiler, AttrProfEnableUint)
{
    auto prof = PROF(INFO, Attr("key", 6U));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:6,");
}

TEST_F(TestProfiler, AttrProfEnableUlong)
{
    auto prof = PROF(INFO, Attr("key", 6UL));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:6,");
}

TEST_F(TestProfiler, AttrProfEnableFloat)
{
    auto prof = PROF(INFO, Attr("key", TEST_NUMER_6));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:0.600000,");
}

TEST_F(TestProfiler, AttrProfDisableNumber)
{
    auto prof = PROF(INFO, Attr("key", TEST_NUMER_6));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:0.600000,");

    auto prof_info_detailed = PROF(INFO, Attr<Level::DETAILED>("key", TEST_NUMER_6));
    EXPECT_STREQ(prof_info_detailed.GetMsg().c_str(), "");

    auto prof_info_info = PROF(INFO, Attr<Level::INFO>("key", TEST_NUMER_6));
    EXPECT_STREQ(prof_info_info.GetMsg().c_str(), "^key^:0.600000,");

    auto prof_detailed = PROF(DETAILED, Attr("key", TEST_NUMER_6));
    EXPECT_STREQ(prof_detailed.GetMsg().c_str(), "");

    auto prof_detailed_detailed = PROF(DETAILED, Attr<Level::DETAILED>("key", TEST_NUMER_6));
    EXPECT_STREQ(prof_detailed_detailed.GetMsg().c_str(), "");

    auto prof_detailed_info = PROF(DETAILED, Attr<Level::INFO>("key", TEST_NUMER_6));
    EXPECT_STREQ(prof_detailed_info.GetMsg().c_str(), "^key^:0.600000,");
}

TEST_F(TestProfiler, AttrProfDisableNull)
{
    auto prof_detailed = PROF(DETAILED, Attr("key", TEST_NUMER_6));
    EXPECT_STREQ(prof_detailed.GetMsg().c_str(), "");

    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = nullptr;

    auto prof_null_info = PROF(INFO, Attr("key", TEST_NUMER_6));
    EXPECT_STREQ(prof_null_info.GetMsg().c_str(), "");

    auto prof_null_info_detailed = PROF(INFO, Attr<Level::DETAILED>("key", TEST_NUMER_6));
    EXPECT_STREQ(prof_null_info_detailed.GetMsg().c_str(), "");

    auto prof_null_info_info = PROF(INFO, Attr<Level::INFO>("key", TEST_NUMER_6));
    EXPECT_STREQ(prof_null_info_info.GetMsg().c_str(), "");

    auto prof_null_detailed = PROF(DETAILED, Attr("key", TEST_NUMER_6));
    EXPECT_STREQ(prof_null_detailed.GetMsg().c_str(), "");

    auto prof_null_detailed_detailed = PROF(DETAILED, Attr<Level::DETAILED>("key", TEST_NUMER_6));
    EXPECT_STREQ(prof_null_detailed_detailed.GetMsg().c_str(), "");

    auto prof_null_detailed_info = PROF(DETAILED, Attr<Level::INFO>("key", TEST_NUMER_6));
    EXPECT_STREQ(prof_null_detailed_info.GetMsg().c_str(), "");

    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = MockedIsEnable;
}

TEST_F(TestProfiler, AttrProfEnableResID)
{
    auto prof = PROF(INFO, Attr("key", ResID(TEST_NUMER_2)));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:2,");
}

TEST_F(TestProfiler, AttrProfEnableResIDStr)
{
    auto prof = PROF(INFO, Attr("key", ResID("2")));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key^:^2^,");
}
TEST_F(TestProfiler, AttrProfDisAbleResID)
{
    auto prof = PROF(DETAILED, Attr("key", ResID(TEST_NUMER_2)));
    EXPECT_STREQ(prof.GetMsg().c_str(), "");
}

TEST_F(TestProfiler, SpanStartProfDisable)
{
    auto prof = PROF(DETAILED, SpanStart("key"));
    EXPECT_STREQ(prof.GetMsg().c_str(), "");
}

TEST_F(TestProfiler, SpanStartProfEnable)
{
    auto prof = PROF(INFO, SpanStart("key"));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^name^:^key^,^type^:2,");
    EXPECT_TRUE(prof.autoEnd_);
}

TEST_F(TestProfiler, SpanStartProfEnableNotAutoEnd)
{
    auto prof = PROF(INFO, SpanStart("key", false));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^name^:^key^,^type^:2,");
    EXPECT_FALSE(prof.autoEnd_);
}

TEST_F(TestProfiler, SpanEndProfDisable)
{
    auto prof = PROF(DETAILED, SpanStart("key"));
    prof.SpanEnd();
}

TEST_F(TestProfiler, SpanEndProfEnable)
{
    auto prof = PROF(INFO, SpanStart("key"));
    prof.SpanEnd();
}

TEST_F(TestProfiler, MetricProfDisable)
{
    auto prof = PROF(DETAILED, Metric("key", TEST_NUMER_123));
    EXPECT_STREQ(prof.GetMsg().c_str(), "");

    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = nullptr;
    auto prof_null_info = PROF(INFO, Metric("key", TEST_NUMER_123));
    EXPECT_STREQ(prof_null_info.GetMsg().c_str(), "");
    auto prof_null_detailed = PROF(DETAILED, Metric("key", TEST_NUMER_123));
    EXPECT_STREQ(prof_null_detailed.GetMsg().c_str(), "");
    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = MockedIsEnable;
}

TEST_F(TestProfiler, MetricProfEnable)
{
    auto prof = PROF(INFO, Metric("key", TEST_NUMER_123));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^key=^:123,");
}

TEST_F(TestProfiler, MaxSizeString)
{
    const char* maxStr = "123456789";  // 长度为 9 的字符串
    ResID resID(maxStr);

    char expected[MAX_RES_STR_IZE] = "123456789";
    expected[MAX_RES_STR_IZE - 1] = '\0';  // 确保终止符

    EXPECT_STREQ(resID.resValue.strRid, expected);
}

TEST_F(TestProfiler, OversizedString)
{
    const char* oversizedStr = "12345678901234567890";  // 长度为 20 的字符串
    ResID resID(oversizedStr);

    char expected[MAX_RES_STR_IZE] = "123456789";
    expected[MAX_RES_STR_IZE - 1] = '\0';  // 确保终止符

    EXPECT_STREQ(resID.resValue.strRid, expected);
}

TEST_F(TestProfiler, MetricScopeProfDisable)
{
    auto prof = PROF(DETAILED, MetricScope("key", TEST_NUMER_123));
    EXPECT_STREQ(prof.GetMsg().c_str(), "");
    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = nullptr;
    auto prof_null_info = PROF(INFO, MetricScope("key", TEST_NUMER_123));
    EXPECT_STREQ(prof_null_info.GetMsg().c_str(), "");
    auto prof_null_detailed = PROF(DETAILED, MetricScope("key", TEST_NUMER_123));
    EXPECT_STREQ(prof_null_detailed.GetMsg().c_str(), "");
    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = MockedIsEnable;
}

TEST_F(TestProfiler, MetricScopeProfEnable)
{
    auto prof = PROF(INFO, MetricScope("key", 12));
    EXPECT_STREQ(prof.GetMsg().c_str(), "^scope#key^:12,");
}

TEST_F(TestProfiler, Launch)
{
    PROF(DETAILED, Launch());
    PROF(INFO, Launch());

    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = nullptr;
    PROF(DETAILED, Launch());
    PROF(INFO, Launch());
    ServiceProfilerInterface::GetInstance().ptrIsEnable_ = MockedIsEnable;
}

TEST_F(TestProfiler, EventProfEnable)
{
    auto prof = PROF(INFO, Domain("test"));
    prof.Event("12");
    EXPECT_STREQ(prof.GetMsg().c_str(), "^domain^:^test^,^name^:^12^,^type^:0,");
}

TEST_F(TestProfiler, EventProfDisable)
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

TEST_F(TestProfiler, LinkProfEnable)
{
    auto prof = PROF(INFO, Domain("test"));
    prof.Link("key", "key2");
    EXPECT_STREQ(prof.GetMsg().c_str(), "^domain^:^test^,^type^:3,^from^:^key^,^to^:^key2^,");
}

TEST_F(TestProfiler, LinkProfDisable)
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