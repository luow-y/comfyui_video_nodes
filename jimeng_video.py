"""
即梦API - 视频生成节点（自动判断文生视频/图生视频）
Jimeng API - Video Generation Node (Auto-detect Text2Video/Image2Video)
"""

import requests
import torch
import numpy as np
from PIL import Image
import io
import tempfile
import os
import json
import shutil
import cv2

# 兼容性导入
try:
    import folder_paths
except ImportError:
    # 如果无法导入，使用自定义路径
    class FolderPaths:
        @staticmethod
        def get_output_directory():
            return os.path.join(os.path.dirname(__file__), "output")
    folder_paths = FolderPaths()

try:
    from comfy.comfy_types import IO
except ImportError:
    # 如果无法导入，使用字符串类型
    class IOCompat:
        VIDEO = "VIDEO"
    IO = IOCompat()


class JimengVideoAdapter:
    """
    视频适配器，封装视频路径，使其能被ComfyUI的保存视频节点识别
    """
    def __init__(self, video_path: str):
        self.video_path = video_path
    
    def get_dimensions(self):
        """获取视频的宽度和高度"""
        try:
            if not self.video_path or not os.path.exists(self.video_path):
                return 1280, 720  # 默认值
            cap = cv2.VideoCapture(self.video_path)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            return width, height
        except Exception as e:
            print(f"[JimengVideoAdapter] 获取视频尺寸失败: {e}")
            return 1280, 720
    
    def save_to(self, output_path, format="auto", codec="auto", metadata=None):
        """保存视频到指定路径"""
        try:
            if self.video_path and os.path.exists(self.video_path):
                shutil.copyfile(self.video_path, output_path)
                return True
            else:
                print(f"[JimengVideoAdapter] 错误: 源视频文件路径无效: {self.video_path}")
                return False
        except Exception as e:
            print(f"[JimengVideoAdapter] 保存视频时出错: {e}")
            return False


class JimengVideo:
    """即梦API视频节点 - 自动判断文生视频或图生视频，自动读取号池配置"""
    
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.prefix_append = "jimeng_video"
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {
                    "default": "a cat walking in the street",
                    "multiline": True,
                    "forceInput": False,
                    "tooltip": "视频描述文本"
                }),
                "model": ([
                    "jimeng-video-3.0-pro",
                    "jimeng-video-3.0",
                    "jimeng-video-2.0-pro",
                    "jimeng-video-2.0"
                ], {
                    "default": "jimeng-video-3.0",
                    "forceInput": False,
                    "tooltip": "生成模型"
                }),
                "aspect_ratio": ([
                    "21:9",
                    "16:9",
                    "4:3",
                    "1:1",
                    "3:4",
                    "9:16"
                ], {
                    "default": "9:16",
                    "forceInput": False,
                    "tooltip": "视频比例"
                }),
                "resolution": ([
                    "720p",
                    "1080p"
                ], {
                    "default": "720p",
                    "forceInput": False,
                    "tooltip": "视频分辨率"
                }),
                "duration": ([
                    "5s",
                    "10s"
                ], {
                    "default": "5s",
                    "forceInput": False,
                    "tooltip": "视频时长（10s需要积分≥90）"
                }),
            },
            "optional": {
                "first_frame": ("IMAGE", {
                    "tooltip": "可选：首帧图片，不输入则为文生视频"
                }),
                "end_frame": ("IMAGE", {
                    "tooltip": "可选：尾帧图片"
                }),
                "api_url": ("STRING", {
                    "default": "http://localhost:5566",
                    "multiline": False,
                    "forceInput": False,
                    "tooltip": "API服务地址"
                }),
                "manual_session": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "forceInput": False,
                    "tooltip": "手动指定Session（为空则自动读取号池）"
                }),
            }
        }
    
    RETURN_TYPES = (IO.VIDEO, "STRING", "STRING")
    RETURN_NAMES = ("video", "video_url", "info")
    FUNCTION = "generate"
    CATEGORY = "Jimeng API"
    OUTPUT_NODE = False
    
    def calculate_dimensions(self, aspect_ratio, resolution):
        """根据比例和分辨率计算宽高"""
        # 基准高度
        base_height = 720 if resolution == "720p" else 1080
        
        # 比例映射到宽高
        ratio_map = {
            "21:9": (21, 9),
            "16:9": (16, 9),
            "4:3": (4, 3),
            "1:1": (1, 1),
            "3:4": (3, 4),
            "9:16": (9, 16)
        }
        
        w_ratio, h_ratio = ratio_map.get(aspect_ratio, (16, 9))
        
        # 根据比例计算宽度
        if h_ratio >= w_ratio:
            # 竖屏或方形，高度为基准
            height = base_height
            width = int(height * w_ratio / h_ratio)
        else:
            # 横屏，宽度为基准
            width = int(base_height * 16 / 9)  # 以16:9的宽度为基准
            height = int(width * h_ratio / w_ratio)
        
        # 确保是64的倍数
        width = (width // 64) * 64
        height = (height // 64) * 64
        
        return width, height
    
    def get_session_id(self, manual_session, duration="5s", api_url="http://localhost:5566"):
        """
        获取号池中的所有Session（后端会根据时长自动选择积分足够的）
        """
        if manual_session and manual_session.strip():
            print(f"🔑 使用手动指定的Session")
            return manual_session.strip()
        
        # 根据时长确定所需积分
        min_credits = 90 if duration == "10s" else 45
        
        # 从后端读取号池配置
        try:
            url = f"{api_url}/admin/session-pool"
            print(f"🔗 读取号池配置...")
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    sessions = data.get('data', {}).get('sessionUSList', [])
                    pool_size = len(sessions)
                    
                    if pool_size == 0:
                        raise Exception('号池为空，请先添加Session')
                    
                    # 将所有session用逗号拼接，后端会自动根据时长选择积分足够的
                    all_sessions = ','.join(sessions)
                    print(f"✅ 读取号池成功（共{pool_size}个Session，后端将自动选择积分>={min_credits}分的）")
                    return all_sessions
                else:
                    error_msg = data.get('message', '读取号池失败')
                    print(f"❌ {error_msg}")
                    raise Exception(error_msg)
            else:
                raise Exception(f"API返回错误状态码: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ 无法连接到API服务: {api_url}")
            print(f"💡 解决方法:")
            print(f"   1. 确保即梦API服务已启动")
            print(f"   2. 检查端口是否正确: {api_url}")
            print(f"   3. 或在节点的 manual_session 参数中手动输入Session")
            raise Exception(f"无法连接到API服务: {api_url}")
        except Exception as e:
            print(f"❌ 读取号池失败: {e}")
            raise
    
    def tensor_to_pil(self, tensor):
        """将ComfyUI的tensor转换为PIL图片"""
        img_array = tensor[0].cpu().numpy()
        img_array = (img_array * 255).astype(np.uint8)
        return Image.fromarray(img_array)
    
    def generate_video(self, api_url, session_id, prompt, model, width, height, 
                      resolution, duration="5s", first_frame=None, end_frame=None):
        """生成视频"""
        url = f"{api_url}/v1/videos/generations"
        
        headers = {
            "Authorization": f"Bearer {session_id}"
        }
        
        # 判断是否有图片输入
        if first_frame is None and end_frame is None:
            # 纯文生视频
            print(f"📝 模式: 文生视频 (Text to Video)")
            payload = {
                "model": model,
                "prompt": prompt,
                "width": width,
                "height": height,
                "resolution": resolution,
                "duration": duration
            }
            
            headers["Content-Type"] = "application/json"
            response = requests.post(url, headers=headers, json=payload, timeout=900)
            
        else:
            # 图生视频
            frame_count = sum([1 for f in [first_frame, end_frame] if f is not None])
            print(f"🖼️  模式: 图生视频 (Image to Video) - {frame_count}张图片")
            
            # 创建临时文件
            temp_files = []
            files_data = []
            
            try:
                if first_frame is not None:
                    pil_img = self.tensor_to_pil(first_frame)
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                    pil_img.save(temp_file.name, format='PNG')
                    temp_file.close()
                    temp_files.append(temp_file.name)
                    files_data.append(('image1', (f'first_frame.png', open(temp_file.name, 'rb'), 'image/png')))
                
                if end_frame is not None:
                    pil_img = self.tensor_to_pil(end_frame)
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                    pil_img.save(temp_file.name, format='PNG')
                    temp_file.close()
                    temp_files.append(temp_file.name)
                    files_data.append(('image2', (f'end_frame.png', open(temp_file.name, 'rb'), 'image/png')))
                
                data = {
                    "prompt": prompt,
                    "model": model,
                    "width": str(width),
                    "height": str(height),
                    "resolution": resolution,
                    "duration": duration
                }
                
                print(f"🌐 发送图生视频请求: {url}")
                response = requests.post(url, headers=headers, files=files_data, data=data, timeout=900)
                
                # 关闭文件句柄
                for _, file_tuple in files_data:
                    file_tuple[1].close()
                
            finally:
                # 清理临时文件
                for temp_file_path in temp_files:
                    try:
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {e}")
        
        if response.status_code == 200:
            result = response.json()
            video_data = result.get("data", [])
            if video_data and len(video_data) > 0:
                video_url = video_data[0].get("url")
                if video_url:
                    return video_url
        
        raise Exception(f"API错误 {response.status_code}: {response.text}")
    
    def download_video(self, video_url, prompt):
        """下载视频到本地"""
        try:
            import time
            from datetime import datetime
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_prompt = "".join(c for c in prompt[:30] if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_prompt = safe_prompt.replace(' ', '_')
            filename = f"jimeng_video_{timestamp}_{safe_prompt}.mp4"
            
            # 完整路径
            output_path = os.path.join(self.output_dir, filename)
            
            print(f"📥 开始下载视频...")
            print(f"📂 保存路径: {output_path}")
            
            # 下载视频
            response = requests.get(video_url, stream=True, timeout=120)
            response.raise_for_status()
            
            # 保存文件
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
            print(f"✅ 视频下载成功！大小: {file_size:.2f} MB")
            
            return filename
            
        except Exception as e:
            print(f"❌ 下载视频失败: {e}")
            raise
    
    def generate(self, prompt, model, aspect_ratio, resolution, duration,
                first_frame=None, end_frame=None,
                api_url="http://localhost:5566", manual_session=""):
        """统一生成接口 - 自动判断文生视频或图生视频"""
        
        print(f"\n{'='*60}")
        print(f"🎬 即梦API - 视频生成节点")
        print(f"{'='*60}")
        
        try:
            # 根据比例和分辨率计算宽高
            width, height = self.calculate_dimensions(aspect_ratio, resolution)
            print(f"📐 比例: {aspect_ratio} → 尺寸: {width}x{height}")
            
            # 获取可用的视频Session（后端会根据时长检查积分）
            session_id = self.get_session_id(manual_session, duration, api_url)
            
            # 判断模式
            mode = "文生视频" if first_frame is None and end_frame is None else "图生视频"
            print(f"📝 提示词: {prompt[:50]}...")
            print(f"🎭 模型: {model}")
            print(f"📺 分辨率: {resolution}")
            print(f"⏰ 时长: {duration}")
            print(f"⏳ 生成中，请耐心等待（可能需要3-15分钟）...")
            
            video_url = self.generate_video(
                api_url, session_id, prompt, model, width, height,
                resolution, duration, first_frame, end_frame
            )
            
            print(f"✅ 视频生成成功！")
            print(f"🔗 视频URL: {video_url}")
            
            # 下载视频到本地
            filename = self.download_video(video_url, prompt)
            
            # 构建完整路径
            video_path = os.path.join(self.output_dir, filename)
            
            # 生成信息文本
            info_text = (
                f"🎬 模式: {mode}\n"
                f"🎭 模型: {model}\n"
                f"📐 尺寸: {width}x{height}\n"
                f"📺 分辨率: {resolution}\n"
                f"⏰ 时长: {duration}\n"
                f"📁 文件: {filename}\n"
                f"💬 提示词: {prompt}"
            )
            
            print(f"✨ 完成！文件: {filename}")
            print(f"📂 路径: {video_path}")
            print(f"{'='*60}\n")
            
            # 返回视频适配器对象、URL和信息
            video_adapter = JimengVideoAdapter(video_path)
            return (video_adapter, video_url, info_text)
            
        except requests.exceptions.Timeout:
            error_msg = "请求超时，视频生成时间较长，请稍后在即梦官网查看"
            print(f"❌ {error_msg}")
            print(f"{'='*60}\n")
            return (JimengVideoAdapter(""), "", f"错误: {error_msg}")
            
        except requests.exceptions.ConnectionError:
            error_msg = "连接失败，请确认API服务已启动"
            print(f"❌ {error_msg}")
            print(f"{'='*60}\n")
            return (JimengVideoAdapter(""), "", f"错误: {error_msg}")
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 生成失败: {error_msg}")
            print(f"{'='*60}\n")
            return (JimengVideoAdapter(""), "", f"错误: {error_msg}")


# ComfyUI节点注册
NODE_CLASS_MAPPINGS = {
    "Jimeng_Video": JimengVideo
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Jimeng_Video": "Jimeng Video (即梦-智能视频)"
}

# 用于直接导入
if __name__ == "__main__":
    print("此文件是ComfyUI节点，请在ComfyUI中使用")

