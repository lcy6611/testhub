# -*- coding: utf-8 -*-
"""
加密相关工具：哈希、Base64、AES 等
"""
import hashlib
import base64
import logging
from typing import Dict, Any

try:
    from Crypto.Cipher import AES
    from Crypto.Protocol.KDF import PBKDF2
    from Crypto.Util.Padding import pad, unpad
    from Crypto.Random import get_random_bytes
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)


class EncryptionTools:
    """加密工具类（简化版）"""

    @staticmethod
    def md5_hash(text: str) -> Dict[str, Any]:
        try:
            h = hashlib.md5(text.encode('utf-8')).hexdigest()
            return {'result': h, 'algorithm': 'MD5', 'input_length': len(text), 'hash_length': len(h)}
        except Exception as e:
            return {'error': f'MD5加密失败: {str(e)}'}

    @staticmethod
    def sha1_hash(text: str) -> Dict[str, Any]:
        try:
            h = hashlib.sha1(text.encode('utf-8')).hexdigest()
            return {'result': h, 'algorithm': 'SHA-1', 'input_length': len(text), 'hash_length': len(h)}
        except Exception as e:
            return {'error': f'SHA1加密失败: {str(e)}'}

    @staticmethod
    def sha256_hash(text: str) -> Dict[str, Any]:
        try:
            h = hashlib.sha256(text.encode('utf-8')).hexdigest()
            return {'result': h, 'algorithm': 'SHA-256', 'input_length': len(text), 'hash_length': len(h)}
        except Exception as e:
            return {'error': f'SHA256加密失败: {str(e)}'}

    @staticmethod
    def sha512_hash(text: str) -> Dict[str, Any]:
        try:
            h = hashlib.sha512(text.encode('utf-8')).hexdigest()
            return {'result': h, 'algorithm': 'SHA-512', 'input_length': len(text), 'hash_length': len(h)}
        except Exception as e:
            return {'error': f'SHA512加密失败: {str(e)}'}

    @staticmethod
    def hash_comparison(text: str, hash_value: str, algorithm: str = 'md5') -> Dict[str, Any]:
        try:
            funcs = {
                'md5': hashlib.md5,
                'sha1': hashlib.sha1,
                'sha256': hashlib.sha256,
                'sha512': hashlib.sha512,
            }
            if algorithm not in funcs:
                return {'error': f'不支持的哈希算法: {algorithm}'}
            computed = funcs[algorithm](text.encode('utf-8')).hexdigest()
            is_match = computed.lower() == hash_value.lower()
            return {
                'result': is_match,
                'computed_hash': computed,
                'provided_hash': hash_value,
                'algorithm': algorithm,
            }
        except Exception as e:
            return {'error': f'哈希比对失败: {str(e)}'}

    @staticmethod
    def base64_encode(text: str, encoding: str = 'utf-8') -> Dict[str, Any]:
        try:
            encoded = base64.b64encode(text.encode(encoding)).decode(encoding)
            return {'result': encoded, 'input_length': len(text), 'encoded_length': len(encoded), 'encoding': encoding}
        except Exception as e:
            return {'error': f'Base64编码失败: {str(e)}'}

    @staticmethod
    def base64_decode(text: str, encoding: str = 'utf-8') -> Dict[str, Any]:
        try:
            decoded = base64.b64decode(text.encode(encoding)).decode(encoding)
            return {'result': decoded, 'encoded_length': len(text), 'decoded_length': len(decoded), 'encoding': encoding}
        except Exception as e:
            return {'error': f'Base64解码失败: {str(e)}'}

    @staticmethod
    def password_strength(password: str) -> Dict[str, Any]:
        """简单密码强度分析"""
        try:
            score = 0
            feedback = []
            length = len(password)
            if length >= 8:
                score += 1
            else:
                feedback.append('密码长度不足8位')
            if length >= 12:
                score += 1
            else:
                feedback.append('建议使用至少12位密码')

            has_lower = any(c.islower() for c in password)
            has_upper = any(c.isupper() for c in password)
            has_digit = any(c.isdigit() for c in password)
            has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
            char_types = sum([has_lower, has_upper, has_digit, has_special])
            score += min(char_types, 2)

            if not has_lower:
                feedback.append('缺少小写字母')
            if not has_upper:
                feedback.append('缺少大写字母')
            if not has_digit:
                feedback.append('缺少数字')
            if not has_special:
                feedback.append('缺少特殊字符')

            if len(set(password)) < len(password) / 2:
                feedback.append('密码中重复字符过多')
                score -= 1

            common_patterns = ['123', 'abc', 'password', 'qwerty']
            if any(p in password.lower() for p in common_patterns):
                feedback.append('密码包含常见模式')
                score -= 1

            score = max(0, min(4, score))
            levels = ['非常弱', '弱', '中等', '强', '非常强']
            strength = levels[score]
            return {
                'result': strength,
                'strength': strength,
                'score': score,
                'max_score': 4,
                'length': length,
                'feedback': feedback,
            }
        except Exception as e:
            return {'error': f'密码强度分析失败: {str(e)}'}

    @staticmethod
    def generate_salt(length: int = 16) -> Dict[str, Any]:
        try:
            import os
            salt = os.urandom(length).hex()
            return {'result': salt, 'length': length, 'format': 'hex'}
        except Exception as e:
            return {'error': f'盐值生成失败: {str(e)}'}

    @staticmethod
    def aes_encrypt(text: str, password: str, mode: str = 'CBC') -> Dict[str, Any]:
        """AES 加密"""
        if not CRYPTO_AVAILABLE:
            return {'error': 'pycryptodome 未安装，请先安装'}
        try:
            salt = get_random_bytes(16)
            key = PBKDF2(password, salt, dkLen=32, count=100000)
            iv = get_random_bytes(16)
            if mode == 'CBC':
                cipher = AES.new(key, AES.MODE_CBC, iv)
                ct_bytes = cipher.encrypt(pad(text.encode('utf-8'), AES.block_size))
            elif mode == 'ECB':
                cipher = AES.new(key, AES.MODE_ECB)
                ct_bytes = cipher.encrypt(pad(text.encode('utf-8'), AES.block_size))
                iv = b''
            else:
                return {'error': f'不支持的AES模式: {mode}'}
            encrypted_data = salt + iv + ct_bytes
            encrypted_str = base64.b64encode(encrypted_data).decode('utf-8')
            return {'result': encrypted_str, 'algorithm': f'AES-{mode}', 'key_length': 256}
        except Exception as e:
            logger.error(f'AES加密失败: {str(e)}')
            return {'error': str(e)}

    @staticmethod
    def aes_decrypt(encrypted_text: str, password: str, mode: str = 'CBC') -> Dict[str, Any]:
        """AES 解密"""
        if not CRYPTO_AVAILABLE:
            return {'error': 'pycryptodome 未安装，请先安装'}
        try:
            encrypted_data = base64.b64decode(encrypted_text.encode('utf-8'))
            salt = encrypted_data[:16]
            if mode == 'ECB':
                iv = b''
                ct_bytes = encrypted_data[16:]
            else:
                iv = encrypted_data[16:32]
                ct_bytes = encrypted_data[32:]
            key = PBKDF2(password, salt, dkLen=32, count=100000)
            if mode == 'CBC':
                cipher = AES.new(key, AES.MODE_CBC, iv)
            elif mode == 'ECB':
                cipher = AES.new(key, AES.MODE_ECB)
            else:
                return {'error': f'不支持的AES模式: {mode}'}
            pt_bytes = unpad(cipher.decrypt(ct_bytes), AES.block_size)
            return {'result': pt_bytes.decode('utf-8'), 'algorithm': f'AES-{mode}', 'success': True}
        except Exception as e:
            logger.error(f'AES解密失败: {str(e)}')
            return {'error': 'AES解密失败，请检查密码和密文'}

