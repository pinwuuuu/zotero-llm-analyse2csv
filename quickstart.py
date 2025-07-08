#!/usr/bin/env python3
"""
Zotero 本地文献分析器 - 快速开始脚本

这个脚本帮助用户快速测试和配置 Zotero 本地分析器。
它会检查环境、读取少量文献进行测试分析。
"""

import os
import sys
from pathlib import Path

def check_dependencies():
    """检查依赖包是否已安装"""
    print("🔍 检查依赖包...")
    
    required_packages = [
        'loguru', 'tqdm', 'openai', 'tiktoken', 
        'fitz', 'pandas'  # fitz 是 PyMuPDF 的模块名
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'fitz':
                import fitz
            else:
                __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package}")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️  缺少依赖包: {missing_packages}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    print("✅ 所有依赖包已安装")
    return True


def check_api_key():
    """检查 API 密钥配置"""
    print("\n🔑 检查 API 密钥...")
    
    # 1. 先检查环境变量
    api_key = os.environ.get('OPENAI_API_KEY')
    if api_key:
        print(f"  ✅ 环境变量中找到 API 密钥: {api_key[:10]}...")
        return api_key
    
    # 2. 检查配置文件
    try:
        from src.config import ConfigManager
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        if config.api_key:
            print(f"  ✅ 配置文件中找到 API 密钥: {config.api_key[:10]}...")
            return config.api_key
        else:
            print("  ⚠️  配置文件中未找到 API 密钥")
    except Exception as e:
        print(f"  ⚠️  无法读取配置文件: {e}")
    
    print("  ⚠️  未在环境变量或配置文件中找到 OPENAI_API_KEY")
    
    # 3. 提示用户输入
    api_key = input("请输入您的 API 密钥（或按回车跳过）: ").strip()
    if api_key:
        print(f"  ✅ 使用输入的 API 密钥: {api_key[:10]}...")
        return api_key
    
    print("  ❌ 未提供 API 密钥")
    return None


def check_zotero_database():
    """检查 Zotero 数据库"""
    print("\n📚 检查 Zotero 数据库...")
    
    try:
        from src.zotero_reader import LocalZoteroReader
        reader = LocalZoteroReader()
        print(f"  ✅ 找到 Zotero 数据库: {reader.database_path}")
        
        # 读取少量数据进行测试
        items = reader.get_all_items()[:5]  # 只读取前5篇
        print(f"  ✅ 成功读取 {len(items)} 篇文献（测试）")
        
        return reader.database_path, items
        
    except Exception as e:
        print(f"  ❌ 无法读取 Zotero 数据库: {e}")
        return None, None


def run_test_analysis(api_key, database_path, test_items):
    """运行测试分析"""
    print("\n🧪 运行测试分析...")
    
    if not test_items:
        print("  ❌ 没有可用的测试文献")
        return False
    
    try:
        from src.analyzer import PaperAnalyzer
        from src.exporter import export_to_csv
        from src.config import ConfigManager
        
        # 读取配置文件获取其他参数
        try:
            config_manager = ConfigManager()
            config = config_manager.load_config()
            base_url = config.base_url
            model = config.model
            language = config.language
            print(f"  📋 使用配置: 模型={model}, 语言={language}")
        except Exception as e:
            print(f"  ⚠️  读取配置失败，使用默认参数: {e}")
            base_url = "https://api.openai.com/v1"
            model = "gpt-4o-mini"  # 使用便宜的模型进行测试
            language = "Chinese"
        
        # 只分析第一篇文献
        test_item = test_items[0]
        print(f"  📖 测试文献: {test_item.get('title', 'Unknown')[:50]}...")
        
        # 初始化分析器
        analyzer = PaperAnalyzer(
            api_key=api_key,
            base_url=base_url,
            model=model,
            language=language
        )
        
        # 分析文献
        zotero_data_dir = str(Path(database_path).parent)
        analysis = analyzer.analyze_paper(test_item, zotero_data_dir)
        
        if analysis.error_message:
            print(f"  ⚠️  分析有错误: {analysis.error_message}")
        else:
            print("  ✅ 分析成功!")
            print(f"    标题: {analysis.title[:50]}...")
            print(f"    作者: {analysis.authors[:50]}...")
            print(f"    创新点长度: {len(analysis.innovation_points)} 字符")
        
        # 导出测试结果
        test_output_dir = "test_output"
        Path(test_output_dir).mkdir(exist_ok=True)
        
        exported_files = export_to_csv([analysis], test_output_dir)
        print(f"  ✅ 测试结果已导出到: {exported_files[0]}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试分析失败: {e}")
        return False


def show_next_steps():
    """显示后续步骤"""
    print("\n🚀 后续步骤:")
    print("1. 运行完整分析:")
    print("   python main.py --limit 10")
    print("\n2. 查看更多选项:")
    print("   python main.py --help")
    print("\n3. 配置向导:")
    print("   python main.py --config-wizard")


def main():
    """主函数"""
    print("=" * 60)
    print("🎯 Zotero 本地文献分析器 - 快速开始")
    print("=" * 60)
    
    # 1. 检查依赖
    if not check_dependencies():
        print("\n❌ 环境检查失败，请先安装依赖")
        sys.exit(1)
    
    # 2. 检查 API 密钥
    api_key = check_api_key()
    if not api_key:
        print("\n⚠️  没有 API 密钥，跳过测试分析")
        print("请设置环境变量或使用配置向导")
        show_next_steps()
        return
    
    # 3. 检查 Zotero 数据库
    database_path, test_items = check_zotero_database()
    if not database_path:
        print("\n❌ 无法找到 Zotero 数据库")
        print("请确保 Zotero 已安装并运行过")
        show_next_steps()
        return
    
    # 4. 运行测试分析
    if test_items:
        print("\n🎯 是否运行测试分析？这将调用 API 分析一篇文献（大约消耗 0.01-0.1 元）")
        response = input("输入 'y' 继续，其他任意键跳过: ").strip().lower()
        
        if response == 'y':
            success = run_test_analysis(api_key, database_path, test_items)
            if success:
                print("\n🎉 测试完成！环境配置正确。")
            else:
                print("\n⚠️  测试失败，请检查 API 密钥和网络连接")
        else:
            print("\n⏭️  跳过测试分析")
    
    # 5. 显示后续步骤
    show_next_steps()
    
    print("\n" + "=" * 60)
    print("✨ 快速开始完成！")
    print("=" * 60)


if __name__ == "__main__":
    main() 