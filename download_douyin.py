#!/usr/bin/env python3
"""
抖音视频下载工具

通过 dlpanda.com 解析下载抖音视频，无需登录、无需 cookie。
零依赖，只需 Python 3 和系统自带的 curl。

用法：
  单个下载：
    python3 download_douyin.py <抖音链接>
    python3 download_douyin.py <抖音链接> "自定义文件名.mp4"

  批量下载：
    python3 download_douyin.py batch <文件路径>
    文件格式：每行一个抖音链接，# 开头为注释

  指定输出目录（默认当前目录）：
    python3 download_douyin.py <链接> -o /path/to/dir

  使用代理：
    python3 download_douyin.py <链接> --proxy socks5://127.0.0.1:1080
    python3 download_douyin.py <链接> --no-proxy

  指定请求间隔（批量时生效，默认8秒）：
    python3 download_douyin.py batch urls.txt --interval 10

示例：
  python3 download_douyin.py https://v.douyin.com/y8W72-LSddY/
  python3 download_douyin.py https://v.douyin.com/y8W72-LSddY/ "AI产品经理分类.mp4"
  python3 download_douyin.py batch urls.txt --interval 15
  python3 download_douyin.py https://v.douyin.com/xxx/ --proxy socks5://127.0.0.1:7890

环境变量：
  PROXY_SERVER - 代理地址（如 socks5://127.0.0.1:1080），命令行 --proxy 优先

原理：
  1. 访问 dlpanda.com 获取 t0ken
  2. 提交抖音链接，dlpanda 服务端解析出视频下载路径
  3. 通过 dlpanda 的 /download/v/{hash} 路径下载无水印视频
  全程使用 curl，无需浏览器自动化

注意事项：
  - 某些地区访问 dlpanda.com 可能需要代理
  - 批量下载时默认间隔 8 秒，避免触发 Cloudflare 频率限制
  - 如果连续失败，可能是被限流，等几分钟再试
"""
import sys
import re
import os
import time
import argparse
import subprocess
from pathlib import Path

DEFAULT_OUTPUT_DIR = Path(".")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
DEFAULT_INTERVAL = 8  # 批量下载间隔秒数

# 全局代理设置，由 main() 根据命令行参数初始化
_proxy = None


def curl_get(url):
    """用 curl 发请求，返回响应内容"""
    cmd = ["curl", "-s", "-L", "-H", f"User-Agent: {UA}"]
    if _proxy:
        cmd.extend(["-x", _proxy])
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout


def get_token():
    """获取 dlpanda 的 t0ken"""
    html = curl_get("https://dlpanda.com/en")
    m = re.search(r'name="t0ken"[^>]*value="([^"]+)"', html)
    if not m:
        raise Exception("无法获取 t0ken，可能被 Cloudflare 限流，请稍后再试")
    return m.group(1)


def parse_video(douyin_url, token):
    """解析抖音视频，返回下载路径和文件名"""
    from urllib.parse import urlencode
    params = urlencode({"url": douyin_url, "t0ken": token})
    url = f"https://dlpanda.com/en?{params}"
    html = curl_get(url)

    # 提取 dlpanda 下载路径
    m = re.search(r"downVideo2\('(/download/v/[^']+)',\s*'([^']+)'\)", html)
    if m:
        return {"path": m.group(1), "filename": m.group(2)}

    # 备用：source 标签里的播放地址
    m = re.search(r'<source\s+src="([^"]+)"', html)
    if m:
        play_url = m.group(1).replace("&amp;", "&")
        if play_url.startswith("//"):
            play_url = "https:" + play_url
        return {"path": play_url, "filename": "video.mp4"}

    return None


def download_file(download_path, save_path):
    """下载文件到指定路径"""
    if download_path.startswith("/"):
        url = f"https://dlpanda.com{download_path}"
    else:
        url = download_path

    cmd = [
        "curl", "-L",
        "-o", str(save_path),
        "-H", f"User-Agent: {UA}",
        "-H", "Referer: https://dlpanda.com/",
        "--progress-bar",
    ]
    if _proxy:
        cmd.extend(["-x", _proxy])
    cmd.append(url)

    subprocess.run(cmd, timeout=300)


def make_save_path(filename, output_dir, output_name=None):
    """生成保存路径"""
    save_name = output_name or re.sub(r'\[DLPanda\.com\]', '', filename).strip()
    if not save_name.endswith(".mp4"):
        save_name += ".mp4"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / save_name


def download_single(douyin_url, output_dir, output_name=None):
    """下载单个视频，返回保存路径或 None"""
    print(f"🔍 解析: {douyin_url}")

    try:
        token = get_token()
    except Exception as e:
        print(f"❌ {e}")
        return None

    result = parse_video(douyin_url, token)
    if not result:
        print("❌ 解析失败，未找到下载链接")
        return None

    save_path = make_save_path(result["filename"], output_dir, output_name)
    print(f"⬇️  下载: {save_path.name}")

    download_file(result["path"], save_path)

    if save_path.exists() and save_path.stat().st_size > 0:
        size_mb = save_path.stat().st_size / 1024 / 1024
        print(f"✅ 完成: {save_path.name} ({size_mb:.1f}MB)")
        return save_path
    else:
        print("❌ 下载失败，文件为空")
        if save_path.exists():
            save_path.unlink()
        return None


def download_batch(file_path, output_dir, interval):
    """批量下载"""
    text = Path(file_path).read_text(encoding="utf-8").strip()
    urls = [line.strip() for line in text.split("\n")
            if line.strip() and not line.strip().startswith("#")]

    if not urls:
        print("❌ 文件中没有有效链接")
        return

    print(f"📋 共 {len(urls)} 个链接，间隔 {interval} 秒\n")

    success = 0
    failed = []

    for i, url in enumerate(urls, 1):
        print(f"--- [{i}/{len(urls)}] ---")
        result = download_single(url, output_dir)
        if result:
            success += 1
        else:
            failed.append(url)

        # 非最后一个，等待间隔
        if i < len(urls):
            print(f"⏳ 等待 {interval} 秒...")
            time.sleep(interval)

        print()

    print(f"🏁 完成！成功 {success}/{len(urls)}")
    if failed:
        print(f"\n❌ 失败 {len(failed)} 个:")
        for u in failed:
            print(f"  {u}")


def main():
    global _proxy

    parser = argparse.ArgumentParser(
        description="抖音视频下载工具（通过 dlpanda.com，无需登录、无需 cookie）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s https://v.douyin.com/y8W72-LSddY/
  %(prog)s https://v.douyin.com/y8W72-LSddY/ "视频名.mp4"
  %(prog)s batch urls.txt --interval 10
  %(prog)s https://v.douyin.com/xxx/ -o ~/Downloads
  %(prog)s https://v.douyin.com/xxx/ --proxy socks5://127.0.0.1:7890
  %(prog)s https://v.douyin.com/xxx/ --no-proxy
        """,
    )
    parser.add_argument("url_or_cmd", help="抖音链接，或 'batch' 表示批量模式")
    parser.add_argument("file_or_name", nargs="?", help="批量模式下为文件路径，单个模式下为自定义文件名")
    parser.add_argument("-o", "--output-dir", type=str, default=None, help="输出目录（默认当前目录）")
    parser.add_argument("--proxy", type=str, default=None, help="代理地址（如 socks5://127.0.0.1:1080）")
    parser.add_argument("--no-proxy", action="store_true", help="不使用代理")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help=f"批量下载间隔秒数（默认 {DEFAULT_INTERVAL}）")

    args = parser.parse_args()

    # 代理优先级：--no-proxy > --proxy > 环境变量 PROXY_SERVER > 不使用代理
    if args.no_proxy:
        _proxy = None
    elif args.proxy:
        _proxy = args.proxy
    else:
        _proxy = os.environ.get("PROXY_SERVER", "")

    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR

    if args.url_or_cmd == "batch":
        if not args.file_or_name:
            print("❌ 批量模式需要指定文件路径：python3 download_douyin.py batch urls.txt")
            sys.exit(1)
        download_batch(args.file_or_name, output_dir, args.interval)
    else:
        download_single(args.url_or_cmd, output_dir, args.file_or_name)


if __name__ == "__main__":
    main()
