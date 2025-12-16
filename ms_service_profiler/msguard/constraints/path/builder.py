# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------

import re

from .path import PathConstraint


class PathMeta(type):
    lower_after_upper_pattern = re.compile(
        r'(?<=[a-z])' # match the position where right after a lower letter
        r'(?=[A-Z])' # and before a upper letter
    )

    def __new__(cls, name, bases, namespace):
        new_class = super().__new__(cls, name, bases, namespace)

        for sub_cls in PathConstraint.__subclasses__():
            sub_cls_name = sub_cls.__name__

            # replace the zero width to underscore _, that makes AbCd to Ab_Cd
            snake_name = cls.lower_after_upper_pattern.sub('_', sub_cls_name).lower()
            setattr(new_class, snake_name, sub_cls)

        return new_class

    def __getattr__(cls, name):
        for sub_cls in PathConstraint.__subclasses__():
            sub_cls_name = sub_cls.__name__
            snake_name = cls.lower_after_upper_pattern.sub('_', sub_cls_name).lower()
            if snake_name == name:
                setattr(cls, snake_name, sub_cls)
                return sub_cls

        return super().__getattr__(name)


class Path(metaclass=PathMeta):
    pass
