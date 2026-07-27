# -*- coding: utf-8 -*-
"""
编码相关工具（条形码 / 二维码 / Base64 / URL / 时间戳等）
简化版，保持与数据工厂视图的调用接口兼容。
"""
import base64
import binascii
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import os

try:
    from urllib.parse import quote, unquote, quote_plus, unquote_plus
    URLLIB_AVAILABLE = True
except ImportError:
    URLLIB_AVAILABLE = False

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

try:
    import barcode
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False

try:
    import qrcode
    QR_CODE_AVAILABLE = True
except ImportError:
    QR_CODE_AVAILABLE = False

try:
    from pyzbar.pyzbar import decode
    from PIL import Image
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False

logger = logging.getLogger(__name__)


class EncodingTools:
    """编码工具类"""

    @staticmethod
    def get_static_img_path() -> str:
        """
        获取 static_files/img 文件夹的路径
        """
        current_file_dir = Path(__file__).parent.parent
        static_img_path = current_file_dir.parent.parent / "static_files" / "img"
        static_img_path.mkdir(parents=True, exist_ok=True)
        return str(static_img_path.resolve())

    @staticmethod
    def download_static_file(filename: str) -> Dict[str, Any]:
        """供视图层下载图片用的简单包装"""
        try:
            if '..' in filename or filename.startswith('/') or '../' in filename:
                return {'error': '非法文件路径，不允许访问上级目录'}
            static_img_path = Path(EncodingTools.get_static_img_path())
            file_path = static_img_path / filename

            try:
                file_path.resolve().relative_to(static_img_path.resolve())
            except ValueError:
                return {'error': '非法文件路径，不允许访问其他目录'}

            if not file_path.exists() or not file_path.is_file():
                return {'error': f'文件不存在: {filename}'}

            return {
                'success': True,
                'filename': filename,
                'file_path': str(file_path),
                'file_size': file_path.stat().st_size,
                'exists': True,
            }
        except Exception as e:
            logger.error(f'文件下载检查失败: {str(e)}')
            return {'error': f'文件下载检查失败: {str(e)}'}

    @staticmethod
    def base64_encode(text: str, encoding: str = 'utf-8') -> Dict[str, Any]:
        """Base64 编码"""
        try:
            encoded = base64.b64encode(text.encode(encoding)).decode(encoding)
            return {
                'result': encoded,
                'original_length': len(text),
                'encoded_length': len(encoded),
            }
        except Exception as e:
            logger.error(f'Base64编码失败: {str(e)}')
            return {'error': f'Base64编码失败: {str(e)}'}

    @staticmethod
    def base64_decode(text: str, encoding: str = 'utf-8') -> Dict[str, Any]:
        """Base64 解码"""
        try:
            decoded = base64.b64decode(text.encode(encoding)).decode(encoding)
            return {
                'result': decoded,
                'encoded_length': len(text),
                'decoded_length': len(decoded),
            }
        except binascii.Error:
            return {'error': '无效的Base64数据'}
        except Exception as e:
            logger.error(f'Base64解码失败: {str(e)}')
            return {'error': f'Base64解码失败: {str(e)}'}

    @staticmethod
    def timestamp_convert(timestamp: Any, convert_type: str = 'to_datetime', timestamp_unit: str = 'auto') -> Dict[str, Any]:
        """时间戳转换"""

        def get_local_timezone_name():
            local_dt = datetime.now().astimezone()
            return local_dt.tzname()

        try:
            if convert_type == 'to_datetime':
                ts_str = str(timestamp).strip()
                ts_float = float(ts_str)
                if timestamp_unit == 'auto':
                    timestamp_unit_local = 'millisecond' if ts_float > 1e11 else 'second'
                else:
                    timestamp_unit_local = timestamp_unit
                if timestamp_unit_local == 'millisecond':
                    ts_float = ts_float / 1000
                dt = datetime.fromtimestamp(ts_float)
                return {
                    'result': dt.strftime('%Y-%m-%d %H:%M:%S'),
                    'iso_format': dt.isoformat(),
                    'date': dt.strftime('%Y-%m-%d'),
                    'time': dt.strftime('%H:%M:%S'),
                    'timezone': get_local_timezone_name(),
                    'timestamp_unit': timestamp_unit_local,
                }
            elif convert_type == 'to_timestamp':
                dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                ts = dt.timestamp()
                return {
                    'result': int(ts),
                    'result_millisecond': int(ts * 1000),
                    'float_result': ts,
                }
            elif convert_type == 'current_timestamp':
                current_ts = time.time()
                dt = datetime.fromtimestamp(current_ts)
                return {
                    'result': int(current_ts),
                    'timestamp': int(current_ts),
                    'timestamp_millisecond': int(current_ts * 1000),
                    'datetime': dt.strftime('%Y-%m-%d %H:%M:%S'),
                }
            else:
                return {'error': f'不支持的转换类型: {convert_type}'}
        except Exception as e:
            logger.error(f'时间戳转换失败: {str(e)}')
            return {'error': f'时间戳转换失败: {str(e)}'}

    @staticmethod
    def generate_barcode(data: str, barcode_type: str = 'code128', save_to_static: bool = True) -> Dict[str, Any]:
        """生成条形码"""
        if not BARCODE_AVAILABLE:
            return {'error': 'barcode 模块未安装，请先安装 python-barcode'}
        barcode_types = ['ean8', 'ean13', 'upc', 'code39', 'code128', 'isbn10', 'isbn13']
        if barcode_type not in barcode_types:
            return {'error': f'不支持的条形码类型: {barcode_type}'}
        data = str(data).strip()
        if not data:
            return {'error': '请输入要编码的数据'}
        try:
            import uuid as _uuid
            barcode_class = barcode.get_barcode_class(barcode_type)
            my_barcode = barcode_class(data, writer=ImageWriter())
            if save_to_static:
                static_img_path = Path(EncodingTools.get_static_img_path())
                filename = f'barcode_{int(time.time())}_{_uuid.uuid4().hex[:8]}_{barcode_type}'
                full_path = static_img_path / filename
                saved_filename = my_barcode.save(str(full_path))
            else:
                saved_filename = my_barcode.save(f'temp_barcode_{barcode_type}')
            result_url = f'/static_files/img/{os.path.basename(saved_filename)}' if save_to_static else None
            return {'url': result_url, 'result': result_url, 'success': True, 'filename': os.path.basename(saved_filename)}
        except Exception as e:
            logger.error(f'条形码生成失败: {str(e)}')
            return {'error': str(e)}

    @staticmethod
    def generate_qrcode(data: str, image_size: int = 300, border: int = 4, save_to_static: bool = True) -> Dict[str, Any]:
        """生成二维码"""
        if not QR_CODE_AVAILABLE:
            return {'error': 'qrcode 模块未安装，请先安装 qrcode'}
        try:
            import uuid as _uuid
            qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=border)
            qr.add_data(data.encode('utf-8'))
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            if image_size > 0:
                img = img.resize((image_size, image_size))
            if save_to_static:
                static_img_path = Path(EncodingTools.get_static_img_path())
                filename = f'qrcode_{int(time.time())}_{_uuid.uuid4().hex[:8]}_{image_size}px.png'
                full_path = static_img_path / filename
                img.save(full_path)
                url = f'/static_files/img/{filename}'
            else:
                filename = f'temp_qrcode_{image_size}px.png'
                img.save(filename)
                url = None
            return {'url': url, 'result': url or filename, 'success': True, 'filename': filename}
        except Exception as e:
            logger.error(f'二维码生成失败: {str(e)}')
            return {'error': str(e)}

    @staticmethod
    def decode_qrcode(image_data: str, image_format: str = 'png') -> Dict[str, Any]:
        """解析二维码"""
        if not PYZBAR_AVAILABLE:
            return {'error': 'pyzbar 模块未安装，请先安装 pyzbar'}
        try:
            from io import BytesIO
            if image_data.startswith('data:image'):
                image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)
            image = Image.open(BytesIO(image_bytes))
            image = Image.open(BytesIO(image_bytes))
            decoded_objects = decode(image)
            if not decoded_objects:
                return {'message': '未检测到二维码', 'result': False}
            results = []
            for obj in decoded_objects:
                try:
                    data_str = obj.data.decode('utf-8')
                except UnicodeDecodeError:
                    data_str = obj.data.decode('gbk', errors='replace')
                results.append({'data': data_str, 'type': obj.type})
            return {'success': True, 'result': results[0]['data'] if len(results) == 1 else results, 'results': results}
        except Exception as e:
            logger.error(f'二维码解析失败: {str(e)}')
            return {'error': str(e)}

    @staticmethod
    def base_convert(number: Any, from_base: int = 10, to_base: int = 16) -> Dict[str, Any]:
        """进制转换"""
        try:
            num_str = str(number).strip()
            decimal_num = int(num_str, from_base) if from_base != 10 else int(num_str)
            if to_base == 10:
                result = str(decimal_num)
            elif to_base == 2:
                result = bin(decimal_num)[2:]
            elif to_base == 8:
                result = oct(decimal_num)[2:]
            elif to_base == 16:
                result = hex(decimal_num)[2:].upper()
            else:
                digits = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                if to_base < 2 or to_base > len(digits):
                    return {'error': f'不支持的进制: {to_base}'}
                is_neg = decimal_num < 0
                decimal_num = abs(decimal_num)
                result = ''
                while decimal_num > 0:
                    result = digits[decimal_num % to_base] + result
                    decimal_num //= to_base
                result = result or '0'
                if is_neg:
                    result = '-' + result
            return {'result': result, 'from_base': from_base, 'to_base': to_base}
        except Exception as e:
            logger.error(f'进制转换失败: {str(e)}')
            return {'error': str(e)}

    @staticmethod
    def unicode_convert(text: str, convert_type: str = 'to_unicode') -> Dict[str, Any]:
        """Unicode 与中文转换"""
        try:
            if convert_type == 'to_unicode':
                result = ''.join([f'\\u{ord(c):04x}' for c in text])
                return {'result': result, 'original': text}
            elif convert_type == 'from_unicode':
                text = text.replace('\\\\u', '\\u')
                result = text.encode('utf-8').decode('unicode-escape')
                return {'result': result, 'original': text}
            return {'error': f'不支持的转换类型: {convert_type}'}
        except Exception as e:
            logger.error(f'Unicode转换失败: {str(e)}')
            return {'error': str(e)}

    @staticmethod
    def ascii_convert(text: str, convert_type: str = 'to_ascii') -> Dict[str, Any]:
        """ASCII 与字符转换"""
        try:
            if convert_type == 'to_ascii':
                codes = [ord(c) for c in text]
                return {'result': codes, 'original': text, 'hex': [f'{c:02x}' for c in codes]}
            elif convert_type == 'from_ascii':
                codes = [int(c.strip()) for c in text.replace(',', ' ').split() if c.strip()]
                result = ''.join(chr(c) for c in codes)
                return {'result': result, 'codes': codes}
            return {'error': f'不支持的转换类型: {convert_type}'}
        except Exception as e:
            logger.error(f'ASCII转换失败: {str(e)}')
            return {'error': str(e)}

    @staticmethod
    def color_convert(color: str, from_type: str = 'hex', to_type: str = 'rgb') -> Dict[str, Any]:
        """颜色格式转换"""
        try:
            if from_type == 'hex':
                hex_color = color.lstrip('#')
                rgb = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
            elif from_type == 'rgb':
                rgb = tuple(map(int, color.replace('rgb(', '').replace(')', '').split(',')))
            else:
                return {'error': f'不支持的类型: {from_type}'}
            if to_type == 'hex':
                result = f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'
            elif to_type == 'rgb':
                result = f'rgb({rgb[0]}, {rgb[1]}, {rgb[2]})'
            elif to_type == 'rgba':
                result = f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 1.0)'
            else:
                return {'error': f'不支持的类型: {to_type}'}
            return {'result': result, 'from_type': from_type, 'to_type': to_type, 'rgb': rgb}
        except Exception as e:
            logger.error(f'颜色转换失败: {str(e)}')
            return {'error': str(e)}

    @staticmethod
    def url_encode(data: str, encoding: str = 'utf-8', safe: str = '', plus: bool = False) -> Dict[str, Any]:
        """URL 编码"""
        if not URLLIB_AVAILABLE:
            return {'error': 'urllib 不可用'}
        try:
            encoded = quote_plus(data, encoding=encoding, safe=safe) if plus else quote(data, encoding=encoding, safe=safe)
            return {'result': encoded, 'original_length': len(data), 'encoded_length': len(encoded)}
        except Exception as e:
            logger.error(f'URL编码失败: {str(e)}')
            return {'error': str(e)}

    @staticmethod
    def url_decode(data: str, encoding: str = 'utf-8', plus: bool = False) -> Dict[str, Any]:
        """URL 解码"""
        if not URLLIB_AVAILABLE:
            return {'error': 'urllib 不可用'}
        try:
            decoded = unquote_plus(data, encoding=encoding) if plus else unquote(data, encoding=encoding)
            return {'result': decoded, 'encoded_length': len(data), 'decoded_length': len(decoded)}
        except Exception as e:
            logger.error(f'URL解码失败: {str(e)}')
            return {'error': str(e)}

    @staticmethod
    def jwt_decode(token: str, verify: bool = False, secret: str = '') -> Dict[str, Any]:
        """JWT 解码"""
        if not JWT_AVAILABLE:
            return {'error': 'PyJWT 未安装，请先安装 pyjwt'}
        try:
            if verify and secret:
                decoded = jwt.decode(token, secret, algorithms=['HS256'])
            else:
                decoded = jwt.decode(token, options={'verify_signature': False})
            header = jwt.get_unverified_header(token)
            return {'result': decoded, 'header': header, 'token': token}
        except jwt.ExpiredSignatureError:
            return {'error': 'JWT 已过期'}
        except jwt.InvalidTokenError as e:
            logger.error(f'JWT 无效: {str(e)}')
            return {'error': 'JWT 无效'}
        except Exception as e:
            logger.error(f'JWT解码失败: {str(e)}')
            return {'error': str(e)}

