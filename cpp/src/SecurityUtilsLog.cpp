// Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
#include <chrono>
#include <ctime>
#include <type_traits>
#include <map>

#include "msServiceProfiler/SecurityUtilsLog.h"

namespace SecurityUtils {

inline std::string ToString(LogLv lv)
{
    using underlying = typename std::underlying_type<LogLv>::type;
    constexpr char const *lvString[static_cast<underlying>(LogLv::COUNT)] = {
        "[DEBUG]",
        "[INFO] ",
        "[WARN] ",
        "[ERROR]"
    };
    return lv < LogLv::COUNT ? lvString[static_cast<underlying>(lv)] : "N";
}

SecurityUtilsLog &SecurityUtilsLog::GetLog(void)
{
    static SecurityUtilsLog instance;
    return instance;
}

std::string SecurityUtilsLog::AddPrefixInfo(std::string const &format, LogLv lv) const
{
    char buf[32] = "0";
    auto now = std::chrono::system_clock::now();
    std::time_t time = std::chrono::system_clock::to_time_t(now);
    struct tm temp;
    std::tm *tm = localtime_r(&time, &temp);
    if (tm != nullptr) {
        std::strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", tm);
    }
    return std::string(buf) + " " + ToString(lv) + " " + format;  // LCOV_EXCL_LINE
}

void SecurityUtilsLog::SetLogLevelByEnvVar()
{
    char *logLevel = secure_getenv("SECURITY_UTILS_LOG_LEVEL");
    if (logLevel == nullptr) {
        return;
    }
    std::map<std::string, LogLv> logLevelMap = {
        {"0", LogLv::DEBUG},
        {"1", LogLv::INFO},
        {"2", LogLv::WARN},
        {"3", LogLv::ERROR},
    };
    if (logLevelMap.count(logLevel) == 0) {
        LogWarn("Env SECURITY_UTILS_LOG_LEVEL can only be set 0,1,2,3 "  // LCOV_EXCL_LINE
            "[0-debug, 1-info, 2-warn, 3-error], use default 1 level.");
        return;
    }
    lv_ = logLevelMap[logLevel];
}

const std::unordered_map<std::string, std::string>& GetInvalidChar(void)
{
    static const std::unordered_map<std::string, std::string> INVALID_CHAR = {
        {"\n", "\\n"}, {"\f", "\\f"}, {"\r", "\\r"}, {"\b", "\\b"},
        {"\t", "\\t"}, {"\v", "\\v"}, {"\u007F", "\\u007F"}
    };
    return INVALID_CHAR;
}

// convert unsafe string to safe string
std::string ToSafeString(const std::string &str)
{
    std::string safeStr(str);
    const std::unordered_map<std::string, std::string> invalidChar = GetInvalidChar();
    size_t i = 0;
    while (i < safeStr.length()) {
        std::string chr(1, safeStr[i]);
        if (invalidChar.find(chr) != invalidChar.end()) {
            const std::string &validStr = invalidChar.at(chr);
            safeStr.replace(i, 1, validStr);
            i += validStr.length();
            continue;
        }
        i++;
    }
    return safeStr;
}

}  // SecurityUtils
