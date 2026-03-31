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

import pytest

from ms_service_metric.core.config.symbol_config import SymbolConfig


def test_given_array_yaml_when_load_then_converted_to_symbol_map(tmp_path):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        "- symbol: a.b:Cls.fn\n"
        "  handler: ms_service_metric.handlers:default_handler\n"
        "  metrics:\n"
        "    - name: m1\n"
        "      type: counter\n",
        encoding="utf-8",
    )

    c = SymbolConfig(user_config_path=str(cfg))
    out = c.load()
    assert "a.b:Cls.fn" in out
    assert isinstance(out["a.b:Cls.fn"], list)
    assert out["a.b:Cls.fn"][0]["handler"] == "ms_service_metric.handlers:default_handler"


def test_given_env_user_config_when_load_then_env_path_takes_precedence(tmp_path, monkeypatch):
    env_cfg = tmp_path / "env.yaml"
    env_cfg.write_text("- symbol: m.n:o\n  handler: ms_service_metric.handlers:default_handler\n", encoding="utf-8")

    fallback_cfg = tmp_path / "fallback.yaml"
    fallback_cfg.write_text("- symbol: x.y:z\n  handler: ms_service_metric.handlers:default_handler\n", encoding="utf-8")

    monkeypatch.setenv(SymbolConfig.ENV_CONFIG_PATH, str(env_cfg))
    c = SymbolConfig(user_config_path=str(fallback_cfg))
    out = c.load()
    assert "m.n:o" in out
    assert "x.y:z" not in out


def test_given_version_bounds_when_filter_then_non_matching_handlers_removed(tmp_path):
    cfg = tmp_path / "ver.yaml"
    cfg.write_text(
        "- symbol: p.q:r\n"
        "  handler: ms_service_metric.handlers:default_handler\n"
        "  min_version: '9.9.9'\n",
        encoding="utf-8",
    )
    c = SymbolConfig(user_config_path=str(cfg), current_version="1.0.0")
    out = c.load()
    assert out == {}


def test_given_handler_without_optional_fields_when_fill_defaults_then_defaults_present(tmp_path):
    cfg = tmp_path / "d.yaml"
    cfg.write_text(
        "- symbol: p.q:r\n"
        "  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    c = SymbolConfig(user_config_path=str(cfg))
    out = c.load()
    h = out["p.q:r"][0]
    assert h["type"] == "wrap"
    assert h["enabled"] is True
    assert h["need_locals"] is False
    assert h["lock_patch"] is False
    assert h["metrics"] == []


def test_given_bad_yaml_when_load_then_raises_config_error(tmp_path):
    cfg = tmp_path / "bad.yaml"
    cfg.write_text(":\n  - bad", encoding="utf-8")
    c = SymbolConfig(user_config_path=str(cfg))
    with pytest.raises(Exception):
        c.load()
