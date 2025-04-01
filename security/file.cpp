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


#include "file.h"
#include <sys/stat.h>
#include <unistd.h>

namespace vos {
    size_t File::GetFileSize(const std::string& filePath) {
        struct stat fileStat;
        if (stat(filePath.c_str(), &fileStat) != 0 || !S_ISREG(fileStat.st_mode)) {
            return 0;
        }
        return static_cast<size_t>(fileStat.st_size);
    }

    bool File::PathLenCheckValid(const std::string& checkPath) {
        if (checkPath.length() > DIR_NAME_LENGTH_LIMIT) {
            return false;
        }
        std::vector<std::string> dirs;
        Split(checkPath, std::back_inserter(dirs), PATH_SEP);
        for (const auto& dir : dirs) {
            if (dir.length() > FILE_NAME_LENGTH_LIMIT) {
                return false;
            }
        }
        return true;
    }
}