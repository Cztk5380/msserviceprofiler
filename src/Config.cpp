/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */
#include <climits>
#include <fstream>
#include <unistd.h>

#include "securec.h"
#include "msServiceProfiler/Log.h"
#include "msServiceProfiler/Config.h"

namespace msServiceProfiler {
constexpr int MILLISECONDS_IN_SECOND = 1000;
Config::Config()
{
    ReadConfigPath();
    InitProfPathDateTail();
    auto configJson = ReadConfigFile();
    ParseConfig(configJson);
    SaveConfigToJsonFile();
}

void Config::ReadConfigPath()
{
    configPath_ = getenv("SERVICE_PROF_CONFIG_PATH") ? getenv("SERVICE_PROF_CONFIG_PATH") : "";
    if (!configPath_.empty() && access(configPath_.c_str(), F_OK) != 0) {
        configPath_ = "";
    }
}

Json Config::ReadConfigFile()
{
    Json jsonData;
    if (configPath_.empty()) {
        return jsonData;
    }
    if (access(configPath_.c_str(), F_OK) != 0) {
        LOG_ONCE_E("SERVICE_PROF_CONFIG_PATH : %s is not file or Permission Denied",
            configPath_.c_str());  // LCOV_EXCL_LINE
        return jsonData;
    } else {
        LOG_ONCE_D("SERVICE_PROF_CONFIG_PATH : %s", configPath_.c_str());
    }

    std::ifstream configFile; // 单独创建 std::ifstream 对象

    char realConfigPath[PATH_MAX] = {0};
    if (realpath(configPath_.c_str(), realConfigPath) == nullptr) {
        LOG_ONCE_E("Failed to get real path of: %s", configPath_.c_str());  // LCOV_EXCL_LINE
        return jsonData;
    }
    configPath_ = realConfigPath;

    try {
        configFile.open(configPath_);
        if (!configFile.good()) {
            LOG_ONCE_E("Fail to open: %s", configPath_.c_str());  // LCOV_EXCL_LINE
            return jsonData;
        }
    } catch (const std::exception &e) {
        LOG_ONCE_E("Fail to open config file: %s, error: %s",
            configPath_.c_str(), e.what());  // LCOV_EXCL_LINE
        return jsonData;
    }

    try {
        configFile >> jsonData; // 尝试解析 JSON 数据
    } catch (const std::exception &e) {
        PROF_LOGE("Fail to parse file content as json object, config path: %s, error: %s",
                  configPath_.c_str(), e.what());  // LCOV_EXCL_LINE
        configFile.close(); // 确保文件关闭
        return jsonData;
    }

    configFile.close(); // 成功解析后关闭文件
    if (jsonData.empty()) {
        PROF_LOGE("Parsed json object is empty, config path: %s", configPath_.c_str());  // LCOV_EXCL_LINE
        return jsonData;
    }
    return jsonData;
}


void Config::ParseConfig(const Json& configJson)
{
    ParseEnable(configJson);
    ParseAclTaskTime(configJson);
    ParseProfPath(configJson);
    ParseLevel(configJson);
    ParseDomain(configJson);
    ParseCollectConfig(configJson);
}

void Config::ParseEnable(const Json& config)
{
    enable_ = false;  // Default to false
    if (config.contains("enable")) {
        if (config["enable"].is_number_integer()) {
            enable_ = config["enable"] == 1;
        } else {
            PROF_LOGW("enable value is not an integer, will set false.");  // LCOV_EXCL_LINE
        }
    }
    PROF_LOGI("profile enable_: %s", enable_ ? "true" : "false");  // LCOV_EXCL_LINE
}

std::string Config::getDefaultProfPath()
{
    std::string profPath;
    std::string homePath = getenv("HOME") ? getenv("HOME") : "";
    profPath.append(homePath).append("/.ms_server_profiler/");
    return profPath;
}

std::string Config::getDirPath(std::string configPath)
{
    std::string dirPath;
    size_t lastSlash = configPath.find_last_of("/\\");
    if (lastSlash != std::string::npos) {
        dirPath = configPath.substr(0, lastSlash);
    } else {
        dirPath = ".";
    }
    return dirPath;
}

void Config::ParseProfPath(const Json& config)
{
    if (config.contains("prof_dir")) {
        profPath_ = config["prof_dir"];
        if (profPath_.back() != '/') {
            profPath_.append("/");
        }
    } else {
        profPath_ = getDefaultProfPath();
    }

    profPath_.append(profPathDateTail_);
}

void Config::ParseAclTaskTime(const Json &config)
{
    enableAclTaskTime_ = false;  // Default to false
    if (config.contains("acl_task_time")) {
        if (config["acl_task_time"].is_number_integer()) {
            enableAclTaskTime_ = config["acl_task_time"] == 1;
        } else {
            PROF_LOGW("Unknown acl_task_time type. acl_task_time disabled.");  // LCOV_EXCL_LINE
        }
    }
    PROF_LOGI("profile enableAclTaskTime_: %s", enableAclTaskTime_ ? "true" : "false");  // LCOV_EXCL_LINE
}

void Config::ParseLevel(const Json &config)
{
    level_ = Level::INFO;
    static const std::map<std::string, Level> ENUM_MAP = {
        {"ERROR",    Level::ERROR},
        {"INFO",     Level::INFO},
        {"DETAILED", Level::DETAILED},
        {"VERBOSE",  Level::VERBOSE},
    };

    if (config.contains("profiler_level")) {
        const auto profilerLevel = config["profiler_level"];
        if (profilerLevel.is_number_integer()) {
            int level = profilerLevel.get<int>();
            if (level >= 0) {
                level_ = static_cast<uint32_t>(level);
            }
        } else if (profilerLevel.is_string()) {
            std::string valueUpper = profilerLevel;
            std::transform(valueUpper.begin(), valueUpper.end(), valueUpper.begin(), [](char const &c) {
                return std::toupper(c);
            });
            if (ENUM_MAP.find(valueUpper) != ENUM_MAP.end()) {
                level_ = ENUM_MAP.at(valueUpper);
            } else {
                PROF_LOGW("Unknown profiler_level. Use the default profiler level.");  // LCOV_EXCL_LINE
            }
        }
    }
    PROF_LOGD("profiler_level: %u", level_);
}

std::string Config::TrimWhitespace(const std::string& str)
{
    std::string result = str;
    result.erase(0, result.find_first_not_of(" \t\n\r\f\v"));
    result.erase(result.find_last_not_of(" \t\n\r\f\v") + 1);
    return result;
}

std::vector<std::string> Config::SplitAndTrimString(const std::string& str, char delimiter)
{
    std::vector<std::string> tokens;
    size_t start = 0;
    size_t end = str.find(delimiter);
    while (end != std::string::npos) {
        std::string token = str.substr(start, end - start);
        token = TrimWhitespace(token);
        if (!token.empty()) {
            tokens.push_back(token);
        }
        start = end + 1;
        end = str.find(delimiter, start);
    }
    // Process last token
    std::string lastToken = str.substr(start);
    lastToken = TrimWhitespace(lastToken);
    if (!lastToken.empty()) {
        tokens.push_back(lastToken);
    }
    return tokens;
}

void Config::LogDomainInfo() const
{
    PROF_LOGI("profile enableDomainFilter_: %s", enableDomainFilter_ ? "true" : "false");
    std::string combined;
    for (const auto& domain : validDomain_) {
        if (!combined.empty()) {
            combined += ", ";
        }
        combined += domain;
    }
    if (!combined.empty()) {
        PROF_LOGI("profiler validDomain_: %s", combined.c_str());
    }
}

void Config::ParseDomain(const Json& config)
{
    enableDomainFilter_ = false;
    validDomain_.clear();
    
    if (!config.contains("domain")) {
        LogDomainInfo();
        return;
    }
    if (!config["domain"].is_string()) {
        PROF_LOGW("Invalid 'domain' format, expected string. Domain filter will be disabled.");
        LogDomainInfo();
        return;
    }
    std::string domainStr = config["domain"];
    std::vector<std::string> domains = SplitAndTrimString(domainStr, ';');
    for (const auto& domain : domains) {
        if (!domain.empty()) {
            validDomain_.insert(domain);
            enableDomainFilter_ = true;
        }
    }
    LogDomainInfo();
}

void Config::InitProfPathDateTail(bool forceReinit)
{
    const size_t tailMaxSize = 32; // 目录的最大大小

    if (profPathDateTail_.empty() || forceReinit) {
        time_t now = time(nullptr);
        auto ltm = std::localtime(&now);
        char pStrDateTail[tailMaxSize + 1] = {0};  // 多申请一点，保证安全
        int ret = sprintf_s(pStrDateTail, tailMaxSize, "%02d%02d-%02d%02d/",
                            ltm->tm_mon + 1, ltm->tm_mday, ltm->tm_hour, ltm->tm_min);
        if (ret == -1) {
            PROF_LOGW("ProfPathDateTail init failed.");  // LCOV_EXCL_LINE
        }
        profPathDateTail_ = pStrDateTail;
    }
}

bool Config::ParseCollectConfig(const Json &config)
{
    bool retHost = ParseHostConfig(config);
    bool retNpu = ParseNpuConfig(config);
    return retHost && retNpu;
}

bool Config::ParseHostConfig(const Json &config)
{
    bool ret = true;
    if (config.contains("host_system_usage_freq") && config["host_system_usage_freq"] != -1) {
        try {
            uint32_t hostFreq = config["host_system_usage_freq"];
            if (hostFreq >= hostFreqMin_ && hostFreq <= hostFreqMax_) {
                hostFreq_ = hostFreq;
                hostCpuUsage_ = true;
                hostMemoryUsage_ = true;
            } else {
                LOG_ONCE_E(
                    "host_system_usage_freq must be between %u and %u, "
                    "will not collect host cpu or host memory usage.",
                    hostFreqMin_,
                    hostFreqMax_);  // LCOV_EXCL_LINE
                hostCpuUsage_ = false;
                hostMemoryUsage_ = false;
                ret = false;
            }
        } catch (const std::exception &e) {
            LOG_ONCE_E("fail to convert host_system_usage_freq config to uint,"
                      "will not collect host cpu or host memory usage.");  // LCOV_EXCL_LINE
            hostCpuUsage_ = false;
            hostMemoryUsage_ = false;
            ret = false;
        }
    } else {
        ret = false;
    }
    PROF_LOGD("host_system_usage_freq %s", ret ? "Enabled" : "Disabled");
    return ret;
}

bool Config::ParseNpuConfig(const Json &config)
{
    bool ret = true;
    if (config.contains("npu_memory_usage_freq") && config["npu_memory_usage_freq"] != -1) {
        try {
            uint32_t npuMemoryFreq = config["npu_memory_usage_freq"];
            if (npuMemoryFreq >= npuMemoryFreqMin_ && npuMemoryFreq <= npuMemoryFreqMax_) {
                npuMemoryFreq_ = npuMemoryFreq;
                npuMemoryUsage_ = true;
            } else {
                LOG_ONCE_E(
                    "npu_memory_usage_freq must be between %u and %u, will not collect npu memory usage.",
                    npuMemoryFreqMin_, npuMemoryFreqMax_);  // LCOV_EXCL_LINE
                npuMemoryUsage_ = false;
                ret = false;
            }
        } catch (const std::exception &e) {
            LOG_ONCE_E(
                "Fail to convert npu_memory_usage_freq config to uint, "
                "will not collect npu memory usage.");  // LCOV_EXCL_LINE
            npuMemoryUsage_ = false;
            ret = false;
        }
        npuMemorySleepMilliseconds_ = static_cast<uint32_t>(std::round(MILLISECONDS_IN_SECOND / npuMemoryFreq_));
    } else {
        ret = false;
    }
    PROF_LOGD("npu_memory_usage_freq %s", ret ? "Enabled" : "Disabled");
    return ret;
}

bool Config::PrepareConfigAndPath(std::string& configPath)
{
    const int jsonSuffixSize = 5;
    if (configPath.empty()) {
        PROF_LOGW("Cannot save config to JSON file - no config path specified");
        return false;
    }
    
    if (configPath.size() < jsonSuffixSize ||
        configPath.substr(configPath.size() - jsonSuffixSize) != ".json") {
        PROF_LOGW("Config path must end with .json: %s", configPath.c_str());
        return false;
    }

    if (access(configPath.c_str(), F_OK) == 0) {
        return false;
    }
    std::string dirPath = getDirPath(configPath);
    if (access(dirPath.c_str(), W_OK) != 0) {
        return false;
    }
    
    return true;
}

void Config::SaveConfigToJsonFile()
{
    const int jsonIndentSize = 4;
    std::string configPath = getenv("SERVICE_PROF_CONFIG_PATH") ? getenv("SERVICE_PROF_CONFIG_PATH") : "";
    if (!PrepareConfigAndPath(configPath)) {
        return;
    }
    std::string profPath = getDefaultProfPath();
    nlohmann::ordered_json configData = {
        {"enable", enable_ ? 1 : 0},
        {"prof_dir", profPath},
        {"profiler_level", "INFO"},
        {"host_system_usage_freq", -1},
        {"npu_memory_usage_freq", -1},
        {"acl_task_time", enableAclTaskTime_ ? 1 : 0},
        {"domain", ""},
    };
    try {
        std::string dirPath = getDirPath(configPath);
        char tempFile[] = "temp_XXXXXX";
        const int fd = mkstemp(tempFile);
        if (fd == -1) {
            PROF_LOGW("mkstemp failed: %s", strerror(errno));
            return;
        }
        close(fd);
        std::string tempPath = dirPath+"/"+tempFile;
        PROF_LOGD("file generation in the path %s", tempPath.c_str());
        std::ofstream outputFile(tempPath);
        if (!outputFile.is_open()) {
            PROF_LOGW("Automatic config file generation failed %s", tempPath.c_str());
            return;
        }
        outputFile << configData.dump(jsonIndentSize);
        outputFile.close();
        
        auto ret = rename(tempPath.c_str(), configPath.c_str());
        if (ret != 0 && errno != ENOENT) {
            PROF_LOGW("Automatic config file generation failed: %s", strerror(errno));
            remove(tempPath.c_str());
            return;
        }
        PROF_LOGI("Successfully saved profiler configuration to: %s", configPath.c_str());
    } catch (const std::exception& e) {
        PROF_LOGE("Failed to save config to JSON file: %s", e.what());
    }
}
}
