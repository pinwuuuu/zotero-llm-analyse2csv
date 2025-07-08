import sqlite3
import os
import platform
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger
import json

class LocalZoteroReader:
    """读取本地 Zotero SQLite 数据库的类"""
    
    def __init__(self, database_path: Optional[str] = None):
        """
        初始化本地 Zotero 读取器
        
        Args:
            database_path: Zotero 数据库文件路径，如果为 None 则自动查找
        """
        if database_path:
            self.database_path = database_path
        else:
            self.database_path = self._find_zotero_database()
        
        if not os.path.exists(self.database_path):
            raise FileNotFoundError(f"Zotero 数据库文件未找到: {self.database_path}")
        
        logger.info(f"使用 Zotero 数据库: {self.database_path}")
    
    def _find_zotero_database(self) -> str:
        """自动查找 Zotero 数据库文件"""
        system = platform.system()
        
        if system == "Windows":
            # Windows 路径
            base_path = Path.home() / "Zotero"
            if not base_path.exists():
                base_path = Path(os.environ.get("APPDATA", "")) / "Zotero" / "Zotero"
        elif system == "Darwin":  # macOS
            base_path = Path.home() / "Zotero"
        else:  # Linux
            base_path = Path.home() / "Zotero"
        
        database_file = base_path / "zotero.sqlite"
        
        if not database_file.exists():
            # 尝试在常见位置查找
            possible_paths = [
                Path.home() / "Documents" / "Zotero" / "zotero.sqlite",
                Path.home() / ".zotero" / "zotero.sqlite",
                Path.home() / "Library" / "Application Support" / "Zotero" / "Profiles" / "*.default" / "zotero.sqlite"
            ]
            
            for path in possible_paths:
                if path.exists():
                    return str(path)
            
            raise FileNotFoundError("无法找到 Zotero 数据库文件，请手动指定路径")
        
        return str(database_file)
    
    def get_all_items(self) -> List[Dict]:
        """获取所有文献条目"""
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row  # 使用行工厂以获得字典样式的访问
        
        try:
            cursor = conn.cursor()
            
            # 查询所有文献条目的基本信息
            query = """
            SELECT 
                i.itemID,
                i.itemTypeID,
                it.typeName,
                i.dateAdded,
                i.dateModified,
                i.key
            FROM items i
            JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
            WHERE i.itemTypeID NOT IN (
                SELECT itemTypeID FROM itemTypes 
                WHERE typeName IN ('note', 'attachment')
            )
            ORDER BY i.dateAdded DESC
            """
            
            cursor.execute(query)
            items = []
            
            for row in cursor.fetchall():
                item = dict(row)
                
                # 获取条目的字段数据
                item_data = self._get_item_data(cursor, item['itemID'])
                item.update(item_data)
                
                # 获取创作者信息
                item['creators'] = self._get_item_creators(cursor, item['itemID'])
                
                # 获取标签
                item['tags'] = self._get_item_tags(cursor, item['itemID'])
                
                # 获取附件
                item['attachments'] = self._get_item_attachments(cursor, item['itemID'])
                
                # 获取笔记
                item['notes'] = self._get_item_notes(cursor, item['itemID'])
                
                items.append(item)
            
            logger.info(f"从本地 Zotero 数据库读取了 {len(items)} 篇文献")
            return items
            
        finally:
            conn.close()
    
    def _get_item_data(self, cursor, item_id: int) -> Dict:
        """获取条目的字段数据"""
        query = """
        SELECT f.fieldName, ifv.value
        FROM itemData id
        JOIN fields f ON id.fieldID = f.fieldID
        JOIN itemDataValues ifv ON id.valueID = ifv.valueID
        WHERE id.itemID = ?
        """
        
        cursor.execute(query, (item_id,))
        data = {}
        
        for row in cursor.fetchall():
            field_name, value = row
            data[field_name] = value
        
        return data
    
    def _get_item_creators(self, cursor, item_id: int) -> List[Dict]:
        """获取条目的创作者信息"""
        query = """
        SELECT 
            c.firstName,
            c.lastName,
            ct.creatorType
        FROM itemCreators ic
        JOIN creators c ON ic.creatorID = c.creatorID
        JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
        WHERE ic.itemID = ?
        ORDER BY ic.orderIndex
        """
        
        cursor.execute(query, (item_id,))
        creators = []
        
        for row in cursor.fetchall():
            firstName, lastName, creatorType = row
            creators.append({
                'firstName': firstName or '',
                'lastName': lastName or '',
                'creatorType': creatorType,
                'name': f"{firstName or ''} {lastName or ''}".strip()
            })
        
        return creators
    
    def _get_item_tags(self, cursor, item_id: int) -> List[str]:
        """获取条目的标签"""
        query = """
        SELECT t.name
        FROM itemTags it
        JOIN tags t ON it.tagID = t.tagID
        WHERE it.itemID = ?
        """
        
        cursor.execute(query, (item_id,))
        return [row[0] for row in cursor.fetchall()]
    
    def _get_item_attachments(self, cursor, item_id: int) -> List[Dict]:
        """获取条目的附件"""
        query = """
        SELECT 
            i.key,
            ifv.value as title,
            ia.path,
            ia.contentType
        FROM items i
        JOIN itemAttachments ia ON i.itemID = ia.itemID
        LEFT JOIN itemData id ON i.itemID = id.itemID AND id.fieldID = (
            SELECT fieldID FROM fields WHERE fieldName = 'title'
        )
        LEFT JOIN itemDataValues ifv ON id.valueID = ifv.valueID
        WHERE ia.parentItemID = ?
        """
        
        cursor.execute(query, (item_id,))
        attachments = []
        
        for row in cursor.fetchall():
            key, title, path, content_type = row
            attachments.append({
                'key': key,
                'title': title or 'Untitled',
                'path': path,
                'contentType': content_type
            })
        
        return attachments
    
    def _get_item_notes(self, cursor, item_id: int) -> List[str]:
        """获取条目的笔记"""
        query = """
        SELECT in_.note
        FROM items i
        JOIN itemNotes in_ ON i.itemID = in_.itemID
        WHERE in_.parentItemID = ?
        """
        
        cursor.execute(query, (item_id,))
        return [row[0] for row in cursor.fetchall()]
    
    def get_attachment_path(self, attachment: Dict, zotero_data_dir: Optional[str] = None) -> Optional[str]:
        """获取附件的完整路径"""
        if not attachment.get('path'):
            return None
        
        if zotero_data_dir is None:
            zotero_data_dir = str(Path(self.database_path).parent)
        
        if attachment['path'].startswith('storage:'):
            # 存储在 Zotero 存储目录中
            relative_path = attachment['path'].replace('storage:', '')
            full_path = Path(zotero_data_dir) / "storage" / attachment['key'] / relative_path
        else:
            # 链接到外部文件
            full_path = Path(attachment['path'])
        
        return str(full_path) if full_path.exists() else None


def get_local_zotero_items(database_path: Optional[str] = None) -> List[Dict]:
    """
    获取本地 Zotero 文献列表的便捷函数
    
    Args:
        database_path: Zotero 数据库文件路径，如果为 None 则自动查找
        
    Returns:
        文献列表
    """
    reader = LocalZoteroReader(database_path)
    return reader.get_all_items() 