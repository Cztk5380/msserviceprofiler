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
#include "../include/msServerProfiler.h"
#include "acl/acl.h"
#include "acl/acl_prof.h"
using namespace msServerProfiler;

constexpr int TEST_VALUE_1234 = 1243;
constexpr int TEST_VALUE_67 = 67;
constexpr int TEST_VALUE_66 = 66;
constexpr int TEST_VALUE_56 = 56;
constexpr int TEST_VALUE_100 = 100;
constexpr int TEST_VALUE_0 = 0;
constexpr int TEST_SPEED_5 = 5;

#define TEST_SMOKE(FUNC) do { \
    try { \
        (FUNC)(); \
    } catch (const std::exception& e) { \
        std::cerr << (#FUNC) << " smoke test FAILED. " << e.what() << std::endl; \
    } \
} while(0)

#define TEST_SPEED(FUNC, ms) do { \
    auto startTime = Now(); \
    (FUNC)(); \
    auto du = Now() - startTime; \
    if (du > ((ms) * 1000)) { \
        std::cerr << (#FUNC) << " speed FAILED. " << (du / 1000.0) << " > " << (ms) << std::endl; \
    } else { \
        std::cout << (#FUNC) << (du / 1000.0) << " < " << (ms) << std::endl; \
    }\
} while(0)

void TestSpan() {
    auto prof = Span<Level::INFO>("test_span", ResID::ILLEGAL_RES);
    prof.AddAttr("attr", TEST_VALUE_1234);
    prof.AddAttr("attr", "str1234");
    prof.AddAttr("attr", std::string("str1234"));
    std::cout << "Test Span" << std::endl;
}

void TestMetric() {
    auto prof = Metric<>("test_metric_66", ResID::ILLEGAL_RES);
    std::cout << "Test Metric" << std::endl;
    prof.Mark(TEST_VALUE_66);

    Metric<>::AddMetric("test_metric_67", ResID::ILLEGAL_RES, TEST_VALUE_67);
}

void TestEvent() {
    auto prof = Event<>("test_event_66", ResID::ILLEGAL_RES);
    std::cout << "Test Event" << std::endl;
    prof.Mark();

    Event<>::AddEvent("test_event_67", ResID::ILLEGAL_RES);
}

void TestLinker() {
    ResLink<>().Mark(TEST_VALUE_1234, "str234");
    std::cout << "Test Event" << std::endl;

    ResLink<>::AddLink(TEST_VALUE_56, "str56");
}

void TestSpan100NumAttr() {
    auto prof = Span<Level::INFO>("test_span_100_Num", ResID::ILLEGAL_RES);
    int nums[TEST_VALUE_100];
    prof.AddNumArrayAttr("attr", nums + TEST_VALUE_0, nums + TEST_VALUE_100);
    std::cout << "Test Span 100 num" << std::endl;
}

void TestSpan100ObjAttr() {
    auto prof = Span<>("test_span_100_Obj", ResID::ILLEGAL_RES);
    int nums[TEST_VALUE_100];
    prof.AddArrayAttr<Level::ERROR>("attr", nums + TEST_VALUE_0, nums + TEST_VALUE_100, [](CollectorHelper* pProfiler, int* pNum) -> void {
        pProfiler->AddAttr("num", *pNum);
        pProfiler->AddAttr("iter", *pNum);
    });
    std::cout << "Test Span 100 obj" << std::endl;
}

void SmokeTest() {
    TEST_SMOKE(TestSpan);
    TEST_SMOKE(TestMetric);
    TEST_SMOKE(TestEvent);
    TEST_SMOKE(TestLinker);
}

int64_t Now() {
    auto now  = std::chrono::high_resolution_clock::now();
    std::chrono::nanoseconds ms = std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch());
    return ms.count();
}


void SpeedTest() {
    TEST_SPEED(TestSpan, TEST_SPEED_5);
    TEST_SPEED(TestMetric, TEST_SPEED_5);
    TEST_SPEED(TestEvent, TEST_SPEED_5);
    TEST_SPEED(TestLinker, TEST_SPEED_5);
    TEST_SPEED(TestSpan100NumAttr, TEST_SPEED_5);
    TEST_SPEED(TestSpan100ObjAttr, TEST_SPEED_5);
    
}

int main() {
    StartServerProfiler();
    aclrtContext context_;
    aclrtStream stream_;

    auto ret = aclrtSetDevice(0);
    if (ret != ACL_ERROR_NONE) {
        std::cout<< "acl prof init failed, ret = " << ret << std::endl;
        return -1;
    }

    ret = aclrtCreateContext(&context_, 0);
    if (ret != ACL_ERROR_NONE) {
        std::cout<< "acl prof init failed, ret = " << ret << std::endl;
        return -1;
    }

    ret = aclrtCreateStream(&stream_);
    if (ret != ACL_ERROR_NONE) {
        std::cout<< "acl prof init failed, ret = " << ret << std::endl;
        return -1;
    }

    SmokeTest();
    SpeedTest();
    StopServerProfiler();
    return 0;
}