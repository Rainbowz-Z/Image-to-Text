"""
Image-to-Text 桌面应用 (pywebview 版)
使用原生窗口，无需 Tcl/Tk
"""
import sys
import os
import threading
import time
from http.server import HTTPServer

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from image_to_text.web_gui import OCRHandler

# 全局窗口对象（存储在模块级别）
_window = None
_window_ready = False


def get_window():
    """获取 pywebview 窗口对象"""
    print(f"[DEBUG] get_window() called, _window={_window}")
    return _window


def is_window_ready():
    """检查窗口是否已创建"""
    return _window_ready


def start_server(port=8080):
    """在后台启动 HTTP 服务器"""
    server = HTTPServer(('localhost', port), OCRHandler)
    server.serve_forever()


def main():
    global _window, _window_ready
    port = 8080

    # 在后台线程启动服务器
    server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    server_thread.start()

    # 等待服务器启动
    time.sleep(0.5)

    try:
        import webview

        # 创建原生窗口
        _window = webview.create_window(
            title="Image-to-Text 文字识别",
            url=f'http://localhost:{port}',
            width=950,
            height=820,
            resizable=True,
            text_select=True,
        )
        _window_ready = True
        print(f"[DEBUG] 窗口已创建: {_window}")

        # 启动 pywebview（阻塞直到窗口关闭）
        webview.start(debug=False)

    except ImportError:
        print("错误: 请先安装 pywebview")
        print("运行: pip install pywebview")
        sys.exit(1)
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
