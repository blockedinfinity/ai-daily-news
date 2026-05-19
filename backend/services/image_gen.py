"""图片生成（硅基流动 flux-schnell）+ 腾讯云 COS 上传。"""

import logging
import os
import uuid
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

SILICONFLOW_KEY = os.getenv("SILICONFLOW_API_KEY", "")
COS_SECRET_ID = os.getenv("COS_SECRET_ID", "")
COS_SECRET_KEY = os.getenv("COS_SECRET_KEY", "")
COS_REGION = os.getenv("COS_REGION", "ap-guangzhou")
COS_BUCKET = os.getenv("COS_BUCKET", "")
COS_CDN_DOMAIN = os.getenv("COS_CDN_DOMAIN", "")

IMAGE_MODEL = "stabilityai/stable-diffusion-3-medium"


# ── 硅基流动生图 ─────────────────────────────────────────────

def generate_image(prompt, width=1024, height=1024, steps=4):
    """调用硅基流动 API 生成图片，返回 bytes 或 None。"""
    if not SILICONFLOW_KEY:
        logger.warning("SILICONFLOW_API_KEY 未配置，跳过图片生成")
        return None

    url = "https://api.siliconflow.cn/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {SILICONFLOW_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": IMAGE_MODEL,
        "prompt": prompt,
        "image_size": {"width": width, "height": height},
        "num_inference_steps": steps,
        "response_format": "bytes",
    }

    logger.info("请求硅基流动生图: %s", prompt[:60])
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        logger.info("图片生成成功，大小: %d bytes", len(resp.content))
        return resp.content
    except requests.RequestException as e:
        logger.error("硅基流动生图失败: %s", e)
        return None


# ── 腾讯云 COS 上传 ─────────────────────────────────────────

def upload_to_cos(image_bytes, filename=None):
    """上传图片 bytes 到腾讯云 COS，返回 CDN URL。"""
    if not all([COS_SECRET_ID, COS_SECRET_KEY, COS_BUCKET]):
        logger.warning("腾讯云 COS 配置不完整，跳过上传")
        return ""

    if filename is None:
        ext = "png"
        filename = f"project-covers/{datetime.now().strftime('%Y%m%d')}/{uuid.uuid4().hex[:8]}.{ext}"

    try:
        # 动态导入，避免没有安装 qcloud_cos_v5 时报错
        from qcloud_cos import CosConfig, CosS3Client

        config = CosConfig(
            Region=COS_REGION,
            SecretId=COS_SECRET_ID,
            SecretKey=COS_SECRET_KEY,
        )
        client = CosS3Client(config)

        client.put_object(
            Bucket=COS_BUCKET,
            Body=image_bytes,
            Key=filename,
            ContentType="image/png",
        )

        cdn = COS_CDN_DOMAIN.rstrip("/")
        if cdn:
            cdn_url = f"{cdn}/{filename}"
        else:
            cdn_url = f"https://{COS_BUCKET}.cos.{COS_REGION}.myqcloud.com/{filename}"

        logger.info("图片上传 COS 成功: %s", cdn_url)
        return cdn_url

    except ImportError:
        logger.warning("qcloud_cos_v5 未安装，跳过 COS 上传，尝试 imgbb 降级")
        return _upload_imgbb_fallback(image_bytes)
    except Exception as e:
        logger.error("COS 上传失败: %s，尝试降级方案", e)
        return _upload_imgbb_fallback(image_bytes)


def _upload_imgbb_fallback(image_bytes):
    """降级：上传到 imgbb（无需注册，返回临时 URL）。"""
    import base64

    api_key = os.getenv("IMGBB_API_KEY", "")
    if not api_key:
        logger.warning("IMGBB_API_KEY 也未配置，无法上传图片")
        return ""

    url = "https://api.imgbb.com/1/upload"
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {"key": api_key, "image": b64, "name": f"cover-{uuid.uuid4().hex[:8]}"}

    try:
        resp = requests.post(url, data=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        img_url = data.get("data", {}).get("url", "")
        logger.info("imgbb 降级上传成功: %s", img_url)
        return img_url
    except Exception as e:
        logger.error("imgbb 上传也失败: %s", e)
        return ""


# ── 完整流程 ─────────────────────────────────────────────────

def generate_and_upload_cover(project):
    """生成项目配图并上传 CDN，返回 CDN URL 或空字符串。"""
    from .project_ranker import generate_cover_prompt

    prompt = generate_cover_prompt(project)
    if not prompt:
        return ""

    image_bytes = generate_image(prompt, width=1024, height=640)  # 横版封面比例
    if not image_bytes:
        return ""

    cdn_url = upload_to_cos(image_bytes)
    return cdn_url
