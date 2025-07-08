import csv
import os
from datetime import datetime
from typing import List
from pathlib import Path
from loguru import logger
from .analyzer import PaperAnalysis

class CSVExporter:
    """CSV 导出器"""
    
    def __init__(self, output_dir: str = "output"):
        """
        初始化 CSV 导出器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info(f"初始化 CSV 导出器，输出目录: {self.output_dir}")
    
    def export_analyses(self, analyses: List[PaperAnalysis], filename: str = None, collection_names: List[str] = None) -> str:
        """
        导出文献分析结果到 CSV 文件
        
        Args:
            analyses: 文献分析结果列表
            filename: 输出文件名，如果为 None 则自动生成
            collection_names: 选择的集合名称列表，用于文件命名
            
        Returns:
            生成的 CSV 文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 如果有集合名称，添加到文件名中
            if collection_names:
                # 清理集合名称，去除特殊字符
                clean_names = []
                for name in collection_names[:3]:  # 最多使用前3个集合名
                    clean_name = "".join(c for c in name if c.isalnum() or c in "._-")
                    clean_names.append(clean_name)
                collection_str = "_".join(clean_names)
                filename = f"zotero_analysis_{collection_str}_{timestamp}.csv"
            else:
                filename = f"zotero_analysis_{timestamp}.csv"
        
        csv_path = self.output_dir / filename
        
        # 定义 CSV 字段（删除原始摘要，添加集合路径和翻译标题）
        fieldnames = [
            '序号',
            'Zotero集合',
            '论文标题',
            '中文标题',
            '作者',
            '优化摘要', 
            '创新点',
            '总结',
            '分析状态',
            '错误信息'
        ]
        
        logger.info(f"开始导出 {len(analyses)} 篇文献分析结果到 {csv_path}")
        
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # 写入表头
            writer.writeheader()
            
            # 写入数据
            for idx, analysis in enumerate(analyses, 1):
                # 处理标题显示
                title_display = analysis.title
                chinese_title = analysis.translated_title if analysis.translated_title else ""
                
                # 如果有中文翻译，在原标题后添加翻译
                if chinese_title:
                    title_display = f"{analysis.title}"
                
                row = {
                    '序号': idx,
                    'Zotero集合': analysis.collection_path,
                    '论文标题': title_display,
                    '中文标题': chinese_title,
                    '作者': analysis.authors,
                    '优化摘要': analysis.abstract,
                    '创新点': analysis.innovation_points,
                    '总结': analysis.summary,
                    '分析状态': '成功' if not analysis.error_message else '失败',
                    '错误信息': analysis.error_message
                }
                
                writer.writerow(row)
        
        logger.success(f"CSV 文件导出完成: {csv_path}")
        return str(csv_path)
    
    def export_summary_statistics(self, analyses: List[PaperAnalysis], filename: str = None, collection_names: List[str] = None) -> str:
        """
        导出统计摘要信息
        
        Args:
            analyses: 文献分析结果列表
            filename: 输出文件名，如果为 None 则自动生成
            collection_names: 选择的集合名称列表，用于文件命名
            
        Returns:
            生成的统计文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 如果有集合名称，添加到文件名中
            if collection_names:
                # 清理集合名称，去除特殊字符
                clean_names = []
                for name in collection_names[:3]:  # 最多使用前3个集合名
                    clean_name = "".join(c for c in name if c.isalnum() or c in "._-")
                    clean_names.append(clean_name)
                collection_str = "_".join(clean_names)
                filename = f"zotero_statistics_{collection_str}_{timestamp}.csv"
            else:
                filename = f"zotero_statistics_{timestamp}.csv"
        
        csv_path = self.output_dir / filename
        
        # 计算统计信息
        total_papers = len(analyses)
        successful_analyses = sum(1 for a in analyses if not a.error_message)
        failed_analyses = total_papers - successful_analyses
        
        # 统计不同错误类型
        error_types = {}
        for analysis in analyses:
            if analysis.error_message:
                error_type = analysis.error_message.split(':')[0] if ':' in analysis.error_message else analysis.error_message
                error_types[error_type] = error_types.get(error_type, 0) + 1
        
        # 统计作者数量分布
        author_counts = {}
        for analysis in analyses:
            author_count = len(analysis.authors.split(';')) if analysis.authors != '未知作者' else 0
            author_count_range = self._get_author_count_range(author_count)
            author_counts[author_count_range] = author_counts.get(author_count_range, 0) + 1
        
        logger.info(f"开始导出统计信息到 {csv_path}")
        
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            
            # 写入基本统计信息
            writer.writerow(['统计项目', '数值'])
            writer.writerow(['总论文数', total_papers])
            writer.writerow(['成功分析数', successful_analyses])
            writer.writerow(['失败分析数', failed_analyses])
            writer.writerow(['成功率', f"{(successful_analyses/total_papers*100):.1f}%" if total_papers > 0 else "0%"])
            writer.writerow([])  # 空行
            
            # 写入错误类型统计
            writer.writerow(['错误类型统计'])
            writer.writerow(['错误类型', '数量'])
            for error_type, count in sorted(error_types.items()):
                writer.writerow([error_type, count])
            writer.writerow([])  # 空行
            
            # 写入作者数量分布
            writer.writerow(['作者数量分布'])
            writer.writerow(['作者数量范围', '论文数量'])
            for range_name, count in sorted(author_counts.items()):
                writer.writerow([range_name, count])
        
        logger.success(f"统计文件导出完成: {csv_path}")
        return str(csv_path)
    
    def _get_author_count_range(self, count: int) -> str:
        """获取作者数量范围标签"""
        if count == 0:
            return "未知作者"
        elif count == 1:
            return "单作者"
        elif count <= 3:
            return "2-3作者"
        elif count <= 5:
            return "4-5作者"
        elif count <= 10:
            return "6-10作者"
        else:
            return "10+作者"
    
    def export_detailed_report(self, analyses: List[PaperAnalysis], filename: str = None, collection_names: List[str] = None) -> str:
        """
        导出详细报告，包含更多分析信息
        
        Args:
            analyses: 文献分析结果列表
            filename: 输出文件名，如果为 None 则自动生成
            collection_names: 选择的集合名称列表，用于文件命名
            
        Returns:
            生成的详细报告文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 如果有集合名称，添加到文件名中
            if collection_names:
                # 清理集合名称，去除特殊字符
                clean_names = []
                for name in collection_names[:3]:  # 最多使用前3个集合名
                    clean_name = "".join(c for c in name if c.isalnum() or c in "._-")
                    clean_names.append(clean_name)
                collection_str = "_".join(clean_names)
                filename = f"zotero_detailed_report_{collection_str}_{timestamp}.csv"
            else:
                filename = f"zotero_detailed_report_{timestamp}.csv"
        
        csv_path = self.output_dir / filename
        
        # 定义详细报告字段（删除原始摘要相关字段）
        fieldnames = [
            '序号',
            'Zotero集合',
            '论文标题',
            '中文标题',
            '作者',
            '作者数量',
            '优化摘要',
            '摘要字数',
            '创新点',
            '创新点字数',
            '总结',
            '总结字数',
            '分析状态',
            '错误信息',
            '标题长度',
            '有翻译标题'
        ]
        
        logger.info(f"开始导出详细报告到 {csv_path}")
        
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # 写入表头
            writer.writeheader()
            
            # 写入数据
            for idx, analysis in enumerate(analyses, 1):
                author_count = len(analysis.authors.split(';')) if analysis.authors != '未知作者' else 0
                
                row = {
                    '序号': idx,
                    'Zotero集合': analysis.collection_path,
                    '论文标题': analysis.title,
                    '中文标题': analysis.translated_title if analysis.translated_title else "",
                    '作者': analysis.authors,
                    '作者数量': author_count,
                    '优化摘要': analysis.abstract,
                    '摘要字数': len(analysis.abstract),
                    '创新点': analysis.innovation_points,
                    '创新点字数': len(analysis.innovation_points),
                    '总结': analysis.summary,
                    '总结字数': len(analysis.summary),
                    '分析状态': '成功' if not analysis.error_message else '失败',
                    '错误信息': analysis.error_message,
                    '标题长度': len(analysis.title),
                    '有翻译标题': '是' if analysis.translated_title else '否'
                }
                
                writer.writerow(row)
        
        logger.success(f"详细报告导出完成: {csv_path}")
        return str(csv_path)


def export_to_csv(analyses: List[PaperAnalysis], 
                  output_dir: str = "output",
                  collection_names: List[str] = None,
                  export_statistics: bool = True,
                  export_detailed: bool = False) -> List[str]:
    """
    便捷函数：导出文献分析结果到 CSV 文件
    
    Args:
        analyses: 文献分析结果列表
        output_dir: 输出目录
        collection_names: 选择的集合名称列表，用于文件命名
        export_statistics: 是否导出统计信息
        export_detailed: 是否导出详细报告
        
    Returns:
        生成的文件路径列表
    """
    exporter = CSVExporter(output_dir)
    
    exported_files = []
    
    # 导出主要分析结果
    main_file = exporter.export_analyses(analyses, collection_names=collection_names)
    exported_files.append(main_file)
    
    # 导出统计信息
    if export_statistics:
        stats_file = exporter.export_summary_statistics(analyses, collection_names=collection_names)
        exported_files.append(stats_file)
    
    # 导出详细报告
    if export_detailed:
        detailed_file = exporter.export_detailed_report(analyses, collection_names=collection_names)
        exported_files.append(detailed_file)
    
    return exported_files 