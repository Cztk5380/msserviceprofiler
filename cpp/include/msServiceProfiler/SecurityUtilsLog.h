// Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
#ifndef __MS_SECURITY_LOG_H__
#define __MS_SECURITY_LOG_H__

#include <type_traits>
#include <string>
#include <unordered_map>
#include <vector>
#include "securec.h"

namespace SecurityUtils {
constexpr int MAX_PRINT = 1000;
std::string ToSafeString(const std::string &str);
const std::unordered_map<std::string, std::string>& GetInvalidChar(void);

enum class LogLv {
    DEBUG = 0,
    INFO,
    WARN,
    ERROR,
    COUNT
};

inline bool operator<(LogLv a, LogLv b)
{
    using underlying = typename std::underlying_type<LogLv>::type;
    return static_cast<underlying>(a) < static_cast<underlying>(b);
}

class SecurityUtilsLog {
public:
    static SecurityUtilsLog &GetLog(void);

    template<typename... Args>
    inline void Printf(std::string const &format, LogLv lv, Args &&... args) const;
    void SetLogLevelByEnvVar();

private:
    SecurityUtilsLog(void) = default;
    ~SecurityUtilsLog(void) = default;
    SecurityUtilsLog(SecurityUtilsLog const &) = delete;
    SecurityUtilsLog &operator=(SecurityUtilsLog const &) = delete;
    std::string AddPrefixInfo(std::string const &format, LogLv lv) const;

private:
    LogLv lv_ { LogLv::INFO };
    FILE *fp_ { stdout };
};

template <typename... Args>
void SecurityUtilsLog::Printf(const std::string &format, LogLv lv, Args &&...args) const
{
    if (fp_ == nullptr) {
        return;
    }
    if (lv < lv_) {
        return;
    }
    std::string f = AddPrefixInfo(format, lv).append("\n");

    char msg[MAX_PRINT] = {0};
    auto res = snprintf_s(msg, MAX_PRINT, MAX_PRINT - 1, f.c_str(), std::forward<Args>(args)...);
    if (res >= 0) {
        fprintf(fp_, "%s", msg);
        return;
    }
    std::string lengthLimit = "Log length reach limit,only show part message";
    lengthLimit = AddPrefixInfo(lengthLimit, lv).append("\n");
    fprintf(fp_, "%s", lengthLimit.c_str());
    fprintf(fp_, "%s \n", msg);
}

template <typename... Args>
inline void LogDebug(std::string const &format, Args &&...args)
{
    SecurityUtilsLog::GetLog().Printf(ToSafeString(format), LogLv::DEBUG, std::forward<Args>(args)...);
}

template <typename... Args>
inline void LogInfo(std::string const &format, Args &&...args)
{
    SecurityUtilsLog::GetLog().Printf(ToSafeString(format), LogLv::INFO, std::forward<Args>(args)...);
}

template <typename... Args>
inline void LogWarn(std::string const &format, Args &&...args)
{
    SecurityUtilsLog::GetLog().Printf(ToSafeString(format), LogLv::WARN, std::forward<Args>(args)...);
}

template <typename... Args>
inline void LogError(std::string const &format, Args &&...args)
{
    SecurityUtilsLog::GetLog().Printf(ToSafeString(format), LogLv::ERROR, std::forward<Args>(args)...);
}

template <typename... Args>
inline void LogSummary(std::string const &format, Args &&...args)
{
    SecurityUtilsLog::GetLog().Printf(format, LogLv::INFO, std::forward<Args>(args)...);
}

inline void SetLogLevelByEnvVar()
{
    SecurityUtilsLog::GetLog().SetLogLevelByEnvVar();
}
} // namespace SecurityUtils

#endif  // __MS_SECURITY_LOG_H__
