"""
image_to_text.clipboard 的单元测试
- 用 mock 拦截 subprocess.run，避免真的去调系统剪贴板
- 覆盖三个平台的分支和异常分支
"""
import os
import sys
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from image_to_text import clipboard


# ---------- helpers ----------

def _patch_platform(mocker, system_name):
    """替换 clipboard.platform.system() 的返回值"""
    return mocker.patch.object(clipboard.platform, 'system', return_value=system_name)


# ---------- Windows ----------

def test_copy_windows_uses_clip_with_gbk(mocker):
    """Windows → 调 clip，文本用 GBK 编码"""
    _patch_platform(mocker, 'Windows')
    fake_run = mocker.patch.object(clipboard.subprocess, 'run')

    ok = clipboard.copy_to_clipboard("你好")

    assert ok is True
    fake_run.assert_called_once()
    call = fake_run.call_args
    # 命令是 ['clip']，shell=True
    assert call.args[0] == ['clip']
    assert call.kwargs.get('shell') is True
    # 输入是 GBK 编码（中文 -> 2字节/汉字）
    encoded = call.kwargs['input']
    assert encoded.decode('gbk') == "你好"
    assert isinstance(encoded, bytes)


def test_copy_windows_chdir_to_c_to_avoid_unc(mocker):
    """Windows: chdir 到 C:\\ 绕开 UNC 路径（剪贴板 subprocess 限制）"""
    _patch_platform(mocker, 'Windows')
    mocker.patch.object(clipboard.subprocess, 'run')
    cwd_spy = mocker.patch.object(clipboard.os, 'chdir')

    clipboard.copy_to_clipboard("test")

    # 第一次 chdir 应该是 C:\\
    first_chdir = cwd_spy.call_args_list[0]
    assert first_chdir.args[0] == 'C:\\'


def test_copy_windows_restores_original_dir_even_on_failure(mocker):
    """Windows: 即便 subprocess 抛异常，也要把 cwd 恢复回去"""
    _patch_platform(mocker, 'Windows')
    mocker.patch.object(
        clipboard.subprocess, 'run',
        side_effect=subprocess.CalledProcessError(1, 'clip'),
    )
    original_cwd = '/some/path'
    mocker.patch.object(clipboard.os, 'getcwd', return_value=original_cwd)
    chdir_spy = mocker.patch.object(clipboard.os, 'chdir')

    ok = clipboard.copy_to_clipboard("test")

    assert ok is False
    # finally 块里 chdir 必须被调回原 cwd
    final_chdir = chdir_spy.call_args_list[-1]
    assert final_chdir.args[0] == original_cwd


def test_copy_windows_ignores_unencodable_chars(mocker):
    """Windows: errors='ignore' 让无法 GBK 编码的字符被丢弃"""
    _patch_platform(mocker, 'Windows')
    fake_run = mocker.patch.object(clipboard.subprocess, 'run')

    # emoji 在 GBK 下编码不了
    clipboard.copy_to_clipboard("hello 😀")

    encoded = fake_run.call_args.kwargs['input']
    # 'hello ' 编码正常，emoji 丢了（不抛异常）
    assert encoded.decode('gbk') == "hello "


# ---------- Linux ----------

def test_copy_linux_uses_xclip(mocker):
    """Linux → 调 xclip -selection clipboard"""
    _patch_platform(mocker, 'Linux')
    fake_run = mocker.patch.object(clipboard.subprocess, 'run')

    ok = clipboard.copy_to_clipboard("test")

    assert ok is True
    fake_run.assert_called_once()
    call = fake_run.call_args
    assert call.args[0] == ['xclip', '-selection', 'clipboard']
    assert call.kwargs.get('check') is True
    # Linux 走 UTF-8
    assert call.kwargs['input'].decode('utf-8') == "test"


# ---------- macOS ----------

def test_copy_macos_uses_pbcopy(mocker):
    """macOS → 调 pbcopy"""
    _patch_platform(mocker, 'Darwin')
    fake_run = mocker.patch.object(clipboard.subprocess, 'run')

    ok = clipboard.copy_to_clipboard("test")

    assert ok is True
    fake_run.assert_called_once_with(['pbcopy'], input=b'test', check=True)


# ---------- 异常 / 错误 ----------

def test_copy_unsupported_os_returns_false(mocker):
    """不支持的 OS（如 FreeBSD）→ 返回 False"""
    _patch_platform(mocker, 'FreeBSD')
    fake_run = mocker.patch.object(clipboard.subprocess, 'run')

    ok = clipboard.copy_to_clipboard("test")

    assert ok is False
    fake_run.assert_not_called()


def test_copy_subprocess_failure_returns_false(mocker):
    """subprocess 抛 CalledProcessError → 返回 False"""
    _patch_platform(mocker, 'Linux')
    mocker.patch.object(
        clipboard.subprocess, 'run',
        side_effect=subprocess.CalledProcessError(1, 'xclip'),
    )

    ok = clipboard.copy_to_clipboard("test")

    assert ok is False


def test_copy_tool_not_found_returns_false(mocker):
    """找不到剪贴板工具（FileNotFoundError）→ 返回 False"""
    _patch_platform(mocker, 'Linux')
    mocker.patch.object(
        clipboard.subprocess, 'run',
        side_effect=FileNotFoundError("xclip not found"),
    )

    ok = clipboard.copy_to_clipboard("test")

    assert ok is False
