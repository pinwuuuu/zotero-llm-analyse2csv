#!/usr/bin/env python3
"""
测试最终功能：验证新字段和CSV导出
作者：刘品吾 (liupinwu@stu.xjtu.edu.cn)
"""

import os
import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.analyzer import PaperAnalyzer, PaperAnalysis
from src.config import ConfigManager
from src.exporter import CSVExporter
from src.selector import CollectionManager
from src.zotero_reader import LocalZoteroReader

def test_new_features():
    """测试新功能"""
    print("🧪 测试新功能：集合路径、标题翻译、CSV导出")
    print("=" * 60)
    
    # 1. 加载配置
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    if not config.api_key:
        # 从环境变量获取
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            print("❌ 需要API密钥，请设置环境变量 OPENAI_API_KEY")
            return
        config.api_key = api_key
    
    # 2. 获取数据库路径
    try:
        reader = LocalZoteroReader()
        database_path = reader.database_path
        print(f"📂 数据库路径: {database_path}")
    except Exception as e:
        print(f"❌ 无法找到Zotero数据库: {e}")
        return
    
    # 3. 创建集合管理器
    collection_manager = CollectionManager(database_path)
    
    # 4. 获取第一篇文献
    papers = reader.get_all_items()
    if not papers:
        print("❌ 未找到任何文献")
        return
    
    # 找一篇英文标题的文献进行测试
    test_paper = None
    for paper in papers[:10]:  # 检查前10篇
        title = paper.get('title', '')
        if title and any(c.isalpha() and ord(c) < 128 for c in title):  # 包含英文字符
            test_paper = paper
            break
    
    if not test_paper:
        test_paper = papers[0]  # 使用第一篇
    
    print(f"📄 测试文献: {test_paper.get('title', '未知')}")
    
    # 5. 创建分析器
    analyzer = PaperAnalyzer(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model,
        language=config.language
    )
    
    # 6. 分析文献
    print("🔍 开始分析...")
    zotero_data_dir = str(Path(database_path).parent)
    
    try:
        analysis = analyzer.analyze_paper(
            test_paper, 
            zotero_data_dir=zotero_data_dir,
            collection_manager=collection_manager
        )
        
        print("✅ 分析完成")
        print(f"   原标题: {analysis.title}")
        print(f"   中文标题: {analysis.translated_title}")
        print(f"   集合路径: {analysis.collection_path}")
        print(f"   作者: {analysis.authors}")
        print(f"   优化摘要长度: {len(analysis.abstract)} 字符")
        print(f"   创新点长度: {len(analysis.innovation_points)} 字符")
        print(f"   总结长度: {len(analysis.summary)} 字符")
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        # 创建模拟分析结果用于测试导出
        analysis = PaperAnalysis(
            title="Test Paper Title",
            translated_title="测试论文标题",
            authors="Test Author",
            collection_path="测试集合 / 子集合",
            abstract="这是一个测试摘要。",
            innovation_points="测试创新点。",
            summary="测试总结。",
            error_message=""
        )
    
    # 7. 测试CSV导出
    print("\n📊 测试CSV导出...")
    
    exporter = CSVExporter("output")
    collection_names = ["测试集合"]
    
    try:
        # 导出主要结果
        csv_file = exporter.export_analyses([analysis], collection_names=collection_names)
        print(f"✅ CSV文件已导出: {csv_file}")
        
        # 读取并显示CSV内容
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            print("\n📋 CSV文件内容预览:")
            print("-" * 40)
            lines = content.split('\n')
            for i, line in enumerate(lines[:5]):  # 显示前5行
                print(f"{i+1}: {line}")
            if len(lines) > 5:
                print("...")
        
    except Exception as e:
        print(f"❌ CSV导出失败: {e}")
    
    print("\n🎉 测试完成！")

if __name__ == "__main__":
    test_new_features() 