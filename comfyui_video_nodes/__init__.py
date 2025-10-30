"""
Jimeng Video API ComfyUI Custom Nodes
即梦视频API ComfyUI自定义节点包
"""

from .jimeng_video import JimengVideo

# 节点映射
NODE_CLASS_MAPPINGS = {
    "Jimeng_Video": JimengVideo,
}

# 节点显示名称
NODE_DISPLAY_NAME_MAPPINGS = {
    "Jimeng_Video": "Jimeng Video (即梦-智能视频)",
}

# 节点版本
__version__ = "3.1.0"

# 导出所有
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

