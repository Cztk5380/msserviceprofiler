/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <chrono>
#include <thread>
#include "msServiceProfiler/msServiceProfiler.h"
#include "msServiceProfiler/NpuMemoryUsage.h"
#include "acl/acl.h"

using namespace msServiceProfiler;

constexpr int TEST_VALUE_1234 = 1243;
constexpr int TEST_VALUE_67 = 67;
constexpr int TEST_VALUE_66 = 66;
constexpr int TEST_VALUE_56 = 56;
constexpr int TEST_VALUE_100 = 100;
constexpr int TEST_VALUE_0 = 0;

constexpr int NANO_TO_MICRO_SECOND = 1e6;
constexpr int NANO_TO_MILLI_SECOND = 1e3;
constexpr int TEST_SPEED_5_US = 5;

int64_t Now()
{
    auto now = std::chrono::high_resolution_clock::now();
    std::chrono::nanoseconds ns = std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch());
    return ns.count();
}

void TestSmoke(const std::string funcName, void (*func)())
{
    try {
        std::cout << "====================" << std::endl;
        std::cout << funcName << " start" << std::endl;
        func();
        std::cout << funcName << " end" << std::endl;
    } catch (const std::exception& e) {
        // 处理异常
        std::cerr << funcName << " smoke test FAILED. " << e.what() << std::endl;
    }
}

void TestSpeed(const std::string funcName, void (*func)(), int targetDurationUs)
{
    std::cout << "====================" << std::endl;
    std::cout << funcName << " start" << std::endl;
    auto startTime = Now();  // ns
    func();
    auto duration = (Now() - startTime) / NANO_TO_MILLI_SECOND;
    std::cout << funcName << " end" << std::endl;
    if (duration > targetDurationUs) {
        std::cerr << funcName << " speed FAILED. " << duration << " > " << targetDurationUs << " (μs)" << std::endl;
    } else {
        std::cout << funcName << duration << " < " << targetDurationUs << " (μs)" << std::endl;
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
}

void TestMetric()
{
    PROF(INFO, Domain(__func__).Metric("attr3", TEST_VALUE_66).SpanStart("test_metric_66"));
}

void TestEvent()
{
    PROF(INFO, Domain(__func__).Attr("attr3", TEST_VALUE_66).Event("test_event_66"));
    PROF(INFO, Domain(__func__).Attr("attr3", TEST_VALUE_56).Event("test_event_66"));
}

void TestLinker()
{
    PROF(INFO, Domain(__func__).Link(TEST_VALUE_1234, "test_event_66"));
    PROF(INFO, Domain(__func__).Link(TEST_VALUE_56, "str56"));
}

void TestNpuMemoryUsage()
{
    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.InitDcmiCardAndDevices();

    for (int ii = 0; ii < 2; ii++) {  // repeat 2 times
        auto startTime = Now();
        std::vector<int> memoryUsed;
        std::vector<int> memoryUtiliza;
        npuMemoryUsage.GetByDcmi(memoryUsed, memoryUtiliza);
        auto du = Now() - startTime;
        std::cout << "Duration: " << (du / NANO_TO_MICRO_SECOND) << "ms" << std::endl;

        std::cout << "Usage: ";
        for (long unsigned int i = 0; i < memoryUsed.size(); i++) {
            std::cout << memoryUsed[i] << ", ";
        }
        std::cout << std::endl;

        std::cout << "Rate: ";
        for (long unsigned int i = 0; i < memoryUtiliza.size(); i++) {
            std::cout << memoryUtiliza[i] << ", ";
        }
        std::cout << std::endl;
    }
}

void TestSpan100NumAttr()
{
    int nums[TEST_VALUE_100];
    auto prof = PROF(INFO, Domain(__func__).SpanStart("test_span_100_Num"));
    PROF(prof.NumArrayAttr("attr", nums + TEST_VALUE_0, nums + TEST_VALUE_100));
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
}

void SmokeTest()
{
    TestSmoke("TestSpan", TestSpan);
    TestSmoke("TestMetric", TestMetric);
    TestSmoke("TestEvent", TestEvent);
    TestSmoke("TestLinker", TestLinker);
    TestSmoke("TestNpuMemoryUsage", TestNpuMemoryUsage);
}

void SpeedTest()
{
    TestSpeed("TestSpan", TestSpan, TEST_SPEED_5_US);
    TestSpeed("TestMetric", TestMetric, TEST_SPEED_5_US);
    TestSpeed("TestEvent", TestEvent, TEST_SPEED_5_US);
    TestSpeed("TestLinker", TestLinker, TEST_SPEED_5_US);
    TestSpeed("TestSpan100NumAttr", TestSpan100NumAttr, TEST_SPEED_5_US);
    TestSpeed("TestSpan100ObjAttr", TestSpan100ObjAttr, TEST_SPEED_5_US);
}

int main()
{
    msServiceProfilerCompatible::ProfilerFunc::GetInstance().CallStartServerProfiler();
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
    const int sleepTime = 10 * NANO_TO_MILLI_SECOND;
    std::this_thread::sleep_for(std::chrono::milliseconds(sleepTime)); // sleep 10 seconds
    msServiceProfilerCompatible::ProfilerFunc::GetInstance().CallStopServerProfiler();
    return 0;
}
