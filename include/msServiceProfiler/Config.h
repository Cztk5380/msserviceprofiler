/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */
#ifndef MS_SERVER_PROFILER_CONFIG_H
#define MS_SERVER_PROFILER_CONFIG_H

#include <string>
#include <nlohmann/json.hpp>
#include "ServiceProfilerInterface.h"

using Json = nlohmann::json;

namespace msServiceProfiler {
class Config {
public:
    Config();
    bool GetEnable() const { return enable_; }
    uint32_t GetLevel() const { return level_; }
    uint32_t GetEnableAclTaskTime() const { return enableAclTaskTime_; }
    const std::string& GetProfPath() const { return profPath_; }
    const std::string& GetConfigPath() const { return configPath_; }
    const std::string& GetProfPathDateTail() const { return profPathDateTail_; }
    bool GetHostCpuUsage() const { return hostCpuUsage_; }
    bool GetHostMemoryUsage() const { return hostMemoryUsage_; }
    bool GetHostFreq() const { return hostFreq_; }
    const std::set<std::string>& GetValidDomain() const { return validDomain_; }
    bool GetEnableDomainFilter() const { return enableDomainFilter_; }

    bool GetNpuMemoryUsage() const { return npuMemoryUsage_; }
    bool GetNpuMemoryFreq() const { return npuMemoryFreq_; }
    uint32_t GetNpuMemorySleepMilliseconds() const { return npuMemorySleepMilliseconds_; }

    void SetEnable(bool enable) { enable_ = enable; }
    void SetProfPathDateTail(std::string profPathDateTail) { profPathDateTail_ = profPathDateTail; }
    void SetConfigPath(std::string configPath) { configPath_ = configPath; }

    Json ReadConfigFile();
    void ParseConfig(const Json& configJson);
    void InitProfPathDateTail(bool forceReinit = false);
    bool PrepareConfigAndPath(std::string& configPath);
    void SaveConfigToJsonFile();
private:
    void ReadConfigPath();
    void ParseEnable(const Json& config);
    void ParseAclTaskTime(const Json& config);
    std::string getDefaultProfPath();
    std::string getDirPath(std::string configPath);
    void ParseProfPath(const Json& config);
    void ParseLevel(const Json& config);
    bool ParseCollectConfig(const Json& config);
    bool ParseHostConfig(const Json& config);
    bool ParseNpuConfig(const Json& config);
    std::string TrimWhitespace(const std::string& str);
    std::vector<std::string> SplitAndTrimString(const std::string& str, char delimiter);
    void LogDomainInfo() const;
    void ParseDomain(const Json& config);

    bool enable_ = false;
    uint32_t level_ = Level::INFO;
    bool enableAclTaskTime_ = false;
    std::string configPath_;
    std::string profPathDateTail_;
    std::string profPath_;
    bool enableDomainFilter_ = false;
    std::set<std::string> validDomain_;

    bool hostCpuUsage_ = false;
    bool hostMemoryUsage_ = false;
    uint32_t hostFreq_ = 10;
    uint32_t hostFreqMin_ = 1;
    uint32_t hostFreqMax_ = 50;

    bool npuMemoryUsage_ = false;
    uint32_t npuMemoryFreq_ = 1;
    uint32_t npuMemoryFreqMin_ = 1;
    uint32_t npuMemoryFreqMax_ = 50;
    uint32_t npuMemorySleepMilliseconds_ = 1000;
};
}
#endif
