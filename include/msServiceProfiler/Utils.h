// Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.

#ifndef MS_UTILS_H
#define MS_UTILS_H

#include <string>
#include <set>

namespace MsUtils {
constexpr int STRING_TO_UINT_BASE = 10;

inline std::pair<std::string, std::string> SplitStr(const std::string &str, char splitChar)
{
    auto start = str.find_first_of(splitChar);
    if (start == std::string::npos) {
        return {str, ""};
    } else {
        return {str.substr(0, start), str.substr(start + 1)};
    }
};

// 分割字符串并存入set 输入字符串格式为"xxxx;xxx;xxx"或"xxx;xxx;"均可
inline std::set<std::string> SplitStringToSet(const std::string &str, char splitSymbol)
{
    std::set<std::string> result;
    std::string token;

    for (char c : str) {
        if (c == splitSymbol) {
            if (!token.empty()) {  // 非空子串才插入
                result.insert(token);
                token.clear();  // 清空临时 token
            }
        } else {
            token += c;  // 累积字符到临时 token
        }
    }

    // 处理最后一个子串（如果末尾没有分号）
    if (!token.empty()) {
        result.insert(token);
    }

    return result;
};

inline unsigned long Str2Uint(const std::string &str)
{
    // 该函数仅将字符串转为数值，不会校验字符串，即使有问题的字符串，也会转为数值。
    char *endPtr;
    return std::strtoul(str.c_str(), &endPtr, STRING_TO_UINT_BASE);
};

uint32_t GetTid();
bool MakeDirs(const std::string &dirPath);
uint64_t GetCurrentTimeInNanoseconds();
const std::string &GetHostName();

};  // namespace MsUtils

#endif  // MS_UTILS_H