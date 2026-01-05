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

#ifndef MS_SERVER_PROFILER_H
#define MS_SERVER_PROFILER_H

#include <iostream>
#include <string>
#include <vector>
#include <limits>
#include <cstdint>
#include <utility>

#include "ServiceProfilerInterface.h"

namespace msServiceProfiler {
    constexpr int MAX_RES_STR_IZE = 128;

    enum class ResType : uint8_t { STRING = '\0', UINT64 };

    union ResIdValue {
        uint64_t rid;
        char strRid[MAX_RES_STR_IZE];
    };

    struct ResID {
        ResIdValue resValue;
        ResType type;

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
            size_t i = 0;
            for (; i < MAX_RES_STR_IZE - 1 && strRid[i] != '\0'; ++i) {
                resValue.strRid[i] = strRid[i];
            }
            resValue.strRid[i] = '\0';   // 统一补终止符
        }

        ResID(const std::string &strRid) noexcept : ResID(strRid.c_str())
        {}

        bool IsIllegal() const
        {
            return resValue.rid == std::numeric_limits<uint64_t>::max() && type == ResType::UINT64;
        }

        static const ResID &IllegalResource()
        {
            static const ResID ILLEGAL_RESOURCE = ResID(std::numeric_limits<uint64_t>::max());
            return ILLEGAL_RESOURCE;
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
        /**
            * @brief 判断是否使能采集数据，当入参级别小于配置的级别时，返回true
            * @param msgLevel [in] 定义的采集等级，取值为INFO
            * @return true表示使能数据采集，false表示未使能
        */
        MS_SERVICE_PROFILER_HIDDEN inline bool IsEnable(Level msgLevel = level) const
        {
            if (!domainAllow_) {
                return false;
            }
            return msServiceProfilerCompatible::ServiceProfilerInterface::GetInstance().CallIsEnable(msgLevel);
        };

        /**
            * @brief 添加数组属性，数组中仅支持数值
            * @param attrName [in] 属性名
            * @param startIter [in] 迭代器开始
            * @param endIter [in] 迭代器结束
            * @return 返回Profiler&当前对象，支持链式调用
        */
        template <Level levelAttr = level, typename T>
        MS_SERVICE_PROFILER_HIDDEN inline Profiler &NumArrayAttr(const char *attrName, const T &startIter, const T &endIter)
        {
            if (!IsEnable(levelAttr)) {
                return *this;
            }
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
            return *this;
        }

        /**
            * @brief 通过回调函数自定义添加数组属性
            * @param attrName [in] 属性名
            * @param startIter [in] 任意的迭代器开始
            * @param endIter [in] 任意的迭代器结束
            * @param callback [in] 回调函数，其第一个入参是当前对象，可以调用它添加属性，
            *                     其第二个入参是当前迭代，可以用它获取需要记录的属性内容
            * @return 返回Profiler&当前对象，支持链式调用
        */
        template <Level levelAttr = level, typename T>
        MS_SERVICE_PROFILER_HIDDEN Profiler &ArrayAttr(const char *attrName, const T &startIter, const T &endIter,
            typename ArrayCollectorHelper<Profiler<level>, T>::AttrCollectCallback callback)
        {
            if (!IsEnable(levelAttr)) {
                return *this;
            }

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
            return *this;
        }

        /**
            * @brief 添加属性，返回当前对象，支持链式调用。在解析为trace数据之后，会显示在args中
            * @param attrName [in] 属性名
            * @param value [in] 属性值，字符串类型
            * @return 返回Profiler&当前对象，支持链式调用
        */
        template <Level levelAttr = level>
        MS_SERVICE_PROFILER_HIDDEN inline Profiler &Attr(const char *attrName, const char *value)
        {
            if (IsEnable(levelAttr)) {
                msg_.append("\"").append(attrName).append("\":\"").append(value).append("\",");
            }
            return *this;
        }

        /**
            * @brief 添加属性，返回当前对象，支持链式调用。在解析为trace数据之后，会显示在args中
            * @param attrName [in] 属性名
            * @param value [in] 属性值，字符串类型
            * @return 返回Profiler&当前对象，支持链式调用
        */
        template <Level levelAttr = level>
        MS_SERVICE_PROFILER_HIDDEN inline Profiler &Attr(const char *attrName, const std::string &value)
        {
            if (IsEnable(levelAttr)) {
                msg_.append("\"").append(attrName).append("\":\"").append(value).append("\",");
            }
            return *this;
        }

        /**
            * @brief 添加属性，返回当前对象，支持链式调用。在解析为trace数据之后，会显示在args中
            * @param attrName [in] 属性名
            * @param value [in] 属性值，ResID类型的编号，ResID可以由字符串或数值隐式转换
            * @return 返回Profiler&当前对象，支持链式调用
        */
        template <Level levelAttr = level>
        MS_SERVICE_PROFILER_HIDDEN inline Profiler &Attr(const char *attrName, const ResID &value)
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

        /**
            * @brief 添加属性，返回当前对象，支持链式调用。在解析为trace数据之后，会显示在args中
            * @param attrName [in] 属性名
            * @param value [in] 属性值，支持整型/浮点型等可转换为字符串的类型
            * @return 返回Profiler&当前对象，支持链式调用
        */
        template <Level levelAttr = level, typename T>
        MS_SERVICE_PROFILER_HIDDEN inline Profiler &Attr(const char *attrName, const T value)
        {
            if (IsEnable(levelAttr)) {
                msg_.append("\"").append(attrName).append("\":").append(std::to_string(value)).append(",");
            }
            return *this;
        }

        /**
            * @brief 添加资源ID，数据和timeline根据资源ID进行关联，一般是请求ID
            * @param rid [in] 请求id，可以由字符串或数值隐式转换
            * @return 返回当前Profiler&对象，支持链式调用
        */
        MS_SERVICE_PROFILER_HIDDEN inline Profiler &Resource(const ResID &rid)
        {
            if (IsEnable(level)) {
                if (!rid.IsIllegal()) {
                    this->Attr("rid", rid);
                }
            }
            return *this;
        }

        /**
            * @brief 添加数组类型资源的关键属性
            * @param startIter [in] 任意的迭代器开始
            * @param endIter [in] 任意的迭代器结束
            * @param callback [in] 元素属性提取回调函数
            * @return 返回当前Profiler&对象，支持链式调用
        */
        template <typename T>
        MS_SERVICE_PROFILER_HIDDEN inline Profiler &ArrayResource(const T &startIter, const T &endIter,
            typename ArrayCollectorHelper<Profiler<level>, T>::AttrCollectCallback callback)
        {
            return this->ArrayAttr("rid", startIter, endIter, callback);
        }

        /**
            * @brief 指定该数据的域，相同域的记录在trace数据中归为一类
            * @param domainName [in] 域名
            * @return 返回当前Profiler&对象，支持链式调用
        */
        MS_SERVICE_PROFILER_HIDDEN inline Profiler &Domain(const char *domainName)
        {
            if (!domainName) {
                domain_.clear();
                return *this;
            }

            domain_ = domainName;

            domainAllow_ = msServiceProfilerCompatible::ServiceProfilerInterface::GetInstance()
                .CallIsDomainEnable(domainName);

            return *this;
        }

        /**
            * @brief 获取当前记录的数据
            * @return 当前记录的数据内容
        */
        const std::string &GetMsg() const
        {
            return msg_;
        }

    public:
        /**
            * @brief 记录一个过程的开始节点
            * @param spanName [in] 区间名字
            * @param autoEnd [in] （可选）是否自动调用End，默认自动调用
            * @return 返回当前Profiler&对象，支持链式调用
        */
        MS_SERVICE_PROFILER_HIDDEN Profiler &SpanStart(const char *spanName, bool autoEnd = true)
        {
            if (IsEnable(level)) {
                name_ = spanName ? spanName : "";
                Attr("type", static_cast<uint8_t>(MarkType::TYPE_SPAN));
                spanHandle_ = msServiceProfilerCompatible::ServiceProfilerInterface::GetInstance()
                    .CallStartSpanWithName(spanName);
                autoEnd_ = autoEnd;
            }
            return *this;
        }

        /**
            * @brief 记录一个过程的结束节点
        */
        MS_SERVICE_PROFILER_HIDDEN void SpanEnd()
        {
            if (IsEnable(level)) {
                const char* name = name_.empty() ? "" : name_.c_str();
                const char* domain = domain_.empty() ? "" : domain_.c_str();
                std::string attrsJson = BuildAttrsJson();
                const char* msg = attrsJson.c_str();

                msServiceProfilerCompatible::ServiceProfilerInterface::GetInstance()
                    .CallSpanEndEx(name, domain, msg, spanHandle_);

                msServiceProfilerCompatible::ServiceProfilerInterface::GetInstance().CallEndSpan(spanHandle_);
                autoEnd_ = false;
            }
        }

        /**
            * @brief 默认构造函数，创建未初始化的Profiler对象
        */
        Profiler()
        {}

        /**
            * @brief 赋值运算符重载，转移资源所有权并修改原对象状态
            * @param obj [in] 被赋值的源对象
            * @return 返回当前对象的引用
        */
        Profiler &operator=(Profiler &obj)
        {
            autoEnd_ = obj.autoEnd_;
            spanHandle_ = obj.spanHandle_;
            domainAllow_ = obj.domainAllow_;
            name_ = std::move(obj.name_);
            domain_ = std::move(obj.domain_);
            msg_ = std::move(obj.msg_);
            obj.autoEnd_ = false;
            return *this;
        }

        /**
            * @brief 拷贝构造函数（转移语义），从源对象接管资源并禁用其自动结束
            * @param obj [in] 源对象
        */
        Profiler(Profiler &obj)
            : autoEnd_(obj.autoEnd_), spanHandle_(obj.spanHandle_), domainAllow_(obj.domainAllow_),
              name_(std::move(obj.name_)), domain_(std::move(obj.domain_)), msg_(std::move(obj.msg_))
        {
            obj.autoEnd_ = false;
        }

        /**
            * @brief Profiler对象析构函数
        */
        ~Profiler()
        {
            if (autoEnd_) {
                SpanEnd();
            }
        }

    public:
        template <typename T>
        MS_SERVICE_PROFILER_HIDDEN inline Profiler &Metric(const char *metricName, T value)
        {
            if (this->IsEnable(level)) {
                msg_.append("\"").append(metricName).append("=\":").append(std::to_string(value)).append(",");
            }
            return *this;
        }

        template <typename T>
        MS_SERVICE_PROFILER_HIDDEN inline Profiler &MetricInc(const char *metricName, T value)
        {
            if (this->IsEnable(level)) {
                msg_.append("\"").append(metricName).append("+\":").append(std::to_string(value)).append(",");
            }
            return *this;
        }

        template <typename T>
        MS_SERVICE_PROFILER_HIDDEN inline Profiler &MetricScope(const char *scopeName, T value)
        {
            if (this->IsEnable(level)) {
                msg_.append("\"scope#").append(scopeName).append("\":").append(std::to_string(value)).append(",");
            }
            return *this;
        }

        MS_SERVICE_PROFILER_HIDDEN inline Profiler &MetricScopeAsReqID()
        {
            if (this->IsEnable(level)) {
                msg_.append("\"scope#\":\"req\",");
            }
            return *this;
        }

        MS_SERVICE_PROFILER_HIDDEN inline Profiler &MetricScopeAsGlobal() const
        {
            return *this;
        }

        /**
            * @brief 正式将该请求记录进行落盘
        */
        MS_SERVICE_PROFILER_HIDDEN void Launch() const
        {
            if (this->IsEnable(level)) {
                const char* name = name_.empty() ? "" : name_.c_str();
                const char* domain = domain_.empty() ? "" : domain_.c_str();
                std::string attrsJson = BuildAttrsJson();
                const char* msg = attrsJson.c_str();

                msServiceProfilerCompatible::ServiceProfilerInterface::GetInstance()
                    .CallMarkEventEx(name, domain, msg);
            }
        }

    public:
        /**
            * @brief 记录一个事件
            * @param eventName [in] 事件名
        */
        MS_SERVICE_PROFILER_HIDDEN void Event(const char *eventName)
        {
            if (IsEnable(level)) {
                name_ = eventName ? eventName : "";
                Attr("type", static_cast<uint8_t>(MarkType::TYPE_LINK));

                const char* name = name_.c_str();
                const char* domain = domain_.empty() ? "" : domain_.c_str();
                std::string attrsJson = BuildAttrsJson();
                const char* msg = attrsJson.c_str();

                msServiceProfilerCompatible::ServiceProfilerInterface::GetInstance()
                    .CallMarkEventEx(name, domain, msg);
            }
        }

    public:
        /**
            * @brief 记录不同资源之间的关联，实际应用时不同模块对同一个请求使用不同的编号。将两个系统的编号关联起来。
            * @param fromRid [in] ResID类型的编号，ResID可以由字符串或数值隐式转换。
            * @param toRid [in] ResID类型的编号，ResID可以由字符串或数值隐式转换。
        */
        MS_SERVICE_PROFILER_HIDDEN void Link(const ResID &fromRid, const ResID &toRid)
        {
            if (this->IsEnable(level)) {
                msg_.clear();
                this->Attr("type", static_cast<uint8_t>(MarkType::TYPE_LINK));
                this->Attr("from", fromRid);
                this->Attr("to", toRid);
                name_ = "Link";

                const char* name = "Link";
                const char* domain = domain_.empty() ? "" : domain_.c_str();
                std::string attrsJson = BuildAttrsJson();
                const char* msg = attrsJson.c_str();

                msServiceProfilerCompatible::ServiceProfilerInterface::GetInstance()
                    .CallMarkEventEx(name, domain, msg);
            }
        }

    public:
        MS_SERVICE_PROFILER_HIDDEN inline void AddMetaInfo(const char *key, const char *value) const
        {
            msServiceProfilerCompatible::ServiceProfilerInterface::GetInstance().CallAddMetaInfo(key, value);
        }

        MS_SERVICE_PROFILER_HIDDEN inline void AddMetaInfo(const char *key, const std::string &value) const
        {
            AddMetaInfo(key, value.c_str());
        }

        template <typename T>
        MS_SERVICE_PROFILER_HIDDEN inline void AddMetaInfo(const char *key, const T value) const
        {
            AddMetaInfo(key, std::to_string(value).c_str());
        }

    private:
        std::string BuildAttrsJson() const
        {
            if (msg_.empty()) {
                return "{}";
            }
            std::string clean = msg_;
            if (clean.back() == ',') {
                clean.pop_back();
            }
            return "{" + clean + "}";
        }

    private:
        bool autoEnd_ = false;
        SpanHandle spanHandle_ = 0U;
        bool domainAllow_ = true;
        std::string name_;
        std::string domain_;
        std::string msg_;
    };

}  // namespace msServiceProfiler

#endif