"""
LLM模型客户端工厂
借鉴ui-automation项目的模型管理设计，统一管理多个模型客户端
"""
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI
import logging

logger = logging.getLogger('django')

# 全局模型客户端缓存
_model_clients: Dict[str, ChatOpenAI] = {}


class LLMFactory:
    """LLM模型客户端工厂，统一管理模型创建和回退"""
    
    @staticmethod
    def create_text_model(config: Any) -> Optional[ChatOpenAI]:
        """创建文本模型客户端
        
        Args:
            config: AIModelConfig对象，包含模型配置信息
            
        Returns:
            ChatOpenAI: 模型客户端实例，失败返回None
        """
        if not config:
            return None
        
        cache_key = f"text_{config.id}"
        if cache_key in _model_clients:
            return _model_clients[cache_key]
        
        try:
            model = ChatOpenAI(
                model=config.model_name,
                base_url=config.base_url,
                api_key=config.api_key,
                temperature=0.7,
                timeout=60,
            )
            _model_clients[cache_key] = model
            logger.info(f"✅ 创建文本模型客户端: {config.model_name} (ID: {config.id})")
            return model
        except Exception as e:
            logger.error(f"❌ 创建文本模型客户端失败: {e}")
            return None
    
    @staticmethod
    def create_vision_model(config: Any) -> Optional[ChatOpenAI]:
        """创建视觉模型客户端
        
        Args:
            config: AIModelConfig对象，包含模型配置信息
            
        Returns:
            ChatOpenAI: 模型客户端实例，失败返回None
        """
        if not config:
            return None
        
        cache_key = f"vision_{config.id}"
        if cache_key in _model_clients:
            return _model_clients[cache_key]
        
        try:
            model = ChatOpenAI(
                model=config.model_name,
                base_url=config.base_url,
                api_key=config.api_key,
                temperature=0.7,
                timeout=60,
            )
            _model_clients[cache_key] = model
            logger.info(f"✅ 创建视觉模型客户端: {config.model_name} (ID: {config.id})")
            return model
        except Exception as e:
            logger.error(f"❌ 创建视觉模型客户端失败: {e}")
            return None
    
    @staticmethod
    def create_with_fallback(primary_config: Any, fallback_config: Any = None) -> Optional[ChatOpenAI]:
        """创建模型客户端，支持回退机制
        
        Args:
            primary_config: 主模型配置
            fallback_config: 备用模型配置
            
        Returns:
            ChatOpenAI: 模型客户端实例，失败返回None
        """
        # 尝试创建主模型
        if primary_config:
            model = LLMFactory.create_text_model(primary_config)
            if model:
                return model
        
        # 主模型失败，尝试备用模型
        if fallback_config:
            logger.warning(f"⚠️ 主模型创建失败，回退到备用模型")
            model = LLMFactory.create_text_model(fallback_config)
            if model:
                return model
        
        logger.error("❌ 所有模型创建失败")
        return None
    
    @staticmethod
    def clear_cache():
        """清空模型客户端缓存"""
        global _model_clients
        _model_clients.clear()
        logger.info("已清空模型客户端缓存")
    
    @staticmethod
    def get_cache_status() -> Dict[str, Any]:
        """获取缓存状态"""
        return {
            "cached_models": list(_model_clients.keys()),
            "cache_count": len(_model_clients)
        }
