#!/usr/bin/env python3
"""
Zotero 本地文献分析器（增强版）

本脚本提供以下功能：
1. 配置文件管理：保存和加载所有参数到本地配置文件
2. 集合选择：交互式选择 Zotero 集合/文件夹进行分析
3. 文献分析：使用大模型 API 分析每篇文献
4. 结构化输出：生成包含题目、作者、摘要、创新点、总结的 CSV 文件

支持的特性：
- 配置文件分层管理（默认配置 + 用户配置）
- 交互式配置向导
- 集合树形显示和搜索
- 批量处理和错误恢复
- 多种 API 服务支持

使用方法：
python zotero_analyzer_enhanced.py [选项]

作者：基于原始 zotero-arxiv-daily 项目修改
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict
from tqdm import tqdm
from loguru import logger
import time

# 导入自定义模块
from zotero_reader import get_local_zotero_items, LocalZoteroReader
from analyzer import PaperAnalyzer, PaperAnalysis
from exporter import CSVExporter
from config import ConfigManager, AnalyzerConfig, ConfigWizard, load_config, save_config
from selector import select_collections_interactive, get_available_collections


def setup_logger(config: AnalyzerConfig):
    """设置日志记录器"""
    logger.remove()
    
    log_level = "DEBUG" if config.debug else config.log_level
    log_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    
    # 控制台输出
    logger.add(sys.stdout, level=log_level, format=log_format)
    
    # 文件输出
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "zotero_analyzer_{time:YYYY-MM-DD}.log",
        level=log_level,
        format=log_format,
        rotation="1 day",
        retention="30 days"
    )


def filter_papers(papers: List[dict], config: AnalyzerConfig) -> List[dict]:
    """
    根据配置过滤文献列表
    
    Args:
        papers: 原始文献列表
        config: 分析器配置
        
    Returns:
        过滤后的文献列表
    """
    filtered_papers = papers.copy()
    
    # 按类型过滤
    if config.include_types:
        filtered_papers = [p for p in filtered_papers if p.get('typeName') in config.include_types]
        logger.info(f"按类型过滤后剩余 {len(filtered_papers)} 篇文献")
    
    # 按关键词排除
    if config.exclude_keywords:
        original_count = len(filtered_papers)
        filtered_papers = [
            p for p in filtered_papers 
            if not any(keyword.lower() in p.get('title', '').lower() for keyword in config.exclude_keywords)
        ]
        excluded_count = original_count - len(filtered_papers)
        if excluded_count > 0:
            logger.info(f"按关键词排除了 {excluded_count} 篇文献，剩余 {len(filtered_papers)} 篇")
    
    # 限制数量
    if config.limit and len(filtered_papers) > config.limit:
        filtered_papers = filtered_papers[:config.limit]
        logger.info(f"限制处理数量为 {config.limit} 篇文献")
    
    return filtered_papers


def analyze_papers_batch(papers: List[dict], 
                        analyzer: PaperAnalyzer,
                        config: AnalyzerConfig,
                        zotero_data_dir: Optional[str] = None) -> List[PaperAnalysis]:
    """
    批量分析文献
    
    Args:
        papers: 文献列表
        analyzer: 文献分析器
        config: 分析器配置
        zotero_data_dir: Zotero 数据目录
        
    Returns:
        分析结果列表
    """
    analyses = []
    total_papers = len(papers)
    
    logger.info(f"开始批量分析 {total_papers} 篇文献")
    
    with tqdm(total=total_papers, desc="分析进度") as pbar:
        for i, paper in enumerate(papers):
            try:
                # 分析单篇文献
                analysis = analyzer.analyze_paper(paper, zotero_data_dir)
                analyses.append(analysis)
                
                # 更新进度条
                title = paper.get('title', 'Unknown')
                pbar.set_description(f"已完成: {title[:50]}...")
                pbar.update(1)
                
                # API 调用间隔
                if config.delay > 0:
                    time.sleep(config.delay)
                    
            except KeyboardInterrupt:
                logger.warning("用户中断，正在保存已分析的结果...")
                return analyses
                
            except Exception as e:
                logger.error(f"分析文献失败: {paper.get('title', 'Unknown')}: {e}")
                # 创建错误分析结果
                error_analysis = PaperAnalysis(
                    title=paper.get('title', '未知标题'),
                    authors='; '.join([c.get('name', '') for c in paper.get('creators', [])]),
                    abstract=paper.get('abstractNote', ''),
                    innovation_points=f"分析失败: {str(e)}",
                    summary=f"分析失败: {str(e)}",
                    original_abstract=paper.get('abstractNote', ''),
                    error_message=str(e)
                )
                analyses.append(error_analysis)
                pbar.update(1)
                
                # 继续处理下一篇
                continue
    
    logger.success(f"批量分析完成，共处理 {len(analyses)} 篇文献")
    return analyses


def get_papers_from_config(config: AnalyzerConfig, interactive_collection: bool = False) -> List[Dict]:
    """
    根据配置获取文献列表
    
    Args:
        config: 分析器配置
        interactive_collection: 是否使用交互式集合选择
        
    Returns:
        文献列表
    """
    # 确定数据库路径
    database_path = config.database_path
    
    if not database_path:
        # 自动检测 Zotero 数据库
        try:
            reader = LocalZoteroReader()
            database_path = reader.database_path
            logger.info(f"自动检测到 Zotero 数据库: {database_path}")
        except Exception as e:
            logger.error(f"无法自动检测 Zotero 数据库: {e}")
            raise
    
    # 选择集合或读取所有文献
    if interactive_collection or config.selected_collections:
        if interactive_collection:
            # 交互式选择集合
            selected_keys, papers = select_collections_interactive(database_path)
            
            # 更新配置中的选择集合
            config.selected_collections = selected_keys
            config_manager = ConfigManager()
            config_manager.save_recent_config(config)
            
        else:
            # 使用配置中的集合
            from selector import CollectionManager
            collection_manager = CollectionManager(database_path)
            papers = collection_manager.get_collection_items(config.selected_collections)
            logger.info(f"从配置的集合中加载了 {len(papers)} 篇文献")
    else:
        # 读取所有文献
        papers = get_local_zotero_items(database_path)
        logger.info(f"读取了所有 {len(papers)} 篇文献")
    
    return papers


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Zotero 本地文献分析器（增强版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用模式:
  1. 首次使用：运行配置向导设置所有参数
     python zotero_analyzer_enhanced.py --config-wizard
  
  2. 交互式集合选择：选择特定文件夹进行分析
     python zotero_analyzer_enhanced.py --select-collections
  
  3. 使用保存的配置：直接运行分析
     python zotero_analyzer_enhanced.py
  
  4. 临时覆盖配置：使用命令行参数
     python zotero_analyzer_enhanced.py --limit 10 --model gpt-4

配置文件管理:
  --config-wizard        运行配置向导
  --config-summary       显示当前配置摘要
  --config-reset         重置配置为默认值
  --config-export FILE   导出配置到文件
  --config-import FILE   从文件导入配置
        """
    )
    
    # 配置管理参数
    config_group = parser.add_argument_group('配置管理')
    config_group.add_argument(
        '--config-wizard',
        action='store_true',
        help='运行交互式配置向导'
    )
    config_group.add_argument(
        '--config-summary',
        action='store_true',
        help='显示当前配置摘要'
    )
    config_group.add_argument(
        '--config-reset',
        action='store_true',
        help='重置配置为默认值'
    )
    config_group.add_argument(
        '--config-export',
        type=str,
        metavar='FILE',
        help='导出配置到文件'
    )
    config_group.add_argument(
        '--config-import',
        type=str,
        metavar='FILE',
        help='从文件导入配置'
    )
    
    # 数据选择参数
    data_group = parser.add_argument_group('数据选择')
    data_group.add_argument(
        '--select-collections',
        action='store_true',
        help='交互式选择 Zotero 集合'
    )
    data_group.add_argument(
        '--database-path',
        type=str,
        help='Zotero 数据库文件路径（覆盖配置）'
    )
    
    # API 配置参数（可覆盖配置文件）
    api_group = parser.add_argument_group('API 配置')
    api_group.add_argument(
        '--api-key',
        type=str,
        help='API 密钥（覆盖配置）'
    )
    api_group.add_argument(
        '--base-url',
        type=str,
        help='API 基础 URL（覆盖配置）'
    )
    api_group.add_argument(
        '--model',
        type=str,
        help='模型名称（覆盖配置）'
    )
    api_group.add_argument(
        '--language',
        type=str,
        choices=['Chinese', 'English'],
        help='输出语言（覆盖配置）'
    )
    
    # 处理配置参数
    process_group = parser.add_argument_group('处理配置')
    process_group.add_argument(
        '--limit',
        type=int,
        help='限制处理文献数量（覆盖配置）'
    )
    process_group.add_argument(
        '--include-types',
        type=str,
        nargs='+',
        help='包含的文献类型（覆盖配置）'
    )
    process_group.add_argument(
        '--exclude-keywords',
        type=str,
        nargs='+',
        help='排除关键词（覆盖配置）'
    )
    process_group.add_argument(
        '--delay',
        type=float,
        help='API 调用间隔秒数（覆盖配置）'
    )
    
    # 输出配置参数
    output_group = parser.add_argument_group('输出配置')
    output_group.add_argument(
        '--output-dir',
        type=str,
        help='输出目录（覆盖配置）'
    )
    output_group.add_argument(
        '--export-detailed',
        action='store_true',
        help='导出详细报告（覆盖配置）'
    )
    output_group.add_argument(
        '--no-export-statistics',
        action='store_true',
        help='不导出统计信息'
    )
    
    # 调试参数
    debug_group = parser.add_argument_group('调试选项')
    debug_group.add_argument(
        '--debug',
        action='store_true',
        help='启用调试模式'
    )
    debug_group.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='日志级别'
    )
    
    args = parser.parse_args()
    
    # 初始化配置管理器
    config_manager = ConfigManager()
    
    # 处理配置管理命令
    if args.config_wizard:
        wizard = ConfigWizard(config_manager)
        config = wizard.run_interactive_setup()
        print("\n✅ 配置已保存，现在可以运行分析了！")
        return
    
    if args.config_summary:
        summary = config_manager.get_config_summary()
        print("📋 当前配置摘要:")
        print("=" * 50)
        for section, values in summary.items():
            print(f"\n{section}:")
            for key, value in values.items():
                print(f"  {key}: {value}")
        return
    
    if args.config_reset:
        confirm = input("⚠️ 确定要重置配置为默认值吗？这将删除所有自定义设置。(y/N): ")
        if confirm.lower() == 'y':
            config_manager.reset_to_default()
            print("✅ 配置已重置为默认值")
        return
    
    if args.config_export:
        config_manager.export_config(args.config_export)
        print(f"✅ 配置已导出到: {args.config_export}")
        return
    
    if args.config_import:
        try:
            config_manager.import_config(args.config_import)
            print(f"✅ 配置已从 {args.config_import} 导入")
        except Exception as e:
            print(f"❌ 导入配置失败: {e}")
            sys.exit(1)
        return
    
    # 加载配置
    config = config_manager.load_config()
    
    # 命令行参数覆盖配置文件设置
    if args.api_key:
        config.api_key = args.api_key
    if args.base_url:
        config.base_url = args.base_url
    if args.model:
        config.model = args.model
    if args.language:
        config.language = args.language
    if args.database_path:
        config.database_path = args.database_path
    if args.limit is not None:
        config.limit = args.limit
    if args.include_types:
        config.include_types = args.include_types
    if args.exclude_keywords:
        config.exclude_keywords = args.exclude_keywords
    if args.delay is not None:
        config.delay = args.delay
    if args.output_dir:
        config.output_dir = args.output_dir
    if args.export_detailed:
        config.export_detailed = True
    if args.no_export_statistics:
        config.export_statistics = False
    if args.debug:
        config.debug = True
    if args.log_level:
        config.log_level = args.log_level
    
    # 设置日志
    setup_logger(config)
    
    # 检查 API 密钥
    if not config.api_key:
        api_key = os.environ.get('OPENAI_API_KEY')
        if api_key:
            config.api_key = api_key
        else:
            logger.error("未找到 API 密钥！")
            print("请通过以下方式之一提供 API 密钥：")
            print("1. 运行配置向导: python zotero_analyzer_enhanced.py --config-wizard")
            print("2. 使用命令行参数: --api-key YOUR_KEY")
            print("3. 设置环境变量: export OPENAI_API_KEY=YOUR_KEY")
            sys.exit(1)
    
    try:
        # 1. 获取文献数据
        logger.info("开始获取文献数据...")
        papers = get_papers_from_config(config, args.select_collections)
        
        if not papers:
            logger.error("未找到任何文献，请检查数据库路径或集合选择")
            sys.exit(1)
        
        logger.info(f"成功获取 {len(papers)} 篇文献")
        
        # 2. 过滤文献
        filtered_papers = filter_papers(papers, config)
        
        if not filtered_papers:
            logger.error("过滤后没有文献需要处理")
            sys.exit(1)
        
        logger.info(f"过滤后需要处理 {len(filtered_papers)} 篇文献")
        
        # 3. 初始化分析器
        logger.info("初始化文献分析器...")
        analyzer = PaperAnalyzer(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            language=config.language,
            max_pages=config.max_pages,
            max_tokens=config.max_tokens
        )
        
        # 4. 获取 Zotero 数据目录
        zotero_data_dir = None
        if config.database_path:
            zotero_data_dir = str(Path(config.database_path).parent)
        else:
            try:
                reader = LocalZoteroReader()
                zotero_data_dir = str(Path(reader.database_path).parent)
            except Exception:
                logger.warning("无法确定 Zotero 数据目录，PDF 附件可能无法读取")
        
        # 5. 批量分析文献
        analyses = analyze_papers_batch(
            filtered_papers,
            analyzer,
            config,
            zotero_data_dir=zotero_data_dir
        )
        
        if not analyses:
            logger.error("没有成功分析任何文献")
            sys.exit(1)
        
        # 6. 导出结果
        logger.info("开始导出分析结果...")
        
        # 确保输出目录存在
        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        exporter = CSVExporter(str(output_dir))
        exported_files = []
        
        # 导出基本分析结果
        basic_file = exporter.export_analyses(analyses)
        exported_files.append(basic_file)
        
        # 导出统计信息
        if config.export_statistics:
            stats_file = exporter.export_summary_statistics(analyses)
            exported_files.append(stats_file)
        
        # 导出详细报告
        if config.export_detailed:
            detailed_file = exporter.export_detailed_report(analyses)
            exported_files.append(detailed_file)
        
        # 7. 保存当前运行配置
        config_manager.save_recent_config(config)
        
        # 8. 显示结果统计
        successful_count = sum(1 for a in analyses if not a.error_message)
        failed_count = len(analyses) - successful_count
        
        logger.success("=" * 60)
        logger.success("分析完成！")
        logger.success(f"总文献数: {len(analyses)}")
        logger.success(f"成功分析: {successful_count}")
        logger.success(f"失败分析: {failed_count}")
        logger.success(f"成功率: {(successful_count/len(analyses)*100):.1f}%")
        logger.success("=" * 60)
        
        logger.success("导出的文件:")
        for file_path in exported_files:
            logger.success(f"  - {file_path}")
        
        logger.success("所有任务已完成！")
        
    except KeyboardInterrupt:
        logger.warning("用户中断程序")
        sys.exit(130)
    except Exception as e:
        logger.error(f"程序执行出错: {e}")
        if config.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 