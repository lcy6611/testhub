# -*- coding: utf-8 -*-
"""
图片与 Base64 互转工具
"""
import base64
import re
from typing import Dict, Any, Optional
from pathlib import Path
import hashlib
import time


class ImageTools:
    """图片工具类"""

    SUPPORTED_FORMATS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico']
    MAX_SIZE_MB = 10
    MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024

    @staticmethod
    def get_static_img_path() -> str:
        current_file_dir = Path(__file__).parent.parent
        static_img_path = current_file_dir.parent.parent / "static_files" / "img"
        static_img_path.mkdir(parents=True, exist_ok=True)
        return str(static_img_path.resolve())

    @staticmethod
    def image_to_base64(image_data: bytes | str, image_format: str, include_prefix: bool = True) -> Dict[str, Any]:
        """图片转 Base64"""
        try:
            if isinstance(image_data, str):
                try:
                    image_data = base64.b64decode(image_data)
                except Exception:
                    return {'error': '图片数据格式错误，无法解码Base64', 'result': False}

            if len(image_data) > ImageTools.MAX_SIZE_BYTES:
                return {
                    'result': False,
                    'error': f'图片大小超过限制（最大{ImageTools.MAX_SIZE_MB}MB）',
                    'actual_size': len(image_data),
                    'max_size': ImageTools.MAX_SIZE_BYTES,
                }

            b64 = base64.b64encode(image_data).decode('utf-8')
            mime_type = ImageTools._get_mime_type(image_format)
            if include_prefix:
                result = f"data:{mime_type};base64,{b64}"
            else:
                result = b64

            return {
                'success': True,
                'result': result,
                'base64_data': b64,
                'mime_type': mime_type,
                'format': image_format,
                'size': len(image_data),
                'size_mb': round(len(image_data) / (1024 * 1024), 2),
                'base64_length': len(b64),
                'include_prefix': include_prefix,
            }
        except Exception as e:
            return {'error': f'图片转Base64失败: {str(e)}', 'result': False}

    @staticmethod
    def base64_to_image(base64_str: str) -> Dict[str, Any]:
        """Base64 转图片并保存到 static_files/img"""
        try:
            data = base64_str.strip()
            mime_type = None
            if data.startswith('data:image'):
                match = re.match(r'data:image/(\w+);base64,', data)
                if match:
                    mime_type = match.group(1)
                    b64 = data.split(',', 1)[1]
                else:
                    return {'error': 'Base64格式错误，无法识别MIME类型', 'result': False}
            else:
                b64 = data

            try:
                image_data = base64.b64decode(b64)
            except Exception as e:
                return {'error': f'Base64解码失败: {str(e)}', 'result': False}

            if len(image_data) > ImageTools.MAX_SIZE_BYTES:
                return {
                    'result': False,
                    'error': f'图片大小超过限制（最大{ImageTools.MAX_SIZE_MB}MB）',
                    'actual_size': len(image_data),
                    'max_size': ImageTools.MAX_SIZE_BYTES,
                }

            ext = mime_type if mime_type else 'png'
            ts = int(time.time())
            h = hashlib.md5(b64.encode('utf-8')).hexdigest()[:8]
            filename = f"base64_{ts}_{h}.{ext}"

            static_img_path = Path(ImageTools.get_static_img_path())
            file_path = static_img_path / filename
            with open(file_path, 'wb') as f:
                f.write(image_data)

            return {
                'success': True,
                'result': {
                    'size': len(image_data),
                    'mime_type': mime_type,
                    'format': ext,
                    'size_mb': round(len(image_data) / (1024 * 1024), 2),
                    'base64_length': len(b64),
                },
                'filename': filename,
                'url': f"/static_files/img/{filename}",
            }
        except Exception as e:
            return {'error': f'Base64转图片失败: {str(e)}', 'result': False}

    @staticmethod
    def _get_mime_type(format_name: str) -> str:
        mime = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'bmp': 'image/bmp',
            'svg': 'image/svg+xml',
            'ico': 'image/x-icon',
        }
        return mime.get(format_name.lower(), 'image/jpeg')

