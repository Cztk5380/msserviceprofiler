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

#ifndef MS_UTILS_H
#define MS_UTILS_H

#include <string>
#include <set>
#include <sys/stat.h>
#include <functional>
#include <vector>

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

inline std::vector<std::string> SplitStrToVector(const std::string &str, char splitSymbol, bool allowEmpty = false)
{
    std::vector<std::string> result;
    std::string token;

    for (char c : str) {
        if (c == splitSymbol) {
            if (!token.empty() || allowEmpty) {  // 非空子串才插入
                result.push_back(token);
                token.clear();  // 清空临时 token
            }
        } else {
            token += c;  // 累积字符到临时 token
        }
    }

    // 处理最后一个子串（如果末尾没有分号）
    if (!token.empty()) {
        result.push_back(token);
    }

    return result;
};

// 分割字符串并存入set 输入字符串格式为"xxxx;xxx;xxx"或"xxx;xxx;"均可
inline std::set<std::string> SplitStringToSet(const std::string &str, char splitSymbol)
{
    std::vector<std::string> vec = SplitStrToVector(str, splitSymbol);
    return std::set<std::string>(vec.begin(), vec.end());
};

inline std::string GetEnvAsString(const std::string &envName)
{
    const char *value = getenv(envName.c_str());
    return std::string((value != nullptr) ? value : "");
};

inline unsigned long Str2Uint(const std::string &str)
{
    // 该函数仅将字符串转为数值，不会校验字符串，即使有问题的字符串，也会转为数值。
    char *endPtr;
    return std::strtoul(str.c_str(), &endPtr, STRING_TO_UINT_BASE);
};

class FailAutoFree {
public:
    void AddFreeFunction(std::function<void()> &&freeFunc, const char *freeMsg)
    {
        freeFuncArray.push_back(std::make_pair<std::function<void()>, std::string>(std::move(freeFunc), freeMsg));
    };

    void SetSuccess()
    {
        failed = false;
    };

    ~FailAutoFree();

private:
    bool failed = true;
    std::vector<std::pair<std::function<void()>, std::string>> freeFuncArray;
};

uint32_t GetTid();
bool MakeDirs(const std::string &dirPath);
uint64_t GetCurrentTimeInNanoseconds();
const std::string &GetHostName();

class UmaskGuard {
public:
    static constexpr mode_t RESTRICTIVE_UMASK = 0137;   // 权限最大为 640
    explicit UmaskGuard(mode_t newUmask = RESTRICTIVE_UMASK): originalUmask_(umask(newUmask))
    {
    };
    
    ~UmaskGuard()
    {
        umask(originalUmask_);
    };
private:
    mode_t originalUmask_;
};

};  // namespace MsUtils

#endif  // MS_UTILS_H