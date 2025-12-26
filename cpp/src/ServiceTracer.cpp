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

#include <cstring>
#include <sys/socket.h>
#include <unistd.h>
#include <stdexcept>
#include <arpa/inet.h>
#include <iostream>
#include "msServiceProfiler/Log.h"
#include "msServiceProfiler/Utils.h"
#include "msServiceProfiler/ServiceProfilerDbWriter.h"
#include "msServiceProfiler/ServiceProfilerInterface.h"
#include "msServiceProfiler/ServiceTracer.h"

namespace msServiceProfiler {

UnixSocketSender::UnixSocketSender(const std::string& abstract_socket_name)
    : sockfd_(-1), isConnected_(false)
{
    sockfd_ = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sockfd_ == -1) {
        throw std::runtime_error("Failed to create socket: " + std::string(strerror(errno)));
    }

    addr_ = {};
    addr_.sun_family = AF_UNIX;
    size_t max_len = sizeof(addr_.sun_path) - 2;
    std::copy_n(abstract_socket_name.begin(), std::min(abstract_socket_name.size(), max_len), addr_.sun_path + 1);
}

bool UnixSocketSender::Connect()
{
    errorMsg_.clear();
    if (isConnected_) {
        return true;
    }

    if (sockfd_ == -1) {
        errorMsg_ = "Socket not initialized.";
        return false;
    }

    socklen_t addr_len = sizeof(sa_family_t) + strlen(addr_.sun_path + 1) + 1;
    if (::connect(sockfd_, (struct sockaddr*)&addr_, addr_len) == -1) {
        errorMsg_ = std::string(strerror(errno));
        return false;
    }

    isConnected_ = true;
    return true;
}

bool UnixSocketSender::Send(const std::string& data)
{
    errorMsg_.clear();
    if (!isConnected_) {
        errorMsg_ = "Not connected to server, call connect() first.";
        return false;
    }
    if (data.empty()) {
        errorMsg_ = "Invalid trace data.";
        return false;
    }

    size_t total_size = sizeof(uint32_t) + data.size();
    std::vector<char> buffer(total_size);
    uint32_t len = htonl(static_cast<uint32_t>(data.size()));

    std::copy(reinterpret_cast<char*>(&len), reinterpret_cast<char*>(&len) + sizeof(len), buffer.begin());
    std::copy(data.begin(), data.end(), buffer.begin() + sizeof(len));

    const char* buffer_ptr = buffer.data();
    size_t buffer_remaining = buffer.size();

    while (buffer_remaining > 0) {
        ssize_t sent = ::send(sockfd_, buffer_ptr, buffer_remaining, 0);
        if (sent == -1) {
            errorMsg_ = std::string(strerror(errno));
            isConnected_ = false;
            return false;
        }
        buffer_ptr += sent;
        buffer_remaining -= sent;
    }

    return true;
}

UnixSocketSender::~UnixSocketSender()
{
    if (sockfd_ != -1) {
        close(sockfd_);
    }
}


bool IsTraceEnvEnable()
{
    static bool traceEnable = MsUtils::GetEnvAsString("MS_TRACE_ENABLE") == "1";
    return traceEnable;
};


void TraceSender::Execute()
{
    UnixSocketSender sender("OTLP_SOCKET");
    if (!sender.IsConnected()) {
        if (!sender.Connect()) {
            PROF_LOGW("[TraceSender:Connect] Failed to connect socket: %s", sender.GetErrorMsg().c_str());
            return;
        }
    }

    if (!sender.Send(msg_)) {
        PROF_LOGW("[TraceSender:Send] Failed to send trace: %s", sender.GetErrorMsg().c_str());
    }

    PROF_LOGD("[TraceSender] Send trace successfully: %zu bytes.", msg_.size());
}


void SendTracer(std::string &&traceMsg)
{
    msServiceProfiler::ServiceTraceThreadSender::GetSender().Send(
        std::move(std::make_unique<msServiceProfiler::TraceSender>(std::move(traceMsg))));
}
}  // namespace msServiceProfiler

bool IsTraceEnable()
{
    static bool traceEnable = msServiceProfiler::IsTraceEnvEnable();
    return traceEnable;
}