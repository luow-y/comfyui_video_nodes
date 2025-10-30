# Jimeng Video (即梦视频) - ComfyUI节点

即梦AI视频生成的ComfyUI自定义节点，支持文生视频和图生视频。

## 功能特性

- ✅ 文生视频（Text to Video）
- ✅ 图生视频（Image to Video）
- ✅ 首尾帧视频（需要两张图片）
- ✅ 自动号池管理
- ✅ 多模型支持

## 安装方法

### 方法1：通过ComfyUI Manager安装

1. 打开ComfyUI Manager
2. 点击"Install Custom Nodes"
3. 搜索"Jimeng Video"或输入仓库地址
4. 点击安装

### 方法2：手动安装

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/luow-y/comfyui_video_nodes.git
cd comfyui_video_nodes
pip install -r requirements.txt
```

## 使用前提

1. **启动即梦API服务**
   - 确保即梦API服务已运行在 `http://localhost:5566`
   - 或在节点中指定自定义API地址

2. **配置号池**
   - 访问 `http://localhost:5566/admin.html`
   - 添加即梦账号的Session ID

## 节点说明

### Jimeng_Video（即梦-智能视频）

自动判断文生视频或图生视频模式。

**输入参数：**
- `prompt` (必需): 视频描述文本
- `model` (必需): 视频模型（jimeng-video-3.0、jimeng-video-2.0等）
- `aspect_ratio` (必需): 视频比例（16:9、9:16、1:1等）
- `resolution` (必需): 视频分辨率（720p、1080p）
- `first_frame` (可选): 首帧图片，不输入则为文生视频
- `end_frame` (可选): 尾帧图片（仅3.0-pro支持）
- `api_url` (可选): API地址（默认localhost:5566）
- `manual_session` (可选): 手动指定Session

**输出：**
- `video`: 视频对象（可连接SaveVideo节点）
- `video_url`: 视频下载地址
- `info`: 生成信息

## 视频模型说明

| 模型 | 积分消耗 | 特性 |
|------|----------|------|
| jimeng-video-3.0-pro | 20分 | 最高质量，支持首尾帧 |
| jimeng-video-3.0 | 5分 | 高质量 |
| jimeng-video-2.0-pro | 15分 | 标准pro版本 |
| jimeng-video-2.0 | 5分 | 标准版本 |

## 示例工作流

见项目根目录的 `文生视频.json` 和 `图生视频.json`

## 常见问题

### Q: 提示"无法连接到API服务"
A: 请确保即梦API服务已启动在 `http://localhost:5566`

### Q: 提示"号池为空"
A: 请访问管理页面添加Session ID

### Q: 视频生成很慢
A: 视频生成通常需要3-15分钟，请耐心等待

### Q: 提示"积分不足"
A: 视频生成需要较多积分（5-20分），请确保账号积分充足

### Q: 视频无法播放
A: 确保连接了SaveVideo节点来保存视频文件

## 注意事项

1. 视频生成时间较长，请耐心等待
2. 首尾帧视频目前仅支持3.0-pro模型
3. 视频会自动下载到ComfyUI的output目录

## 更新日志

### v3.1.0 (2025-10-30)
- 修复节点命名格式（改为下划线格式）
- 添加导入错误处理
- 添加ComfyUI版本兼容性处理
- 优化依赖管理

## 许可证

MIT License

## 相关链接

- 即梦API: https://github.com/luow-y/jimeng-api
- 即梦图片节点: https://github.com/luow-y/comfyui_nodes

