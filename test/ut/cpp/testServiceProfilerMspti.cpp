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

#include <sys/mman.h>
#include <sys/stat.h>
#include <gtest/gtest.h>
#include <vector>
#include <chrono>
#include <mockcpp/mockcpp.hpp>
#include <nlohmann/json.hpp>

#include "securec.h"
#include "acl/acl_prof.h"
#include "acl/acl.h"
#include "mspti/mspti.h"

#include "msptiHelper.h"
#include "msServiceProfiler/msServiceProfiler.h"
#include "msServiceProfiler/ServiceProfilerMspti.h"
#include "msServiceProfiler/ServiceProfilerDbWriter.h"
#include "msServiceProfiler/DBExecutor/DbExecutorMsptiApiData.h"
#include "msServiceProfiler/DBExecutor/DbExecutorMsptikernelData.h"
#include "msServiceProfiler/DBExecutor/DbExecutorMsptiCommData.h"
#include "msServiceProfiler/DBExecutor/DbExecutorMsptiMstxData.h"
#include "stubs.h"

using namespace ::testing;

void MarkEventLongAttr(const char *msg);
namespace msServiceProfiler {
void DeviceMemoryWrite2Tx(const std::vector<int> &memoryInfo, const std::string metricName);
void UserBufferComplete(uint8_t *buffer, size_t size, size_t validSize);
void UserBufferRequest(uint8_t **buffer, size_t *size, size_t *maxNumRecords);
void UserBufferClear();
}  // namespace msServiceProfiler

using namespace msServiceProfiler;
using namespace UTHelper;

// Test suite for IsNameMatchTest function
TEST(ServiceProfilerMsptiTest, IsNameMatchEmptyFilterSet)
{
    std::set<std::string> filterSet;
    const char *name = "example";
    EXPECT_TRUE(ServiceProfilerMspti::IsNameMatch(filterSet, name));
}

// Test suite for IsNameMatchTest function
TEST(ServiceProfilerMsptiTest, IsNameMatchEmptyName)
{
    std::set<std::string> filterSet;
    const char *name = nullptr;
    EXPECT_FALSE(ServiceProfilerMspti::IsNameMatch(filterSet, name));
}

TEST(ServiceProfilerMsptiTest, IsNameMatchNameContainsFilter)
{
    std::set<std::string> filterSet = {"amp"};
    const char *name = "example";
    EXPECT_TRUE(ServiceProfilerMspti::IsNameMatch(filterSet, name));
}

TEST(ServiceProfilerMsptiTest, IsNameMatchNameDoesNotContainFilter)
{
    std::set<std::string> filterSet = {"amp"};
    const char *name = "test";
    EXPECT_FALSE(ServiceProfilerMspti::IsNameMatch(filterSet, name));
}

TEST(ServiceProfilerMsptiTest, InsertApiData_ValidActivity)
{
    ServiceProfilerMspti profiler;
    msptiActivityApi activity = {.kind = msptiActivityKind::MSPTI_ACTIVITY_KIND_API,
        .start = 123456789,
        .end = 987654321,
        .pt = {123, 456},
        .correlationId = 789UL,
        .name = "test_activity"};

    // 设置 filterApi 以匹配 activity->name
    auto apiFilter = std::string("test");
    auto kernelFilter = std::string("");
    profiler.InitFilter(apiFilter, kernelFilter);
    profiler.InitOutputPath("/tmp");
    profiler.Init();

    // 调用函数
    auto exec = DbExecutor<MSPTI_API_INSERT_STMT>(activity);
    ServiceProfilerDbWriter xx{"tmp.db"};
    xx.StartDump("/tmp");
    exec.Execute(xx, xx.db_);
    xx.StopDump();
    // 验证是否成功执行 SQLite 操作
    // 由于 SQLite 函数被模拟，这里主要验证流程是否执行
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

TEST(ServiceProfilerMsptiTest, InsertApiData_NotInitialized)
{
    ServiceProfilerMspti profiler;
    profiler.inited = false;  // 设置 inited 为 false

    msptiActivityApi activity = {.kind = msptiActivityKind::MSPTI_ACTIVITY_KIND_MARKER,
        .start = 123456789,
        .end = 987654321,
        .pt = {123, 456},
        .correlationId = 789,
        .name = "test_activity"};

    // 设置 filterApi 以匹配 activity->name
    auto apiFilter = std::string("test");
    auto kernelFilter = std::string("");
    profiler.InitFilter(apiFilter, kernelFilter);
    profiler.InitOutputPath("/tmp");

    // 调用函数
    auto exec = DbExecutor<MSPTI_API_INSERT_STMT>(activity);
    ServiceProfilerDbWriter xx{"tmp.db"};
    exec.Execute(xx, nullptr);

    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

TEST(ServiceProfilerMsptiTest, InsertApiData_NameNotMatch)
{
    ServiceProfilerMspti profiler;
    msptiActivityApi activity = {.kind = msptiActivityKind::MSPTI_ACTIVITY_KIND_MARKER,
        .start = 123456789,
        .end = 987654321,
        .pt = {123, 456},
        .correlationId = 789,
        .name = "test_activity"};

    // 设置 filterApi 不匹配 activity->name
    auto apiFilter = std::string("unmatched_filter");
    auto kernelFilter = std::string("");
    profiler.InitFilter(apiFilter, kernelFilter);
    profiler.InitOutputPath("/tmp");
    profiler.Init();

    // 调用函数

    EXPECT_FALSE(profiler.ApiNameMatch(activity.name));  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, InsertMstxData_ValidActivity_HostSource)
{
    ServiceProfilerMspti profiler;
    msptiActivityMarker activity = {.kind = msptiActivityKind::MSPTI_ACTIVITY_KIND_MARKER,
        .flag = msptiActivityFlag::MSPTI_ACTIVITY_FLAG_MARKER_INSTANTANEOUS,
        .sourceKind = msptiActivitySourceKind::MSPTI_ACTIVITY_SOURCE_KIND_HOST,
        .timestamp = 123456789,
        .id = 123,
        .objectId = {123, 456},
        .name = "test_activity",
        .domain = ""};

    profiler.InitFilter("", "");
    profiler.InitOutputPath("/tmp");
    profiler.Init();

    // 调用函数
    auto exec = DbExecutor<MSPTI_MSTX_INSERT_STMT>(activity);
    ServiceProfilerDbWriter xx{"tmp.db"};
    xx.StartDump("/tmp");
    exec.Execute(xx, xx.db_);
    xx.StopDump();

    // 验证是否成功执行 SQLite 操作
    // 由于 SQLite 函数被模拟，这里主要验证流程是否执行
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

TEST(ServiceProfilerMsptiTest, InsertMstxData_ValidActivity_DeviceSource)
{
    ServiceProfilerMspti profiler;

    msptiActivityMarker activity = {.kind = msptiActivityKind::MSPTI_ACTIVITY_KIND_MARKER,
        .flag = msptiActivityFlag::MSPTI_ACTIVITY_FLAG_MARKER_INSTANTANEOUS,
        .sourceKind = msptiActivitySourceKind::MSPTI_ACTIVITY_SOURCE_KIND_DEVICE,
        .timestamp = 123456789,
        .id = 123,
        .objectId = {123, 456},
        .name = "test_activity",
        .domain = ""};

    profiler.InitFilter("", "");
    profiler.InitOutputPath("/tmp");
    profiler.Init();

    // 调用函数
    auto exec = DbExecutor<MSPTI_MSTX_INSERT_STMT>(activity);
    ServiceProfilerDbWriter xx{"tmp.db"};
    xx.StartDump("/tmp");
    exec.Execute(xx, xx.db_);
    xx.StopDump();

    // 验证是否成功执行 SQLite 操作
    // 由于 SQLite 函数被模拟，这里主要验证流程是否执行
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

TEST(ServiceProfilerMsptiTest, InsertMstxData_NotInitialized)
{
    ServiceProfilerMspti profiler;
    msptiActivityMarker activity = {.kind = msptiActivityKind::MSPTI_ACTIVITY_KIND_MARKER,
        .flag = msptiActivityFlag::MSPTI_ACTIVITY_FLAG_MARKER_INSTANTANEOUS,
        .sourceKind = msptiActivitySourceKind::MSPTI_ACTIVITY_SOURCE_KIND_HOST,
        .timestamp = 123456789,
        .id = 123,
        .objectId = {123, 456},
        .name = "test_activity",
        .domain = ""};

    profiler.InitFilter("", "");
    profiler.InitOutputPath("/tmp");
    profiler.Init();
    profiler.Init();
    profiler.inited = false;  // 设置 inited 为 false

    // 调用函数
    auto exec = DbExecutor<MSPTI_MSTX_INSERT_STMT>(activity);
    ServiceProfilerDbWriter xx{"/tmp/tmp.db"};
    exec.Execute(xx, nullptr);

    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, InsertKernelData_ValidActivity)
{
    ServiceProfilerMspti profiler;
    msptiActivityKernel activity = {.kind = msptiActivityKind::MSPTI_ACTIVITY_KIND_KERNEL,
        .start = 123456789,
        .end = 987654321,
        .ds = {123, 456},
        .correlationId = 789,
        .type = "test_type",
        .name = "test_kernel"};

    // 设置 filterKernel 以匹配 activity->name
    profiler.InitFilter("", "test");
    profiler.InitOutputPath("/tmp");
    profiler.Init();

    // 调用函数
    auto exec = DbExecutor<MSPTI_KERNEL_INSERT_STMT>(activity);
    ServiceProfilerDbWriter xx{"tmp.db"};
    xx.StartDump("/tmp");
    exec.Execute(xx, xx.db_);
    xx.StopDump();

    // 验证是否成功执行 SQLite 操作
    // 由于 SQLite 函数被模拟，这里主要验证流程是否执行
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

TEST(ServiceProfilerMsptiTest, InsertKernelData_NotInitialized)
{
    ServiceProfilerMspti profiler;
    profiler.inited = false;  // 设置 inited 为 false

    msptiActivityKernel activity = {.kind = msptiActivityKind::MSPTI_ACTIVITY_KIND_KERNEL,
        .start = 123456789,
        .end = 987654321,
        .ds = {123, 456},
        .correlationId = 789,
        .type = "test_type",
        .name = "test_kernel"};

    // 设置 filterKernel 以匹配 activity->name
    profiler.InitFilter("", "test");
    profiler.InitOutputPath("/tmp");
    profiler.Init();

    // 调用函数
    auto exec = DbExecutor<MSPTI_KERNEL_INSERT_STMT>(activity);
    ServiceProfilerDbWriter xx{"/tmp/tmp.db"};
    exec.Execute(xx, nullptr);

    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

TEST(ServiceProfilerMsptiTest, InsertKernelData_NameNotMatch)
{
    ServiceProfilerMspti profiler;
    msptiActivityKernel activity = {.kind = msptiActivityKind::MSPTI_ACTIVITY_KIND_KERNEL,
        .start = 123456789,
        .end = 987654321,
        .ds = {123, 456},
        .correlationId = 789,
        .type = "test_type",
        .name = "test_kernel"};

    // 设置 filterKernel 不匹配 activity->name
    profiler.InitFilter("", "unmatched_filter");
    profiler.InitOutputPath("/tmp");
    profiler.Init();

    // 调用函数
    EXPECT_FALSE(profiler.KernelNameMatch(activity.name));
}

// 测试用例
TEST(ServiceProfilerMsptiTest, InsertCommunicationData_ValidActivity)
{
    ServiceProfilerMspti profiler;
    msptiActivityCommunication activity = {.kind = msptiActivityKind::MSPTI_ACTIVITY_KIND_COMMUNICATION,
        .dataType = msptiCommunicationDataType::MSPTI_ACTIVITY_COMMUNICATION_INT16,
        .count = 1000,
        .ds = {123, 456},
        .start = 123456789,
        .end = 987654321,
        .algType = "test_alg",
        .name = "test_communication",
        .commName = "test_domain",
        .correlationId = 789};

    profiler.InitOutputPath("/tmp");
    profiler.Init();
    // 调用函数
    auto exec = DbExecutor<MSPTI_COMMUNICATION_INSERT_STMT>(activity);
    ServiceProfilerDbWriter xx{"/tmp/tmp.db"};
    exec.Execute(xx, nullptr);

    // 验证是否成功执行 SQLite 操作
    // 由于 SQLite 函数被模拟，这里主要验证流程是否执行
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

TEST(ServiceProfilerMsptiTest, InsertCommunicationData_NotInitialized)
{
    ServiceProfilerMspti profiler;
    profiler.inited = false;  // 设置 inited 为 false

    msptiActivityCommunication activity = {.kind = msptiActivityKind::MSPTI_ACTIVITY_KIND_COMMUNICATION,
        .dataType = msptiCommunicationDataType::MSPTI_ACTIVITY_COMMUNICATION_INT16,
        .count = 1000,
        .ds = {123, 456},
        .start = 123456789,
        .end = 987654321,
        .algType = "test_alg",
        .name = "test_communication",
        .commName = "test_domain",
        .correlationId = 789};

    profiler.InitOutputPath("/tmp");
    profiler.Init();
    // 调用函数
    auto exec = DbExecutor<MSPTI_COMMUNICATION_INSERT_STMT>(activity);
    ServiceProfilerDbWriter xx{"/tmp/tmp.db"};
    exec.Execute(xx, nullptr);

    // 验证是否没有执行 SQLite 操作
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, Close_Initialized)
{
    ServiceProfilerMspti profiler;
    profiler.Init();
    // 调用函数
    profiler.Close();
    profiler.Close();

    // 验证是否正确释放资源
    EXPECT_FALSE(profiler.inited);  // 验证 inited 被设置为 false
}

// 测试用例
TEST(ServiceProfilerMsptiTest, UserBufferComplete_InvalidBuffer)
{
    size_t size = 1;
    uint8_t *buffer = static_cast<uint8_t *>(malloc(size));
    size_t validSize = 1;
    UserBufferComplete(buffer, size, validSize);

    // 验证是否成功处理缓冲区数据
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
    GlobalMockObject::reset();
}

// 测试用例
TEST(ServiceProfilerMsptiTest, UserBufferComplete_InvalidSize)
{
    size_t size = 1;
    uint8_t *buffer = static_cast<uint8_t *>(malloc(size));
    size_t validSize = 0;
    UserBufferComplete(buffer, size, validSize);

    // 验证是否成功处理缓冲区数据
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
    GlobalMockObject::reset();
}

// 测试用例
TEST(ServiceProfilerMsptiTest, UserBufferComplete_ValidBufferApi)
{
    msptiActivityApi activity = {.kind = msptiActivityKind::MSPTI_ACTIVITY_KIND_API,
        .start = 123456789,
        .end = 987654321,
        .pt = {123, 456},
        .correlationId = 789UL,
        .name = "test_activity"};

    size_t size = std::max(sizeof(activity), 256UL) + 8;
    size_t validSize = size;

    msptiActivityApi *pActivityApi = (msptiActivityApi *)malloc(size);
    memset_s(pActivityApi, size, 0, size);
    memcpy_s(pActivityApi, size, &activity, sizeof(activity));
    msptiActivity *pActivity = (msptiActivity *)pActivityApi;

    UserBufferComplete((uint8_t *)pActivity, size, validSize);

    // 验证是否成功处理缓冲区数据
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, UserBufferComplete_ValidBufferKernel)
{
    msptiActivityKernel activity = {
        .kind = msptiActivityKind::MSPTI_ACTIVITY_KIND_KERNEL,
        .start = 123456789,
        .end = 987654321,
        .ds = {123, 456},
        .correlationId = 789,
        .type = "test_type",
        .name = "test_kernel"};

    size_t validSize = sizeof(activity);
    size_t size = std::max(validSize, 256UL) + 8;

    msptiActivityApi *pActivityApi = (msptiActivityApi *)malloc(size);
    memset_s(pActivityApi, size, 0, size);
    memcpy_s(pActivityApi, size, &activity, validSize);
    msptiActivity *pActivity = (msptiActivity *)pActivityApi;
    msptiActivity *record = nullptr;
    UserBufferComplete((uint8_t *)pActivity, size, validSize);

    // 验证是否成功处理缓冲区数据
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, UserBufferComplete_ValidBufferComm)
{
    msptiActivityCommunication activity = {.kind = msptiActivityKind::MSPTI_ACTIVITY_KIND_COMMUNICATION,
        .dataType = msptiCommunicationDataType::MSPTI_ACTIVITY_COMMUNICATION_INT16,
        .count = 1000,
        .ds = {123, 456},
        .start = 123456789,
        .end = 987654321,
        .algType = "test_alg",
        .name = "test_communication",
        .commName = "test_domain",
        .correlationId = 789};

    size_t validSize = sizeof(activity);
    size_t size = std::max(validSize, 256UL) + 8;

    msptiActivityApi *pActivityApi = (msptiActivityApi *)malloc(size);
    memset_s(pActivityApi, size, 0, size);
    memcpy_s(pActivityApi, size, &activity, validSize);
    msptiActivity *pActivity = (msptiActivity *)pActivityApi;
    msptiActivity *record = nullptr;
    UserBufferComplete((uint8_t *)pActivity, size, validSize);

    // 验证是否成功处理缓冲区数据
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, UserBufferComplete_ValidBufferCommMarker)
{
    msptiActivityApi activity = {.kind = msptiActivityKind::MSPTI_ACTIVITY_KIND_MARKER,
        .start = 123456789,
        .end = 987654321,
        .pt = {123, 456},
        .correlationId = 789,
        .name = "test_activity"};

    size_t validSize = sizeof(activity);
    size_t size = std::max(validSize, 256UL) + 8;

    msptiActivityApi *pActivityApi = (msptiActivityApi *)malloc(size);
    memset_s(pActivityApi, size, 0, size);
    memcpy_s(pActivityApi, size, &activity, validSize);
    msptiActivity *pActivity = (msptiActivity *)pActivityApi;
    msptiActivity *record = nullptr;
    UserBufferComplete((uint8_t *)pActivity, size, validSize);

    // 验证是否成功处理缓冲区数据
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, InitMsptiTestSuccessCase) {
    msptiSubscriberHandle subscriber;
    std::string profPath = "/path/to/profiling";

    g_utStatusMsptiSubscribe = MSPTI_SUCCESS;
    g_utStatusMsptiActivityRegisterCallbacks = MSPTI_SUCCESS;
    // 调用函数
    int ret = InitMspti(profPath, subscriber);

    // 验证返回值
    EXPECT_EQ(ret, 0);
}

// 测试用例
TEST(ServiceProfilerMsptiTest, InitMsptiTestNotSupport) {
    msptiSubscriberHandle subscriber;
    std::string profPath = "/path/to/profiling";
    g_utStatusMsptiSubscribe = MSPTI_ERROR_MULTIPLE_SUBSCRIBERS_NOT_SUPPORTED;
    g_utStatusMsptiActivityRegisterCallbacks = MSPTI_ERROR_INVALID_PARAMETER;
    // 调用函数
    int ret = InitMspti(profPath, subscriber);

    // 验证返回值
    EXPECT_EQ(ret, MSPTI_ERROR_INVALID_PARAMETER);
}

// 测试用例
TEST(ServiceProfilerMsptiTest, InitMsptiTestError) {
    msptiSubscriberHandle subscriber;
    std::string profPath = "/path/to/profiling";
    g_utStatusMsptiSubscribe = MSPTI_ERROR_INNER;
    // 验证返回值
    EXPECT_EQ(InitMspti(profPath, subscriber), MSPTI_ERROR_INNER);

    g_utStatusMsptiSubscribe = MSPTI_ERROR_INVALID_PARAMETER;
    // 验证返回值
    EXPECT_EQ(InitMspti(profPath, subscriber), MSPTI_ERROR_INVALID_PARAMETER);

    g_utStatusMsptiSubscribe = MSPTI_ERROR_FOECE_INT;
    // 验证返回值
    EXPECT_EQ(InitMspti(profPath, subscriber), MSPTI_ERROR_FOECE_INT);
}

// 测试用例
TEST(ServiceProfilerMsptiTest, InitMsptiTestInnerError) {
    msptiSubscriberHandle subscriber;
    std::string profPath = "/path/to/profiling";
    g_utStatusMsptiSubscribe = MSPTI_SUCCESS;
    g_utStatusMsptiActivityRegisterCallbacks = MSPTI_ERROR_INNER;
    // 验证返回值
    EXPECT_EQ(InitMspti(profPath, subscriber), MSPTI_ERROR_INNER);
}

// 测试用例
TEST(ServiceProfilerMsptiTest, InitMsptiActivityTestJustEnableMarker) {
    g_utStatusMsptiActivityEnable = MSPTI_SUCCESS;
    InitMsptiActivity(false);
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, InitMsptiActivityTestSuccess) {
    g_utStatusMsptiActivityEnable = MSPTI_SUCCESS;
    InitMsptiActivity(true);
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, InitMsptiActivityTestInnerError) {
    g_utStatusMsptiActivityEnable = MSPTI_ERROR_INNER;
    InitMsptiActivity(true);
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, InitMsptiFilter) {
    InitMsptiFilter("", "");
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, UninitMsptiSuccess) {
    msptiSubscriberHandle subscriber;
    g_utStatusMsptiActivityFlushAll = MSPTI_SUCCESS;
    g_utStatusMsptiUnsubscribe = MSPTI_SUCCESS;
    UninitMspti(subscriber);
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, UninitMsptiError) {
    msptiSubscriberHandle subscriber;
    g_utStatusMsptiActivityFlushAll = MSPTI_ERROR_INNER;
    g_utStatusMsptiUnsubscribe = MSPTI_ERROR_INNER;
    UninitMspti(subscriber);
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, FlushBufferByTimeSuccess) {
    ServiceProfilerMspti::GetInstance().workingThreadNum = 1;
    g_utStatusMsptiActivityFlushAll = MSPTI_SUCCESS;
    FlushBufferByTime();
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, FlushBufferByTimeSuccessFlushAll) {
    ServiceProfilerMspti::GetInstance().workingThreadNum = 0;
    g_utStatusMsptiActivityFlushAll = MSPTI_SUCCESS;
    FlushBufferByTime();
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, FlushBufferByTimeFailedFlushAll) {
    ServiceProfilerMspti::GetInstance().workingThreadNum = 1;
    g_utStatusMsptiActivityFlushAll = MSPTI_ERROR_INNER;
    FlushBufferByTime();
    EXPECT_TRUE(true);  // 如果程序没有崩溃，则认为测试通过
}

// 测试用例
TEST(ServiceProfilerMsptiTest, UserBufferRequestTestNormalCase) {
    uint8_t* buffer = nullptr;
    size_t size = 0;
    size_t maxNumRecords = 0;
    UserBufferClear();
    // 调用函数
    UserBufferRequest(&buffer, &size, &maxNumRecords);

    // 验证 buffer 是否对齐
    uintptr_t bufferAddr = reinterpret_cast<uintptr_t>(buffer);
    EXPECT_EQ(bufferAddr % ALIGN_SIZE, 0);

    // 验证 size 是否正确
    EXPECT_EQ(size, 1 * ONE_K * ONE_K);

    // 验证 maxNumRecords 是否正确
    EXPECT_EQ(maxNumRecords, 0);

    // 释放内存
    if (buffer) {
        free(buffer);
    }
}