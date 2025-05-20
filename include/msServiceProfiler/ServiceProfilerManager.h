/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef MS_SERVER_PROFILER_MARKER_H
#define MS_SERVER_PROFILER_MARKER_H

#include <string>
#include <thread>

#include <nlohmann/json.hpp>

#include "ServiceProfilerInterface.h"
#include "Config.h"

#include "acl/acl.h"
#include "mspti/mspti.h"

using Json = nlohmann::json;

namespace msServiceProfiler {
    using AclprofConfig = struct aclprofConfig;
    class ServiceProfilerManager {
    public:
        ServiceProfilerManager(const ServiceProfilerManager &) = delete;
        ServiceProfilerManager& operator=(const ServiceProfilerManager &) = delete;

        static ServiceProfilerManager &GetInstance();

        inline bool IsEnable(uint32_t level) const
        {
            return config_->GetEnable() && config_->GetLevel() >= level;
        }

        void StartProfiler();

        void StopProfiler();

        void StopThread();

        static std::string ToSemName(const std::string &oriSemName);

        const std::string &GetConfigPath()
        {
            return config_->GetConfigPath();
        }

    private:
        ServiceProfilerManager();

        ~ServiceProfilerManager();

        void SetAclProfHostSysConfig() const;

        void DynamicControl();

        void LaunchThread();

        void ThreadFunction();

        void MarkFirstProcessAsMain();

        AclprofConfig* ProfCreateConfig();

    private:
        bool isMaster_ = true;
        bool started_ = false;
        bool isAclInit_ = false;
        void *configHandle_ = nullptr;
        int lastUpdate_ = 0;
        std::unique_ptr<Config> config_;

        std::thread thread_;

        msptiSubscriberHandle msptiHandle_;
        bool msptiEnabled = false;
    };
}  // namespace msServiceProfiler

#endif
