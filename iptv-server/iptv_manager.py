#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import subprocess
import threading
import requests
from urllib.parse import urlparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置
UPSTREAM_SOURCES = [
    "https://live.zbds.top/tv/iptv4.txt",
    "https://iptv-org.github.io/iptv/countries/cn.m3u"
]

MAX_WORKERS = 20  # 并发检测线程数
TIMEOUT = 8  # 超时时间（秒）
OUTPUT_DIR = "output"
LOG_DIR = "logs"

# EPG 和台标地址
EPG_URL = "https://epg.112114.xyz"
LOGO_URL = "https://epg.112114.xyz/logo/{name}.png"


class IPTVManager:
    def __init__(self):
        self.channels = {}  # {频道名: [(url, group, delay), ...]}
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(self.base_dir, OUTPUT_DIR)
        self.log_dir = os.path.join(self.base_dir, LOG_DIR)
        
        # 确保目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

    def log(self, message):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        
        # 写入日志文件
        log_file = os.path.join(self.log_dir, "manager.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_message + "\n")

    def fetch_sources(self):
        """从上游源抓取频道列表"""
        self.log("开始抓取上游源...")
        
        for source_url in UPSTREAM_SOURCES:
            try:
                self.log(f"正在抓取: {source_url}")
                response = requests.get(source_url, timeout=30)
                response.encoding = 'utf-8'
                content = response.text
                
                if source_url.endswith('.m3u') or '#EXTM3U' in content:
                    self._parse_m3u(content, source_url)
                else:
                    self._parse_txt(content, source_url)
                    
                self.log(f"抓取成功: {source_url}")
            except Exception as e:
                self.log(f"抓取失败 {source_url}: {str(e)}")
        
        total_channels = len(self.channels)
        total_urls = sum(len(urls) for urls in self.channels.values())
        self.log(f"抓取完成，共获取 {total_channels} 个频道，{total_urls} 个源地址")

    def _parse_m3u(self, content, source_url):
        """解析 M3U 格式"""
        lines = content.split('\n')
        current_name = None
        current_group = "未分组"
        
        for line in lines:
            line = line.strip()
            if line.startswith('#EXTINF:'):
                # 解析频道名和分组
                parts = line.split(',', 1)
                if len(parts) == 2:
                    current_name = parts[1].strip()
                    
                # 提取分组信息
                if 'group-title="' in line:
                    start = line.index('group-title="') + 13
                    end = line.index('"', start)
                    current_group = line[start:end]
                    
            elif line and not line.startswith('#') and current_name:
                # 这是URL行
                url = line.strip()
                if url:
                    if current_name not in self.channels:
                        self.channels[current_name] = []
                    self.channels[current_name].append((url, current_group, None))
                current_name = None

    def _parse_txt(self, content, source_url):
        """解析 TXT 格式 (频道名,URL 或 频道名#分组,URL)"""
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            parts = line.split(',', 1)
            if len(parts) != 2:
                continue
                
            name_part = parts[0].strip()
            url = parts[1].strip()
            
            # 解析频道名和分组
            if '#' in name_part:
                name, group = name_part.split('#', 1)
                name = name.strip()
                group = group.strip()
            else:
                name = name_part
                group = "未分组"
            
            if name and url:
                if name not in self.channels:
                    self.channels[name] = []
                self.channels[name].append((url, group, None))

    def check_stream(self, url):
        """使用 ffprobe 检测流是否可用"""
        try:
            start_time = time.time()
            
            # 使用 ffprobe 检测流
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                '-timeout', str(TIMEOUT * 1000000),  # 微秒
                url
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=TIMEOUT,
                check=False
            )
            
            elapsed = time.time() - start_time
            
            if result.returncode == 0:
                # 验证是否有有效的流信息
                try:
                    data = json.loads(result.stdout.decode('utf-8'))
                    if 'streams' in data and len(data['streams']) > 0:
                        return True, round(elapsed * 1000)  # 返回毫秒
                except (json.JSONDecodeError, UnicodeDecodeError, KeyError):
                    pass
            
            return False, None
            
        except subprocess.TimeoutExpired:
            return False, None
        except Exception as e:
            return False, None

    def check_all_streams(self):
        """并发检测所有流地址"""
        self.log(f"开始检测流可用性（并发数: {MAX_WORKERS}）...")
        
        # 准备检测任务
        tasks = []
        for name, urls in self.channels.items():
            for url, group, _ in urls:
                tasks.append((name, url, group))
        
        total = len(tasks)
        checked = 0
        available = 0
        
        # 使用线程池并发检测
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_task = {
                executor.submit(self.check_stream, url): (name, url, group)
                for name, url, group in tasks
            }
            
            for future in as_completed(future_to_task):
                name, url, group = future_to_task[future]
                checked += 1
                
                try:
                    is_available, delay = future.result()
                    
                    if is_available:
                        available += 1
                        # 更新频道信息
                        if name in self.channels:
                            # 找到并更新延迟信息
                            for i, (u, g, _) in enumerate(self.channels[name]):
                                if u == url:
                                    self.channels[name][i] = (u, g, delay)
                                    break
                    else:
                        # 移除不可用的源
                        if name in self.channels:
                            self.channels[name] = [
                                (u, g, d) for u, g, d in self.channels[name]
                                if u != url
                            ]
                    
                    # 进度显示
                    if checked % 10 == 0 or checked == total:
                        self.log(f"检测进度: {checked}/{total}, 可用: {available}")
                        
                except Exception as e:
                    self.log(f"检测异常 {name}: {str(e)}")
        
        # 清理没有可用源的频道
        self.channels = {
            name: urls for name, urls in self.channels.items()
            if urls and any(delay is not None for _, _, delay in urls)
        }
        
        self.log(f"检测完成，可用频道: {len(self.channels)}, 可用源: {available}")

    def sort_channels(self):
        """按延迟排序每个频道的源"""
        for name in self.channels:
            # 按延迟排序（延迟小的在前）
            self.channels[name].sort(key=lambda x: x[2] if x[2] is not None else float('inf'))

    def generate_live_txt(self):
        """生成 live.txt（每个频道只保留最快的源）"""
        output_file = os.path.join(self.output_dir, "live.txt")
        
        # 按频道名排序
        sorted_channels = sorted(self.channels.items())
        
        with open(output_file, 'w', encoding='utf-8') as f:
            current_group = None
            
            for name, urls in sorted_channels:
                if not urls:
                    continue
                
                # 获取最快的源
                best_url, group, delay = urls[0]
                
                # 写入分组标题
                if group != current_group:
                    if current_group is not None:
                        f.write('\n')
                    f.write(f"{group},#genre#\n")
                    current_group = group
                
                # 写入频道
                f.write(f"{name},{best_url}\n")
        
        self.log(f"已生成: {output_file}")

    def generate_live_multi_txt(self):
        """生成 live_multi.txt（每个频道保留多个备用源）"""
        output_file = os.path.join(self.output_dir, "live_multi.txt")
        
        # 按频道名排序
        sorted_channels = sorted(self.channels.items())
        
        with open(output_file, 'w', encoding='utf-8') as f:
            current_group = None
            
            for name, urls in sorted_channels:
                if not urls:
                    continue
                
                group = urls[0][1]  # 所有URL应该有相同的分组
                
                # 写入分组标题
                if group != current_group:
                    if current_group is not None:
                        f.write('\n')
                    f.write(f"{group},#genre#\n")
                    current_group = group
                
                # 写入所有可用源
                for url, _, delay in urls:
                    delay_str = f" ({delay}ms)" if delay else ""
                    f.write(f"{name}{delay_str},{url}\n")
        
        self.log(f"已生成: {output_file}")

    def generate_config_json(self):
        """生成 config.json（供 TV APP 使用）"""
        output_file = os.path.join(self.output_dir, "config.json")
        
        # 构建配置
        config = {
            "spider": "",
            "lives": [
                {
                    "name": "直播",
                    "type": 0,
                    "url": f"http://{{host}}:8080/live.txt",
                    "epg": EPG_URL,
                    "logo": LOGO_URL
                }
            ]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        self.log(f"已生成: {output_file}")

    def update_sources(self):
        """更新源（完整流程）"""
        self.log("=" * 60)
        self.log("开始更新 IPTV 源")
        self.log("=" * 60)
        
        start_time = time.time()
        
        # 1. 抓取源
        self.fetch_sources()
        
        # 2. 检测可用性
        if self.channels:
            self.check_all_streams()
        
        # 3. 排序
        if self.channels:
            self.sort_channels()
        
        # 4. 生成输出文件
        if self.channels:
            self.generate_live_txt()
            self.generate_live_multi_txt()
            self.generate_config_json()
        else:
            self.log("警告: 没有可用的频道")
        
        elapsed = time.time() - start_time
        self.log(f"更新完成，耗时: {elapsed:.1f} 秒")
        self.log("=" * 60)


class CORSHTTPRequestHandler(SimpleHTTPRequestHandler):
    """支持 CORS 的 HTTP 请求处理器"""
    
    def end_headers(self):
        # 添加 CORS 头
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
    
    def log_message(self, format, *args):
        # 自定义日志格式
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"[{timestamp}] {self.address_string()} - {format % args}"
        print(message)


def start_http_server(port=8080):
    """启动 HTTP 服务器"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, OUTPUT_DIR)
    
    # 切换到输出目录
    os.chdir(output_dir)
    
    server = HTTPServer(('0.0.0.0', port), CORSHTTPRequestHandler)
    print(f"\n{'=' * 60}")
    print(f"HTTP 服务已启动")
    print(f"监听端口: {port}")
    print(f"服务目录: {output_dir}")
    print(f"访问地址:")
    print(f"  - http://localhost:{port}/config.json")
    print(f"  - http://localhost:{port}/live.txt")
    print(f"  - http://localhost:{port}/live_multi.txt")
    print(f"{'=' * 60}\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭服务器...")
        server.shutdown()


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 iptv_manager.py update    # 更新源")
        print("  python3 iptv_manager.py serve     # 启动 HTTP 服务")
        print("  python3 iptv_manager.py full      # 更新源并启动服务")
        sys.exit(1)
    
    command = sys.argv[1]
    manager = IPTVManager()
    
    if command == "update":
        # 仅更新源
        manager.update_sources()
        
    elif command == "serve":
        # 仅启动 HTTP 服务
        start_http_server()
        
    elif command == "full":
        # 更新源并启动服务
        manager.update_sources()
        
        # 在单独线程中启动 HTTP 服务
        server_thread = threading.Thread(target=start_http_server, daemon=False)
        server_thread.start()
        server_thread.join()
        
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
