// Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
#include "msServiceProfiler/SecurityUtils.h"
#include <iostream>
#include <sys/stat.h>
#include <cstring>
#include <unistd.h>
#include <climits>
#include <algorithm>
#include <regex>
#include <cstdlib>
#include "msServiceProfiler/SecurityUtilsLog.h"

namespace SecurityUtils {
bool IsExist(const std::string &absPath)
{
    struct stat fileStat;
    if (stat(absPath.c_str(), &fileStat) != 0) {
        LogWarn("File not exist: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsReadable(const std::string &absPath)
{
    struct stat fileStat;
    if ((stat(absPath.c_str(), &fileStat) != 0) || (fileStat.st_mode & S_IRUSR) == 0) {
        LogWarn("File not readable: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsWritable(const std::string &absPath)
{
    struct stat fileStat;
    if ((stat(absPath.c_str(), &fileStat) != 0) || (fileStat.st_mode & S_IWUSR) == 0) {
        LogWarn("File not writable: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsExecutable(const std::string &absPath)
{
    struct stat fileStat;
    if ((stat(absPath.c_str(), &fileStat) != 0) || (fileStat.st_mode & S_IXUSR) == 0) {
        LogWarn("File not executable: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsOwner(const std::string &absPath)
{
    struct stat fileStat;
    if ((stat(absPath.c_str(), &fileStat) != 0) || (fileStat.st_uid != getuid())) {
        LogWarn("File not owned by current user: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsRootUser()
{
    constexpr __uid_t root = 0;
    return getuid() == root;
}

bool IsSoftLink(const std::string &absPath)
{
    struct stat fileStat;
    if ((lstat(absPath.c_str(), &fileStat) != 0) || ((S_IFMT & fileStat.st_mode) != S_IFLNK)) {
        return false;
    } else {
        LogWarn("File is symbol link: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return true;
    }
}

bool IsFile(const std::string &absPath)
{
    struct stat fileStat;
    if ((stat(absPath.c_str(), &fileStat) != 0) || !S_ISREG(fileStat.st_mode)) {
        LogWarn("Path is not regular file: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsDir(std::string const &absPath)
{
    struct stat fileStat;
    if (stat(absPath.c_str(), &fileStat) != 0 || (fileStat.st_mode & S_IFDIR) == 0) {
        LogWarn("Path is not directory: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsPathLenLegal(const std::string &absPath)
{
    if (absPath.empty() || (absPath.size() >= PATH_MAX)) {
        LogWarn("Path length is ilegal");  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsPathDepthLegal(const std::string &absPath)
{
    if (std::count(absPath.begin(), absPath.end(), PATH_SEPARATOR) > PATH_DEPTH_MAX) {
        LogWarn("Path depth exceeds limit");  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsFileSizeLegal(const std::string &absPath, long long maxSize)
{
    struct stat fileStat;
    if (stat(absPath.c_str(), &fileStat) != 0 || !S_ISREG(fileStat.st_mode) || fileStat.st_size >= maxSize) {
        LogWarn("File size is not legal, path: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsPathCharactersValid(const std::string &absPath)
{
    if (!std::regex_match(absPath, std::regex(FILE_VALID_PATTERN))) {
        LogWarn("File path contain invalid characters");  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

static std::string GetRealPath(std::string const &path)
{
    char* absPath = realpath(path.c_str(), nullptr);
    if (absPath == nullptr) {
        LogWarn("Cannot GetRealPath");  // LCOV_EXCL_LINE
        return "";
    }
    std::string result(absPath);
    free(absPath);
    return result;
}

static std::string GetParentDir(const std::string &path)
{
    if (path.empty() || path == "/") {
        LogWarn("Cannot GetParentDir");  // LCOV_EXCL_LINE
    }
    size_t found = path.find_last_of('/');
    if (found != std::string::npos) {
        return path.substr(0, found);
    }
    return ".";
}

static void Split(std::string const &str, std::back_insert_iterator<std::vector<std::string>> it,
    std::string const &seps)
{
    if (!seps.empty() && !str.empty() && str.find_first_of(seps) == 0) {
        *it = "";
        ++it;
    }
    std::string::size_type slow = str.find_first_not_of(seps);
    while (slow != std::string::npos && slow < str.length()) {
        std::string::size_type fast = str.find_first_of(seps, slow);
        if (fast == std::string::npos) {
            fast = str.length();
        }
        if (fast != slow) {
            *it = str.substr(slow, fast - slow);
            ++it;
        }
        slow = fast + 1;
    }
}

bool CheckPathContainSoftLink(const std::string &path)
{
    constexpr char const *pathSep = "/";
    std::string nonConstPath = path;
    while (!nonConstPath.empty() && nonConstPath.back() == '/') {
        nonConstPath.pop_back();
    }
    std::vector<std::string> dirs;
    Split(nonConstPath, std::back_inserter(dirs), pathSep);
    if (dirs.empty()) {
        return false;
    }
    std::string current;
    for (auto it = dirs.cbegin(); it != dirs.cend(); ++it) {
        if (it == dirs.cbegin()) {
            current = *it;
        } else {
            current.append(pathSep + *it);
        }
        if (*it == "." || *it == ".." || *it == "") {
            continue;
        }
        if (SecurityUtils::IsSoftLink(current)) {
            return true;
        }
    }
    return false;
}

static mode_t GetFilePermissions(const std::string &path)
{
    struct stat fileStat;
    if (stat(path.c_str(), &fileStat) != 0) {
        return 0;
    }
    mode_t permissions = fileStat.st_mode & (S_IRWXU | S_IRWXG | S_IRWXO);
    return permissions;
}

bool CheckFileBeforeWrite(const std::string &path)
{
    if (IsSoftLink(path)) {
        return false;
    }

    const auto absPath = GetRealPath(path);
    if (!IsPathLenLegal(absPath) || !IsPathCharactersValid(absPath) || !IsFile(absPath) ||
        !IsOwner(GetParentDir(absPath)) || !IsOwner(absPath) || !IsWritable(absPath)) {
        LogWarn("CheckFileBeforeWrite faild, path: %s", path.c_str());  // LCOV_EXCL_LINE
        return false;
    }

    const mode_t defaultWriteFilePerm = 0640;
    if (GetFilePermissions(absPath) > defaultWriteFilePerm) {
        LogWarn("Permission of file to write is over 0640, path: %s", path.c_str());  // LCOV_EXCL_LINE
    }
    return true;
}

bool CheckFileBeforeRead(const std::string &path, long long maxSize)
{
    if (IsSoftLink(path)) {
        return false;
    }

    const auto absPath = GetRealPath(path);
    if (!IsPathLenLegal(absPath) || !IsPathCharactersValid(absPath) || !IsFile(absPath)) {
        LogWarn("CheckFileBeforeRead faild, path: %s", path.c_str());  // LCOV_EXCL_LINE
        return false;
    }

    struct stat fileStat;
    if (stat(absPath.c_str(), &fileStat) != 0) {
        LogWarn("File not exist: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    if ((fileStat.st_mode & (S_IWGRP | S_IWOTH)) != 0) {
        LogWarn("Group or others user can write, path: %s", path.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    if (fileStat.st_uid != getuid() && fileStat.st_uid != 0) {
        LogWarn("file owner is not self or root: %s", path.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    if (!IsReadable(absPath)) {
        return false;
    }
    if (!IsFileSizeLegal(absPath, maxSize)) {
        return false;
    }
    return true;
}

}  // SecurityUtils
