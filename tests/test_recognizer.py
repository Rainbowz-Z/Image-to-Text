"""
image_to_text.recognizer 的单元测试
- 用 mock 拦截 OpenAI 客户端，避免真实调用豆包 API
- 用 tmp_path 写假图片，确保不会污染真实文件
"""
import os
import sys
import io
import base64
import configparser
from unittest.mock import MagicMock

import pytest
from PIL import Image

from image_to_text import recognizer


# ---------- fixtures ----------

@pytest.fixture
def fake_config():
    """假的 config，模拟正常加载到的配置"""
    cfg = configparser.ConfigParser()
    cfg.read_dict({
        'api': {
            'api_key': 'fake-api-key',
            'endpoint_id': 'fake-endpoint',
            'base_url': 'https://fake.api/v3',
        }
    })
    return cfg


@pytest.fixture
def fake_png(tmp_path):
    """100x100 白色 png，常规尺寸"""
    img = Image.new('RGB', (100, 100), color='white')
    p = tmp_path / "normal.png"
    img.save(p)
    return str(p)


@pytest.fixture
def fake_tiny_png(tmp_path):
    """5x5 极小 png，触发 resize 逻辑（阈值 14）"""
    img = Image.new('RGB', (5, 5), color='white')
    p = tmp_path / "tiny.png"
    img.save(p)
    return str(p)


@pytest.fixture
def fake_jpg(tmp_path):
    """jpeg 图，验证 mime 推导"""
    img = Image.new('RGB', (50, 50), color='white')
    p = tmp_path / "pic.jpg"
    img.save(p)
    return str(p)


@pytest.fixture
def fake_unknown_ext(tmp_path):
    """扩展名不在 mime_map 里，应回退到 image/png"""
    # PIL 不能直接 save 到 .xyz，所以先存 png 再改成 .xyz 扩展名
    img = Image.new('RGB', (50, 50), color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    p = tmp_path / "pic.xyz"
    p.write_bytes(buf.getvalue())
    return str(p)


def _make_fake_response(content: str):
    """构造一个假的 OpenAI ChatCompletion 响应对象"""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


# ---------- recognize_text 主体测试 ----------

def test_recognize_text_happy_path(mocker, fake_config, fake_png):
    """正常图片 → 调 API → 返回文本"""
    mocker.patch.object(recognizer, '_load_config', return_value=fake_config)
    fake_client = mocker.patch.object(recognizer, 'OpenAI')
    fake_client.return_value.chat.completions.create.return_value = _make_fake_response(
        "你好世界"
    )

    result = recognizer.recognize_text(fake_png)

    assert result == "你好世界"
    fake_client.assert_called_once_with(
        base_url='https://fake.api/v3',
        api_key='fake-api-key',
    )
    call_kwargs = fake_client.return_value.chat.completions.create.call_args.kwargs
    assert call_kwargs['model'] == 'fake-endpoint'
    assert call_kwargs['temperature'] == 0.1
    assert call_kwargs['max_tokens'] == 4096
    # content 是 [image_url, text] 结构
    msgs = call_kwargs['messages']
    assert msgs[0]['role'] == 'user'
    content = msgs[0]['content']
    assert content[0]['type'] == 'image_url'
    assert content[0]['image_url']['url'].startswith('data:image/png;base64,')
    assert content[1]['type'] == 'text'
    # prompt 里要求纯文本输出
    assert '不要使用Markdown格式' in content[1]['text']


def test_recognize_text_filters_unrecognized_response(mocker, fake_config, fake_png):
    """API 返回含"未识别到"的字符串 → 应过滤为空字符串"""
    mocker.patch.object(recognizer, '_load_config', return_value=fake_config)
    fake_client = mocker.patch.object(recognizer, 'OpenAI')
    fake_client.return_value.chat.completions.create.return_value = _make_fake_response(
        "未识别到文字"
    )

    result = recognizer.recognize_text(fake_png)

    assert result == ""


def test_recognize_text_filters_none_only_response(mocker, fake_config, fake_png):
    """API 返回单独的"无" → 应过滤为空字符串"""
    mocker.patch.object(recognizer, '_load_config', return_value=fake_config)
    fake_client = mocker.patch.object(recognizer, 'OpenAI')
    fake_client.return_value.chat.completions.create.return_value = _make_fake_response("无")

    result = recognizer.recognize_text(fake_png)

    assert result == ""


def test_recognize_text_returns_multiline_content(mocker, fake_config, fake_png):
    """API 返回多行文本 → 原样返回（不被过滤）"""
    mocker.patch.object(recognizer, '_load_config', return_value=fake_config)
    fake_client = mocker.patch.object(recognizer, 'OpenAI')
    fake_client.return_value.chat.completions.create.return_value = _make_fake_response(
        "第一行\n第二行\n第三行"
    )

    result = recognizer.recognize_text(fake_png)

    assert result == "第一行\n第二行\n第三行"


def test_recognize_text_resizes_tiny_image(mocker, fake_config, fake_tiny_png):
    """<14px 的图片必须放大到至少 14 维，再上传"""
    mocker.patch.object(recognizer, '_load_config', return_value=fake_config)
    fake_client = mocker.patch.object(recognizer, 'OpenAI')
    fake_client.return_value.chat.completions.create.return_value = _make_fake_response("OK")

    result = recognizer.recognize_text(fake_tiny_png)

    assert result == "OK"
    # 抓取传给 API 的 base64，解码后应是放大过的图（>=14px）
    call_kwargs = fake_client.return_value.chat.completions.create.call_args.kwargs
    url = call_kwargs['messages'][0]['content'][0]['image_url']['url']
    assert url.startswith('data:image/png;base64,')
    img_b64 = url.split(',', 1)[1]
    img_bytes = base64.b64decode(img_b64)
    img = Image.open(io.BytesIO(img_bytes))
    w, h = img.size
    assert w >= 14 and h >= 14


def test_recognize_text_passes_jpeg_mime(mocker, fake_config, fake_jpg):
    """.jpg → image/jpeg"""
    mocker.patch.object(recognizer, '_load_config', return_value=fake_config)
    fake_client = mocker.patch.object(recognizer, 'OpenAI')
    fake_client.return_value.chat.completions.create.return_value = _make_fake_response("OK")

    recognizer.recognize_text(fake_jpg)

    call_kwargs = fake_client.return_value.chat.completions.create.call_args.kwargs
    url = call_kwargs['messages'][0]['content'][0]['image_url']['url']
    assert url.startswith('data:image/jpeg;base64,')


def test_recognize_text_passes_jpeg_mime_uppercase_ext(mocker, fake_config, tmp_path):
    """.JPG（大写扩展名）→ 仍应为 image/jpeg"""
    img = Image.new('RGB', (50, 50), color='white')
    p = tmp_path / "pic.JPG"
    img.save(p)

    mocker.patch.object(recognizer, '_load_config', return_value=fake_config)
    fake_client = mocker.patch.object(recognizer, 'OpenAI')
    fake_client.return_value.chat.completions.create.return_value = _make_fake_response("OK")

    recognizer.recognize_text(str(p))

    call_kwargs = fake_client.return_value.chat.completions.create.call_args.kwargs
    url = call_kwargs['messages'][0]['content'][0]['image_url']['url']
    assert url.startswith('data:image/jpeg;base64,')


def test_recognize_text_unknown_ext_defaults_to_png(mocker, fake_config, fake_unknown_ext):
    """.xyz 等未知扩展名 → 回退到 image/png"""
    mocker.patch.object(recognizer, '_load_config', return_value=fake_config)
    fake_client = mocker.patch.object(recognizer, 'OpenAI')
    fake_client.return_value.chat.completions.create.return_value = _make_fake_response("OK")

    recognizer.recognize_text(fake_unknown_ext)

    call_kwargs = fake_client.return_value.chat.completions.create.call_args.kwargs
    url = call_kwargs['messages'][0]['content'][0]['image_url']['url']
    assert url.startswith('data:image/png;base64,')


def test_recognize_text_propagates_api_error(mocker, fake_config, fake_png):
    """OpenAI 抛异常 → 直接向上传播，不吞"""
    mocker.patch.object(recognizer, '_load_config', return_value=fake_config)
    fake_client = mocker.patch.object(recognizer, 'OpenAI')
    fake_client.return_value.chat.completions.create.side_effect = RuntimeError("网络挂了")

    with pytest.raises(RuntimeError, match="网络挂了"):
        recognizer.recognize_text(fake_png)


def test_recognize_text_uses_default_base_url_when_missing(mocker, fake_png):
    """config 里没有 base_url → 用 fallback 默认值"""
    cfg = configparser.ConfigParser()
    cfg.read_dict({
        'api': {
            'api_key': 'k',
            'endpoint_id': 'e',
            # 没有 base_url
        }
    })
    mocker.patch.object(recognizer, '_load_config', return_value=cfg)
    fake_client = mocker.patch.object(recognizer, 'OpenAI')
    fake_client.return_value.chat.completions.create.return_value = _make_fake_response("OK")

    recognizer.recognize_text(fake_png)

    fake_client.assert_called_once_with(
        base_url='https://ark.cn-beijing.volces.com/api/v3',
        api_key='k',
    )


# ---------- _load_config 自身测试 ----------

def test_load_config_reads_external_config_when_exists(mocker, tmp_path):
    """外部 config.ini 存在 → 用外部的"""
    cfg_file = tmp_path / "config.ini"
    cfg_file.write_text(
        "[api]\napi_key = external-key\nendpoint_id = external-ep\nbase_url = https://x\n",
        encoding='utf-8',
    )
    mocker.patch.object(recognizer, '_resolve_config_path', return_value=str(cfg_file))

    cfg = recognizer._load_config()
    assert cfg.get('api', 'api_key') == 'external-key'
    assert cfg.get('api', 'endpoint_id') == 'external-ep'
    assert cfg.get('api', 'base_url') == 'https://x'


def test_load_config_falls_back_to_hardcoded_defaults(mocker):
    """_resolve_config_path 返回 None → 用硬编码默认值"""
    mocker.patch.object(recognizer, '_resolve_config_path', return_value=None)

    cfg = recognizer._load_config()
    assert cfg.get('api', 'api_key') == ''
    assert cfg.get('api', 'endpoint_id') == ''
    assert cfg.get('api', 'base_url') == 'https://ark.cn-beijing.volces.com/api/v3'


def test_load_config_handles_missing_file_path(mocker, tmp_path):
    """_resolve_config_path 返回一个不存在的路径 → 用默认值（不抛异常）"""
    nonexistent = str(tmp_path / "no-such-config.ini")
    mocker.patch.object(recognizer, '_resolve_config_path', return_value=nonexistent)

    cfg = recognizer._load_config()
    assert cfg.get('api', 'base_url') == 'https://ark.cn-beijing.volces.com/api/v3'


# ---------- _resolve_config_path 测试 ----------

def test_resolve_config_path_uses_exe_dir_when_frozen(mocker):
    """sys.frozen=True → 用 sys.executable 同目录"""
    mocker.patch.object(sys, 'frozen', True, create=True)
    mocker.patch.object(sys, 'executable', r'C:\dist\Image-to-Text.exe', create=True)

    p = recognizer._resolve_config_path()

    assert p == r'C:\dist\config.ini'


def test_resolve_config_path_uses_project_root_when_source(tmp_path):
    """源码运行（无 frozen） → 用项目根目录的 config.ini"""
    # 此函数查真实项目路径；只要项目根有 config.ini 就 OK
    # （.gitignore 把 config.ini 列进去是为了不把真 key 提交；本地开发时它仍在）
    p = recognizer._resolve_config_path()
    assert p is not None
    assert p.endswith('config.ini')
    # 应是项目根（recognizer.py 的父目录的父目录）
    project_root = os.path.dirname(os.path.dirname(recognizer.__file__))
    assert os.path.dirname(p) == project_root
