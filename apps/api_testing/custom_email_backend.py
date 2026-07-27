from django.core.mail.backends.smtp import EmailBackend
from django.conf import settings
import ssl
import smtplib
import logging

logger = logging.getLogger(__name__)


class CustomEmailBackend(EmailBackend):
    def open(self):
        """打开SMTP连接，使用自定义SSL上下文"""
        if self.connection:
            return False
        
        # 记录配置信息（不记录密码）
        logger.info(f"正在连接SMTP服务器: {self.host}:{self.port}")
        logger.info(f"SSL: {self.use_ssl}, TLS: {self.use_tls}, 用户名: {self.username}")
        
        # 创建SSL上下文，禁用证书验证
        ssl_context = ssl._create_unverified_context()
        
        try:
            if self.use_ssl:
                # 使用SSL连接 (端口465)
                logger.info(f"尝试使用SSL连接到 {self.host}:{self.port}")
                self.connection = smtplib.SMTP_SSL(
                    self.host, 
                    self.port, 
                    context=ssl_context,
                    timeout=self.timeout
                )
                logger.info("SSL连接建立成功")
            else:
                # 使用普通连接，然后升级到TLS (端口587)
                logger.info(f"尝试连接到 {self.host}:{self.port}")
                self.connection = smtplib.SMTP(
                    self.host, 
                    self.port, 
                    timeout=self.timeout
                )
                logger.info("SMTP连接建立成功")
                if self.use_tls:
                    logger.info("正在启动TLS...")
                    self.connection.starttls(context=ssl_context)
                    logger.info("TLS启动成功")
            
            if self.username and self.password:
                logger.info(f"正在使用用户名 '{self.username}' 进行认证...")
                self.connection.login(self.username, self.password)
                logger.info("SMTP认证成功")
            else:
                logger.warning("未提供用户名或密码，跳过认证")
            
            return True
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP认证失败: {str(e)}. 请检查EMAIL_HOST_USER和EMAIL_HOST_PASSWORD是否正确"
            logger.error(error_msg)
            if not self.fail_silently:
                raise Exception(error_msg) from e
        except smtplib.SMTPConnectError as e:
            error_msg = f"无法连接到SMTP服务器 {self.host}:{self.port}: {str(e)}. 请检查EMAIL_HOST和EMAIL_PORT是否正确"
            logger.error(error_msg)
            if not self.fail_silently:
                raise Exception(error_msg) from e
        except smtplib.SMTPServerDisconnected as e:
            error_msg = f"SMTP服务器意外断开连接: {str(e)}. 可能的原因：1) 服务器地址或端口错误 2) TLS/SSL配置不匹配 3) 防火墙阻止连接 4) 连接超时"
            logger.error(error_msg)
            # 确保清理连接状态，以便下次重试
            self.connection = None
            if not self.fail_silently:
                raise Exception(error_msg) from e
        except (ConnectionError, OSError) as e:
            # 处理 "Connection unexpectedly closed" 等网络错误
            error_msg = f"SMTP连接网络错误: {str(e)}. 可能的原因：1) 网络不稳定 2) 服务器主动断开连接 3) 防火墙或代理问题"
            logger.error(error_msg)
            self.connection = None
            if not self.fail_silently:
                raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"SMTP连接失败: {type(e).__name__}: {str(e)}. 配置: host={self.host}, port={self.port}, ssl={self.use_ssl}, tls={self.use_tls}"
            logger.error(error_msg, exc_info=True)
            self.connection = None
            if not self.fail_silently:
                raise Exception(error_msg) from e