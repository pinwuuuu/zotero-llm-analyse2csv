# Zotero 本地文献分析器

🔬 一个智能的 Zotero 文献库分析工具，基于大模型 API 自动分析和总结您的学术文献。

## ✨ 主要功能

- **📚 本地文献读取**：直接读取本地 Zotero 数据库，无需导出
- **🤖 智能分析**：使用大模型 API 深度分析文献内容，提取创新点和总结
- **📄 PDF 全文解析**：自动读取并分析 PDF 附件的完整内容
- **🗂️ 集合选择**：交互式选择特定 Zotero 集合/文件夹进行分析
- **🌐 智能翻译**：自动检测英文标题并翻译为中文
- **📍 集合路径显示**：显示文献在 Zotero 中的完整集合路径
- **⚙️ 配置管理**：本地配置文件系统，保存所有设置参数
- **📊 结构化输出**：生成详细的 CSV 分析报告，文件名包含集合信息

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

#### 方法一：环境变量
```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # 可选
```

#### 方法二：交互式配置（推荐）
```bash
python main.py --config-wizard
```

### 3. 快速测试

```bash
python quickstart.py
```

### 4. 完整分析

```bash
# 分析所有文献
python main.py

# 选择特定集合
python main.py --select-collections

# 限制分析数量
python main.py --limit 10

# 调试模式
python main.py --debug --limit 1
```

## 📋 详细使用

### 基本命令

```bash
# 显示帮助
python main.py --help

# 配置向导（首次使用）
python main.py --config-wizard

# 查看当前配置
python main.py --config-summary

# 重置配置
python main.py --config-reset
```

### 分析选项

```bash
# 交互式选择集合
python main.py --select-collections

# 使用特定模型
python main.py --model "gpt-4o-mini"

# 设置输出语言
python main.py --language "English"

# 限制PDF页数
python main.py --max-pages 20

# 设置API调用间隔
python main.py --delay 2.0
```

### 输出控制

```bash
# 指定输出目录
python main.py --output-dir "my_results"

# 详细日志
python main.py --debug

# 静默模式
python main.py --log-level ERROR
```

## 📁 项目结构

```
zotero-analyzer/
├── main.py              # 主程序入口
├── quickstart.py         # 快速测试脚本
├── requirements.txt      # 依赖列表
├── README.md            # 说明文档
├── src/                 # 源代码模块
│   ├── __init__.py
│   ├── analyzer.py      # 文献分析模块
│   ├── config.py        # 配置管理
│   ├── exporter.py      # CSV导出
│   ├── selector.py      # 集合选择
│   ├── simple_analyzer.py # 简单分析器
│   └── zotero_reader.py # Zotero数据读取
├── config/              # 配置文件目录
│   ├── default.json     # 默认配置
│   ├── user.json        # 用户配置
│   └── recent.json      # 最近配置
├── output/              # 分析结果输出
└── logs/                # 日志文件
```

## ⚙️ 配置文件

配置文件采用分层管理：

1. **默认配置**（`config/default.json`）：系统默认设置
2. **用户配置**（`config/user.json`）：个人自定义设置
3. **运行时配置**：命令行参数覆盖

主要配置项：

```json
{
  "api_key": "your-api-key",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o",
  "language": "Chinese",
  "max_pages": 50,
  "max_tokens": 8000,
  "delay": 1.0,
  "database_path": "auto-detect"
}
```

## 📊 输出结果

分析完成后会生成以下 CSV 文件：

### 1. 主要分析结果（`zotero_analysis_[集合名]_YYYYMMDD_HHMMSS.csv`）

包含以下字段：
- **序号**：文献序号
- **Zotero集合**：文献所属的 Zotero 集合路径
- **论文标题**：原始论文标题
- **中文标题**：英文标题的中文翻译（如果原标题是英文）
- **作者**：文献作者列表
- **优化摘要**：AI 重新整理的文献摘要（200-300字）
- **创新点**：论文的主要创新点和贡献（3-5个要点）
- **总结**：论文的总体总结和评价（150-250字）
- **分析状态**：成功/失败
- **错误信息**：如有错误，显示具体信息

### 2. 统计摘要（`zotero_statistics_[集合名]_YYYYMMDD_HHMMSS.csv`）

- 分析数量统计
- 成功率统计  
- 错误类型汇总
- 作者数量分布

### 主要特性

- 🗂️ **智能集合识别**：自动显示文献在 Zotero 中的集合路径
- 🌐 **标题翻译**：自动检测英文标题并翻译为中文
- 📝 **删除冗余**：不再包含原始摘要，专注于AI优化内容
- 📂 **文件命名**：CSV文件名包含选择的集合名称，便于识别

## 🔧 支持的大模型

- **OpenAI**：GPT-4, GPT-4o
- **OpenAI 兼容服务**：
  - DeepSeek API
  - 月之暗面 API
  - 智谱 API
  - 硅基流动 API (推荐使用) (Qwen3)
  - 其他兼容 OpenAI 格式的服务

## 📝 注意事项

1. **Zotero 数据库**：确保 Zotero 软件已关闭，避免数据库锁定
2. **API 密钥**：妥善保管您的 API 密钥，不要提交到代码仓库
3. **PDF 文件**：确保 PDF 附件路径正确，支持 Zotero 存储格式
4. **网络连接**：分析过程需要稳定的网络连接调用 API

## 🆘 故障排除

### 常见问题

**Q: 找不到 Zotero 数据库**
A: 运行 `python quickstart.py` 检查数据库路径，或手动指定：
```bash
python main.py --database-path "path/to/zotero.sqlite"
```

**Q: PDF 文件无法读取**
A: 确保：
- PDF 文件存在于 Zotero 存储目录
- 文件权限正确
- PDF 格式有效

**Q: API 调用失败**
A: 检查：
- API 密钥是否正确
- 网络连接是否正常
- API 服务是否可用

**Q: 内存不足**
A: 减少处理数量：
```bash
python main.py --limit 50 --max-pages 20
```

## 📖 开发者自述

本人是一名来自西安交通大学的在读博士，平时使用 Zotero 阅读并记录文献，但是 Zotero 的笔记系统无法让我直观地看到文献的大致内容，缺乏按照表格结构化展示文章信息的功能。如果忘记某篇文献的标题与大致内容，在引用时非常麻烦。

此时看到了 [zotero-arxiv-daily](https://github.com/hellojukay/zotero-arxiv-daily) 项目获得了启发，完成了这个本地文献分析工具。通过结合大模型的能力，可以自动分析文献内容，提取创新点和总结，并以结构化的 CSV 表格形式展示，大大提高了文献管理的效率。

以后可能会继续完善这个项目（如果不忙的话😄）。本人能力有限，只熟悉 Python 编程，不会制作 Zotero 插件。如果有感兴趣的同学可以联系我（liupinwu@stu.xjtu.edu.cn），把这个项目做成 Zotero 插件，可以更加方便大家的使用。

**感谢开发过程中 Cursor（DeepSeek、Claude、Gemini）的强力支持！** 🤖

## 📄 许可证

本项目基于 [GNU Affero General Public License v3.0](LICENSE) 开源。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

如果您有兴趣将此项目开发为 Zotero 插件，请联系：**liupinwu@stu.xjtu.edu.cn**

## 🙏 特别致谢

- 感谢 [zotero-arxiv-daily](https://github.com/hellojukay/zotero-arxiv-daily) 项目的启发
- 感谢 Cursor IDE 和 AI 助手（DeepSeek、Claude、Gemini）在开发过程中的支持
- 感谢 Zotero 开源社区提供的优秀文献管理工具

---

💡 **提示**：首次使用建议运行 `python quickstart.py` 进行环境测试。

📧 **联系作者**：刘品吾 (liupinwu@stu.xjtu.edu.cn) - 西安交通大学在读博士 
