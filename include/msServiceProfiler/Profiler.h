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

#ifndef MS_SERVER_PROFILER_H
#define MS_SERVER_PROFILER_H

#include <iostream>
#include <string>
#include <vector>
#include <limits>
#include <cstdint>

#include "ServiceProfilerManager.h"

constexpr int MAX_RES_STR_IZE = 128;

namespace msServiceProfiler {

    enum class ResType : uint8_t { STRING = '\0', UINT64 };

    union ResIdValue {
        uint64_t rid;
        char strRid[MAX_RES_STR_IZE];
    };

    struct ResID {
        ResIdValue resValue;
        ResType type;

        static const ResID illegalResource ;

        ResID(int rid) noexcept : type(ResType::UINT64)
        {
            resValue.rid = static_cast<uint64_t>(rid);
        }

        ResID(uint32_t rid) noexcept : type(ResType::UINT64)
        {
            resValue.rid = static_cast<uint64_t>(rid);
        }

        ResID(uint64_t rid) noexcept : type(ResType::UINT64)
        {
            resValue.rid = static_cast<uint64_t>(rid);
        }

        ResID(const char *strRid) noexcept : type(ResType::STRING)
        {
            for (size_t i = 0; i < MAX_RES_STR_IZE; i++) {
                resValue.strRid[i] = strRid[i];
                if (strRid[i] == '\0') {
                    break;
                }
            }
        }

        ResID(const std::string &strRid) noexcept : ResID(strRid.c_str()) {}

        bool IsIllegal() const
        {
            return resValue.rid == std::numeric_limits<uint64_t>::max() && type == ResType::UINT64;
        }
    };

    enum class MarkType : uint8_t { TYPE_EVENT = 0, TYPE_METRIC = 1, TYPE_SPAN = 2, TYPE_LINK = 3 };

    template <typename TProfiler, typename T>
    class ArrayCollectorHelper {
    public:
        using AttrCollectCallback = void (*)(TProfiler *pCollector, T pParam);
    };

    template <Level level = Level::INFO>
    class Profiler {
    public:
        inline bool IsEnable(Level msgLevel = level)
        {
            return msServiceProfiler::ServiceProfilerManager::GetInstance().IsEnable(msgLevel);
        };

        template <Level levelAttr = level, typename T>
        inline Profiler &NumArrayAttr(const char *attrName, const T &startIter, const T &endIter)
        {
            if (!IsEnable(levelAttr)) {
                return *this;
            }
            msg_.append("^").append(attrName).append("^:[");
            for (T iter = startIter; iter != endIter; ++iter) {
                msg_.append(std::to_string(*iter)).append(",");
            }
            if (msg_.back() == ',') {
                msg_[msg_.size() - 1] = ']';
            } else {
                msg_.append("]");
            }
            msg_.append(",");
            return *this;
        }

        template <Level levelAttr = level, typename T>
        Profiler &ArrayAttr(const char *attrName, const T &startIter, const T &endIter,
                            typename ArrayCollectorHelper<Profiler<level>, T>::AttrCollectCallback callback)
        {
            if (!IsEnable(levelAttr)) {
                return *this;
            }

            msg_.append("^").append(attrName).append("^:[");
            for (T iter = startIter; iter != endIter; ++iter) {
                msg_.append("{");
                callback(this, iter);
                if (msg_.back() == ',') {
                    msg_[msg_.size() - 1] = '}';
                } else {
                    msg_.append("}");
                }
                msg_.append(",");
            }
            if (msg_.back() == ',') {
                msg_[msg_.size() - 1] = ']';
            } else {
                msg_.append("]");
            }
            msg_.append(",");
            return *this;
        }

        template <Level levelAttr = level>
        inline Profiler &Attr(const char *attrName, const char *value)
        {
            if (IsEnable(levelAttr)) {
                msg_.append("^").append(attrName).append("^:^").append(value).append("^,");
            }
            return *this;
        }

        template <Level levelAttr = level>
        inline Profiler &Attr(const char *attrName, const std::string &value)
        {
            if (IsEnable(levelAttr)) {
                msg_.append("^").append(attrName).append("^:^").append(value).append("^,");
            }
            return *this;
        }

        template <Level levelAttr = level>
        inline Profiler &Attr(const char *attrName, const ResID &value)
        {
            if (IsEnable(levelAttr)) {
                if (value.type == ResType::UINT64) {
                    return Attr(attrName, value.resValue.rid);
                } else {
                    return Attr(attrName, value.resValue.strRid);
                }
            }
            return *this;
        }

        template <Level levelAttr = level, typename T>
        inline Profiler &Attr(const char *attrName, const T value)
        {
            if (IsEnable(levelAttr)) {
                msg_.append("^").append(attrName).append("^:").append(std::to_string(value)).append(",");
            }
            return *this;
        }

        inline Profiler &Resource(const ResID &rid)
        {
            if (IsEnable(level)) {
                if (!rid.IsIllegal()) {
                    this->Attr("rid", rid);
                }
            }
            return *this;
        }

        template <typename T>
        inline Profiler &ArrayResource(const T &startIter, const T &endIter,
                                       typename ArrayCollectorHelper<Profiler<level>, T>::AttrCollectCallback callback)
        {
            return this->ArrayAttr("rid", startIter, endIter, callback);
        }

        inline Profiler &Domain(const char *domainName)
        {
            if (IsEnable(level)) {
                this->Attr("domain", domainName);
            }
            return *this;
        }

        std::string &GetMsg()
        {
            return msg_;
        }

    public:
        Profiler &SpanStart(const char *spanName, bool autoEnd = true)
        {
            if (IsEnable(level)) {
                this->Attr("name", spanName);
                this->Attr("type", static_cast<uint8_t>(MarkType::TYPE_SPAN));
                spanHandle_ = StartSpan();
                autoEnd_ = autoEnd;
            }
            return *this;
        }

        void SpanEnd()
        {
            if (this->IsEnable(level)) {
                MarkSpanAttr(this->GetMsg().c_str(), spanHandle_);
                EndSpan(spanHandle_);
                autoEnd_ = false;
            }
        }

        Profiler()
        {
        }

        Profiler(Profiler &obj):autoEnd_(obj.autoEnd_), spanHandle_(obj.spanHandle_), msg_(std::move(obj.msg_))
        {
            obj.autoEnd_ = false;
        }

        ~Profiler()
        {
            if (autoEnd_) {
                SpanEnd();
            }
        }

    public:
        template <typename T>
        inline Profiler &Metric(const char *metricName, T value)
        {
            if (this->IsEnable(level)) {
                msg_.append("^").append(metricName).append("=^:").append(std::to_string(value)).append(",");
            }
            return *this;
        }

        template <typename T>
        inline Profiler &MetricInc(const char *metricName, T value)
        {
            if (this->IsEnable(level)) {
                msg_.append("^").append(metricName).append("+^:").append(std::to_string(value)).append(",");
            }
            return *this;
        }

        template <typename T>
        inline Profiler &MetricScope(const char *scopeName, T value)
        {
            if (this->IsEnable(level)) {
                msg_.append("^scope#").append(scopeName).append("^:").append(std::to_string(value)).append(",");
            }
            return *this;
        }

        template <typename T>
        inline Profiler &MetricScopeAsReqID()
        {
            if (this->IsEnable(level)) {
                msg_.append("^scope#^:^req^,");
            }
            return *this;
        }

        template <typename T>
        inline Profiler &MetricScopeAsGlobal()
        {
            // default, do nothing
            return *this;
        }

        void Launch()
        {
            if (this->IsEnable(level)) {
                MarkEvent(this->GetMsg().c_str());
            }
        }

    public:
        void Event(const char *eventName)
        {
            if (this->IsEnable(level)) {
                this->Attr("name", eventName);
                this->Attr("type", static_cast<uint8_t>(MarkType::TYPE_EVENT));
                MarkEvent(this->GetMsg().c_str());
            }
        }

    public:
        void Link(const ResID &fromRid, const ResID &toRid)
        {
            if (this->IsEnable(level)) {
                this->Attr("type", static_cast<uint8_t>(MarkType::TYPE_LINK));
                this->Attr("from", fromRid);
                this->Attr("to", toRid);
                MarkEvent(this->GetMsg().c_str());
            }
        }

    private:
        std::string msg_;
        bool autoEnd_ = false;
        SpanHandle spanHandle_ = 0;
    };

}  // namespace msServiceProfiler

#endif
