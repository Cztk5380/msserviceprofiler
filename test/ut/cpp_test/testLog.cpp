/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <gtest/gtest.h>
#include <gmock/gmock.h>
#include <string>
#include "msServiceProfiler/Log.h"

using namespace msServiceProfiler;

TEST(ProfilerTest, ProfLogInit)
{
    ProfLogInit();
}

TEST(ProfilerTest, ProfLogInitDEBUG)
{
    setenv("PROF_LOG_LEVEL", "DEBUG", 1);
    ProfLogInit();
}

TEST(ProfilerTest, ProfLogInitINFO)
{
    setenv("PROF_LOG_LEVEL", "INFO", 1);
    ProfLogInit();
}

TEST(ProfilerTest, ProfLogInitWARNING)
{
    setenv("PROF_LOG_LEVEL", "WARNING", 1);
    ProfLogInit();
}

TEST(ProfilerTest, ProfLogInitERROR)
{
    setenv("PROF_LOG_LEVEL", "ERROR", 1);
    ProfLogInit();
}

TEST(ProfilerTest, ProfLogInitNONE)
{
    setenv("PROF_LOG_LEVEL", "NONE", 1);
    ProfLogInit();
}

TEST(ProfilerTest, ProfLogInitElse)
{
    setenv("PROF_LOG_LEVEL", "DEFAULT", 1);
    ProfLogInit();
    setenv("PROF_LOG_LEVEL", "INFO", 1);
}

TEST(ProfilerTest, ProfLogGetLevel)
{
    ProfLogGetLevel();
}

TEST(ProfilerTest, ProfLogSetLevel)
{
    ProfLogSetLevel(ProfLogLevel::PROF_LOG_INFO);
}
