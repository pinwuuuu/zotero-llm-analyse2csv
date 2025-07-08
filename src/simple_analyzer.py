#!/usr/bin/env python3
"""
Zotero 本地文献分析器

本脚本用于：
1. 读取本地 Zotero 数据库文件
2. 对每篇文献调用大模型 API 进行分析
3. 输出结构化的分析结果到 CSV 文件

使用方法：
python zotero_local_analyzer.py --api-key YOUR_API_KEY [其他选项]

作者：基于原始 zotero-arxiv-daily 项目修改
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional
from tqdm import tqdm
from loguru import logger
import time

# 导入自定义模块
from .zotero_reader import get_local_zotero_items, LocalZoteroReader
from .analyzer import PaperAnalyzer, PaperAnalysis
from .exporter import export_to_csv


def setup_logger(debug: bool = False):
    """设置日志记录器"""
    logger.remove()
    
    log_level = "DEBUG" if debug else "INFO"
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


def filter_papers(papers: List[dict], 
                  limit: Optional[int] = None,
                  include_types: Optional[List[str]] = None,
                  exclude_keywords: Optional[List[str]] = None) -> List[dict]:
    """
    过滤文献列表
    
    Args:
        papers: 原始文献列表
        limit: 限制处理的文献数量
        include_types: 包含的文献类型
        exclude_keywords: 排除包含特定关键词的文献
        
    Returns:
        过滤后的文献列表
    """
    filtered_papers = papers.copy()
    
    # 按类型过滤
    if include_types:
        filtered_papers = [p for p in filtered_papers if p.get('typeName') in include_types]
        logger.info(f"按类型过滤后剩余 {len(filtered_papers)} 篇文献")
    
    # 按关键词排除
    if exclude_keywords:
        original_count = len(filtered_papers)
        filtered_papers = [
            p for p in filtered_papers 
            if not any(keyword.lower() in p.get('title', '').lower() for keyword in exclude_keywords)
        ]
        excluded_count = original_count - len(filtered_papers)
        if excluded_count > 0:
            logger.info(f"按关键词排除了 {excluded_count} 篇文献，剩余 {len(filtered_papers)} 篇")
    
    # 限制数量
    if limit and len(filtered_papers) > limit:
        filtered_papers = filtered_papers[:limit]
        logger.info(f"限制处理数量为 {limit} 篇文献")
    
    return filtered_papers


def analyze_papers_batch(papers: List[dict], 
                        analyzer: PaperAnalyzer,
                        zotero_data_dir: Optional[str] = None,
                        batch_size: int = 1,
                        delay_between_calls: float = 1.0) -> List[PaperAnalysis]:
    """
    批量分析文献
    
    Args:
        papers: 文献列表
        analyzer: 文献分析器
        zotero_data_dir: Zotero 数据目录
        batch_size: 批处理大小
        delay_between_calls: API 调用间隔（秒）
        
    Returns:
        分析结果列表
    """
    analyses = []
    total_papers = len(papers)
    
    logger.info(f"开始批量分析 {total_papers} 篇文献，批大小: {batch_size}")
    
    with tqdm(total=total_papers, desc="分析进度") as pbar:
        for i in range(0, total_papers, batch_size):
            batch = papers[i:i + batch_size]
            
            for paper in batch:
                try:
                    # 分析单篇文献
                    analysis = analyzer.analyze_paper(paper, zotero_data_dir)
                    analyses.append(analysis)
                    
                    # 更新进度条
                    pbar.set_description(f"已完成: {paper.get('title', 'Unknown')[:50]}...")
                    pbar.update(1)
                    
                    # API 调用间隔
                    if delay_between_calls > 0:
                        time.sleep(delay_between_calls)
                        
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


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Zotero 本地文献分析器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基本使用（需要设置 OPENAI_API_KEY 环境变量）
  python zotero_local_analyzer.py
  
  # 指定 API 密钥和其他参数
  python zotero_local_analyzer.py --api-key sk-xxx --model gpt-4 --limit 10
  
  # 使用其他 API 服务（如 SiliconFlow）
  python zotero_local_analyzer.py --api-key sk-xxx --base-url https://api.siliconflow.cn/v1 --model Qwen/Qwen2.5-7B-Instruct
  
  # 指定 Zotero 数据库路径
  python zotero_local_analyzer.py --database-path /path/to/zotero.sqlite
        """
    )
    
    # 必需参数
    parser.add_argument(
        '--api-key',
        type=str,
        help='OpenAI API 密钥（也可通过 OPENAI_API_KEY 环境变量设置）'
    )
    
    # 可选参数
    parser.add_argument(
        '--database-path',
        type=str,
        help='Zotero 数据库文件路径（如果不指定则自动查找）'
    )
    
    parser.add_argument(
        '--base-url',
        type=str,
        default='https://api.openai.com/v1',
        help='API 基础 URL（默认: https://api.openai.com/v1）'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default='gpt-4o',
        help='使用的模型名称（默认: gpt-4o）'
    )
    
    parser.add_argument(
        '--language',
        type=str,
        default='Chinese',
        choices=['Chinese', 'English'],
        help='输出语言（默认: Chinese）'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='输出目录（默认: output）'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help='限制处理的文献数量'
    )
    
    parser.add_argument(
        '--include-types',
        type=str,
        nargs='+',
        help='包含的文献类型（如: journalArticle conferencePaper）'
    )
    
    parser.add_argument(
        '--exclude-keywords',
        type=str,
        nargs='+',
        help='排除包含特定关键词的文献'
    )
    
    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='API 调用间隔秒数（默认: 1.0）'
    )
    
    parser.add_argument(
        '--export-detailed',
        action='store_true',
        help='导出详细报告'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='启用调试模式'
    )
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logger(args.debug)
    
    # 获取 API 密钥
    api_key = args.api_key or os.environ.get('OPENAI_API_KEY')
    if not api_key:
        logger.error("请提供 API 密钥，通过 --api-key 参数或 OPENAI_API_KEY 环境变量")
        sys.exit(1)
    
    try:
        # 1. 读取本地 Zotero 数据
        logger.info("开始读取本地 Zotero 数据...")
        papers = get_local_zotero_items(args.database_path)
        
        if not papers:
            logger.error("未找到任何文献，请检查 Zotero 数据库路径")
            sys.exit(1)
        
        logger.info(f"成功读取 {len(papers)} 篇文献")
        
        # 2. 过滤文献
        filtered_papers = filter_papers(
            papers,
            limit=args.limit,
            include_types=args.include_types,
            exclude_keywords=args.exclude_keywords
        )
        
        if not filtered_papers:
            logger.error("过滤后没有文献需要处理")
            sys.exit(1)
        
        logger.info(f"过滤后需要处理 {len(filtered_papers)} 篇文献")
        
        # 3. 初始化分析器
        logger.info("初始化文献分析器...")
        analyzer = PaperAnalyzer(
            api_key=api_key,
            base_url=args.base_url,
            model=args.model,
            language=args.language
        )
        
        # 4. 获取 Zotero 数据目录
        zotero_data_dir = None
        if args.database_path:
            zotero_data_dir = str(Path(args.database_path).parent)
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
            zotero_data_dir=zotero_data_dir,
            delay_between_calls=args.delay
        )
        
        if not analyses:
            logger.error("没有成功分析任何文献")
            sys.exit(1)
        
        # 6. 导出结果
        logger.info("开始导出分析结果...")
        exported_files = export_to_csv(
            analyses,
            output_dir=args.output_dir,
            export_statistics=True,
            export_detailed=args.export_detailed
        )
        
        # 7. 显示结果统计
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
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 