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
#include <nlohmann/json.hpp>
#include <fstream>
#include <dlfcn.h>
#include <fcntl.h>
#include <unistd.h>

#include "acl/acl_prof.h"
#include "acl/acl.h"

#include "msServiceProfiler/msServiceProfiler.h"
#include "msServiceProfiler/ServiceProfilerManager.h"
#include "msServiceProfiler/Utils.h"
#include "msServiceProfiler/Config.h"
#include "stubs.h"

using namespace ::testing;

void MarkEventLongAttr(const char *msg);
namespace msServiceProfiler {
void DeviceMemoryWrite2Tx(const std::vector<int> &memoryInfo, const std::string &metricName);
}

using namespace msServiceProfiler;


class AclStubFunc {
public:
    virtual aclError aclInit(const char *configPath) = 0;
    virtual aclError aclprofInit(const char *profilerResultPath, size_t length) = 0;
    virtual aclprofConfig *aclprofCreateConfig(uint32_t *deviceIdList, uint32_t deviceNums,
        aclprofAicoreMetrics aicoreMetrics, aclprofAicoreEvents *aicoreEvents, uint64_t dataTypeConfig) = 0;
    virtual aclError aclprofStart(const aclprofConfig *profilerConfig) = 0;
    virtual aclError aclprofStop(const aclprofConfig *profilerConfig) = 0;
    virtual aclError aclprofDestroyConfig(const aclprofConfig *profilerConfig) = 0;
    virtual aclError aclprofFinalize() = 0;
};

class MockAclStubFunc : public AclStubFunc {
public:
    MOCK_METHOD1(aclInit, aclError(const char*));
    MOCK_METHOD2(aclprofInit, aclError(const char*, size_t));
    MOCK_METHOD5(aclprofCreateConfig, aclprofConfig*(
        uint32_t*, uint32_t, aclprofAicoreMetrics, aclprofAicoreEvents*, uint64_t));
    MOCK_METHOD1(aclprofStart, aclError(const aclprofConfig *));
    MOCK_METHOD1(aclprofStop, aclError(const aclprofConfig *));
    MOCK_METHOD1(aclprofDestroyConfig, aclError(const aclprofConfig *));
    MOCK_METHOD0(aclprofFinalize, aclError());
};

using DATA_PTR = struct ProfSetDevParaDevice *;

struct ProfSetDevParaDevice {
    uint32_t chipId;
    uint32_t deviceId;
    bool isOpen;
};

// sys call mock
// 原始函数指针
static int (*real_shm_open)(const char*, int, mode_t) = nullptr;
static void* (*real_mmap)(void*, size_t, int, int, int, off_t) = nullptr;
static int (*real_ftruncate)(int, off_t) = nullptr;

// Mock 控制
struct MockControl {
    bool real_func = true;
    bool bool_return = false;
    int int_return = 0;
    void* void_return = nullptr;
    int call_count = 0;
};

static MockControl mock_control_shm_open;
static MockControl mock_control_mmap;
static MockControl mock_control_ftruncate;
// static MockControl mock_control_aclInit;
// static MockControl mock_control_aclprofInit;
// static MockControl mock_control_aclprofStart;

// Mock 实现
extern "C" int shm_open(const char* name, int oflag, mode_t mode)
{
    mock_control_shm_open.call_count++;
    if (mock_control_shm_open.real_func) {
        real_shm_open = reinterpret_cast<decltype(real_shm_open)>(
            dlsym(RTLD_NEXT, "shm_open")
        );
        return real_shm_open(name, oflag, mode);
    }
    return mock_control_shm_open.int_return;
}

extern "C" void* mmap(void* addr, size_t length, int prot, int flags, int fd, off_t offset)
{
    mock_control_mmap.call_count++;
    if (mock_control_mmap.real_func) {
        real_mmap = reinterpret_cast<decltype(real_mmap)>(
            dlsym(RTLD_NEXT, "mmap")
        );
        return real_mmap(addr, length, prot, flags, fd, offset);
    }
    return mock_control_mmap.void_return;
}

extern "C" int ftruncate(int fd, off_t length)
{
    mock_control_ftruncate.call_count++;
    if (mock_control_ftruncate.real_func) {
        real_ftruncate = reinterpret_cast<decltype(real_ftruncate)>(
            dlsym(RTLD_NEXT, "ftruncate")
        );
        return real_ftruncate(fd, length);
    }
    return mock_control_ftruncate.int_return;
}


// Test suite for StartSpan function
TEST(ProfilerTest, StartSpan)
{
    SpanHandle span = StartSpan();
    ASSERT_GE(span, 0U);
}

TEST(ProfilerTest, StartSpanWithName)
{
    SpanHandle span = StartSpanWithName("TestStartSpanWithName");
    ASSERT_GE(span, 0U);
}

TEST(ProfilerTest, StartSpanWithNameNull)
{
    SpanHandle span = StartSpanWithName(nullptr);
}

TEST(ProfilerTest, MarkSpanAttr)
{
    SpanHandle span = StartSpan();
    MarkSpanAttr("MarkSpanAttr", span);
    ASSERT_GE(span, 0U);
}

TEST(ProfilerTest, MarkSpanAttrNull)
{
    SpanHandle span = StartSpan();
    MarkSpanAttr(nullptr, span);
}

TEST(ProfilerTest, MarkEventNull)
{
    MarkEvent(nullptr);
}

TEST(ProfilerTest, GetValidDomain)
{
    GetValidDomain();
}

TEST(ProfilerTest, AddMetaInfo)
{
    AddMetaInfo("test", "test2");
}


TEST(ProfilerTest, EndSpan)
{
    SpanHandle span = StartSpan();
    EndSpan(span);
    ASSERT_GE(span, 0U);
}

TEST(ProfilerTest, StartServerProfiler)
{
    StartServerProfiler();
}

TEST(ProfilerTest, StopServerProfiler)
{
    StopServerProfiler();
}

TEST(ProfilerTest, TestServiceProfilerManager)
{
    MockStubFunc stubs;
    char mockRealpath[] = "aa";
    EXPECT_CALL(stubs, StartSpanWithName(::testing::_)).Times(0);
    EXPECT_CALL(stubs, access(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(0));
    EXPECT_CALL(stubs, realpath(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return((char*)mockRealpath));
    EXPECT_CALL(stubs, stat(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(1));
    EXPECT_CALL(stubs, dlopen(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return((void*)(1)));
    ServiceProfilerManager manager;
    // set Profiling env name
    setenv("SERVICE_PROF_CONFIG_PATH", "/ut_test/prof.json", 1);
}

TEST(ProfilerTest, TestRegisterSetDeviceCallbackDlopenNull)
{
    MockStubFunc stubs;
    ServiceProfilerManager manager;

    // set Profiling env name
    setenv("SERVICE_PROF_CONFIG_PATH", "/ut_test/prof.json", 1);
        // Clean up
}

void MsprofSetDeviceCallbackImpl(DATA_PTR data, uint32_t len);

TEST(ProfilerTest, MsprofSetDeviceCallbackImplLen0)
{
    DATA_PTR data;
    uint32_t len = 0;
    MsprofSetDeviceCallbackImpl(data, len);
}

TEST(ProfilerTest, MsprofSetDeviceCallbackImplDataNull)
{
    DATA_PTR data = nullptr;
    uint32_t len = sizeof(ProfSetDevParaDevice);
    MsprofSetDeviceCallbackImpl(data, len);
}

TEST(ProfilerTest, MsprofSetDeviceCallbackImplDeviceID)
{
    ProfSetDevParaDevice temp;
    DATA_PTR data = &temp;
    uint32_t len = sizeof(ProfSetDevParaDevice);
    MsprofSetDeviceCallbackImpl(data, len);
}

TEST(ProfilerTest, MsprofSetDeviceCallbackImplStartServerProfiler1)
{
    ProfSetDevParaDevice temp;
    temp.deviceId = 1;
    DATA_PTR data = &temp;
    uint32_t len = sizeof(ProfSetDevParaDevice);
    MsprofSetDeviceCallbackImpl(data, len);
}

TEST(ProfilerTest, MsprofSetDeviceCallbackImplStartServerProfiler2)
{
    ProfSetDevParaDevice temp;
    temp.deviceId = 1;
    DATA_PTR data = &temp;
    uint32_t len = sizeof(ProfSetDevParaDevice);
    MsprofSetDeviceCallbackImpl(data, len);
}

TEST(ProfilerTest, TestRegisterSetDeviceCallbackProfRegDeviceStateCallbackNull)
{
    MockStubFunc stubs;
    char mockRealpath[] = "aa";
    EXPECT_CALL(stubs, StartSpanWithName(::testing::_)).Times(0);
    EXPECT_CALL(stubs, access(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(0));
    EXPECT_CALL(stubs, realpath(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return((char*)mockRealpath));
    EXPECT_CALL(stubs, stat(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(1));
    EXPECT_CALL(stubs, dlopen(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return((void*)(1)));
    EXPECT_CALL(stubs, dlsym(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(nullptr));
    ServiceProfilerManager manager;
    // set Profiling env name
    setenv("SERVICE_PROF_CONFIG_PATH", "/ut_test/prof.json", 1);
}

TEST(ProfilerTest, MakeDirs)
{
    MockStubFunc stubs;
    char mockRealpath[] = "aa";
    EXPECT_CALL(stubs, StartSpanWithName(::testing::_)).Times(0);
    EXPECT_CALL(stubs, access(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(0));
    EXPECT_CALL(stubs, realpath(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return((char*)mockRealpath));
    EXPECT_CALL(stubs, stat(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(1));
    EXPECT_CALL(stubs, dlopen(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return((void*)(1)));
    EXPECT_CALL(stubs, dlsym(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(nullptr));
    ServiceProfilerManager manager;
    // set Profiling env name
    setenv("SERVICE_PROF_CONFIG_PATH", "/ut_test/prof.json", 1);
}

TEST(ProfilerTest, TestReadEnableYes)
{
    nlohmann::json configTest = nlohmann::json::object();
    nlohmann::json configTest2 = nlohmann::json::object();
    nlohmann::json configTest3 = nlohmann::json::object();
    nlohmann::json configTest4 = nlohmann::json::object();
    configTest["enable"] = 1;
    configTest["prof_dir"] = "/aaa";
    configTest["acl_task_time"] = 1;
    configTest["acl_prof_task_time_level"] = "L1;10";
    configTest["profiler_level"] = 1;
    configTest["host_system_usage_freq"] = 2;
    configTest["npu_memory_usage_freq"] = 2;
    configTest["timelimit"] = -1;
    configTest["domain"] = "Request; KVCache";
    configTest2["profiler_level"] = "Level";
    configTest2["acl_prof_task_time_level"] = "L3;";
    configTest2["host_system_usage_freq"] = "aaa";
    configTest2["npu_memory_usage_freq"] = "aaa";
    configTest2["timelimit"] = 2;
    configTest2["domain"] = "";
    configTest3["host_system_usage_freq"] = 99999;
    configTest3["npu_memory_usage_freq"] = 99999;
    configTest3["acl_prof_task_time_level"] = "L3;L1";
    configTest3["timelimit"] = 8000;
    configTest4["timelimit"] = "aaa";
    configTest4["acl_prof_task_time_level"] = "L1;0";

    ServiceProfilerManager manager;
    EXPECT_NO_THROW(manager.config_->ParseConfig(configTest));
    EXPECT_NO_THROW(manager.config_->ParseConfig(configTest2));
    EXPECT_NO_THROW(manager.config_->ParseConfig(configTest3));
    EXPECT_NO_THROW(manager.config_->ParseConfig(configTest4));
}

TEST(ProfilerTest, TestDynamicControlStart2Stop1)
{
    nlohmann::json configTest = nlohmann::json::object();
    configTest["enable"] = 1;

    ServiceProfilerManager manager;
    manager.config_->ParseConfig(configTest);

    MockStubFunc stubs;
    EXPECT_CALL(stubs, stat(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(0));

    manager.lastUpdate_ = 123;
    manager.config_->SetConfigPath("/home");

    // set Profiling env name
    setenv("SERVICE_PROF_CONFIG_PATH", "/ut_test/prof.json", 1);

    manager.DynamicControl();
}

TEST(ProfilerTest, TestSetAclProfHostSysConfig1)
{
    ServiceProfilerManager manager;

    nlohmann::json configTest = nlohmann::json::object();
    configTest["host_system_usage_freq"] = 2;
    manager.config_->ParseConfig(configTest);
    manager.SetAclProfHostSysConfig();
}

TEST(ProfilerTest, TestSetAclProfHostSysConfig2)
{
    ServiceProfilerManager manager;
    nlohmann::json configTest = nlohmann::json::object();
    configTest["host_system_usage_freq"] = 0;
    manager.config_->ParseConfig(configTest);
    manager.SetAclProfHostSysConfig();
}

TEST(ProfilerTest, TestSetAclProfHostSysConfig3)
{
    ServiceProfilerManager manager;
    nlohmann::json configTest = nlohmann::json::object();
    configTest["host_system_usage_freq"] = 10000;
    manager.config_->ParseConfig(configTest);
    manager.SetAclProfHostSysConfig();
}

TEST(ProfilerTest, TestStopProfiler)
{
    ServiceProfilerManager manager;

    manager.started_ = true;
    manager.StopProfiler();
}

TEST(ProfilerTest, TestMarkFirstProcessAsMainShmOpenFailed)
{
    MockStubFunc stubs;
    EXPECT_CALL(stubs, shm_open(::testing::_, ::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(-1));

    ServiceProfilerManager manager;
    manager.config_->SetConfigPath("/home");
    manager.MarkFirstProcessAsMain();
}

TEST(ProfilerTest, TestMarkFirstProcessAsMainFtruncateFailed)
{
    MockStubFunc stubs;
    EXPECT_CALL(stubs, ftruncate(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(-1));

    ServiceProfilerManager manager;
    manager.config_->SetConfigPath("/home");
    manager.MarkFirstProcessAsMain();
}

TEST(ProfilerTest, TestReadConfigFailed)
{
    MockStubFunc stubs;
    EXPECT_CALL(stubs, access(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(0));

    ServiceProfilerManager manager;
    manager.config_->ReadConfigFile();
}

TEST(ProfilerTest, TestMarkFirstProcessAsMainReturn)
{
    ServiceProfilerManager manager;
    manager.MarkFirstProcessAsMain();
}

TEST(ProfilerTest, TestMarkFirstProcessAsMain)
{
    ServiceProfilerManager manager;
    manager.config_->SetConfigPath("/home");
    manager.MarkFirstProcessAsMain();
}

TEST(ProfilerTest, TestReadConfigFileFailed)
{
    ServiceProfilerManager manager;
    manager.config_->SetConfigPath("/home");
    manager.config_->ReadConfigFile();
}

TEST(ProfilerTest, TestDynamicControlReadConfigFileStatFailed)
{
    MockStubFunc stubs;
    EXPECT_CALL(stubs, stat(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(1));

    ServiceProfilerManager manager;
    manager.config_->SetConfigPath("/home");
    manager.DynamicControl();
}

TEST(ProfilerTest, TestDynamicControlReturn)
{
    ServiceProfilerManager manager;
    manager.DynamicControl();
}

TEST(ProfilerTest, TestStartProfilerCreatConfigFailed)
{
    static MockAclStubFunc aclStubs;
    EXPECT_CALL(aclStubs, aclInit(::testing::_))
        .WillRepeatedly(::testing::Return(222));
    EXPECT_CALL(aclStubs, aclprofInit(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(222));

    ServiceProfilerManager manager;
    nlohmann::json configTest = nlohmann::json::object();
    configTest["acl_task_time"] = 1;
    manager.config_->ParseConfig(configTest);
    manager.started_ = false;
    manager.StartProfiler();
}

TEST(ProfilerTest, TestStartProfilerStarted)
{
    ServiceProfilerManager manager;
    manager.started_ = true;
    manager.StartProfiler();
}

TEST(ProfilerTest, TestStartProfilerAclProfStartFailed)
{
    static MockAclStubFunc aclStubs;
    EXPECT_CALL(aclStubs, aclInit(::testing::_))
        .WillRepeatedly(::testing::Return(222));
    EXPECT_CALL(aclStubs, aclprofInit(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(ACL_ERROR_NONE));
    EXPECT_CALL(aclStubs, aclprofCreateConfig(::testing::_, ::testing::_, ::testing::_, ::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return((aclprofConfig*)1));
    EXPECT_CALL(aclStubs, aclprofStart(::testing::_))
        .WillRepeatedly(::testing::Return(222));

    ServiceProfilerManager manager;
    nlohmann::json configTest = nlohmann::json::object();
    configTest["acl_task_time"] = 1;
    manager.config_->ParseConfig(configTest);
    manager.started_ = false;
    manager.StartProfiler();
}

TEST(ProfilerTest, TestStopProfilerAclProfStopFailed)
{
    static MockAclStubFunc aclStubs;
    EXPECT_CALL(aclStubs, aclprofStop(::testing::_))
        .WillRepeatedly(::testing::Return(222));
    EXPECT_CALL(aclStubs, aclprofDestroyConfig(::testing::_))
        .WillRepeatedly(::testing::Return(222));

    ServiceProfilerManager manager;
    manager.started_ = true;
    manager.StopProfiler();
}

TEST(ProfilerTest, TestStopProfilerAclDestroyConfigFailed)
{
    static MockAclStubFunc aclStubs;
    EXPECT_CALL(aclStubs, aclprofStop(::testing::_))
        .WillRepeatedly(::testing::Return(ACL_ERROR_NONE));
    EXPECT_CALL(aclStubs, aclprofDestroyConfig(::testing::_))
        .WillRepeatedly(::testing::Return(222));

    ServiceProfilerManager manager;
    manager.started_ = true;
    manager.StopProfiler();
}

TEST(ProfilerTest, TestStopProfilerAclFrofFinalizeFailed)
{
    static MockAclStubFunc aclStubs;
    EXPECT_CALL(aclStubs, aclprofStop(::testing::_))
        .WillRepeatedly(::testing::Return(ACL_ERROR_NONE));
    EXPECT_CALL(aclStubs, aclprofDestroyConfig(::testing::_))
        .WillRepeatedly(::testing::Return(ACL_ERROR_NONE));
    EXPECT_CALL(aclStubs, aclprofFinalize())
        .WillRepeatedly(::testing::Return(222));

    ServiceProfilerManager manager;
    manager.started_ = true;
    manager.StopProfiler();
}

TEST(ProfilerTest, TestWrite2TxMemoryInfoEmpty)
{
    std::vector<int> memoryInfo;
    std::string metricName;
    DeviceMemoryWrite2Tx(memoryInfo, metricName);
}

TEST(ProfilerTest, TestWrite2Tx)
{
    std::vector<int> memoryInfo {1, 1};
    std::string metricName;
    DeviceMemoryWrite2Tx(memoryInfo, metricName);
}

TEST(ProfilerTest, ThreadFunctionTimeLimit)
{
    ServiceProfilerManager manager;
    manager.started_ = true;
    manager.config_->SetTimeLimit(1);
    manager.threadRunFlag_ = true;
    std::thread([&manager]() {
        std::this_thread::sleep_for(std::chrono::seconds(2)); // 等待 1 秒
        manager.threadRunFlag_ = false;
        std::cout << "g_threadRunFlag has been set to false." << std::endl;
    }).detach();
    manager.ThreadFunction();
}

TEST(ProfilerTest, ThreadFunctionAclTaskTimeLimit)
{
    ServiceProfilerManager manager;
    manager.aclProfStarted_ = true;
    manager.config_->SetAclTaskTimeDuration(1);
    manager.threadRunFlag_ = true;
    std::thread([&manager]() {
        std::this_thread::sleep_for(std::chrono::seconds(2)); // 等待 1 秒
        manager.threadRunFlag_ = false;
        std::cout << "g_threadRunFlag has been set to false." << std::endl;
    }).detach();
    manager.ThreadFunction();
}

TEST(ProfilerTest, ThreadFunctionGetEnable)
{
    ServiceProfilerManager manager;
    manager.aclProfStarted_ = true;
    manager.config_->SetEnable(true);
    manager.config_->npuMemoryUsage_ = true;
    manager.isMaster_ = true;
    manager.threadRunFlag_ = true;
    std::thread([&manager]() {
        std::this_thread::sleep_for(std::chrono::seconds(1)); // 等待 1 秒
        manager.threadRunFlag_ = false;
        std::cout << "g_threadRunFlag has been set to false." << std::endl;
    }).detach();
    manager.ThreadFunction();
}

TEST(ProfilerTest, ThreadFunctionGetEnable2)
{
    ServiceProfilerManager manager;
    manager.aclProfStarted_ = true;
    manager.config_->SetEnable(false);
    manager.config_->npuMemoryUsage_ = false;
    manager.isMaster_ = true;
    manager.threadRunFlag_ = true;
    std::thread([&manager]() {
        std::this_thread::sleep_for(std::chrono::seconds(1)); // 等待 2 秒
        manager.threadRunFlag_ = false;
        std::cout << "g_threadRunFlag has been set to false." << std::endl;
    }).detach();
    manager.ThreadFunction();
}

TEST(ProfilerTest, SetAclProfHostSysConfigCPU)
{
    ServiceProfilerManager manager;
    manager.config_->hostCpuUsage_ = true;
    manager.config_->hostMemoryUsage_ = false;

    manager.SetAclProfHostSysConfig();
}

TEST(ProfilerTest, SetAclProfHostSysConfigMEN)
{
    ServiceProfilerManager manager;
    manager.config_->hostCpuUsage_ = false;
    manager.config_->hostMemoryUsage_ = true;

    manager.SetAclProfHostSysConfig();
}

TEST(ProfilerTest, ProfCreateConfig)
{
    ServiceProfilerManager manager;

    manager.ProfCreateConfig(-1);
}

TEST(ProfilerTest, ProfCreateConfigL1)
{
    ServiceProfilerManager manager;
    manager.config_->enableAclTaskTime_ = 1;
    manager.config_->aclTaskTimeLevel_ = "L1";
    manager.ProfCreateConfig(1);
}

TEST(ProfilerTest, StartMsptiProf)
{
    ServiceProfilerManager manager;
    std::string profPath = "/home";
    manager.StartMsptiProf(profPath);
}

TEST(ProfilerTest, StopAclTaskTimeMsptiEnabled)
{
    ServiceProfilerManager manager;
    manager.msptiStarted_ = true;
    manager.StopAclProf();
}

TEST(ProfilerTest, StopAclTaskTime)
{
    ServiceProfilerManager manager;
    manager.msptiStarted_ = false;
    manager.config_->enableAclTaskTime_ = 1;
    manager.config_->hostCpuUsage_ = true;
    manager.config_->hostMemoryUsage_ = true;
    manager.StopAclProf();
}

TEST(ProfilerTest, TestMarkFirstProcessAsMainShmOpenFailedUseSysMock)
{
    mock_control_shm_open.real_func = false;
    mock_control_shm_open.int_return = -1;

    ServiceProfilerManager manager;
    manager.config_->SetConfigPath("/home");
    manager.MarkFirstProcessAsMain();
}

TEST(ProfilerTest, TestMarkFirstProcessAsMainFtruncateFailedUseSysMock)
{
    mock_control_shm_open.real_func = false;
    mock_control_shm_open.int_return = 0;

    mock_control_ftruncate.real_func = false;
    mock_control_ftruncate.int_return = -1;

    ServiceProfilerManager manager;
    manager.config_->SetConfigPath("/home");
    manager.MarkFirstProcessAsMain();
}

TEST(ProfilerTest, TestMarkFirstProcessAsMainMmapFailedUseSysMock)
{
    mock_control_shm_open.real_func = false;
    mock_control_shm_open.int_return = 0;

    mock_control_ftruncate.real_func = false;
    mock_control_ftruncate.int_return = 0;

    mock_control_mmap.real_func = false;
    mock_control_mmap.void_return = MAP_FAILED;

    ServiceProfilerManager manager;
    manager.config_->SetConfigPath("/home");
    manager.MarkFirstProcessAsMain();
}

TEST(ProfilerTest, TestMarkFirstProcessAsMainSuccessUseSysMock)
{
    mock_control_shm_open.real_func = false;
    mock_control_shm_open.int_return = 0;

    mock_control_ftruncate.real_func = false;
    mock_control_ftruncate.int_return = 0;

    mock_control_mmap.real_func = true;

    ServiceProfilerManager manager;
    manager.config_->SetConfigPath("/home");
    manager.MarkFirstProcessAsMain();
}
