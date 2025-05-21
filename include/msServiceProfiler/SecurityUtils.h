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

#ifndef MS_STANDARD_SECYRUTY_UTILS_H
#define MS_STANDARD_SECYRUTY_UTILS_H

#include <string>
#include "SecurityConstants.h"

namespace SecurityUtils {
    bool IsExist(const std::string &absPath); // 检查文件是否存在
    bool IsReadable(const std::string &absPath); // 检查文件是否可读
    bool IsWritable(const std::string &absPath); // 检查文件是否可写
    bool IsExecutable(const std::string &absPath); // 检查文件是否可执行
    bool IsOwner(const std::string &absPath); // 检查是否为文件属主
    bool IsSoftLink(const std::string &absPath); // 检查是否为软链接
    bool IsFile(const std::string &absPath); // 检查是否为文件
    bool IsDir(std::string const &absPath); // 检查是否为文件夹
    bool IsPathLenLegal(const std::string &absPath); // 检查路径长度是否合法
    bool IsPathDepthLegal(const std::string &absPath); // 检查路径深度是否合法
    bool IsFileSizeLegal(const std::string &absPath, long long maxSize = MAX_FILE_SIZE_10G); // 检查文件大小是否合法
    bool IsPathCharactersValid(const std::string &absPath); // 检查路径中是否有非法字符

    bool CheckPathContainSoftLink(const std::string &path); // 检查路径中各层级是否为软链接
    bool CheckFileBeforeWrite(const std::string &path); // 写入前综合检查
    bool CheckFileBeforeRead(const std::string &path, long long maxSize = MAX_FILE_SIZE_10G); // 读取前综合检查
};

#endif // MS_STANDARD_SECYRUTY_UTILS_H