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
#include <fstream>
#include <cstdlib>
#include <iostream>

#include "acl/acl_prof.h"
#include "acl/acl.h"

#include "msServiceProfiler/msServiceProfiler.h"
#include "msServiceProfiler/ServiceProfilerManager.h"
#include "msServiceProfiler/Utils.h"
#include "msServiceProfiler/Config.h"
#include "stubs.h"

using namespace ::testing;

void MarkEventLongAttr(const char *msg);
namespace msServiceProfiler { void Write2Tx(const std::vector<int> &memoryInfo, const std::string metricName); }

using namespace msServiceProfiler;

TEST(ProfilerTest, TestParseMspti)
{
    nlohmann::json configTest1 = nlohmann::json::object();
    nlohmann::json configTest2 = nlohmann::json::object();
    configTest1["api_filter"] = "";
    configTest1["kernel_filter"] = "";
    configTest2["api_filter"] = 1;
    configTest2["kernel_filter"] = 1;

    ServiceProfilerManager manager;

    EXPECT_NO_THROW(manager.config_->ParseMspti(configTest1));
    EXPECT_NO_THROW(manager.config_->ParseMspti(configTest2));
}

TEST(ProfilerTest, TestGetConfigData)
{
    ServiceProfilerManager manager;

    EXPECT_NO_THROW(manager.config_->GetConfigData());
}

TEST(ProfilerTest, TestSetFileEnable)
{
    ServiceProfilerManager manager;

    EXPECT_NO_THROW(manager.config_->SetFileEnable(0));
}

TEST(ProfilerTest, TestSaveConfigToJsonFileInvalidPath)
{
    std::string path = "";
    int result = std::setenv("SERVICE_PROF_CONFIG_PATH", path.c_str(), 1);
    ServiceProfilerManager manager;

    EXPECT_NO_THROW(manager.config_->SaveConfigToJsonFile());
}

TEST(ProfilerTest, TestSaveConfigToJsonFileValidPath)
{
    std::string path = "enable.json";
    int result = std::setenv("SERVICE_PROF_CONFIG_PATH", path.c_str(), 1);
    ServiceProfilerManager manager;

    EXPECT_NO_THROW(manager.config_->SaveConfigToJsonFile());
}

TEST(ProfilerTest, TestSplitAndTrimString)
{
    ServiceProfilerManager manager;

    EXPECT_NO_THROW(manager.config_->SplitAndTrimString("Request; KVCache", ";"));
}