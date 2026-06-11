import os
import base64
import configparser
from openai import OpenAI


def _load_config():
    """加载配置文件"""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
    config.read(config_path, encoding='utf-8')
    return config


def recognize_text(image_path: str) -> str:
    """
    识别图片中的文字（调用豆包 Doubao API）

    Args:
        image_path: 图片文件路径

    Returns:
        识别到的文本
    """
    # 加载配置
    config = _load_config()
    api_key = config.get('api', 'api_key')
    endpoint_id = config.get('api', 'endpoint_id')
    base_url = config.get('api', 'base_url', fallback='https://ark.cn-beijing.volces.com/api/v3')

    # 读取图片并检查尺寸，太小则放大
    from PIL import Image
    img = Image.open(image_path)
    width, height = img.size
    if width < 14 or height < 14:
        scale = max(14 / width, 14 / height)
        new_width = int(width * scale)
        new_height = int(height * scale)
        img = img.resize((new_width, new_height), Image.LANCZOS)
        # 保存到临时文件
        import io
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
    else:
        # 转为 base64
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

    # 获取图片格式
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.bmp': 'image/bmp'}
    mime_type = mime_map.get(ext, 'image/png')

    # 创建客户端
    client = OpenAI(
        base_url=base_url,
        api_key=api_key
    )

    # 调用豆包 API
    response = client.chat.completions.create(
        model=endpoint_id,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "请识别图片中的所有文字，保持原始排版格式，直接输出纯文本内容，不要使用Markdown格式，不要添加任何解释。"
                    }
                ]
            }
        ],
        temperature=0.1,
        max_tokens=4096
    )

    result = response.choices[0].message.content

    # 如果返回的是"未识别到"或"无"之类的提示，返回空字符串
    if result and ("未识别" in result or result.strip() == "无"):
        return ""

    return result
