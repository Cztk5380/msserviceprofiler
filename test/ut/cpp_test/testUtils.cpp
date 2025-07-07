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

namespace MsUtils {
bool IsNameMatch(std::set<std::string> &filterSet, const char *name);
}

TEST(ServiceProfilerUtilsTest, SplitStrSuccess)
{
    std::set<std::string> filterSet;
    const char *name = "example1;example2;;example3";
    char splitSymbol = ';';
    auto result = SplitStringToSet(name, splitSymbol);
    EXPECT_EQ(result.size(), 3);
    EXPECT_NE(result.find("apple"), result.end());
    EXPECT_NE(result.find("banana"), result.end());
    EXPECT_NE(result.find("cherry"), result.end());
}
