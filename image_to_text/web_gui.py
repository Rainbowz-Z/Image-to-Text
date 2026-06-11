"""
Image-to-Text Web 界面
基于 HTTP Server + pywebview 的 Web GUI
"""
import sys
import os
import json
import base64
import tempfile
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from image_to_text.recognizer import recognize_text
from image_to_text.clipboard import copy_to_clipboard


# HTML 模板
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image-to-Text 文字识别</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }

        .container {
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            width: 100%;
            max-width: 900px;
            padding: 40px;
        }

        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            font-size: 28px;
        }

        .btn-area {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }

        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .btn:active {
            transform: scale(0.95);
        }

        .btn-primary {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }

        .btn-primary:hover {
            background: linear-gradient(135deg, #5a6fd6, #6a4192);
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }

        .btn-primary:disabled {
            background: #ccc;
            cursor: not-allowed;
            box-shadow: none;
        }

        .btn-secondary {
            background: linear-gradient(135deg, #f97316, #ea580c) !important;
            color: white !important;
        }

        .btn-secondary:hover {
            background: linear-gradient(135deg, #ea6306, #d9480c) !important;
            box-shadow: 0 4px 15px rgba(249, 115, 22, 0.4);
        }

        .btn-success {
            background: linear-gradient(135deg, #11998e, #38ef7d);
            color: white;
        }

        .btn-success:hover {
            background: linear-gradient(135deg, #0e8a7e, #2ed66d);
            box-shadow: 0 4px 15px rgba(17, 153, 142, 0.4);
        }

        .btn-success:disabled {
            background: #ccc;
            cursor: not-allowed;
            box-shadow: none;
        }

        .btn-toggle {
            background: linear-gradient(135deg, #4caf50, #45a049);
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .btn-toggle:hover {
            background: linear-gradient(135deg, #45a049, #3d8b40);
            box-shadow: 0 4px 15px rgba(76, 175, 80, 0.4);
        }

        .btn-toggle.active {
            background: linear-gradient(135deg, #ef5350, #e53935);
        }

        .btn-toggle.active:hover {
            background: linear-gradient(135deg, #e53935, #d32f2f);
            box-shadow: 0 4px 15px rgba(239, 83, 80, 0.4);
        }

        .preview-area {
            border: 2px dashed #ccc;
            border-radius: 12px;
            padding: 30px;
            text-align: center;
            margin-bottom: 20px;
            min-height: 200px;
            display: flex;
            justify-content: center;
            align-items: center;
            background: #fafafa;
        }

        .preview-area img {
            max-width: 100%;
            max-height: 300px;
            border-radius: 8px;
        }

        .preview-area .placeholder {
            color: #999;
            font-size: 16px;
        }

        .result-area {
            margin-top: 20px;
        }

        .result-area label {
            display: block;
            font-weight: 600;
            color: #333;
            margin-bottom: 8px;
            font-size: 16px;
        }

        .result-area textarea {
            width: 100%;
            min-height: 200px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            padding: 15px;
            font-size: 15px;
            line-height: 1.6;
            resize: vertical;
            font-family: inherit;
            transition: border-color 0.3s;
        }

        .result-area textarea:focus {
            outline: none;
            border-color: #667eea;
        }

        .status-bar {
            margin-top: 15px;
            padding: 10px 15px;
            background: #f5f5f5;
            border-radius: 8px;
            color: #666;
            font-size: 14px;
            text-align: center;
        }

        .spinner {
            display: none;
            width: 18px;
            height: 18px;
            border: 3px solid #ddd;
            border-radius: 50%;
            border-top-color: #667eea;
            animation: spin 0.8s ease-in-out infinite;
            margin-left: 8px;
            vertical-align: middle;
        }

        .spinner.active {
            display: inline-block;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Image-to-Text 文字识别</h1>

        <div class="btn-area">
            <button class="btn btn-primary" id="btnScreenshot" onclick="takeScreenshot()">
                &#x1f4f7; 截图识别
            </button>
            <button class="btn-toggle" id="btnToggleHide" onclick="toggleHideWindow()">
                &#x2705; 显示窗口
            </button>
            <button class="btn btn-secondary" id="btnSelect" onclick="selectImage()">
                &#x1f4c2; 选择图片
            </button>
            <button class="btn btn-success" id="btnCopy" onclick="copyResult()" disabled>
                &#x1f4cb; 复制结果
            </button>
        </div>

        <div class="preview-area" id="previewArea">
            <span class="placeholder">请截图或者选择图片...</span>
        </div>

        <div class="result-area">
            <label>识别结果：</label>
            <textarea id="resultText" readonly placeholder="识别结果将显示在这里..."></textarea>
        </div>

        <div class="status-bar" id="statusBar">就绪<span class="spinner" id="spinner"></span></div>
    </div>

    <!-- 隐藏的文件选择器 -->
    <input type="file" id="fileInput" accept="image/*" style="display:none" onchange="handleFileSelect(event)">

    <script>
        // 是否隐藏窗口（截图时先隐藏主窗口）
        let hideWindowEnabled = false;

        function toggleHideWindow() {
            hideWindowEnabled = !hideWindowEnabled;
            const btn = document.getElementById('btnToggleHide');
            if (hideWindowEnabled) {
                btn.classList.add('active');
                btn.innerHTML = '&#x274c; 隐藏窗口';
            } else {
                btn.classList.remove('active');
                btn.innerHTML = '&#x2705; 显示窗口';
            }
        }

        function setStatus(msg, showSpinner) {
            var bar = document.getElementById('statusBar');
            var spinner = document.getElementById('spinner');
            if (showSpinner === undefined) {
                // 默认：识别和截图时显示 spinner
                showSpinner = msg.indexOf('识别') !== -1 || msg.indexOf('截图') !== -1;
            }
            if (showSpinner) {
                spinner.classList.add('active');
            } else {
                spinner.classList.remove('active');
            }
            bar.textContent = msg;
            bar.appendChild(spinner);
        }

        function setButtonsEnabled(enabled) {
            document.getElementById('btnScreenshot').disabled = !enabled;
            document.getElementById('btnSelect').disabled = !enabled;
            document.getElementById('btnCopy').disabled = !enabled;
        }

        function showPreview(base64Data) {
            const area = document.getElementById('previewArea');
            area.innerHTML = '<img src="' + base64Data + '" alt="预览">';
        }

        function showPreviewPlaceholder() {
            const area = document.getElementById('previewArea');
            area.innerHTML = '<span class="placeholder">请选择图片或截图</span>';
        }

        function takeScreenshot() {
            setStatus('正在截图...');

            fetch('/api/screenshot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ hide_window: hideWindowEnabled })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showPreview(data.image_base64);
                    // 截图完成后，清空识别结果并显示加载提示
                    document.getElementById('resultText').value = '⏳ 识别中，请稍候...';
                    document.getElementById('btnCopy').disabled = true;
                    setStatus('截图成功，正在识别...', true);
                    return fetch('/api/recognize', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ image_path: data.temp_path })
                    });
                } else {
                    setStatus(data.error || '截图失败', false);
                    throw new Error(data.error);
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('resultText').value = data.text;
                    document.getElementById('btnCopy').disabled = !data.text;
                    setStatus('识别完成 - 共 ' + data.text.length + ' 个字符', false);
                } else {
                    setStatus('识别失败: ' + (data.error || '未知错误'), false);
                }
            })
            .catch(err => {
                if (err.message !== '截图失败') {
                    setStatus('请求失败: ' + err.message, false);
                }
            });
        }

        function selectImage() {
            document.getElementById('fileInput').click();
        }

        function handleFileSelect(event) {
            const file = event.target.files[0];
            if (!file) return;

            setStatus('正在读取图片...', true);
            setButtonsEnabled(false);

            const reader = new FileReader();
            reader.onload = function(e) {
                const base64Data = e.target.result;
                showPreview(base64Data);
                setStatus('图片已加载，正在识别...', true);

                fetch('/api/recognize_file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image_data: base64Data, filename: file.name })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('resultText').value = data.text;
                        document.getElementById('btnCopy').disabled = !data.text;
                        setStatus('识别完成 - 共 ' + data.text.length + ' 个字符', false);
                    } else {
                        setStatus('识别失败: ' + (data.error || '未知错误'), false);
                    }
                    setButtonsEnabled(true);
                })
                .catch(err => {
                    setStatus('请求失败: ' + err.message, false);
                    setButtonsEnabled(true);
                });
            };
            reader.readAsDataURL(file);

            // 重置 input 以便再次选择同一文件
            event.target.value = '';
        }

        function copyResult() {
            const text = document.getElementById('resultText').value;
            if (!text) return;

            fetch('/api/copy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    setStatus('已复制到剪贴板', false);
                } else {
                    setStatus('复制失败: ' + (data.error || '未知错误'), false);
                }
            })
            .catch(err => {
                setStatus('复制请求失败: ' + err.message, false);
            });
        }
    </script>
</body>
</html>"""


class OCRHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    def do_GET(self):
        """处理 GET 请求，返回 HTML 页面"""
        parsed = urlparse(self.path)
        if parsed.path == '/' or parsed.path == '/index.html':
            self._serve_html()
        else:
            self.send_error(404, 'Not Found')

    def do_POST(self):
        """处理 POST 请求"""
        parsed = urlparse(self.path)
        if parsed.path == '/api/screenshot':
            self._handle_screenshot()
        elif parsed.path == '/api/recognize':
            self._handle_recognize()
        elif parsed.path == '/api/recognize_file':
            self._handle_recognize_file()
        elif parsed.path == '/api/copy':
            self._handle_copy()
        else:
            self.send_error(404, 'Not Found')

    def _serve_html(self):
        """返回 HTML 页面"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(HTML_TEMPLATE.encode('utf-8'))

    def _json_response(self, data):
        """发送 JSON 响应"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _select_region(self):
        """区域截图选择器（直接集成，无需 subprocess）"""
        import pygame
        from PIL import ImageGrab

        # 截取全屏
        screenshot = ImageGrab.grab()
        screen_width, screen_height = screenshot.size

        # 初始化 pygame
        pygame.init()
        screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN)
        pygame.display.set_caption("左键选择第一个点，移动鼠标，再次左键确定 | ESC 退出")

        # 隐藏默认鼠标光标
        pygame.mouse.set_visible(False)

        # 将 PIL 图片转换为 pygame 表面
        screenshot_str = screenshot.tobytes()
        screenshot_surface = pygame.image.fromstring(screenshot_str, (screen_width, screen_height), 'RGB')

        # 创建半透明遮罩
        overlay = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))

        # 选区相关
        first_point = None
        mouse_pos = (0, 0)
        result_path = None

        # 十字光标
        cross_width = 2

        # 字体（支持中文）
        font = pygame.font.SysFont("microsoftyaheimicrosoftyaheiui,simhei,arial", 24)

        clock = pygame.time.Clock()
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # 左键
                        if first_point is None:
                            first_point = event.pos
                        else:
                            second_point = event.pos
                            x1, y1 = first_point
                            x2, y2 = second_point
                            left = min(x1, x2)
                            top = min(y1, y2)
                            width = abs(x2 - x1)
                            height = abs(y2 - y1)

                            if width > 10 and height > 10:
                                cropped = screenshot.crop((left, top, left + width, top + height))
                                temp_dir = tempfile.gettempdir()
                                result_path = os.path.join(temp_dir, "selected_region.png")
                                cropped.save(result_path)
                                running = False
                            else:
                                first_point = None

                    elif event.button == 3:  # 右键取消
                        first_point = None

                elif event.type == pygame.MOUSEMOTION:
                    mouse_pos = event.pos

            # 绘制
            screen.blit(screenshot_surface, (0, 0))
            screen.blit(overlay, (0, 0))

            # 绘制实时矩形
            if first_point:
                x1, y1 = first_point
                x2, y2 = mouse_pos
                left = min(x1, x2)
                top = min(y1, y2)
                width = abs(x2 - x1)
                height = abs(y2 - y1)

                pygame.draw.line(screen, (0, 255, 0), (left, top), (left, top + height), cross_width)
                pygame.draw.line(screen, (0, 255, 0), (left, top), (left + width, top), cross_width)

                if width > 50 and height > 20:
                    size_text = f"{width} x {height}"
                    text_surface = font.render(size_text, True, (255, 255, 255))
                    text_bg = pygame.Surface((text_surface.get_width() + 10, text_surface.get_height() + 6))
                    text_bg.fill((0, 0, 0))
                    text_bg.set_alpha(180)
                    screen.blit(text_bg, (left + 5, top - 30))
                    screen.blit(text_surface, (left + 10, top - 27))

            # 绘制绿色十字光标
            mx, my = mouse_pos
            if first_point:
                x1, y1 = first_point
                pygame.draw.line(screen, (0, 255, 0), (min(x1, mx), my), (max(x1, mx), my), cross_width)
                pygame.draw.line(screen, (0, 255, 0), (mx, min(y1, my)), (mx, max(y1, my)), cross_width)
            else:
                pygame.draw.line(screen, (0, 255, 0), (0, my), (screen_width, my), cross_width)
                pygame.draw.line(screen, (0, 255, 0), (mx, 0), (mx, screen_height), cross_width)

            # 显示提示信息
            if first_point is None:
                hint = "左键选择矩形左上角 | ESC 退出"
            else:
                hint = "移动鼠标，再次左键确定 | 右键取消 | ESC 退出"
            hint_surface = font.render(hint, True, (255, 255, 255))
            hint_bg = pygame.Surface((hint_surface.get_width() + 20, hint_surface.get_height() + 10))
            hint_bg.fill((0, 0, 0))
            hint_bg.set_alpha(180)
            screen.blit(hint_bg, (screen_width // 2 - hint_bg.get_width() // 2, 20))
            screen.blit(hint_surface, (screen_width // 2 - hint_surface.get_width() // 2, 25))

            pygame.display.flip()
            clock.tick(60)

        pygame.quit()
        return result_path

    def _handle_screenshot(self):
        """处理截图请求：调用区域选择器截图并返回 base64 图片"""
        try:
            import io
            import platform
            import time
            from PIL import Image

            # 读取请求体中的 hide_window 参数
            hide_window = False
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    body = self.rfile.read(content_length)
                    data = json.loads(body)
                    hide_window = data.get('hide_window', False)
            except:
                pass

            temp_path = os.path.join(tempfile.gettempdir(), "ocr_screenshot.png")

            # 根据参数决定是否隐藏主窗口
            window = None
            if hide_window:
                try:
                    import webview
                    window = webview.active_window()
                    if window:
                        window.hide()
                        time.sleep(0.3)
                except Exception as e:
                    print(f"隐藏窗口失败: {e}")

            if platform.system() == 'Windows':
                # Windows: 直接调用区域选择器
                selected_path = self._select_region()

                if selected_path and os.path.exists(selected_path):
                    screenshot = Image.open(selected_path)
                    screenshot.save(temp_path)
                    os.remove(selected_path)
                else:
                    # 用户取消了
                    if window:
                        try:
                            window.show()
                        except:
                            pass
                    self._json_response({'success': False, 'error': '已取消截图'})
                    return
            else:
                # Linux/Mac: 使用 scrot
                import subprocess
                env = os.environ.copy()
                env['DISPLAY'] = ':0'
                result = subprocess.run(['scrot', temp_path], env=env, capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f"scrot 截图失败: {result.stderr}")
                screenshot = Image.open(temp_path)

            # 转为 base64
            buffer = io.BytesIO()
            screenshot.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode()

            # 恢复窗口显示
            if window:
                try:
                    window.show()
                except:
                    pass

            self._json_response({
                'success': True,
                'temp_path': temp_path,
                'image_base64': 'data:image/png;base64,' + img_base64
            })
        except Exception as e:
            error_msg = str(e)
            self._json_response({'success': False, 'error': error_msg})
            # 恢复窗口显示
            try:
                import webview
                window = webview.active_window()
                if window:
                    window.show()
            except:
                pass

    def _handle_recognize(self):
        """处理 OCR 识别请求（通过临时文件路径）"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            image_path = data.get('image_path', '')
            if not image_path or not os.path.exists(image_path):
                self._json_response({'success': False, 'error': '图片路径无效'})
                return

            text = recognize_text(image_path)

            self._json_response({
                'success': True,
                'text': text
            })
        except Exception as e:
            self._json_response({'success': False, 'error': str(e)})

    def _handle_recognize_file(self):
        """处理 OCR 识别请求（通过 base64 图片数据）"""
        try:
            import io
            from PIL import Image

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            image_data = data.get('image_data', '')
            if not image_data:
                self._json_response({'success': False, 'error': '未提供图片数据'})
                return

            # 解析 base64 数据
            if ',' in image_data:
                header, encoded = image_data.split(',', 1)
            else:
                encoded = image_data

            img_bytes = base64.b64decode(encoded)

            # 保存为临时文件
            temp_path = os.path.join(tempfile.gettempdir(), "ocr_input.png")
            with open(temp_path, 'wb') as f:
                f.write(img_bytes)

            # OCR 识别
            text = recognize_text(temp_path)

            self._json_response({
                'success': True,
                'text': text
            })
        except Exception as e:
            self._json_response({'success': False, 'error': str(e)})

    def _handle_copy(self):
        """处理复制到剪贴板请求"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            text = data.get('text', '')
            if not text:
                self._json_response({'success': False, 'error': '没有可复制的文本'})
                return

            success = copy_to_clipboard(text)
            if success:
                self._json_response({'success': True})
            else:
                self._json_response({'success': False, 'error': '复制到剪贴板失败'})
        except Exception as e:
            self._json_response({'success': False, 'error': str(e)})

    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[HTTP] {args[0]}")


def main():
    """启动 Web 服务器"""
    port = 8080
    server = HTTPServer(('localhost', port), OCRHandler)
    print(f"Web 服务器已启动: http://localhost:{port}")
    print("按 Ctrl+C 停止服务器")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.server_close()


if __name__ == '__main__':
    main()
