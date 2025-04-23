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

void MarkEventLongAttr(const char *msg);
namespace msServiceProfiler { void Write2Tx(const std::vector<int> &memoryInfo, const std::string metricName); }

using namespace msServiceProfiler;

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
    char mockRealpath[] = "aa";
    MOCKER(access).stubs().will(returnValue(0));
    MOCKER(realpath).stubs().will(returnValue((char*)mockRealpath));
    MOCKER(stat).stubs().will(returnValue(1));
    
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
    manager.ReadEnable(configTest);
    manager.ReadProfPath(configTest);
    manager.ReadAclTaskTime(configTest);
    manager.ReadLevel(configTest);
    manager.ReadLevel(configTest2);
    manager.ReadHostConfig(configTest);
    manager.ReadHostConfig(configTest2);
    manager.ReadHostConfig(configTest3);
    manager.ReadNpuConfig(configTest);
    manager.ReadNpuConfig(configTest2);
    manager.ReadNpuConfig(configTest3);
}

TEST(ProfilerTest, TestWrite2Tx)
{
    const std::vector<int> memInfo(10, 1);
    const std::string metricName = "helloTest";
    Write2Tx(memInfo, metricName);
}

TEST(ProfilerTest, TestDynamicControlStart2Stop)
{
    nlohmann::json configTest = nlohmann::json::object();
    configTest["enable"] = 1;
    ServiceProfilerManager manager;

    MOCKER(stat).stubs().will(returnValue(0));

    std::string configPath_ = "aaa";
    manager.lastUpdate_ = 123;
    manager.enable_ = true;
    
    // set Profiling env name
    setenv("SERVICE_PROF_CONFIG_PATH", "/ut_test/prof.json", 1);

    manager.DynamicControl();

    GlobalMockObject::reset();
}

TEST(ProfilerTest, TestSetAclProfHostSysConfig1)
{
    ServiceProfilerManager manager;

    manager.hostCpuUsage_ = true;
    manager.hostMemoryUsage_ = true;
    manager.SetAclProfHostSysConfig();
}

TEST(ProfilerTest, TestSetAclProfHostSysConfig2)
{
    ServiceProfilerManager manager;

    manager.hostCpuUsage_ = true;
    manager.hostMemoryUsage_ = false;
    manager.SetAclProfHostSysConfig();
}

TEST(ProfilerTest, TestSetAclProfHostSysConfig3)
{
    ServiceProfilerManager manager;

    manager.hostCpuUsage_ = false;
    manager.hostMemoryUsage_ = true;
    manager.SetAclProfHostSysConfig();
}

TEST(ProfilerTest, TestSetAclProfHostSysConfig4)
{
    ServiceProfilerManager manager;

    manager.hostCpuUsage_ = false;
    manager.hostMemoryUsage_ = false;
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
    MOCKER(shm_open).stubs().will(returnValue(-1));

    ServiceProfilerManager manager;
    manager.MarkFirstProcessAsMain();

    GlobalMockObject::reset();
}

TEST(ProfilerTest, TestMarkFirstProcessAsMainFtruncateFailed)
{
    MOCKER(ftruncate).stubs().will(returnValue(-1));

    ServiceProfilerManager manager;
    manager.MarkFirstProcessAsMain();

    GlobalMockObject::reset();
}

TEST(ProfilerTest, TestReadConfigFailed)
{
    MOCKER(access).stubs().will(returnValue(0));

    ServiceProfilerManager manager;
    manager.ReadConfig();

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
    manager.configPath_ = "/home";
    manager.ReadConfig();
}

TEST(ProfilerTest, TestDynamicControlReadConfigFileStatFailed)
{
    MOCKER(stat).stubs().will(returnValue(1));

    ServiceProfilerManager manager;
    manager.DynamicControl();

    GlobalMockObject::reset();
}

TEST(ProfilerTest, TestStartProfilerCreatConfigFailed)
{
    MOCKER(aclInit).stubs().will(returnValue(222));
    MOCKER(aclprofInit).stubs().will(returnValue(222));

    ServiceProfilerManager manager;
    manager.started_ = false;
    manager.enableAclTaskTime_ = true;
    manager.StartProfiler();

    GlobalMockObject::reset();
}

TEST(ProfilerTest, TestStartProfilerAclProfStartFailed)
{
    MOCKER(aclInit).stubs().will(returnValue(222));
    MOCKER(aclprofInit).stubs().will(returnValue(ACL_ERROR_NONE));
    MOCKER(aclprofCreateConfig).stubs().will(returnValue((aclprofConfig*)1));
    MOCKER(aclprofStart).stubs().will(returnValue(222));

    ServiceProfilerManager manager;
    manager.started_ = false;
    manager.enableAclTaskTime_ = true;
    manager.StartProfiler();

    GlobalMockObject::reset();
}

TEST(ProfilerTest, TestStopProfilerAclProfStopFailed)
{
    MOCKER(aclprofStop).stubs().will(returnValue(222));
    MOCKER(aclprofDestroyConfig).stubs().will(returnValue(222));

    ServiceProfilerManager manager;
    manager.started_ = true;
    manager.StopProfiler();

    GlobalMockObject::reset();
}

TEST(ProfilerTest, TestStopProfilerAclDestroyConfigFailed)
{
    MOCKER(aclprofStop).stubs().will(returnValue(ACL_ERROR_NONE));
    MOCKER(aclprofDestroyConfig).stubs().will(returnValue(222));

    ServiceProfilerManager manager;
    manager.started_ = true;
    manager.StopProfiler();

    GlobalMockObject::reset();
}

TEST(ProfilerTest, TestStopProfilerAclFrofFinalizeFailed)
{
    MOCKER(aclprofStop).stubs().will(returnValue(ACL_ERROR_NONE));
    MOCKER(aclprofDestroyConfig).stubs().will(returnValue(ACL_ERROR_NONE));
    MOCKER(aclprofFinalize).stubs().will(returnValue(222));

    ServiceProfilerManager manager;
    manager.started_ = true;
    manager.StopProfiler();

    GlobalMockObject::reset();
}

