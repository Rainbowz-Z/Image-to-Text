"""
pytest 全局配置
- 把项目根目录加入 sys.path，让 `import image_to_text` 在 tests/ 里也能工作
- 屏蔽 pygame 启动时 pkg_resources 的 deprecation warning（pygame 内部依赖）
"""
import sys
import os
import warnings

# 把项目根目录加进 path（项目根 = conftest.py 的父目录的父目录）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 屏蔽 pygame import 时抛的 pkg_resources 弃用 warning（与项目代码无关）
warnings.filterwarnings(
    "ignore",
    message=".*pkg_resources is deprecated.*",
    category=UserWarning,
)
