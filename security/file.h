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

#ifndef VOS_INCLUDE_FILE_H
#define VOS_INCLUDE_FILE_H

#include <string>
#include <vector>

namespace vos {
    // 使用 inline constexpr 定义常量（避免多文件包含时重复定义）
    inline constexpr int DIR_NAME_LENGTH_LIMIT = 1024;
    inline constexpr int FILE_NAME_LENGTH_LIMIT = 255;

    class File {
    public:
        size_t GetFileSize(const std::string& filePath);
        bool PathLenCheckValid(const std::string& checkPath);
    };

    template<typename Iterator>
    void Split(std::string const &str, Iterator it, std::string const &seps = "/") {
        std::string::size_type fast = 0;
        if (!seps.empty() && str.rfind(seps, 0) == 0) {
            *it = "";
            ++it;
        }
        std::string::size_type slow = str.find_first_not_of(seps);
        for (; fast < str.length(); slow = str.find_first_not_of(seps, fast)) {
            fast = str.find_first_of(seps, slow);
            if (fast != slow) {
                *it = str.substr(slow, fast - slow);
                ++it;
            }
        }
    }
}

#endif