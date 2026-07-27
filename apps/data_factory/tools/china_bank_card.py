# -*- coding: utf-8 -*-
# -----------------------------
# @Author    : 影子
# @Time      : 2026/1/18 23:05
# @Software  : PyCharm
# @FileName  : bank_card.py
# -----------------------------
"""银行卡号生成器"""
import random


class BankCard:
    """银行卡号生成器"""

    @staticmethod
    def __generate_bin():
        """随机返回银行卡相应的 BIN（前6位）"""
        # 这里直接复用完整 BIN 列表
        bins = (622208, 622848, 622777, 622262, 623529, 625153, 6201361, 6201362, 6201363, 6201365, 6201366, 6201367,
                6201368, 6201369, 6230740, 6230741, 6230742, 6230743, 6230745, 6230746, 6230747, 6230748, 6230749,
                6235241, 6235242, 6235243, 6235244, 6235245, 6235246, 6235248, 6251640, 6251642, 6251643, 6251644,
                6251645, 6251646, 6251647, 6251648, 6251649)
        return str(random.choice(bins))

    @staticmethod
    def __calculate_luhn(card_number):
        """计算并返回 Luhn 校验位"""

        def digits_of(n):
            return [int(d) for d in str(n)]

        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
        return (10 - checksum % 10) % 10

    @staticmethod
    def generate_card_number(length=16):
        """生成指定长度的银行卡号"""
        middle_part_length = length - 7  # 减去 BIN 和校验位
        middle_part = ''.join([str(random.randint(0, 9)) for _ in range(middle_part_length)])

        card_number_without_checksum = BankCard.__generate_bin() + middle_part
        checksum_digit = BankCard.__calculate_luhn(card_number_without_checksum)
        card_number = card_number_without_checksum + str(checksum_digit)

        return card_number


def bank_card():
    """对外提供银行卡号调用"""
    card_number = BankCard.generate_card_number()
    return card_number

