/*
* Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#include <sys/mman.h>
#include <sys/stat.h>
#include <gtest/gtest.h>
#include <vector>
#include <chrono>
#include <mockcpp/mockcpp.hpp>
#include <nlohmann/json.hpp>

#include "acl/acl_prof.h"
#include "acl/acl.h"

#include "msServiceProfiler/msServiceProfiler.h"
#include "msServiceProfiler/ServiceProfilerManager.h"
#include "msServiceProfiler/Utils.h"
#include "stubs.h"

using namespace ::testing;

void MarkEventLongAttr(const char *msg);
namespace msServiceProfiler { void Write2Tx(const std::vector<int> &memoryInfo, const std::string metricName); }

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
    MOCK_METHOD5(aclprofCreateConfig, aclprofConfig*(uint32_t*, uint32_t, aclprofAicoreMetrics, aclprofAicoreEvents*, uint64_t));
    MOCK_METHOD1(aclprofStart, aclError(const aclprofConfig *));
    MOCK_METHOD1(aclprofStop, aclError(const aclprofConfig *));
    MOCK_METHOD1(aclprofDestroyConfig, aclError(const aclprofConfig *));
    MOCK_METHOD0(aclprofFinalize, aclError());
};

using DATA_PTR = struct ProfSetDevPara *;

struct ProfSetDevPara {
    uint32_t chipId;
    uint32_t deviceId;
    bool isOpen;
};

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
    AddMetaInfo("test","test2");
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
    GlobalMockObject::reset();
}

TEST(ProfilerTest, TestRegisterSetDeviceCallbackDlopenNull)
{
    MockStubFunc stubs;
    ServiceProfilerManager manager;
    
    // set Profiling env name
    setenv("SERVICE_PROF_CONFIG_PATH", "/ut_test/prof.json", 1);
        // Clean up
    GlobalMockObject::reset();
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
    uint32_t len = sizeof(ProfSetDevPara);
    MsprofSetDeviceCallbackImpl(data, len);
}

TEST(ProfilerTest, MsprofSetDeviceCallbackImplDeviceID)
{
    ProfSetDevPara temp;
    DATA_PTR data = &temp;
    uint32_t len = sizeof(ProfSetDevPara);
    MsprofSetDeviceCallbackImpl(data, len);
}
extern int g_deviceID;
extern bool g_startFlag;

TEST(ProfilerTest, MsprofSetDeviceCallbackImplStartServerProfiler1)
{
    ProfSetDevPara temp;
    temp.deviceId = 1;
    DATA_PTR data = &temp;
    uint32_t len = sizeof(ProfSetDevPara);
    g_deviceID = 1;
    g_startFlag = true;
    MsprofSetDeviceCallbackImpl(data, len);
}

TEST(ProfilerTest, MsprofSetDeviceCallbackImplStartServerProfiler2)
{
    ProfSetDevPara temp;
    temp.deviceId = 1;
    DATA_PTR data = &temp;
    uint32_t len = sizeof(ProfSetDevPara);
    g_deviceID = 2;
    g_startFlag = true;
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
    GlobalMockObject::reset();
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
    GlobalMockObject::reset();
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
    configTest["profiler_level"] = 1;
    configTest["host_system_usage_freq"] = 2;
    configTest["npu_memory_usage_freq"] = 2;
    configTest["timelimit"] = -1;
    configTest2["profiler_level"] = "Level";
    configTest2["host_system_usage_freq"] = "aaa";
    configTest2["npu_memory_usage_freq"] = "aaa";
    configTest2["timelimit"] = 2;
    configTest3["host_system_usage_freq"] = 99999;
    configTest3["npu_memory_usage_freq"] = 99999;
    configTest3["timelimit"] = 8000;
    configTest4["timelimit"] = "aaa";

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

    GlobalMockObject::reset();
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

    GlobalMockObject::reset();
}

TEST(ProfilerTest, TestMarkFirstProcessAsMainFtruncateFailed)
{
    MockStubFunc stubs;
    EXPECT_CALL(stubs, ftruncate(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(-1));

    ServiceProfilerManager manager;
    manager.config_->SetConfigPath("/home");
    manager.MarkFirstProcessAsMain();

    GlobalMockObject::reset();
}

TEST(ProfilerTest, TestReadConfigFailed)
{
    MockStubFunc stubs;
    EXPECT_CALL(stubs, access(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(0));

    ServiceProfilerManager manager;
    manager.config_->ReadConfigFile();

    GlobalMockObject::reset();
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

    GlobalMockObject::reset();
}

TEST(ProfilerTest, TestDynamicControlReturn)
{
    ServiceProfilerManager manager;
    manager.DynamicControl();

    GlobalMockObject::reset();
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

    GlobalMockObject::reset();
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

    GlobalMockObject::reset();
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

    GlobalMockObject::reset();
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

    GlobalMockObject::reset();
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

    GlobalMockObject::reset();
}

TEST(ProfilerTest, TestWrite2TxMemoryInfoEmpty)
{
    std::vector<int> memoryInfo;
    std::string metricName;
    Write2Tx(memoryInfo, metricName);
}

TEST(ProfilerTest, TestWrite2Tx)
{
    std::vector<int> memoryInfo {1,1};
    std::string metricName;
    Write2Tx(memoryInfo, metricName);
}
extern bool g_threadRunFlag;

TEST(ProfilerTest, ThreadFunctionTimeLimit)
{
    ServiceProfilerManager manager;
    manager.started_ = true;
    manager.config_->SetTimeLimit(1);
    g_threadRunFlag = true;
    std::thread([]() {
        std::this_thread::sleep_for(std::chrono::seconds(2)); // 等待 1 秒
        g_threadRunFlag = false;
        std::cout << "g_threadRunFlag has been set to false." << std::endl;
    }).detach(); 
    manager.ThreadFunction();
}

TEST(ProfilerTest, ThreadFunctionAclTaskTimeLimit)
{
    ServiceProfilerManager manager;
    manager.npuFlag_ = true;
    manager.config_->SetAclTaskTimeDuration(1);
    g_threadRunFlag = true;
    std::thread([]() {
        std::this_thread::sleep_for(std::chrono::seconds(2)); // 等待 1 秒
        g_threadRunFlag = false;
        std::cout << "g_threadRunFlag has been set to false." << std::endl;
    }).detach(); 
    manager.ThreadFunction();
}

TEST(ProfilerTest, ThreadFunctionGetEnable)
{
    ServiceProfilerManager manager;
    manager.npuFlag_ = true;
    manager.config_->SetEnable(true);
    manager.config_->npuMemoryUsage_ = true;
    manager.isMaster_ = true;
    g_threadRunFlag = true;
    std::thread([]() {
        std::this_thread::sleep_for(std::chrono::seconds(1)); // 等待 1 秒
        g_threadRunFlag = false;
        std::cout << "g_threadRunFlag has been set to false." << std::endl;
    }).detach(); 
    manager.ThreadFunction();
}

TEST(ProfilerTest, ThreadFunctionGetEnable2)
{
    ServiceProfilerManager manager;
    manager.npuFlag_ = true;
    manager.config_->SetEnable(false);
    manager.config_->npuMemoryUsage_ = false;
    manager.isMaster_ = true;
    g_threadRunFlag = true;
    std::thread([]() {
        std::this_thread::sleep_for(std::chrono::seconds(1)); // 等待 1 秒
        g_threadRunFlag = false;
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
    g_deviceID = static_cast<uint32_t>(-1);
   
    manager.ProfCreateConfig();
}

TEST(ProfilerTest, ProfCreateConfigL1)
{
    ServiceProfilerManager manager;
    g_deviceID = 1;
    manager.config_->enableAclTaskTime_ = 1;
    manager.config_->aclTaskTimeLevel_ = "L1";
    manager.ProfCreateConfig();
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
    manager.msptiEnabled = true;
    manager.StopAclTaskTime();
}

TEST(ProfilerTest, StopAclTaskTime)
{
    ServiceProfilerManager manager;
    manager.msptiEnabled = false;
    manager.config_->enableAclTaskTime_ = 1;
    manager.config_->hostCpuUsage_ = true;
    manager.config_->hostMemoryUsage_ = true;
    manager.StopAclTaskTime();
}