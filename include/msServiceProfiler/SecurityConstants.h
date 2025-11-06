// Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.

#ifndef MS_STANDARD_SECYRUTY_CONSTANTS_H
#define MS_STANDARD_SECYRUTY_CONSTANTS_H

#include <cstdint>

constexpr const uint32_t PATH_DEPTH_MAX = 50;
constexpr const char PATH_SEPARATOR = '/';
constexpr uint64_t MAX_FILE_SIZE_10G = static_cast<uint64_t>(1024 * 1024 * 1024) * 10; // 10G
constexpr const char* FILE_VALID_PATTERN = "(\\.|\\\\|/|:|_|-|[~0-9a-zA-Z])+";

#endif // MS_STANDARD_SECYRUTY_CONSTANTS_H
