/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#include <gtest/gtest.h>
#include <gmock/gmock.h>
#include <string>
#include <string>
#include <set>

#include "msServiceProfiler/Utils.h"

using namespace ::testing;
using namespace MsUtils;

TEST(ServiceProfilerUtilsTest, SplitStrSuccess)
{
    std::string input = "Hello World";
    char splitChar = ' ';
    auto result = MsUtils::SplitStr(input, splitChar);
    EXPECT_EQ(result.first, "Hello");
    EXPECT_EQ(result.second, "World");
}

TEST(ServiceProfilerUtilsTest, SplitStrWithNoSplitChar) {
    std::string input = "HelloWorld";
    char splitChar = ' ';
    auto result = MsUtils::SplitStr(input, splitChar);
    EXPECT_EQ(result.first, "HelloWorld");
    EXPECT_EQ(result.second, "");
}

TEST(ServiceProfilerUtilsTest, SplitStrToSetSuccess)
{
    std::set<std::string> filterSet;
    const char *name = "example1;example2;example3";
    char splitSymbol = ';';
    auto result = SplitStringToSet(name, splitSymbol);
    EXPECT_EQ(result.size(), 3);
    EXPECT_NE(result.find("example1"), result.end());
    EXPECT_NE(result.find("example2"), result.end());
    EXPECT_NE(result.find("example3"), result.end());
}

TEST(ServiceProfilerUtilsTest, SplitStrToSetSuccessWithEmptySubstrings)
{
    std::set<std::string> filterSet;
    const char *name = "example1;example2;;example3;";
    char splitSymbol = ';';
    auto result = SplitStringToSet(name, splitSymbol);
    EXPECT_EQ(result.size(), 3);
    EXPECT_NE(result.find("example1"), result.end());
    EXPECT_NE(result.find("example2"), result.end());
    EXPECT_NE(result.find("example3"), result.end());
}

TEST(ServiceProfilerUtilsTest, SplitStrToSetSuccessWithOneSubstring)
{
    std::set<std::string> filterSet;
    const char *name = "example";
    char splitSymbol = ';';
    auto result = SplitStringToSet(name, splitSymbol);
    EXPECT_EQ(result.size(), 1);
    EXPECT_NE(result.find("example"), result.end());
}

