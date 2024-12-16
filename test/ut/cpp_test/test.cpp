/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <chrono>
#include "../../../include/msServiceProfiler.h"
#include "acl/acl_prof.h"
#include "acl/acl.h"

using namespace msServiceProfiler;

constexpr int TEST_VALUE_1234 = 1243;
constexpr int TEST_VALUE_67 = 67;
constexpr int TEST_VALUE_66 = 66;
constexpr int TEST_VALUE_56 = 56;
constexpr int TEST_VALUE_100 = 100;
constexpr int TEST_VALUE_0 = 0;
constexpr int TEST_SPEED_5 = 5;

int64_t Now()
{
    auto now = std::chrono::high_resolution_clock::now();
    std::chrono::nanoseconds ms = std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch());
    return ms.count();
}

void TestSmoke(const std::string funcName, void (*func)()) {
    try {
        func();
    } catch (const std::exception& e) {
        // 处理异常
        std::cerr << funcName << " smoke test FAILED. " << e.what() << std::endl;
    }
}

void TestSpeed(const std::string funcName, void (*func)(), int ms) {
    auto startTime = Now();
    func();
    auto du = Now() - startTime;
    if (du > (ms * 1000)) {
        std::cerr << funcName << " speed FAILED. " << (du / 1000.0) << " > " << ms << std::endl;
    } else {
        std::cout << funcName << (du / 1000.0) << " < " << ms << std::endl;
    }
}

void TestSpan()
{
    PROF(INFO,
         Domain("test_span")
                 .Attr("attr", TEST_VALUE_1234)
                 .Attr("attr2", "str1234")
                 .Attr("attr3", std::string("str1234"))
                 .SpanStart("test"));

    std::cout << "Test Span" << std::endl;
}

void TestMetric()
{
    PROF(INFO, Domain(__func__).Metric("attr3", TEST_VALUE_66).SpanStart("test_metric_66"));
    std::cout << "Test Metric" << std::endl;
}

void TestEvent()
{
    PROF(INFO, Domain(__func__).Attr("attr3", TEST_VALUE_66).Event("test_event_66"));
    PROF(INFO, Domain(__func__).Attr("attr3", TEST_VALUE_56).Event("test_event_66"));
    std::cout << "Test Event" << std::endl;
}

void TestLinker()
{
    PROF(INFO, Domain(__func__).Link(TEST_VALUE_1234, "test_event_66"));
    PROF(INFO, Domain(__func__).Link(TEST_VALUE_56, "str56"));
    std::cout << "Test Linker" << std::endl;
}

void TestSpan100NumAttr()
{
    int nums[TEST_VALUE_100];
    auto prof = PROF(INFO, Domain(__func__).SpanStart("test_span_100_Num"));
    PROF(prof.NumArrayAttr("attr", nums + TEST_VALUE_0, nums + TEST_VALUE_100));
    std::cout << "Test Span 100 num" << std::endl;
}

void TestSpan100ObjAttr()
{
    int nums[TEST_VALUE_100];
    auto prof = PROF(ERROR, Domain(__func__).SpanStart("test_span_100_Obj"));

    PROF(prof.ArrayAttr<Level::ERROR>(
            "attr", nums + TEST_VALUE_0, nums + TEST_VALUE_100, [](decltype(prof) *pProfiler, int *pNum) -> void {
            pProfiler->Attr("num", *pNum);
            pProfiler->Attr("iter", *pNum);
    }));
    std::cout << "Test Span 100 obj" << std::endl;
}

void SmokeTest()
{
    TestSmoke("TestSpan", TestSpan);
    TestSmoke("TestMetric", TestMetric);
    TestSmoke("TestEvent", TestEvent);
    TestSmoke("TestLinker", TestLinker);
}

void SpeedTest()
{
    TestSpeed("TestSpan", TestSpan, TEST_SPEED_5);
    TestSpeed("TestMetric", TestMetric, TEST_SPEED_5);
    TestSpeed("TestEvent", TestEvent, TEST_SPEED_5);
    TestSpeed("TestLinker", TestLinker, TEST_SPEED_5);
    TestSpeed("TestSpan100NumAttr", TestSpan100NumAttr, TEST_SPEED_5);
    TestSpeed("TestSpan100ObjAttr", TestSpan100ObjAttr, TEST_SPEED_5);
}

int main()
{
    StartServerProfiler();
    aclrtContext context_;
    aclrtStream stream_;

    auto ret = aclrtSetDevice(0);
    if (ret != ACL_ERROR_NONE) {
        std::cout << "acl prof init failed, ret = " << ret << std::endl;
        return -1;
    }

    ret = aclrtCreateContext(&context_, 0);
    if (ret != ACL_ERROR_NONE) {
        std::cout << "acl prof init failed, ret = " << ret << std::endl;
        return -1;
    }

    ret = aclrtCreateStream(&stream_);
    if (ret != ACL_ERROR_NONE) {
        std::cout << "acl prof init failed, ret = " << ret << std::endl;
        return -1;
    }

    SmokeTest();
    SpeedTest();
    StopServerProfiler();
    return 0;
}