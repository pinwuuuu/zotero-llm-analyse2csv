#!/usr/bin/env python3
"""
配置文件管理模块

用于保存和加载 Zotero 本地分析器的所有配置参数。
支持默认配置、用户配置和运行时配置的分层管理。
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from loguru import logger


@dataclass
class AnalyzerConfig:
    """分析器配置数据类"""
    # API 配置
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    language: str = "Chinese"
    
    # Zotero 配置
    database_path: str = ""
    zotero_data_dir: str = ""
    
    # 过滤配置
    limit: Optional[int] = None
    include_types: List[str] = None
    exclude_keywords: List[str] = None
    selected_collections: List[str] = None
    
    # 处理配置
    delay: float = 1.0
    max_pages: int = 50
    max_tokens: int = 8000
    
    # 输出配置
    output_dir: str = "output"
    export_detailed: bool = False
    export_statistics: bool = True
    
    # 调试配置
    debug: bool = False
    log_level: str = "INFO"
    
    def __post_init__(self):
        """初始化后处理"""
        if self.include_types is None:
            self.include_types = []
        if self.exclude_keywords is None:
            self.exclude_keywords = []
        if self.selected_collections is None:
            self.selected_collections = []


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = "config"):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        self.default_config_file = self.config_dir / "default.json"
        self.user_config_file = self.config_dir / "user.json"
        self.recent_config_file = self.config_dir / "recent.json"
        
        # 创建默认配置文件
        self._create_default_config()
        
        logger.info(f"配置管理器初始化完成，配置目录: {self.config_dir}")
    
    def _create_default_config(self):
        """创建默认配置文件"""
        if not self.default_config_file.exists():
            default_config = AnalyzerConfig()
            self._save_config_to_file(default_config, self.default_config_file)
            logger.info("创建默认配置文件")
    
    def _save_config_to_file(self, config: AnalyzerConfig, file_path: Path):
        """保存配置到文件"""
        try:
            config_dict = asdict(config)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            logger.debug(f"配置已保存到: {file_path}")
        except Exception as e:
            logger.error(f"保存配置失败 {file_path}: {e}")
            raise
    
    def _load_config_from_file(self, file_path: Path) -> Optional[AnalyzerConfig]:
        """从文件加载配置"""
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            
            # 处理可能的 None 值
            for key in ['include_types', 'exclude_keywords', 'selected_collections']:
                if config_dict.get(key) is None:
                    config_dict[key] = []
            
            config = AnalyzerConfig(**config_dict)
            logger.debug(f"配置已从 {file_path} 加载")
            return config
            
        except Exception as e:
            logger.error(f"加载配置失败 {file_path}: {e}")
            return None
    
    def load_config(self) -> AnalyzerConfig:
        """
        加载配置（分层合并）
        优先级：用户配置 > 默认配置
        
        Returns:
            合并后的配置对象
        """
        # 加载默认配置
        default_config = self._load_config_from_file(self.default_config_file)
        if default_config is None:
            default_config = AnalyzerConfig()
        
        # 加载用户配置
        user_config = self._load_config_from_file(self.user_config_file)
        
        if user_config is None:
            return default_config
        
        # 合并配置
        merged_config = self._merge_configs(default_config, user_config)
        return merged_config
    
    def _merge_configs(self, base_config: AnalyzerConfig, override_config: AnalyzerConfig) -> AnalyzerConfig:
        """合并两个配置对象"""
        base_dict = asdict(base_config)
        override_dict = asdict(override_config)
        
        # 合并字典，非空值覆盖基础值
        for key, value in override_dict.items():
            if value is not None and value != "" and value != []:
                base_dict[key] = value
        
        return AnalyzerConfig(**base_dict)
    
    def save_user_config(self, config: AnalyzerConfig):
        """保存用户配置"""
        self._save_config_to_file(config, self.user_config_file)
        logger.info("用户配置已保存")
    
    def save_recent_config(self, config: AnalyzerConfig):
        """保存最近使用的配置"""
        self._save_config_to_file(config, self.recent_config_file)
        logger.debug("最近配置已保存")
    
    def load_recent_config(self) -> Optional[AnalyzerConfig]:
        """加载最近使用的配置"""
        return self._load_config_from_file(self.recent_config_file)
    
    def update_user_config(self, **kwargs):
        """更新用户配置的特定字段"""
        # 加载现有用户配置
        current_config = self._load_config_from_file(self.user_config_file)
        if current_config is None:
            current_config = AnalyzerConfig()
        
        # 更新指定字段
        current_dict = asdict(current_config)
        for key, value in kwargs.items():
            if hasattr(current_config, key):
                current_dict[key] = value
            else:
                logger.warning(f"忽略未知配置字段: {key}")
        
        # 保存更新后的配置
        updated_config = AnalyzerConfig(**current_dict)
        self.save_user_config(updated_config)
        
        return updated_config
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要信息"""
        config = self.load_config()
        
        return {
            "API 配置": {
                "base_url": config.base_url,
                "model": config.model,
                "language": config.language,
                "api_key_set": bool(config.api_key)
            },
            "Zotero 配置": {
                "database_path": config.database_path,
                "auto_detect": not bool(config.database_path)
            },
            "过滤配置": {
                "limit": config.limit,
                "include_types": config.include_types,
                "exclude_keywords": config.exclude_keywords,
                "selected_collections": len(config.selected_collections)
            },
            "输出配置": {
                "output_dir": config.output_dir,
                "export_detailed": config.export_detailed,
                "export_statistics": config.export_statistics
            }
        }
    
    def reset_to_default(self):
        """重置为默认配置"""
        if self.user_config_file.exists():
            backup_file = self.config_dir / f"user_backup_{int(__import__('time').time())}.json"
            self.user_config_file.rename(backup_file)
            logger.info(f"用户配置已备份到: {backup_file}")
        
        logger.info("配置已重置为默认值")
    
    def export_config(self, export_path: str):
        """导出当前配置到指定路径"""
        config = self.load_config()
        export_file = Path(export_path)
        
        # 导出时移除敏感信息
        export_dict = asdict(config)
        if export_dict.get('api_key'):
            export_dict['api_key'] = "YOUR_API_KEY_HERE"
        
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(export_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"配置已导出到: {export_path}")
    
    def import_config(self, import_path: str):
        """从指定路径导入配置"""
        import_file = Path(import_path)
        if not import_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {import_path}")
        
        imported_config = self._load_config_from_file(import_file)
        if imported_config is None:
            raise ValueError(f"无法解析配置文件: {import_path}")
        
        self.save_user_config(imported_config)
        logger.info(f"配置已从 {import_path} 导入")


class ConfigWizard:
    """配置向导"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
    
    def run_interactive_setup(self) -> AnalyzerConfig:
        """运行交互式配置向导"""
        print("🧙‍♂️ Zotero 分析器配置向导")
        print("=" * 50)
        
        config = self.config_manager.load_config()
        
        # API 配置
        print("\n📡 API 配置")
        config = self._setup_api_config(config)
        
        # Zotero 配置
        print("\n📚 Zotero 配置")
        config = self._setup_zotero_config(config)
        
        # 处理配置
        print("\n⚙️ 处理配置")
        config = self._setup_processing_config(config)
        
        # 输出配置
        print("\n📤 输出配置")
        config = self._setup_output_config(config)
        
        # 保存配置
        self.config_manager.save_user_config(config)
        
        print("\n✅ 配置完成！")
        return config
    
    def _setup_api_config(self, config: AnalyzerConfig) -> AnalyzerConfig:
        """设置 API 配置"""
        # API 密钥
        current_key = "已设置" if config.api_key else "未设置"
        print(f"当前 API 密钥: {current_key}")
        
        if not config.api_key or input("是否更新 API 密钥? (y/N): ").lower() == 'y':
            api_key = input("请输入 OpenAI API 密钥: ").strip()
            if api_key:
                config.api_key = api_key
        
        # API 基础 URL
        print(f"当前 API URL: {config.base_url}")
        if input("是否使用其他 API 服务? (y/N): ").lower() == 'y':
            print("推荐选项:")
            print("1. OpenAI (默认): https://api.openai.com/v1")
            print("2. SiliconFlow: https://api.siliconflow.cn/v1")
            print("3. 自定义")
            
            choice = input("请选择 (1/2/3): ").strip()
            if choice == '2':
                config.base_url = "https://api.siliconflow.cn/v1"
                config.model = "Qwen/Qwen2.5-7B-Instruct"
            elif choice == '3':
                url = input("请输入自定义 API URL: ").strip()
                if url:
                    config.base_url = url
        
        # 模型选择
        print(f"当前模型: {config.model}")
        if input("是否更换模型? (y/N): ").lower() == 'y':
            model = input("请输入模型名称: ").strip()
            if model:
                config.model = model
        
        return config
    
    def _setup_zotero_config(self, config: AnalyzerConfig) -> AnalyzerConfig:
        """设置 Zotero 配置"""
        print(f"当前数据库路径: {config.database_path or '自动检测'}")
        
        if input("是否手动指定 Zotero 数据库路径? (y/N): ").lower() == 'y':
            path = input("请输入数据库文件路径: ").strip()
            if path and Path(path).exists():
                config.database_path = path
            else:
                print("路径无效，将使用自动检测")
        
        return config
    
    def _setup_processing_config(self, config: AnalyzerConfig) -> AnalyzerConfig:
        """设置处理配置"""
        # 处理限制
        print(f"当前处理限制: {config.limit or '无限制'}")
        if input("是否设置处理数量限制? (y/N): ").lower() == 'y':
            try:
                limit = int(input("请输入最大处理数量: "))
                config.limit = limit if limit > 0 else None
            except ValueError:
                print("输入无效，保持原设置")
        
        # API 调用间隔
        print(f"当前 API 调用间隔: {config.delay} 秒")
        if input("是否调整 API 调用间隔? (y/N): ").lower() == 'y':
            try:
                delay = float(input("请输入间隔秒数: "))
                config.delay = max(0, delay)
            except ValueError:
                print("输入无效，保持原设置")
        
        return config
    
    def _setup_output_config(self, config: AnalyzerConfig) -> AnalyzerConfig:
        """设置输出配置"""
        # 输出目录
        print(f"当前输出目录: {config.output_dir}")
        if input("是否更改输出目录? (y/N): ").lower() == 'y':
            output_dir = input("请输入输出目录: ").strip()
            if output_dir:
                config.output_dir = output_dir
        
        # 导出选项
        print(f"导出详细报告: {config.export_detailed}")
        print(f"导出统计信息: {config.export_statistics}")
        
        if input("是否修改导出选项? (y/N): ").lower() == 'y':
            config.export_detailed = input("导出详细报告? (y/N): ").lower() == 'y'
            config.export_statistics = input("导出统计信息? (y/N): ").lower() == 'y'
        
        return config


# 便捷函数
def get_config_manager() -> ConfigManager:
    """获取配置管理器实例"""
    return ConfigManager()


def load_config() -> AnalyzerConfig:
    """快速加载配置"""
    return get_config_manager().load_config()


def save_config(config: AnalyzerConfig):
    """快速保存配置"""
    get_config_manager().save_user_config(config) 