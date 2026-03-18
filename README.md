# 抖音视频下载工具

通过 [dlpanda.com](https://dlpanda.com) 解析下载抖音无水印视频。

**无需登录、无需 cookie、零依赖**（只需 Python 3 + curl）。

## 安装

不需要安装任何第三方包，下载 `download_douyin.py` 即可使用。

**系统要求：**
- Python 3.6+
- curl（macOS/Linux 系统自带）

## 用法

### 下载单个视频

```bash
python3 download_douyin.py https://v.douyin.com/xxx/
```

自定义文件名：
```bash
python3 download_douyin.py https://v.douyin.com/xxx/ "我的视频.mp4"
```

### 批量下载

准备一个文本文件（如 `urls.txt`），每行一个链接：
```
# 这是注释，会被忽略
https://v.douyin.com/aaa/
https://v.douyin.com/bbb/
https://v.douyin.com/ccc/
```

执行批量下载：
```bash
python3 download_douyin.py batch urls.txt
```

### 常用参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-o, --output-dir` | 输出目录 | 当前目录 |
| `--proxy` | 代理地址 | 无 |
| `--no-proxy` | 强制不使用代理 | - |
| `--interval` | 批量下载间隔秒数 | 8 |

### 代理配置

某些地区可能需要代理才能访问 dlpanda.com：

```bash
# 命令行指定
python3 download_douyin.py https://v.douyin.com/xxx/ --proxy socks5://127.0.0.1:7890

# 或通过环境变量
export PROXY_SERVER="socks5://127.0.0.1:7890"
python3 download_douyin.py https://v.douyin.com/xxx/

# 强制不使用代理（忽略环境变量）
python3 download_douyin.py https://v.douyin.com/xxx/ --no-proxy
```

代理优先级：`--no-proxy` > `--proxy` > 环境变量 `PROXY_SERVER`

## 原理

1. 访问 dlpanda.com 获取页面 token
2. 提交抖音链接，dlpanda 服务端解析出视频下载地址
3. 通过 curl 下载无水印视频

全程使用 curl 发起 HTTP 请求，无需浏览器自动化。

## 注意事项

- 批量下载默认间隔 8 秒，避免触发 Cloudflare 频率限制
- 如果连续失败，可能是被限流，等几分钟再试
- 本工具依赖 dlpanda.com 的服务，如果该网站不可用则无法使用

## License

MIT
