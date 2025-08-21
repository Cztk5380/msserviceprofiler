/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */
#include <functional>
#include <chrono>
#include <thread>
#include "msServiceProfiler/msServiceProfiler.h"
#include "msServiceProfiler/NpuMemoryUsage.h"
#include "acl/acl.h"
#include "msServiceProfiler/ServiceProfilerDbWriter.h"

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
    } catch (const std::exception &e) {
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

template <int threadCnt>
void TestWithThread(std::function<void()> func)
{
    std::cout << "~~~~~~~~~~~~~~~~~~~~~ thread * " << threadCnt << std::endl;
    std::vector<std::thread> threadArray;
    for (int i = 0; i < threadCnt; ++i) {
        threadArray.emplace_back(func);
    }
    for (auto &t : threadArray) {
        t.join();
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

void TestMetaData()
{
    PROF(INFO, Domain(__func__).AddMetaInfo("meta", TEST_VALUE_66));
    PROF(INFO, Domain(__func__).AddMetaInfo("meta2", "str1234"));
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

void Times(void (*func)(), int times = 1000)
{
    for (int i = 0; i < times; ++i) {
        func();
    }
}

void SmokeTest()
{
    TestSmoke("TestSpan", TestSpan);
    TestSmoke("TestMetric", TestMetric);
    TestSmoke("TestEvent", TestEvent);
    TestSmoke("TestLinker", TestLinker);
    TestSmoke("TestNpuMemoryUsage", TestNpuMemoryUsage);
    TestSmoke("TestMetaData", TestMetaData);
}

static uint64_t GetCurrentTimeInNanoseconds()
{
    // 获取当前时间点
    auto now = std::chrono::high_resolution_clock::now();

    // 转换为从epoch开始的时间跨度
    auto duration = now.time_since_epoch();

    // 转换为纳秒计数
    auto nanoseconds = std::chrono::duration_cast<std::chrono::nanoseconds>(duration);

    // 返回int64_t类型的纳秒数
    return static_cast<uint64_t>(nanoseconds.count());
}

void TestSpeed(uint64_t allTime, uint64_t preTokenTime, uint64_t preTokenData, const char *data)
{
    std::cout << "====================" << std::endl;
    long unsigned int allRunTime = 0;
    long unsigned int allTimes = 0;
    long unsigned int maxTime = 0;

    auto allStartTime = GetCurrentTimeInNanoseconds();
    size_t cannot_pref_times = 0;
    for (uint64_t time = 0; time < allTime; time = time + preTokenTime) {
        auto startTime = GetCurrentTimeInNanoseconds();
        for (int dataTimes = 0; dataTimes < preTokenData; ++dataTimes) {
            PROF(INFO, Domain(__func__).Attr("data", data).Event("test_event_66"));
        }
        auto endTime = GetCurrentTimeInNanoseconds();
        if ((endTime - startTime) > preTokenTime * 1000 * 1000) {
            cannot_pref_times++;
        }
        if (endTime - allStartTime < (time + preTokenTime) * 1000 * 1000) {
            std::this_thread::sleep_for(std::chrono::nanoseconds(
                (time + preTokenTime) * 1000 * 1000 - (endTime - allStartTime)));  // sleep 满50ms
        }

        auto durationTime = endTime - startTime;
        maxTime = std::max(durationTime, maxTime);
        allRunTime += durationTime;
        allTimes += 1;
    }
    if (cannot_pref_times) {
        std::cerr << "cannot push " << preTokenData << " data in. * " << cannot_pref_times << std::endl;
    }
    WaitForAllDump();
    auto allEndTime = GetCurrentTimeInNanoseconds();
    std::cout << "done. " << std::endl;
    std::cout << "data(" << preTokenData << ") avg time:" << allRunTime / 1000.0 / allTimes
              << "(μs) max time:" << maxTime / 1000.0 << "(μs)" << std::endl;
    std::cout << "all dump time:" << (allEndTime - allStartTime) / 1000000 << "(ms)" << std::endl;
}

void SpeedTest()
{
    TestSpeed("TestSpan", TestSpan, TEST_SPEED_5_US);
    TestSpeed("TestMetric", TestMetric, TEST_SPEED_5_US);
    TestSpeed("TestEvent", TestEvent, TEST_SPEED_5_US);
    TestSpeed("TestLinker", TestLinker, TEST_SPEED_5_US);
    TestSpeed("TestSpan100NumAttr", TestSpan100NumAttr, TEST_SPEED_5_US);
    TestSpeed("TestSpan100ObjAttr", TestSpan100ObjAttr, TEST_SPEED_5_US);
    TestSpeed(
        "TestEvent1000Times", []() -> void { Times(TestEvent, 1000); }, TEST_SPEED_5_US * 1000);
}

void ViolentSpeedTest()
{
    const char *DATA_50_BIT = "12345678902234567890323456789042345678905234567890";
    // 测试10s, 每 1ms 写入 180 数据，每个数据50+ bit 数据: 完全可以
    TestSpeed(10000, 1, 160, DATA_50_BIT);
    // 2*160 个数据，勉强可以,180 非常吃力
    TestWithThread<2>([DATA_50_BIT]() -> void { TestSpeed(10000, 1, 140, DATA_50_BIT); });
    // 3*100 个数据，勉强可以
    TestWithThread<3>([DATA_50_BIT]() -> void { TestSpeed(10000, 1, 80, DATA_50_BIT); });
    // 4*80 个数据，勉强可以, 90 非常吃力
    TestWithThread<4>([DATA_50_BIT]() -> void { TestSpeed(10000, 1, 70, DATA_50_BIT); });
}

int main()
{
    msServiceProfilerCompatible::ServiceProfilerInterface::GetInstance().CallStartServerProfiler();

    SmokeTest();
    SpeedTest();
    ViolentSpeedTest();
    msServiceProfilerCompatible::ServiceProfilerInterface::GetInstance().CallStopServerProfiler();
    // start again
    msServiceProfilerCompatible::ServiceProfilerInterface::GetInstance().CallStartServerProfiler();
    SmokeTest();
    SpeedTest();
    msServiceProfilerCompatible::ServiceProfilerInterface::GetInstance().CallStopServerProfiler();
    return 0;
}
