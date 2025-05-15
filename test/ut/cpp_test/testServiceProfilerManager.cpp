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

TEST(ProfilerTest, MarkSpanAttr)
{
    SpanHandle span = StartSpan();
    MarkSpanAttr("MarkSpanAttr", span);
    ASSERT_GE(span, 0U);
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
    
    // set Profiling env name
    setenv("SERVICE_PROF_CONFIG_PATH", "/ut_test/prof.json", 1);

    ServiceProfilerManager manager;

    GlobalMockObject::reset();
}

TEST(ProfilerTest, TestReadEnableYes)
{
    nlohmann::json configTest = nlohmann::json::object();
    nlohmann::json configTest2 = nlohmann::json::object();
    nlohmann::json configTest3 = nlohmann::json::object();
    configTest["enable"] = 1;
    configTest["prof_dir"] = "/aaa";
    configTest["acl_task_time"] = 1;
    configTest["profiler_level"] = 1;
    configTest["host_system_usage_freq"] = 2;
    configTest["npu_memory_usage_freq"] = 2;
    configTest2["profiler_level"] = "Level";
    configTest2["host_system_usage_freq"] = "aaa";
    configTest2["npu_memory_usage_freq"] = "aaa";
    configTest3["host_system_usage_freq"] = 99999;
    configTest3["npu_memory_usage_freq"] = 99999;

    ServiceProfilerManager manager;
    EXPECT_NO_THROW(manager.config_->ParseConfig(configTest));
    EXPECT_NO_THROW(manager.config_->ParseConfig(configTest2));
    EXPECT_NO_THROW(manager.config_->ParseConfig(configTest3));
}

TEST(ProfilerTest, TestDynamicControlStart2Stop)
{
    nlohmann::json configTest = nlohmann::json::object();
    configTest["enable"] = 1;
    
    ServiceProfilerManager manager;
    manager.config_->ParseConfig(configTest);

    MockStubFunc stubs;
    EXPECT_CALL(stubs, stat(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(0));

    manager.lastUpdate_ = 123;

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
    manager.MarkFirstProcessAsMain();

    GlobalMockObject::reset();
}

TEST(ProfilerTest, TestMarkFirstProcessAsMainFtruncateFailed)
{
    MockStubFunc stubs;
    EXPECT_CALL(stubs, ftruncate(::testing::_, ::testing::_))
        .WillRepeatedly(::testing::Return(-1));

    ServiceProfilerManager manager;
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

TEST(ProfilerTest, TestMarkFirstProcessAsMainMmapFailed)
{
    ServiceProfilerManager manager;
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
