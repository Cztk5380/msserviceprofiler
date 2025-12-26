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
