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
    void ReadAndSaveConfig();
    MS_SERVICE_INLINE_FLAG bool GetEnable() const { return enable_; }
    MS_SERVICE_INLINE_FLAG uint32_t GetTimeLimit() const { return timeLimit_; }
    MS_SERVICE_INLINE_FLAG uint32_t GetLevel() const { return level_; }
    MS_SERVICE_INLINE_FLAG bool GetEnableAclTaskTime() const { return enableAclTaskTime_; }
    MS_SERVICE_INLINE_FLAG const std::string& GetProfPath() const { return profPath_; }
    MS_SERVICE_INLINE_FLAG const std::string& GetConfigPath() const { return configPath_; }
    MS_SERVICE_INLINE_FLAG const std::string& GetProfPathDateTail() const { return profPathDateTail_; }
    MS_SERVICE_INLINE_FLAG bool GetHostCpuUsage() const { return hostCpuUsage_; }
    MS_SERVICE_INLINE_FLAG bool GetHostMemoryUsage() const { return hostMemoryUsage_; }
    MS_SERVICE_INLINE_FLAG bool GetHostFreq() const { return hostFreq_; }
    MS_SERVICE_INLINE_FLAG const std::set<std::string>& GetValidDomain() const { return validDomain_; }
    MS_SERVICE_INLINE_FLAG bool GetEnableDomainFilter() const { return enableDomainFilter_; }
    MS_SERVICE_INLINE_FLAG bool IsAclProf() const {return enableAclTaskTime_ || hostCpuUsage_ || hostMemoryUsage_; }

    MS_SERVICE_INLINE_FLAG std::string GetAclTaskTimeLevel() const { return aclTaskTimeLevel_; }
    MS_SERVICE_INLINE_FLAG int GetAclTaskTimeDuration() const { return aclTaskTimeDuration_; }
    void SetAclTaskTimeDuration(int aclTaskTimeDuration){aclTaskTimeDuration_ = aclTaskTimeDuration;}
    MS_SERVICE_INLINE_FLAG bool GetNpuMemoryUsage() const { return npuMemoryUsage_; }
    MS_SERVICE_INLINE_FLAG bool GetNpuMemoryFreq() const { return npuMemoryFreq_; }
    MS_SERVICE_INLINE_FLAG uint32_t GetNpuMemorySleepMilliseconds() const { return npuMemorySleepMilliseconds_; }

    MS_SERVICE_INLINE_FLAG void SetEnable(bool enable) { enable_ = enable; }
    void SetFileEnable(bool enable);
    MS_SERVICE_INLINE_FLAG void SetTimeLimit(uint32_t timelimit) { timeLimit_ = timelimit; }
    void SetProfPathDateTail(std::string profPathDateTail) { profPathDateTail_ = profPathDateTail; }
    MS_SERVICE_INLINE_FLAG void SetConfigPath(std::string configPath) { configPath_ = configPath; }

    nlohmann::ordered_json ReadConfigFile();
    void ParseConfig(const Json& configJson);
    void InitProfPathDateTail(bool forceReinit = false);
    bool PrepareConfigAndPath(std::string& configPath) const;
    void SaveConfigToJsonFile() const;

    MS_SERVICE_INLINE_FLAG bool GetMsptiEnable() const { return msptiEnable_; }
    MS_SERVICE_INLINE_FLAG const std::string GetApiFilter() const { return apiFilter_; }
    MS_SERVICE_INLINE_FLAG const std::string GetKernelFilter() const { return kernelFilter_; }

private:
    std::string GetEnvAsString(const std::string& envName) const;
    void ReadConfigPath();
    void ParseEnable(const Json& config);
    void ParseTimeLimit(const Json& config);
    void ParseAclTaskTime(const Json& config);
    void CheckMsptiConflict();
    void CheckAclKernelConflict();
    std::string GetDefaultProfPath() const;
    std::string GetDirPath(std::string configPath) const;
    void ParseProfPath(const Json& config);
    void ParseLevel(const Json& config);
    bool ParseCollectConfig(const Json& config);
    bool ParseHostConfig(const Json& config);
    bool ParseNpuConfig(const Json& config);
    void ParseMspti(const Json& config);
    std::vector<std::string> SplitAndTrimString(const std::string& str, char delimiter) const;
    void LogDomainInfo() const;
    void ParseDomain(const Json& config);
    nlohmann::ordered_json GetConfigData() const;

    bool isServiceProfConfigPathSet = false;
    bool enable_ = false;
    uint32_t level_ = Level::INFO;
    uint32_t timeLimit_ = 0;
    bool enableAclTaskTime_ = false;
    int aclTaskTimeDuration_ = 0;
    std::string aclTaskTimeLevel_ = "L0";
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

    bool msptiEnable_ = false;

    std::string apiFilter_;
    std::string kernelFilter_;
};
}
#endif
