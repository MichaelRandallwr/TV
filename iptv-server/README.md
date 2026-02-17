# IPTV 直播源自动管理服务

一个完整的 IPTV 直播源自动管理系统，支持自动抓取、检测、更新直播源，并提供 HTTP 服务分发频道列表。

## 功能特性

- 🚀 **一键安装**：自动安装所有依赖，配置服务和定时任务
- 🔄 **自动更新**：每 6 小时自动抓取和检测上游源
- ✅ **存活检测**：使用 ffprobe 并发检测流可用性，按延迟排序
- 🌐 **HTTP 服务**：内置 HTTP 服务器，支持 CORS，可直接在电视盒子上使用
- 📱 **多格式支持**：支持 TXT 和 M3U 两种格式的上游源
- 🔧 **易于扩展**：可轻松添加更多上游源
- 💾 **多种输出**：生成 live.txt（最优源）、live_multi.txt（多备用源）和 config.json（TV APP 配置）

## 系统要求

- Ubuntu 20.04 / 22.04 / 24.04
- root 权限
- 互联网连接

## 快速开始

### 一键安装

```bash
cd iptv-server
sudo bash install.sh
```

安装脚本会自动完成：
1. 安装所有依赖（Python3、pip、ffmpeg、requests）
2. 注册 systemd 服务，实现开机自启
3. 设置 crontab 定时任务，每 6 小时自动更新
4. 执行首次源抓取和检测
5. 启动 HTTP 服务（8080 端口）

### 在 TV APP 中使用

安装完成后，在您的 TV APP（如 FongMi 影视）中添加配置地址：

```
http://你的服务器IP:8080/config.json
```

或直接使用直播源文件：

```
http://你的服务器IP:8080/live.txt
```

## 目录结构

```
iptv-server/
├── install.sh          # 一键安装脚本
├── iptv_manager.py     # 核心 Python 程序
├── update.sh           # 定时更新脚本
├── iptv.service        # systemd 服务文件
├── README.md           # 使用说明
├── output/             # 输出目录
│   ├── config.json     # TV APP 配置文件
│   ├── live.txt        # 单源直播列表（最快源）
│   └── live_multi.txt  # 多源直播列表（含备用源）
└── logs/               # 日志目录
    ├── service.log     # 服务日志
    ├── manager.log     # 管理器日志
    └── update.log      # 更新日志
```

## 使用方法

### 服务管理

```bash
# 查看服务状态
systemctl status iptv

# 启动服务
systemctl start iptv

# 停止服务
systemctl stop iptv

# 重启服务
systemctl restart iptv

# 查看实时日志
journalctl -u iptv -f
```

### 手动更新源

```bash
# 方式 1：使用更新脚本
/opt/iptv-server/update.sh

# 方式 2：直接使用 Python 程序
cd /opt/iptv-server
python3 iptv_manager.py update
```

### 访问输出文件

安装完成后，可以通过以下地址访问：

- **config.json**（TV APP 配置）：`http://服务器IP:8080/config.json`
- **live.txt**（单源列表）：`http://服务器IP:8080/live.txt`
- **live_multi.txt**（多源列表）：`http://服务器IP:8080/live_multi.txt`

## 高级配置

### 添加更多上游源

编辑 `/opt/iptv-server/iptv_manager.py` 文件，找到 `UPSTREAM_SOURCES` 列表：

```python
UPSTREAM_SOURCES = [
    "https://live.zbds.top/tv/iptv4.txt",
    "https://iptv-org.github.io/iptv/countries/cn.m3u",
    # 在这里添加更多上游源
    "你的上游源地址1",
    "你的上游源地址2",
]
```

修改后重启服务：

```bash
systemctl restart iptv
```

### 修改监听端口

1. 编辑 `/opt/iptv-server/iptv_manager.py`，找到 `start_http_server` 函数，修改默认端口：

```python
def start_http_server(port=8080):  # 修改为你想要的端口
```

2. 编辑 `/etc/systemd/system/iptv.service`，如果需要传递端口参数

3. 重新加载服务：

```bash
systemctl daemon-reload
systemctl restart iptv
```

### 修改更新频率

```bash
# 编辑 crontab
crontab -e

# 修改定时任务
# 默认：0 */6 * * * /opt/iptv-server/update.sh  # 每 6 小时
# 改为：0 */3 * * * /opt/iptv-server/update.sh  # 每 3 小时
# 或者：0 0 * * * /opt/iptv-server/update.sh    # 每天凌晨
```

### 调整检测参数

编辑 `/opt/iptv-server/iptv_manager.py`：

```python
MAX_WORKERS = 20  # 并发检测线程数（可根据服务器性能调整）
TIMEOUT = 8       # 超时时间（秒）
```

修改后重启服务生效。

## 输出格式说明

### live.txt 格式

每个频道只保留最快的一个源，格式如下：

```
央视频道,#genre#
CCTV1,http://xxx.xxx.xxx/cctv1.m3u8
CCTV2,http://xxx.xxx.xxx/cctv2.m3u8

卫视频道,#genre#
湖南卫视,http://xxx.xxx.xxx/hunan.m3u8
浙江卫视,http://xxx.xxx.xxx/zhejiang.m3u8
```

### live_multi.txt 格式

每个频道保留多个备用源，附带延迟信息：

```
央视频道,#genre#
CCTV1 (120ms),http://xxx.xxx.xxx/cctv1.m3u8
CCTV1 (350ms),http://yyy.yyy.yyy/cctv1.m3u8
CCTV2 (95ms),http://xxx.xxx.xxx/cctv2.m3u8
```

### config.json 格式

适用于支持 JSON 配置的 TV APP：

```json
{
  "spider": "",
  "lives": [
    {
      "name": "直播",
      "type": 0,
      "url": "http://{host}:8080/live.txt",
      "epg": "https://epg.112114.xyz",
      "logo": "https://epg.112114.xyz/logo/{name}.png"
    }
  ]
}
```

## 常见问题

### 1. 服务启动失败

检查日志：

```bash
journalctl -u iptv -n 50
```

常见原因：
- 端口 8080 被占用：修改监听端口
- Python 依赖未安装：手动运行 `pip3 install requests`
- ffmpeg 未安装：运行 `apt-get install ffmpeg`

### 2. 无法访问 HTTP 服务

检查防火墙设置：

```bash
# Ubuntu/Debian
ufw allow 8080/tcp

# 或检查 iptables
iptables -L -n | grep 8080
```

### 3. 源检测太慢

调整并发数和超时参数：

```python
MAX_WORKERS = 30  # 增加并发数
TIMEOUT = 5       # 减少超时时间
```

### 4. 定时任务不执行

检查 crontab 是否正确设置：

```bash
crontab -l | grep iptv
```

查看更新日志：

```bash
tail -f /opt/iptv-server/logs/update.log
```

### 5. 频道列表为空

可能原因：
- 上游源无法访问
- 所有流都检测失败
- 网络问题

查看日志排查：

```bash
cat /opt/iptv-server/logs/manager.log
```

## 卸载方法

```bash
# 1. 停止并禁用服务
systemctl stop iptv
systemctl disable iptv

# 2. 删除服务文件
rm /etc/systemd/system/iptv.service
systemctl daemon-reload

# 3. 删除 crontab 任务
crontab -e
# 手动删除包含 /opt/iptv-server/update.sh 的行

# 4. 删除安装目录
rm -rf /opt/iptv-server

# 5. （可选）卸载依赖
# 如果这些依赖不被其他程序使用，可以卸载：
# apt-get remove ffmpeg
# pip3 uninstall requests
```

## 技术栈

- **Python 3**：核心程序语言
- **requests**：HTTP 请求库
- **ffprobe**：流媒体检测工具
- **systemd**：服务管理
- **crontab**：定时任务

## 上游源说明

本项目默认使用以下公开上游源：

1. https://live.zbds.top/tv/iptv4.txt
2. https://iptv-org.github.io/iptv/countries/cn.m3u

感谢这些开源项目的贡献者！

## 许可证

本项目采用 MIT 许可证。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 注意事项

1. 本项目仅供学习交流使用
2. 请遵守相关法律法规和版权要求
3. 上游源的可用性和内容由源提供者负责
4. 建议在内网环境使用，避免暴露到公网

## 更新日志

### v1.0.0 (2024-01)

- 初始版本发布
- 支持 TXT 和 M3U 格式源抓取
- 实现并发流检测
- 提供 HTTP 服务
- 支持定时自动更新
- 完整的安装和部署脚本
