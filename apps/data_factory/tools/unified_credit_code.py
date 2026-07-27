# -*- coding: utf-8 -*-
# -----------------------------
# @Author    : 影子
# @Time      : 2026/1/17 22:24
# @Software  : PyCharm
# @FileName  : unified_credit_code.py
# -----------------------------
"""
统一社会信用代码生成工具
"""
import random

# 统一社会信用代码中不使用 I, O, Z, S, V
SOCIAL_CREDIT_CHECK_CODE_DICT = {
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    'A': 10, 'B': 11, 'C': 12, 'D': 13, 'E': 14, 'F': 15, 'G': 16, 'H': 17, 'J': 18, 'K': 19, 'L': 20, 'M': 21,
    'N': 22, 'P': 23, 'Q': 24, 'R': 25, 'T': 26, 'U': 27, 'W': 28, 'X': 29, 'Y': 30
}

ORGANIZATION_CHECK_CODE_DICT = {
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    'A': 10, 'B': 11, 'C': 12, 'D': 13, 'E': 14, 'F': 15, 'G': 16, 'H': 17, 'J': 19, 'K': 20, 'L': 21, 'M': 22,
    'N': 23, 'P': 25, 'Q': 26, 'R': 27, 'T': 29, 'U': 30, 'W': 32, 'X': 33, 'Y': 34
}


class CreditIdentifier:
    """生成统一社会信用代码"""

    @staticmethod
    def get_category_code():
        """随机前两位类别代码"""
        categories = ['11', '12', '13', '19', '51', '52', '53', '59', '91', '92', '93', 'Y1']
        return random.choice(categories)

    @staticmethod
    def get_district_code():
        """随机地区行政代码（简化版）"""
        districts = ['110000', '310000', '440100', '440300', '510100', '320100']
        return random.choice(districts)

    @staticmethod
    def get_org_code():
        """生成组织机构代码（9位，含校验位）"""
        org_keys = ORGANIZATION_CHECK_CODE_DICT.keys()
        keys_str = "".join(org_keys)
        o_code = "".join(random.choice(keys_str) for _ in range(8))
        weighting_factor = [3, 7, 9, 10, 5, 8, 4, 2]
        total = 0
        for i, ch in enumerate(o_code):
            total += ORGANIZATION_CHECK_CODE_DICT[ch] * weighting_factor[i]
        c9 = 11 - total % 11
        if c9 == 10:
            c9 = 'X'
        elif c9 == 11:
            c9 = '0'
        else:
            c9 = str(c9)
        return o_code + c9

    def get_social_credit_code(self):
        """拼接生成完整统一社会信用代码"""
        category_code = self.get_category_code()
        district_code = self.get_district_code()
        org_code = self.get_org_code()
        codes = category_code + district_code + org_code  # 本体代码 17 位

        weighting_factor = [1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28]
        total = 0
        for i, ch in enumerate(codes):
            total += SOCIAL_CREDIT_CHECK_CODE_DICT[ch] * weighting_factor[i]
        check = 31 - total % 31
        if check == 31:
            c18 = '0'
        else:
            for k, v in SOCIAL_CREDIT_CHECK_CODE_DICT.items():
                if v == check:
                    c18 = k
                    break
        return codes + c18


def business_license():
    """统一对外接口"""
    return CreditIdentifier().get_social_credit_code()

