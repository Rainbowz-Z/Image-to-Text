import subprocess
import platform
import os


def copy_to_clipboard(text: str) -> bool:
    """
    将文本复制到系统剪贴板

    Args:
        text: 要复制的文本

    Returns:
        bool: 是否成功复制
    """
    system = platform.system()

    try:
        if system == 'Darwin':  # macOS
            encoded = text.encode('utf-8')
            subprocess.run(['pbcopy'], input=encoded, check=True)
        elif system == 'Linux':
            encoded = text.encode('utf-8')
            subprocess.run(['xclip', '-selection', 'clipboard'], input=encoded, check=True)
        elif system == 'Windows':
            # Windows 使用 GBK 编码，并切换到 C 盘避免 UNC 路径问题
            encoded = text.encode('gbk', errors='ignore')
            # 切换到 C 盘避免 UNC 路径问题
            original_dir = os.getcwd()
            try:
                os.chdir('C:\\')
                subprocess.run(['clip'], input=encoded, shell=True, check=True)
            finally:
                os.chdir(original_dir)
        else:
            print(f"不支持的操作系统: {system}")
            return False
        return True
    except FileNotFoundError:
        print(f"未找到剪贴板工具，请安装 xclip (Linux)")
        return False
    except subprocess.CalledProcessError as e:
        print(f"复制到剪贴板失败: {e}")
        return False
