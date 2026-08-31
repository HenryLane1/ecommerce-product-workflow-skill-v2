# -*- coding: utf-8 -*-
"""
豆包 Seedream 图像生成模块（电商 skill 生图 L1 能力 · 国内直连）
================================================================
底层模型：火山方舟 Doubao Seedream（5.0 / 4.5 / 4.0），字节跳动
API Key ：从环境变量 ARK_API_KEY 读取；skill 文件内一律使用占位符 ${ARK_API_KEY}
          严禁把明文 Key 写进任何 skill / 脚本 / 配置文件中。
获取 Key ：https://console.volcengine.com/ark/region:cn-beijing/apikey （火山方舟 API Key 管理）

用法示例：
    python doubao_image_gen.py --prompt "..." --output "D:/out/main.png" [--size 2K] [--model doubao-seedream-5-0-260128] [--no-watermark]

支持：
- 文生图（--prompt）
- 图生图（--image 可传本地路径或 URL，自动转 base64）
- 组图（--n 生成多张）
"""
import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.request
import urllib.error

DEFAULT_MODEL = "doubao-seedream-5-0-260128"  # Seedream 5.0 最新
API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"


def get_api_key():
    key = os.environ.get("ARK_API_KEY", "").strip()
    if not key or key.startswith("${"):
        sys.stderr.write(
            "[ERROR] 未检测到有效的 ARK_API_KEY。\n"
            "请到火山方舟控制台获取 API Key：https://console.volcengine.com/ark/region:cn-beijing/apikey\n"
            "然后配置环境变量 ARK_API_KEY（或用占位符 ${ARK_API_KEY} 由运行时注入）。\n"
        )
        sys.exit(2)
    return key


def to_image_item(src):
    """把本地路径 / base64 / URL 统一转为 API 的 image 字段项。

    火山方舟图片生成 API 的 image 参数为 string / string[]：
    - URL 直接传字符串；
    - Base64 需为小写 data URI，格式 data:image/png;base64,...
    """
    if src.startswith("data:"):
        return src  # 已是 base64 data URI
    if src.startswith("http://") or src.startswith("https://"):
        return src  # URL 直接作为字符串
    if os.path.exists(src):
        mime = mimetypes.guess_type(src)[0] or "image/png"
        with open(src, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        return f"data:{mime};base64,{b64}"
    raise ValueError(f"无法识别的图片输入: {src}")


def download(url, out_path):
    req = urllib.request.Request(url, headers={"User-Agent": "Marvis"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    with open(out_path, "wb") as fh:
        fh.write(data)
    return out_path, len(data)


def generate(prompt, output_path, size="2048x2048", model=DEFAULT_MODEL, num_images=1,
             image_inputs=None, watermark=True, response_format="url", timeout=120):
    key = get_api_key()
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": num_images,
        "response_format": response_format,
        "watermark": watermark,
    }
    if image_inputs:
        payload["image"] = [to_image_item(p) for p in image_inputs]

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        sys.stderr.write(f"[ERROR] Ark API HTTP {e.code}: {body}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"[ERROR] 请求失败: {e}\n")
        sys.exit(1)

    items = data.get("data") or []
    if not items:
        err = data.get("error") or data
        sys.stderr.write(f"[ERROR] 未返回图片。返回: {json.dumps(err, ensure_ascii=False)[:800]}\n")
        sys.exit(1)

    saved = []
    base_out = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(base_out), exist_ok=True)
    stem, ext = os.path.splitext(base_out)
    if not ext:
        ext = ".png"
        base_out = stem + ext

    for idx, item in enumerate(items):
        out = base_out
        if len(items) > 1:
            out = f"{stem}_{idx + 1}{ext}"
        if item.get("url"):
            out, nbytes = download(item["url"], out)
        elif item.get("b64_json"):
            raw = base64.b64decode(item["b64_json"])
            with open(out, "wb") as fh:
                fh.write(raw)
            nbytes = len(raw)
        else:
            sys.stderr.write(f"[ERROR] 第{idx + 1}张无 url/b64_json 字段\n")
            continue
        saved.append(out)
        print(f"[OK] 图片已保存: {out} ({nbytes} bytes)")
    return saved


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="豆包 Seedream 生图")
    ap.add_argument("--prompt", required=True, help="图像描述（中文≤300字 / 英文≤600词，效果更佳）")
    ap.add_argument("--output", required=True, help="输出文件路径（如 D:/out/main.png）")
    ap.add_argument("--size", default="2048x2048", help="尺寸（Seedream 5.0 支持 2048x2048 / 4K 等；4.0 支持 1K/2K/4K 或具体分辨率如 1024x1024）")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="模型 ID，默认 doubao-seedream-5-0-260128")
    ap.add_argument("--n", type=int, default=1, help="生成数量（组图，最多 4）")
    ap.add_argument("--image", nargs="*", default=None, help="参考图（本地路径或 URL），用于图生图")
    ap.add_argument("--no-watermark", action="store_true", help="关闭水印（默认开启水印）")
    ap.add_argument("--timeout", type=int, default=120, help="请求超时（秒）")
    args = ap.parse_args()
    generate(
        args.prompt, args.output, args.size, args.model, args.n,
        args.image, not args.no_watermark, timeout=args.timeout,
    )
