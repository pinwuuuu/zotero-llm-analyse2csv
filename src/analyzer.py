import os
import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger
import tiktoken
from openai import OpenAI
import time
import re

@dataclass
class PaperAnalysis:
    """文献分析结果数据类"""
    title: str
    translated_title: str = ""  # 翻译后的标题（如果原标题是英文）
    authors: str = ""
    collection_path: str = ""  # Zotero集合路径
    abstract: str = ""
    innovation_points: str = ""
    summary: str = ""
    error_message: str = ""

class PaperAnalyzer:
    """文献分析器"""
    
    def __init__(self, 
                 api_key: str,
                 base_url: str = "https://api.openai.com/v1",
                 model: str = "gpt-4o",
                 language: str = "Chinese",
                 max_pages: int = 50,
                 max_tokens: int = 8000):
        """
        初始化文献分析器
        
        Args:
            api_key: OpenAI API 密钥
            base_url: API 基础 URL
            model: 使用的模型名称
            language: 输出语言
            max_pages: PDF 最大读取页数
            max_tokens: 最大 token 数量
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.language = language
        self.max_pages = max_pages
        self.max_tokens = max_tokens
        self.enc = tiktoken.encoding_for_model("gpt-4o")  # 用于估算 token 数量
        
        logger.info(f"初始化文献分析器: 模型={model}, 语言={language}, 最大页数={max_pages}, 最大tokens={max_tokens}")
    
    def extract_pdf_text(self, pdf_path: str, max_pages: Optional[int] = None) -> str:
        """
        从 PDF 文件中提取文本
        
        Args:
            pdf_path: PDF 文件路径
            max_pages: 最大读取页数（如果为None则使用实例设置）
            
        Returns:
            提取的文本内容
        """
        if max_pages is None:
            max_pages = self.max_pages
            
        try:
            doc = fitz.open(pdf_path)
            text = ""
            
            # 限制页数以避免过长的文本
            num_pages = min(len(doc), max_pages)
            
            for page_num in range(num_pages):
                page = doc[page_num]
                text += page.get_text()
            
            doc.close()
            
            # 清理文本
            text = self._clean_text(text)
            
            logger.debug(f"从 {pdf_path} 提取了 {len(text)} 个字符的文本")
            return text
            
        except Exception as e:
            logger.error(f"提取 PDF 文本失败 {pdf_path}: {e}")
            return ""
    
    def _clean_text(self, text: str) -> str:
        """清理提取的文本"""
        # 删除过多的空行
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # 删除页眉页脚等重复内容
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if len(line) < 3:  # 跳过过短的行
                continue
            if line.isdigit():  # 跳过单独的页码
                continue
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def truncate_text(self, text: str, max_tokens: Optional[int] = None) -> str:
        """截断文本以适应模型的 token 限制"""
        if max_tokens is None:
            max_tokens = self.max_tokens
            
        tokens = self.enc.encode(text)
        if len(tokens) <= max_tokens:
            return text
        
        truncated_tokens = tokens[:max_tokens]
        return self.enc.decode(truncated_tokens)
    
    def analyze_paper(self, paper: Dict, zotero_data_dir: Optional[str] = None, collection_manager=None) -> PaperAnalysis:
        """
        分析单篇文献
        
        Args:
            paper: 文献数据字典
            zotero_data_dir: Zotero 数据目录路径
            collection_manager: 集合管理器，用于获取文献所属集合信息
            
        Returns:
            文献分析结果
        """
        # 提取基本信息
        title = paper.get('title', '未知标题')
        authors = self._format_authors(paper.get('creators', []))
        original_abstract = paper.get('abstractNote', '')
        
        logger.info(f"开始分析文献: {title}")
        
        # 翻译英文标题
        translated_title = self._translate_title(title)
        
        # 获取集合路径
        collection_path = ""
        if collection_manager and paper.get('key'):
            try:
                collection_paths = collection_manager.get_item_collection_paths(paper['key'])
                collection_path = " | ".join(collection_paths) if collection_paths else "未分类"
            except Exception as e:
                logger.warning(f"获取集合路径失败: {e}")
                collection_path = "未知"
        
        # 尝试获取 PDF 全文
        full_text = ""
        attachments = paper.get('attachments', [])
        
        for attachment in attachments:
            if attachment.get('contentType') == 'application/pdf':
                pdf_path = self._get_attachment_path(attachment, paper.get('key'), zotero_data_dir)
                if pdf_path and os.path.exists(pdf_path):
                    full_text = self.extract_pdf_text(pdf_path)
                    if full_text:
                        logger.info(f"成功提取 PDF 全文: {len(full_text)} 字符")
                        break
                else:
                    logger.warning(f"PDF 文件不存在: {pdf_path}")
        
        if not full_text and not original_abstract:
            logger.warning(f"文献 {title} 没有可用的文本内容")
            return PaperAnalysis(
                title=title,
                translated_title=translated_title,
                authors=authors,
                collection_path=collection_path,
                abstract="无可用摘要",
                innovation_points="无法分析 - 缺少文本内容",
                summary="无法分析 - 缺少文本内容",
                error_message="缺少文本内容"
            )
        
        # 如果没有全文，只使用摘要
        analysis_text = full_text if full_text else original_abstract
        
        # 调用大模型进行分析
        try:
            analysis_result = self._call_llm_analysis(title, authors, analysis_text, bool(full_text))
            
            return PaperAnalysis(
                title=title,
                translated_title=translated_title,
                authors=authors,
                collection_path=collection_path,
                abstract=analysis_result.get('abstract', original_abstract if original_abstract else "无摘要"),
                innovation_points=analysis_result.get('innovation_points', ''),
                summary=analysis_result.get('summary', '')
            )
            
        except Exception as e:
            logger.error(f"LLM 分析失败 {title}: {e}")
            return PaperAnalysis(
                title=title,
                translated_title=translated_title,
                authors=authors,
                collection_path=collection_path,
                abstract=original_abstract if original_abstract else "无摘要",
                innovation_points=f"分析失败: {str(e)}",
                summary=f"分析失败: {str(e)}",
                error_message=str(e)
            )
    
    def _format_authors(self, creators: List[Dict]) -> str:
        """格式化作者信息"""
        author_names = []
        for creator in creators:
            if creator.get('creatorType') == 'author':
                name = creator.get('name', '').strip()
                if not name:
                    first_name = creator.get('firstName', '').strip()
                    last_name = creator.get('lastName', '').strip()
                    name = f"{first_name} {last_name}".strip()
                if name:
                    author_names.append(name)
        
        return '; '.join(author_names) if author_names else '未知作者'
    
    def _get_attachment_path(self, attachment: Dict, item_key: str, zotero_data_dir: Optional[str]) -> Optional[str]:
        """获取附件的完整路径"""
        if not attachment.get('path'):
            return None
        
        attachment_path = attachment['path']
        
        if attachment_path.startswith('storage:'):
            # 存储在 Zotero 存储目录中
            if not zotero_data_dir:
                return None
            
            # 使用附件的 key，而不是文献的 key
            attachment_key = attachment.get('key')
            if not attachment_key:
                logger.warning(f"附件缺少 key 字段: {attachment}")
                return None
            
            relative_path = attachment_path.replace('storage:', '')
            full_path = Path(zotero_data_dir) / "storage" / attachment_key / relative_path
            
            logger.debug(f"构建的PDF路径: {full_path}")
        else:
            # 链接到外部文件
            full_path = Path(attachment_path)
        
        return str(full_path) if full_path.exists() else None
    
    def _is_english_title(self, title: str) -> bool:
        """检测标题是否为英文"""
        # 简单的英文检测：如果标题中英文字符占比超过70%，则认为是英文
        if not title:
            return False
        
        english_chars = sum(1 for char in title if char.isascii() and char.isalpha())
        total_chars = sum(1 for char in title if char.isalpha())
        
        if total_chars == 0:
            return False
        
        english_ratio = english_chars / total_chars
        return english_ratio > 0.7

    def _translate_title(self, title: str) -> str:
        """翻译英文标题为中文"""
        if not self._is_english_title(title):
            return ""  # 不是英文标题，返回空字符串
        
        try:
            messages = [
                {
                    "role": "system",
                    "content": "你是一位专业的学术翻译专家，请将英文学术论文标题准确翻译为中文。要求：1) 保持学术术语的准确性 2) 中文表达自然流畅 3) 只返回翻译结果，不要额外说明"
                },
                {
                    "role": "user",
                    "content": f"请将以下英文论文标题翻译为中文：\n{title}"
                }
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=200
            )
            
            translated_title = response.choices[0].message.content.strip()
            logger.debug(f"标题翻译: {title} -> {translated_title}")
            return translated_title
            
        except Exception as e:
            logger.error(f"标题翻译失败: {e}")
            return ""
    
    def _call_llm_analysis(self, title: str, authors: str, text: str, has_full_text: bool) -> Dict:
        """调用大模型进行文献分析"""
        
        # 截断文本以适应模型限制
        truncated_text = self.truncate_text(text)
        
        if has_full_text:
            prompt = f"""
请分析以下学术论文的完整文本，并提供结构化的分析结果。

论文标题：{title}
作者：{authors}

论文全文：
{truncated_text}

请用{self.language}回答以下问题，并以JSON格式返回结果：

1. abstract: 重新整理和优化的论文摘要（200-300字）
2. innovation_points: 论文的主要创新点和贡献（3-5个要点，每个要点50-100字）
3. summary: 论文的总体总结和评价（150-250字）

请确保返回有效的JSON格式，字段名使用英文，内容使用{self.language}。
"""
        else:
            prompt = f"""
请分析以下学术论文的摘要，并提供结构化的分析结果。

论文标题：{title}
作者：{authors}

论文摘要：
{truncated_text}

请用{self.language}回答以下问题，并以JSON格式返回结果：

1. abstract: 重新整理和优化的论文摘要（保持原意但更加清晰）
2. innovation_points: 基于摘要推断的主要创新点（2-3个要点）
3. summary: 基于摘要的总体总结和评价（100-150字）

请确保返回有效的JSON格式，字段名使用英文，内容使用{self.language}。
"""

        messages = [
            {
                "role": "system",
                "content": f"你是一位专业的学术论文分析专家，擅长提取论文的核心内容、创新点和价值。请用{self.language}进行回答，并确保返回格式严格遵循JSON格式。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.debug(f"调用 LLM 分析，尝试 {attempt + 1}/{max_retries}")
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2000
                )
                
                content = response.choices[0].message.content.strip()
                
                # 尝试解析 JSON
                if content.startswith('```json'):
                    content = content.replace('```json', '').replace('```', '').strip()
                elif content.startswith('```'):
                    content = content.replace('```', '').strip()
                
                # 解析 JSON 响应
                import json
                result = json.loads(content)
                
                # 验证必需字段
                required_fields = ['abstract', 'innovation_points', 'summary']
                if all(field in result for field in required_fields):
                    logger.debug("LLM 分析成功")
                    return result
                else:
                    raise ValueError(f"响应缺少必需字段: {required_fields}")
                    
            except json.JSONDecodeError as e:
                logger.warning(f"JSON 解析失败，尝试 {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    # 返回原始响应作为总结
                    return {
                        'abstract': truncated_text[:300],
                        'innovation_points': f"解析失败，原始响应: {content[:200]}",
                        'summary': f"解析失败，原始响应: {content[:200]}"
                    }
            except Exception as e:
                logger.error(f"LLM 调用失败，尝试 {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # 等待后重试
                else:
                    raise
        
        # 如果所有重试都失败，抛出异常
        raise Exception("LLM 分析失败，已达到最大重试次数") 