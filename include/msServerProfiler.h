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

#include "msServerProfilerMarker.h"

constexpr int MAX_RES_STR_IZE = 128;

namespace msServerProfiler {

enum class ResType : uint8_t { STRING = '\0', UINT64 };

union ResIdValue {
    uint64_t rid;
    char strRid[MAX_RES_STR_IZE];
};

struct ResID {
    ResIdValue resValue;
    ResType type;

    static const ResID ILLEGAL_RES;

    ResID(int rid) noexcept : type(ResType::UINT64)  {
        resValue.rid = static_cast<uint64_t>(rid);
    }

    ResID(uint32_t rid) noexcept : type(ResType::UINT64) {
        resValue.rid = static_cast<uint64_t>(rid);
    }

    ResID(uint64_t rid) noexcept : type(ResType::UINT64) {
        resValue.rid = static_cast<uint64_t>(rid);
    }

    ResID(const char *strRid) noexcept : type(ResType::STRING) {
        for (size_t i = 0; i < MAX_RES_STR_IZE; i++) {
            resValue.strRid[i] = strRid[i];
            if (strRid[i] == '\0') {
                break;
            }
        }
    }
    ResID(const std::string &strRid) noexcept : ResID(strRid.c_str()) {}

    bool IsIllegal() const {
        return resValue.rid == std::numeric_limits<uint64_t>::max() && type == ResType::UINT64;
    }
};

enum class MarkType : uint8_t { TYPE_EVENT = 0, TYPE_METRIC = 1, TYPE_SPAN = 2, TYPE_LINK = 3 };


template <typename TCollector, typename T>
class ArrayCollectorHelper {
  public:
    using AttrCollectCallback = void (*)(TCollector *pCollector,
                                         T pParam);
};

class CollectorHelper {
  public:
    template <typename T>
    inline void AddNumArrayAttr(const char *attrName, const T &startIter,
                                const T &endIter) {
        msg_.append("\"").append(attrName).append("\":[");
        for (T iter = startIter; iter != endIter; ++iter) {
            msg_.append(std::to_string(*iter)).append(",");
        }
        if (msg_.back() == ',') {
            msg_[msg_.size() - 1] = ']';
        } else {
            msg_.append("]");
        }
        msg_.append(",");
    }

    template <typename T>
    void AddArrayAttr(
        const char *attrName, const T &startIter, const T &endIter,
        typename ArrayCollectorHelper<CollectorHelper, T>::AttrCollectCallback callback) {

        msg_.append("\"").append(attrName).append("\":[");
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
    }

    inline void AddAttr(const char *attrName, const char *value) {
        msg_.append("\"").append(attrName).append("\":\"").append(value).append(
            "\",");
    }

    inline void AddAttr(const char *attrName, const std::string &value) {
        msg_.append("\"").append(attrName).append("\":\"").append(value).append(
            "\",");
    }

    inline void AddAttr(const char *attrName, const ResID &value) {
        if (value.type == ResType::UINT64) {
            return AddAttr(attrName, value.resValue.rid);
        } else {
            return AddAttr(attrName, value.resValue.strRid);
        }
    }

    template <typename T>
    inline void AddAttr(const char *attrName, const T value) {
        msg_.append("\"")
            .append(attrName)
            .append("\":")
            .append(std::to_string(value))
            .append(",");
    }

    std::string &GetMsg() { return msg_; }

  private:
    std::string msg_;
};

template <Level level=Level::INFO>
class ProfilerBase {
  public:
    inline bool IsEnable(Level msgLevel=level) { 
        return ServerProfilerManager::GetInstance().IsEnable(msgLevel);
    };

    template <Level levelAttr=level, typename T>
    inline ProfilerBase &AddNumArrayAttr(const char *attrName,
                                         const T &startIter, const T &endIter) {
        if (IsEnable(levelAttr)) {
            collector_.AddNumArrayAttr(attrName, startIter, endIter);
        }
        return *this;
    }

    template <Level levelAttr=level, typename T>
    ProfilerBase &AddArrayAttr(
        const char *attrName, const T &startIter, const T &endIter,
        typename ArrayCollectorHelper<CollectorHelper, T>::AttrCollectCallback callback) {
        if (IsEnable(levelAttr)) {
            collector_.AddArrayAttr(attrName, startIter, endIter, callback);
        }
        return *this;
    }

    template <Level levelAttr=level>
    inline ProfilerBase &AddAttr(const char *attrName, const char *value) {
        if (IsEnable(levelAttr)) {
            collector_.AddAttr(attrName, value);
        }
        return *this;
    }

    template <Level levelAttr=level>
    inline ProfilerBase &AddAttr(const char *attrName,
                                 const std::string &value) {
        if (IsEnable(levelAttr)) {
            collector_.AddAttr(attrName, value);
        }
        return *this;
    }

    template <Level levelAttr=level>
    inline ProfilerBase &AddAttr(const char *attrName, const ResID &value) {
        if (IsEnable(levelAttr)) {
            collector_.AddAttr(attrName, value);
        }
        return *this;
    }

    template <Level levelAttr=level, typename T>
    inline ProfilerBase &AddAttr(const char *attrName, const T value) {
        if (IsEnable(levelAttr)) {
            collector_.AddAttr(attrName, value);
        }
        return *this;
    }

    std::string &GetMsg() { 
        return collector_.GetMsg(); 
    }

  private:
    CollectorHelper collector_;
};

template <Level level = Level::INFO>
class Span : public ProfilerBase<level> {
  public:
    Span(const char *spanName, const ResID &rid, bool autoStart = true,
         bool autoEnd = true)
        : autoEnd_(autoEnd) {
        if (!this->IsEnable(level)) {
            return;
        }
        if (autoStart) {
            Start();
        }
        this->AddAttr("name", spanName);
        this->AddAttr("type", static_cast<uint8_t>(MarkType::TYPE_SPAN));
        if (!rid.IsIllegal()) {
            this->AddAttr("rid", rid);
        }
    }
    ~Span() {
        if (this->IsEnable(level) && autoEnd_) {
            End();
        }
    }
    void Start() {
        if (this->IsEnable(level)) {
            spanHandle_ = StartSpan();
        }
    }
    void End() {
        if (this->IsEnable(level)) {
            MarkSpanAttr(this->GetMsg().c_str(), spanHandle_);
            EndSpan(spanHandle_);
            autoEnd_ = false;
        }
    }

  private:
    bool autoEnd_ = true;
    SpanHandle spanHandle_ = 0;
};

template <Level level = Level::INFO>
class Metric : public ProfilerBase<level> {
  public:
    Metric(const char *metricName, const ResID &rid) {
        if (!this->IsEnable(level)) {
            return;
        }
        this->AddAttr("name", metricName);
        this->AddAttr("type", static_cast<uint8_t>(MarkType::TYPE_METRIC));
        if (!rid.IsIllegal()) {
            this->AddAttr("rid", rid);
        }
    }

    template <typename T>
    void Mark(T value) {
        if (this->IsEnable(level)) {
            this->AddAttr("value", value);
            MarkEvent(this->GetMsg().c_str());
        }
    }

    template <typename T>
    static void AddMetric(const char *metricName, const ResID &rid, T value) {
        Metric(metricName, rid).Mark(value);
    }
};

template <Level level = Level::INFO>
class Event : public ProfilerBase<level> {
  public:
    Event(const char *eventName, const ResID &rid) {
        if (!this->IsEnable(level)) {
            return;
        }
        this->AddAttr("name", eventName);
        this->AddAttr("type", static_cast<uint8_t>(MarkType::TYPE_EVENT));
        if (!rid.IsIllegal()) {
            this->AddAttr("rid", rid);
        }
    }

    void Mark() {
        if (this->IsEnable(level)) {
            MarkEvent(this->GetMsg().c_str());
        }
    }

    static void AddEvent(const char *eventName, const ResID &rid) {
        Event(eventName, rid).Mark();
    }
};

template <Level level = Level::INFO>
class ResLink : public ProfilerBase<level> {
  public:
    void Mark(const ResID &fromRid, const ResID &toRid) {
        if (this->IsEnable(level)) {
            this->AddAttr("type", static_cast<uint8_t>(MarkType::TYPE_LINK));
            this->AddAttr("from", fromRid);
            this->AddAttr("to", toRid);
            MarkEvent(this->GetMsg().c_str());
        }
    }

    static void AddLink(const ResID &fromRid, const ResID &toRid) {
        ResLink().Mark(fromRid, toRid);
    }
};

} // namespace msServerProfiler

#endif