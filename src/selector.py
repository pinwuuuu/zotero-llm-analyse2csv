#!/usr/bin/env python3
"""
Zotero 集合选择模块

提供交互式界面让用户选择要分析的 Zotero 集合（文件夹）。
支持层级集合显示、多选、搜索过滤等功能。
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class ZoteroCollection:
    """Zotero 集合数据类"""
    key: str
    name: str
    parent_key: Optional[str]
    item_count: int = 0
    children: List['ZoteroCollection'] = None
    level: int = 0
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


class CollectionManager:
    """集合管理器"""
    
    def __init__(self, database_path: str):
        """
        初始化集合管理器
        
        Args:
            database_path: Zotero 数据库路径
        """
        self.database_path = database_path
        self.collections = {}  # key -> ZoteroCollection
        self.root_collections = []  # 顶级集合列表
        
        if not Path(database_path).exists():
            raise FileNotFoundError(f"Zotero 数据库文件不存在: {database_path}")
        
        self._load_collections()
        logger.info(f"加载了 {len(self.collections)} 个集合")
    
    def _load_collections(self):
        """从数据库加载集合信息"""
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        
        try:
            cursor = conn.cursor()
            
            # 获取所有集合
            query = """
            SELECT 
                c.key,
                c.collectionName as name,
                c.parentCollectionID,
                pc.key as parent_key
            FROM collections c
            LEFT JOIN collections pc ON c.parentCollectionID = pc.collectionID
            ORDER BY c.collectionName
            """
            
            cursor.execute(query)
            collection_rows = cursor.fetchall()
            
            # 创建集合对象
            for row in collection_rows:
                collection = ZoteroCollection(
                    key=row['key'],
                    name=row['name'],
                    parent_key=row['parent_key']
                )
                self.collections[collection.key] = collection
            
            # 构建层级关系
            self._build_hierarchy()
            
            # 计算每个集合的文献数量
            self._count_items_in_collections(cursor)
            
        finally:
            conn.close()
    
    def _build_hierarchy(self):
        """构建集合层级关系"""
        # 找出所有顶级集合和构建父子关系
        for collection in self.collections.values():
            if collection.parent_key is None:
                self.root_collections.append(collection)
                collection.level = 0
            else:
                parent = self.collections.get(collection.parent_key)
                if parent:
                    parent.children.append(collection)
                    collection.level = parent.level + 1
        
        # 按名称排序
        self.root_collections.sort(key=lambda x: x.name)
        for collection in self.collections.values():
            collection.children.sort(key=lambda x: x.name)
    
    def _count_items_in_collections(self, cursor):
        """计算每个集合中的文献数量"""
        # 获取每个集合的直接文献数量
        query = """
        SELECT 
            c.key,
            COUNT(DISTINCT ci.itemID) as item_count
        FROM collections c
        LEFT JOIN collectionItems ci ON c.collectionID = ci.collectionID
        LEFT JOIN items i ON ci.itemID = i.itemID
        WHERE i.itemTypeID NOT IN (
            SELECT itemTypeID FROM itemTypes 
            WHERE typeName IN ('note', 'attachment')
        ) OR i.itemID IS NULL
        GROUP BY c.collectionID, c.key
        """
        
        cursor.execute(query)
        
        for row in cursor.fetchall():
            collection_key = row['key']
            item_count = row['item_count']
            
            if collection_key in self.collections:
                self.collections[collection_key].item_count = item_count
    
    def get_collection_tree(self) -> List[ZoteroCollection]:
        """获取集合树结构"""
        return self.root_collections
    
    def get_all_collections(self) -> List[ZoteroCollection]:
        """获取所有集合的平铺列表"""
        return list(self.collections.values())
    
    def find_collections(self, search_term: str) -> List[ZoteroCollection]:
        """搜索集合"""
        search_term = search_term.lower()
        results = []
        
        for collection in self.collections.values():
            if search_term in collection.name.lower():
                results.append(collection)
        
        return sorted(results, key=lambda x: x.name)
    
    def get_item_collection_paths(self, item_key: str) -> List[str]:
        """获取文献所属的所有集合路径"""
        conn = sqlite3.connect(self.database_path)
        
        try:
            cursor = conn.cursor()
            
            # 查找文献所属的集合
            query = """
            SELECT c.key as collection_key
            FROM items i
            JOIN collectionItems ci ON i.itemID = ci.itemID
            JOIN collections c ON ci.collectionID = c.collectionID
            WHERE i.key = ?
            """
            
            cursor.execute(query, (item_key,))
            collection_keys = [row[0] for row in cursor.fetchall()]
            
            # 获取每个集合的完整路径
            collection_paths = []
            for collection_key in collection_keys:
                path = self.get_collection_path(collection_key)
                if path:
                    collection_paths.append(path)
            
            return collection_paths
            
        finally:
            conn.close()

    def get_collection_path(self, collection_key: str) -> str:
        """获取集合的完整路径"""
        collection = self.collections.get(collection_key)
        if not collection:
            return ""
        
        path_parts = [collection.name]
        current = collection
        
        while current.parent_key:
            parent = self.collections.get(current.parent_key)
            if parent:
                path_parts.insert(0, parent.name)
                current = parent
            else:
                break
        
        return " / ".join(path_parts)
    
    def get_collection_items(self, collection_keys: List[str]) -> List[Dict]:
        """获取指定集合中的所有文献"""
        if not collection_keys:
            return []
        
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        
        try:
            cursor = conn.cursor()
            
            # 构建 IN 子句的占位符
            placeholders = ','.join(['?' for _ in collection_keys])
            
            query = f"""
            SELECT DISTINCT
                i.itemID,
                i.itemTypeID,
                it.typeName,
                i.dateAdded,
                i.dateModified,
                i.key
            FROM items i
            JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
            JOIN collectionItems ci ON i.itemID = ci.itemID
            JOIN collections c ON ci.collectionID = c.collectionID
            WHERE c.key IN ({placeholders})
            AND i.itemTypeID NOT IN (
                SELECT itemTypeID FROM itemTypes 
                WHERE typeName IN ('note', 'attachment')
            )
            ORDER BY i.dateAdded DESC
            """
            
            cursor.execute(query, collection_keys)
            items = []
            
            for row in cursor.fetchall():
                item = dict(row)
                
                # 获取条目的详细数据（使用原有的方法）
                from .zotero_reader import LocalZoteroReader
                reader = LocalZoteroReader(self.database_path)
                item_data = reader._get_item_data(cursor, item['itemID'])
                item.update(item_data)
                
                # 获取创作者信息
                item['creators'] = reader._get_item_creators(cursor, item['itemID'])
                
                # 获取标签
                item['tags'] = reader._get_item_tags(cursor, item['itemID'])
                
                # 获取附件
                item['attachments'] = reader._get_item_attachments(cursor, item['itemID'])
                
                # 获取笔记
                item['notes'] = reader._get_item_notes(cursor, item['itemID'])
                
                items.append(item)
            
            logger.info(f"从 {len(collection_keys)} 个集合中获取了 {len(items)} 篇文献")
            return items
            
        finally:
            conn.close()


class CollectionSelector:
    """集合选择器（交互式界面）"""
    
    def __init__(self, collection_manager: CollectionManager):
        self.collection_manager = collection_manager
        self.selected_collections: Set[str] = set()
    
    def run_interactive_selection(self) -> List[str]:
        """运行交互式集合选择"""
        print("📁 Zotero 集合选择器")
        print("=" * 50)
        
        collections = self.collection_manager.get_collection_tree()
        
        if not collections:
            print("❌ 未找到任何集合")
            return []
        
        while True:
            self._display_menu()
            choice = input("\n请选择操作: ").strip()
            
            if choice == '1':
                self._display_all_collections()
            elif choice == '2':
                self._select_collections_interactive()
            elif choice == '3':
                self._search_and_select()
            elif choice == '4':
                self._show_selected_collections()
            elif choice == '5':
                self._clear_selection()
            elif choice == '6':
                break
            else:
                print("❌ 无效选择，请重试")
        
        return list(self.selected_collections)
    
    def _display_menu(self):
        """显示主菜单"""
        print(f"\n📊 当前已选择 {len(self.selected_collections)} 个集合")
        print("1. 查看所有集合")
        print("2. 选择集合")
        print("3. 搜索并选择集合")
        print("4. 查看已选择的集合")
        print("5. 清空选择")
        print("6. 完成选择")
    
    def _display_all_collections(self):
        """显示所有集合（树形结构）"""
        print("\n📂 所有集合:")
        print("-" * 40)
        
        def print_collection(collection: ZoteroCollection, indent: str = ""):
            status = "✓" if collection.key in self.selected_collections else " "
            print(f"{indent}[{status}] {collection.name} ({collection.item_count} 篇)")
            
            for child in collection.children:
                print_collection(child, indent + "  ")
        
        collections = self.collection_manager.get_collection_tree()
        for collection in collections:
            print_collection(collection)
    
    def _select_collections_interactive(self):
        """交互式选择集合"""
        print("\n📋 选择集合（输入集合编号，多个用逗号分隔）:")
        print("-" * 50)
        
        # 创建编号到集合的映射
        all_collections = self.collection_manager.get_all_collections()
        collection_map = {}
        
        for i, collection in enumerate(all_collections, 1):
            status = "✓" if collection.key in self.selected_collections else " "
            path = self.collection_manager.get_collection_path(collection.key)
            print(f"{i:2d}. [{status}] {path} ({collection.item_count} 篇)")
            collection_map[str(i)] = collection.key
        
        print("\n输入示例: 1,3,5 或 all（选择全部）或 none（清空选择）")
        
        user_input = input("请输入选择: ").strip()
        
        if user_input.lower() == 'all':
            self.selected_collections = set(collection_map.values())
            print(f"✅ 已选择所有 {len(self.selected_collections)} 个集合")
        elif user_input.lower() == 'none':
            self.selected_collections.clear()
            print("✅ 已清空选择")
        elif user_input:
            try:
                indices = [s.strip() for s in user_input.split(',')]
                new_selections = set()
                
                for index in indices:
                    if index in collection_map:
                        new_selections.add(collection_map[index])
                    else:
                        print(f"⚠️ 忽略无效编号: {index}")
                
                if new_selections:
                    self.selected_collections.update(new_selections)
                    print(f"✅ 已添加 {len(new_selections)} 个集合到选择")
                
            except Exception as e:
                print(f"❌ 输入格式错误: {e}")
    
    def _search_and_select(self):
        """搜索并选择集合"""
        search_term = input("\n🔍 请输入搜索关键词: ").strip()
        
        if not search_term:
            print("❌ 搜索词不能为空")
            return
        
        results = self.collection_manager.find_collections(search_term)
        
        if not results:
            print(f"❌ 未找到包含 '{search_term}' 的集合")
            return
        
        print(f"\n🔍 搜索结果 ({len(results)} 个):")
        print("-" * 40)
        
        for i, collection in enumerate(results, 1):
            status = "✓" if collection.key in self.selected_collections else " "
            path = self.collection_manager.get_collection_path(collection.key)
            print(f"{i:2d}. [{status}] {path} ({collection.item_count} 篇)")
        
        selection = input("\n请输入要选择的编号（多个用逗号分隔）: ").strip()
        
        if selection:
            try:
                indices = [int(s.strip()) for s in selection.split(',')]
                selected_count = 0
                
                for index in indices:
                    if 1 <= index <= len(results):
                        collection = results[index - 1]
                        self.selected_collections.add(collection.key)
                        selected_count += 1
                    else:
                        print(f"⚠️ 忽略无效编号: {index}")
                
                if selected_count > 0:
                    print(f"✅ 已选择 {selected_count} 个集合")
                
            except ValueError:
                print("❌ 输入格式错误，请输入数字")
    
    def _show_selected_collections(self):
        """显示已选择的集合"""
        if not self.selected_collections:
            print("\n📋 尚未选择任何集合")
            return
        
        print(f"\n📋 已选择的集合 ({len(self.selected_collections)} 个):")
        print("-" * 50)
        
        total_items = 0
        for i, collection_key in enumerate(self.selected_collections, 1):
            collection = self.collection_manager.collections.get(collection_key)
            if collection:
                path = self.collection_manager.get_collection_path(collection_key)
                print(f"{i:2d}. {path} ({collection.item_count} 篇)")
                total_items += collection.item_count
        
        print(f"\n📊 总计约 {total_items} 篇文献（可能有重复）")
    
    def _clear_selection(self):
        """清空选择"""
        if self.selected_collections:
            confirm = input(f"\n⚠️ 确定要清空已选择的 {len(self.selected_collections)} 个集合吗? (y/N): ")
            if confirm.lower() == 'y':
                self.selected_collections.clear()
                print("✅ 已清空选择")
        else:
            print("\n📋 当前没有选择任何集合")


def select_collections_interactive(database_path: str) -> Tuple[List[str], List[Dict]]:
    """
    交互式选择集合并获取文献
    
    Args:
        database_path: Zotero 数据库路径
        
    Returns:
        (选中的集合键列表, 集合中的文献列表)
    """
    try:
        # 初始化集合管理器
        collection_manager = CollectionManager(database_path)
        
        # 运行集合选择器
        selector = CollectionSelector(collection_manager)
        selected_keys = selector.run_interactive_selection()
        
        if not selected_keys:
            print("\n📋 未选择任何集合")
            return [], []
        
        # 获取选中集合的文献
        print(f"\n📖 正在加载 {len(selected_keys)} 个集合中的文献...")
        items = collection_manager.get_collection_items(selected_keys)
        
        print(f"✅ 成功加载 {len(items)} 篇文献")
        return selected_keys, items
        
    except Exception as e:
        logger.error(f"集合选择失败: {e}")
        print(f"❌ 集合选择失败: {e}")
        return [], []


def get_available_collections(database_path: str) -> List[ZoteroCollection]:
    """
    获取可用集合列表（非交互式）
    
    Args:
        database_path: Zotero 数据库路径
        
    Returns:
        集合列表
    """
    try:
        collection_manager = CollectionManager(database_path)
        return collection_manager.get_all_collections()
    except Exception as e:
        logger.error(f"获取集合列表失败: {e}")
        return [] 