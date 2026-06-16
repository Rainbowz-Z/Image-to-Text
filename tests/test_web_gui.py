"""
image_to_text.web_gui 中 HTTP 处理器（OCRHandler）的单元测试
- 用一个 FakeHandler 类（继承 OCRHandler 但绕开 BaseHTTPRequestHandler 初始化）
- 把外部依赖（recognize_text / copy_to_clipboard）打 patch
"""
import io
import json
import base64
from unittest.mock import patch

import pytest
from PIL import Image

from image_to_text.web_gui import OCRHandler


# ---------- helpers ----------

class FakeHandler(OCRHandler):
    """绕开 BaseHTTPRequestHandler.__init__，让我们能直接测试 handle 方法

    BaseHTTPRequestHandler.__init__ 需要 socket/client_address/server，
    测试里不需要这些。FakeHandler 自己持有 rfile/wfile/path 等关键状态。
    """

    def __init__(self, body_dict=None):
        body = b''
        if body_dict is not None:
            body = json.dumps(body_dict).encode('utf-8')
        self.headers = {'Content-Length': str(len(body))}
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.path = '/'
        # 记录 _json_response / send_error 的调用
        self._json_calls = []
        self._send_error_calls = []

    # 屏蔽继承自 BaseHTTPRequestHandler 的真实 socket 操作
    def send_response(self, code):
        pass

    def send_header(self, key, value):
        pass

    def end_headers(self):
        pass

    def send_error(self, code, message=None):
        self._send_error_calls.append((code, message))

    def _json_response(self, data):
        # 真实实现会调 send_response/send_header/end_headers/wfile.write，
        # 我们只关心参数，所以只记参数
        self._json_calls.append(data)


def last_json(handler):
    if not handler._json_calls:
        return None
    return handler._json_calls[-1]


# ---------- GET ----------

def test_get_root_returns_html():
    """GET / → _serve_html"""
    h = FakeHandler()
    h.path = '/'
    with patch.object(OCRHandler, '_serve_html') as mock:
        OCRHandler.do_GET(h)
    mock.assert_called_once()


def test_get_index_returns_html():
    """GET /index.html → _serve_html"""
    h = FakeHandler()
    h.path = '/index.html'
    with patch.object(OCRHandler, '_serve_html') as mock:
        OCRHandler.do_GET(h)
    mock.assert_called_once()


def test_get_unknown_returns_404():
    """GET /unknown → send_error(404)"""
    h = FakeHandler()
    h.path = '/foo'
    OCRHandler.do_GET(h)
    assert h._send_error_calls == [(404, 'Not Found')]


# ---------- POST 路由分发 ----------

def test_post_screenshot_dispatches():
    """POST /api/screenshot → _handle_screenshot"""
    h = FakeHandler()
    h.path = '/api/screenshot'
    with patch.object(OCRHandler, '_handle_screenshot') as mock:
        OCRHandler.do_POST(h)
    mock.assert_called_once()


def test_post_recognize_dispatches():
    """POST /api/recognize → _handle_recognize"""
    h = FakeHandler()
    h.path = '/api/recognize'
    with patch.object(OCRHandler, '_handle_recognize') as mock:
        OCRHandler.do_POST(h)
    mock.assert_called_once()


def test_post_recognize_file_dispatches():
    """POST /api/recognize_file → _handle_recognize_file"""
    h = FakeHandler()
    h.path = '/api/recognize_file'
    with patch.object(OCRHandler, '_handle_recognize_file') as mock:
        OCRHandler.do_POST(h)
    mock.assert_called_once()


def test_post_copy_dispatches():
    """POST /api/copy → _handle_copy"""
    h = FakeHandler()
    h.path = '/api/copy'
    with patch.object(OCRHandler, '_handle_copy') as mock:
        OCRHandler.do_POST(h)
    mock.assert_called_once()


def test_post_unknown_returns_404():
    """POST /api/unknown → 404"""
    h = FakeHandler()
    h.path = '/api/unknown'
    OCRHandler.do_POST(h)
    assert h._send_error_calls == [(404, 'Not Found')]


# ---------- /api/recognize ----------

def test_handle_recognize_invalid_path():
    """image_path 不存在 → 返回 success=False"""
    h = FakeHandler({'image_path': '/no/such/file.png'})
    OCRHandler._handle_recognize(h)
    assert last_json(h) == {'success': False, 'error': '图片路径无效'}


def test_handle_recognize_missing_path():
    """image_path 缺失 → 返回 success=False"""
    h = FakeHandler({})
    OCRHandler._handle_recognize(h)
    assert last_json(h) == {'success': False, 'error': '图片路径无效'}


def test_handle_recognize_success(tmp_path):
    """正常调用 → 返回识别文本"""
    real_img = tmp_path / "x.png"
    Image.new('RGB', (50, 50), color='white').save(real_img)

    with patch('image_to_text.web_gui.recognize_text', return_value='识别到的文字'):
        h = FakeHandler({'image_path': str(real_img)})
        OCRHandler._handle_recognize(h)
    assert last_json(h) == {'success': True, 'text': '识别到的文字'}


def test_handle_recognize_propagates_exception(tmp_path):
    """recognize_text 抛异常 → 返回 success=False + 错误信息"""
    real_img = tmp_path / "x.png"
    Image.new('RGB', (50, 50), color='white').save(real_img)

    with patch('image_to_text.web_gui.recognize_text', side_effect=RuntimeError("API 挂了")):
        h = FakeHandler({'image_path': str(real_img)})
        OCRHandler._handle_recognize(h)
    data = last_json(h)
    assert data['success'] is False
    assert 'API 挂了' in data['error']


# ---------- /api/recognize_file ----------

def test_handle_recognize_file_no_data():
    """image_data 为空 → success=False"""
    h = FakeHandler({'image_data': ''})
    OCRHandler._handle_recognize_file(h)
    assert last_json(h) == {'success': False, 'error': '未提供图片数据'}


def test_handle_recognize_file_success():
    """base64 图片 → 解码 → 调 recognizer"""
    img = Image.new('RGB', (50, 50), color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    data_uri = f'data:image/png;base64,{b64}'

    with patch('image_to_text.web_gui.recognize_text', return_value='OK') as mock_recognize:
        h = FakeHandler({'image_data': data_uri, 'filename': 'test.png'})
        OCRHandler._handle_recognize_file(h)
    assert last_json(h) == {'success': True, 'text': 'OK'}
    assert mock_recognize.call_count == 1


def test_handle_recognize_file_without_data_uri_prefix():
    """image_data 不带 'data:...,base64,' 前缀也应能正常解码"""
    img = Image.new('RGB', (10, 10), color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')

    with patch('image_to_text.web_gui.recognize_text', return_value='OK'):
        h = FakeHandler({'image_data': b64})
        OCRHandler._handle_recognize_file(h)
    assert last_json(h) == {'success': True, 'text': 'OK'}


def test_handle_recognize_file_bad_base64():
    """非法的 base64 → success=False"""
    # 用 validate=True 强制报错：binascii.Error
    # 直接 mock recognizer_text 让它看到 binascii.Error 之前就抛
    from binascii import Error as BinasciiError
    with patch('image_to_text.web_gui.recognize_text') as mock_recognize:
        mock_recognize.side_effect = BinasciiError("Invalid base64-encoded string")
        h = FakeHandler({'image_data': 'data:image/png;base64,@@@NOT_VALID@@@'})
        OCRHandler._handle_recognize_file(h)
    data = last_json(h)
    assert data['success'] is False
    assert 'error' in data


# ---------- /api/copy ----------

def test_handle_copy_empty_text():
    """text 为空 → success=False"""
    h = FakeHandler({'text': ''})
    OCRHandler._handle_copy(h)
    assert last_json(h) == {'success': False, 'error': '没有可复制的文本'}


def test_handle_copy_success():
    """正常复制 → success=True"""
    with patch('image_to_text.web_gui.copy_to_clipboard', return_value=True) as mock_copy:
        h = FakeHandler({'text': '要复制的内容'})
        OCRHandler._handle_copy(h)
    assert last_json(h) == {'success': True}
    mock_copy.assert_called_once_with('要复制的内容')


def test_handle_copy_failure():
    """剪贴板返回 False → success=False"""
    with patch('image_to_text.web_gui.copy_to_clipboard', return_value=False):
        h = FakeHandler({'text': 'x'})
        OCRHandler._handle_copy(h)
    assert last_json(h) == {'success': False, 'error': '复制到剪贴板失败'}
