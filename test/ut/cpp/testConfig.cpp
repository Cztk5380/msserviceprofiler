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
#include <fstream>
#include <cstdlib>
#include <iostream>

#include "acl/acl_prof.h"
#include "acl/acl.h"

#include "msServiceProfiler/Utils.h"
#include "msServiceProfiler/Config.h"
#include "stubs.h"

using namespace ::testing;

using namespace msServiceProfiler;

TEST(ProfilerTest, TestParseMspti)
{
    nlohmann::json configTest1 = nlohmann::json::object();
    nlohmann::json configTest2 = nlohmann::json::object();
    configTest1["api_filter"] = "";
    configTest1["kernel_filter"] = "";
    configTest2["api_filter"] = 1;
    configTest2["kernel_filter"] = 1;

    Config config;

    EXPECT_NO_THROW(config.ParseMspti(configTest1));
    EXPECT_NO_THROW(config.ParseMspti(configTest2));
}

TEST(ProfilerTest, TestGetConfigData)
{
    Config config;

    EXPECT_NO_THROW(config.GetConfigData());
}

TEST(ProfilerTest, TestSetFileEnable)
{
    Config config;

    EXPECT_NO_THROW(config.SetFileEnable(0));
}

TEST(ProfilerTest, TestSaveConfigToJsonFileInvalidPath)
{
    std::string path = "";
    setenv("SERVICE_PROF_CONFIG_PATH", path.c_str(), 1);
    Config config;

    EXPECT_NO_THROW(config.SaveConfigToJsonFile());
}

TEST(ProfilerTest, TestSaveConfigToJsonFileValidPath)
{
    std::string path = "/tmp/enable.json";
    setenv("SERVICE_PROF_CONFIG_PATH", path.c_str(), 1);
    Config config;

    EXPECT_NO_THROW(config.SaveConfigToJsonFile());
    EXPECT_NO_THROW(config.SaveConfigToJsonFile());  // Run again for testing file exists
    if (access(path.c_str(), F_OK) == 0) {
        std::remove(path.c_str());
    }
}

TEST(ProfilerTest, TestSplitAndTrimString)
{
    Config config;

    EXPECT_NO_THROW(config.SplitAndTrimString("Request; KVCache", ";"));
}

TEST(ProfilerTest, TestAclprofAicoreMetricsValid)
{
    Config config;
    nlohmann::json configTest = nlohmann::json::object();
    configTest["aclprofAicoreMetrics"] = "ACL_AICORE_PIPE_UTILIZATION";
    EXPECT_NO_THROW(config.ParseConfig(configTest));
}

TEST(ProfilerTest, TestAclprofAicoreMetricsInvalid)
{
    Config config;
    nlohmann::json configTest = nlohmann::json::object();
    configTest["aclprofAicoreMetrics"] = "test";
    EXPECT_NO_THROW(config.ParseConfig(configTest));
}

TEST(ProfilerTest, TestAclDataTypeConfigValid)
{
    Config config;
    nlohmann::json configTest = nlohmann::json::object();
    configTest["aclDataTypeConfig"] = "test";
    EXPECT_NO_THROW(config.ParseConfig(configTest));
}

TEST(ProfilerTest, TestAclDataTypeConfigInValid)
{
    Config config;
    nlohmann::json configTest = nlohmann::json::object();
    configTest["aclDataTypeConfig"] = "ACL_PROF_TASK_TIME,ACL_PROF_TASK_MEMORY";
    EXPECT_NO_THROW(config.ParseConfig(configTest));
}

TEST(ProfilerTest, TestGetProfilingSwitchL0)
{
    Config config;
    nlohmann::json configTest = nlohmann::json::object();
    configTest["acl_prof_task_time_level"] = "L0";
    configTest["aclDataTypeConfig"] = "ACL_PROF_ACL_API,ACL_PROF_TASK_TIME,ACL_PROF_AICORE_METRICS";
    EXPECT_NO_THROW(config.ParseConfig(configTest));

    uint32_t profSwitch = config.GetProfilingSwitch();
    EXPECT_EQ(profSwitch, 0x887);
}

TEST(ProfilerTest, TestGetProfilingSwitchL1)
{
    Config config;
    nlohmann::json configTest = nlohmann::json::object();
    configTest["acl_prof_task_time_level"] = "L1";
    configTest["aclDataTypeConfig"] = "ACL_PROF_ACL_API,ACL_PROF_TASK_TIME,ACL_PROF_AICORE_METRICS";
    EXPECT_NO_THROW(config.ParseConfig(configTest));

    uint32_t profSwitch = config.GetProfilingSwitch();
    EXPECT_EQ(profSwitch, 0x87);
}

TEST(ProfilerTest, TestGetProfilingSwitchInvalid)
{
    Config config;
    nlohmann::json configTest = nlohmann::json::object();
    configTest["acl_prof_task_time_level"] = "test";
    configTest["aclDataTypeConfig"] = "ACL_PROF_ACL_API,ACL_PROF_TASK_TIME,ACL_PROF_AICORE_METRICS";
    EXPECT_NO_THROW(config.ParseConfig(configTest));

    uint32_t profSwitch = config.GetProfilingSwitch();
    EXPECT_EQ(profSwitch, 0x887);
}
