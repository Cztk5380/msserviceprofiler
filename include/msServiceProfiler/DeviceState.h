/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
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
#ifndef DEVICE_STATE_H
#define DEVICE_STATE_H

#include <vector>

namespace msServiceProfiler {
#pragma once
extern uint32_t g_deviceID;

const uint32_t INVALID_DEVICE_ID = static_cast<uint32_t>(-1);
const int EXITCODE_DEVICE_STATE_SUCCESS = 0;
const int EXITCODE_DEVICE_STATE_INVALID_DATA = 1;

struct ProfSetDevPara {
    uint32_t chipId;
    uint32_t deviceId;
    bool isOpen;
};

int32_t MsprofSetDeviceCallbackImpl(void * data, uint32_t len);
void registerSetDeviceCallback();
}
#endif  // DEVICE_STATE_H
