#!/usr/bin/env python3
"""
Inventory Management RESTful API
A single-file SQLite-backed inventory system with REST API and web dashboard.
No external dependencies beyond Python standard library.

Usage:
    python inventory_api.py                    # Start server on port 8000
    python inventory_api.py --port 8080        # Start on custom port
    python inventory_api.py --init-demo        # Initialize with demo data
"""

import json
import sqlite3
import argparse
import urllib.parse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler
from contextlib import contextmanager


# ============================================================================
# DATABASE LAYER
# ============================================================================

DB_PATH = Path("inventory.db")


@contextmanager
def get_db():
    """Context manager for database connections with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database() -> None:
    """Create tables if they don't exist."""
    schema = """
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        category TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0,
        unit_price REAL NOT NULL DEFAULT 0.0,
        location TEXT,
        supplier TEXT,
        min_stock INTEGER DEFAULT 10,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('IN', 'OUT', 'ADJUST')),
        quantity INTEGER NOT NULL,
        note TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_items_sku ON items(sku);
    CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
    CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
    CREATE INDEX IF NOT EXISTS idx_transactions_item ON transactions(item_id);
    """

    with get_db() as conn:
        conn.executescript(schema)
    print(f"✅ Database initialized: {DB_PATH.resolve()}")


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class Item:
    id: Optional[int] = None
    sku: str = ""
    name: str = ""
    description: str = ""
    category: str = ""
    quantity: int = 0
    unit_price: float = 0.0
    location: str = ""
    supplier: str = ""
    min_stock: int = 10
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Item":
        return cls(**{k: row[k] for k in row.keys()})


@dataclass
class Transaction:
    id: Optional[int] = None
    item_id: int = 0
    type: str = ""  # IN, OUT, ADJUST
    quantity: int = 0
    note: str = ""
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# REPOSITORY PATTERN
# ============================================================================

class ItemRepository:
    """Data access layer for inventory items."""

    @staticmethod
    def create(item: Item) -> Item:
        with get_db() as conn:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                """INSERT INTO items (sku, name, description, category, quantity,
                   unit_price, location, supplier, min_stock, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item.sku, item.name, item.description, item.category,
                 item.quantity, item.unit_price, item.location, item.supplier,
                 item.min_stock, now, now)
            )
            item.id = cursor.lastrowid
            item.created_at = now
            item.updated_at = now
            return item

    @staticmethod
    def get_by_id(item_id: int) -> Optional[Item]:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM items WHERE id = ?", (item_id,)
            ).fetchone()
            return Item.from_row(row) if row else None

    @staticmethod
    def get_by_sku(sku: str) -> Optional[Item]:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM items WHERE sku = ?", (sku,)
            ).fetchone()
            return Item.from_row(row) if row else None

    @staticmethod
    def list_all(
        category: Optional[str] = None,
        low_stock: bool = False,
        search: Optional[str] = None,
        sort_by: str = "id",
        order: str = "asc",
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Item], int]:
        with get_db() as conn:
            conditions = ["1=1"]
            params = []

            if category:
                conditions.append("category = ?")
                params.append(category)

            if low_stock:
                conditions.append("quantity <= min_stock")

            if search:
                conditions.append("(name LIKE ? OR sku LIKE ? OR description LIKE ?)")
                search_term = f"%{search}%"
                params.extend([search_term, search_term, search_term])

            where = " AND ".join(conditions)

            count_row = conn.execute(
                f"SELECT COUNT(*) as total FROM items WHERE {where}", params
            ).fetchone()
            total = count_row["total"] if count_row else 0

            valid_columns = {"id", "sku", "name", "category", "quantity", 
                           "unit_price", "created_at", "updated_at"}
            if sort_by not in valid_columns:
                sort_by = "id"
            order = "DESC" if order.lower() == "desc" else "ASC"

            rows = conn.execute(
                f"""SELECT * FROM items WHERE {where}
                    ORDER BY {sort_by} {order}
                    LIMIT ? OFFSET ?""",
                params + [limit, offset]
            ).fetchall()

            items = [Item.from_row(r) for r in rows]
            return items, total

    @staticmethod
    def update(item_id: int, updates: Dict[str, Any]) -> Optional[Item]:
        if not updates:
            return ItemRepository.get_by_id(item_id)

        updates.pop("id", None)
        updates.pop("created_at", None)
        updates["updated_at"] = datetime.now().isoformat()

        fields = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [item_id]

        with get_db() as conn:
            conn.execute(
                f"UPDATE items SET {fields} WHERE id = ?", values
            )
            return ItemRepository.get_by_id(item_id)

    @staticmethod
    def delete(item_id: int) -> bool:
        with get_db() as conn:
            cursor = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_categories() -> List[str]:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT DISTINCT category FROM items ORDER BY category"
            ).fetchall()
            return [r["category"] for r in rows]

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        with get_db() as conn:
            stats = {}

            row = conn.execute("""
                SELECT COUNT(*) as total_items, 
                       COALESCE(SUM(quantity * unit_price), 0) as total_value,
                       COALESCE(SUM(quantity), 0) as total_units
                FROM items
            """).fetchone()
            stats.update(dict(row))

            row = conn.execute(
                "SELECT COUNT(*) as low_stock FROM items WHERE quantity <= min_stock"
            ).fetchone()
            stats.update(dict(row))

            rows = conn.execute("""
                SELECT category, COUNT(*) as count, SUM(quantity) as units
                FROM items GROUP BY category ORDER BY count DESC
            """).fetchall()
            stats["categories"] = [dict(r) for r in rows]

            return stats


class TransactionRepository:
    """Data access layer for stock transactions."""

    @staticmethod
    def create(item_id: int, trans_type: str, quantity: int, note: str = "") -> Transaction:
        with get_db() as conn:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                """INSERT INTO transactions (item_id, type, quantity, note, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (item_id, trans_type, quantity, note, now)
            )

            if trans_type == "IN":
                conn.execute(
                    "UPDATE items SET quantity = quantity + ? WHERE id = ?",
                    (quantity, item_id)
                )
            elif trans_type == "OUT":
                conn.execute(
                    "UPDATE items SET quantity = quantity - ? WHERE id = ?",
                    (quantity, item_id)
                )

            return Transaction(
                id=cursor.lastrowid,
                item_id=item_id,
                type=trans_type,
                quantity=quantity,
                note=note,
                created_at=now
            )

    @staticmethod
    def get_by_item(item_id: int, limit: int = 50) -> List[Transaction]:
        with get_db() as conn:
            rows = conn.execute(
                """SELECT * FROM transactions WHERE item_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (item_id, limit)
            ).fetchall()
            return [Transaction(**{k: r[k] for k in r.keys()}) for r in rows]


# ============================================================================
# WEB DASHBOARD (HTML/CSS/JS)
# ============================================================================

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📦 Inventory Management</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f3f4f6; color: #1f2937; line-height: 1.6;
        }
        .header { 
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
            color: white; padding: 24px 32px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header h1 { font-size: 1.8em; display: flex; align-items: center; gap: 12px; }
        .container { max-width: 1400px; margin: 0 auto; padding: 24px; }

        .stats-grid { 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px; margin-bottom: 32px;
        }
        .stat-card { 
            background: white; padding: 24px; border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08); border-left: 4px solid #3b82f6;
            transition: transform 0.2s;
        }
        .stat-card:hover { transform: translateY(-2px); }
        .stat-card.warning { border-left-color: #f59e0b; }
        .stat-card.danger { border-left-color: #ef4444; }
        .stat-card.success { border-left-color: #10b981; }
        .stat-card h3 { font-size: 0.85em; color: #6b7280; text-transform: uppercase; margin-bottom: 8px; }
        .stat-card .value { font-size: 2.2em; font-weight: bold; color: #111827; }
        .stat-card .sub { font-size: 0.9em; color: #6b7280; margin-top: 4px; }

        .panel { 
            background: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            margin-bottom: 24px; overflow: hidden;
        }
        .panel-header { 
            padding: 20px 24px; border-bottom: 1px solid #e5e7eb;
            display: flex; justify-content: space-between; align-items: center;
        }
        .panel-header h2 { font-size: 1.2em; color: #111827; }

        .toolbar { 
            padding: 16px 24px; background: #f9fafb; border-bottom: 1px solid #e5e7eb;
            display: flex; gap: 12px; flex-wrap: wrap; align-items: center;
        }
        input, select, button { 
            padding: 10px 14px; border: 1px solid #d1d5db; border-radius: 8px;
            font-size: 0.95em; background: white;
        }
        input:focus, select:focus { outline: none; border-color: #3b82f6; }
        button { 
            background: #3b82f6; color: white; border: none; cursor: pointer;
            font-weight: 500; transition: background 0.2s;
        }
        button:hover { background: #2563eb; }
        button.secondary { background: #6b7280; }
        button.secondary:hover { background: #4b5563; }
        button.danger { background: #ef4444; }
        button.danger:hover { background: #dc2626; }
        button.success { background: #10b981; }
        button.success:hover { background: #059669; }

        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 14px 20px; text-align: left; border-bottom: 1px solid #e5e7eb; }
        th { background: #f9fafb; font-weight: 600; color: #4b5563; font-size: 0.85em; text-transform: uppercase; }
        tr:hover { background: #f9fafb; }
        .low-stock { color: #ef4444; font-weight: 600; }
        .badge { 
            display: inline-block; padding: 4px 10px; border-radius: 20px;
            font-size: 0.75em; font-weight: 600;
        }
        .badge-success { background: #d1fae5; color: #065f46; }
        .badge-warning { background: #fef3c7; color: #92400e; }
        .badge-danger { background: #fee2e2; color: #991b1b; }

        .modal-overlay { 
            display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.5); z-index: 100; justify-content: center; align-items: center;
        }
        .modal-overlay.active { display: flex; }
        .modal { 
            background: white; border-radius: 16px; width: 90%; max-width: 600px;
            max-height: 90vh; overflow-y: auto; box-shadow: 0 20px 25px rgba(0,0,0,0.15);
        }
        .modal-header { 
            padding: 20px 24px; border-bottom: 1px solid #e5e7eb;
            display: flex; justify-content: space-between; align-items: center;
        }
        .modal-body { padding: 24px; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; margin-bottom: 6px; font-weight: 500; color: #374151; }
        .form-group input, .form-group select, .form-group textarea { 
            width: 100%; padding: 10px 14px;
        }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

        .toast { 
            position: fixed; bottom: 24px; right: 24px; padding: 16px 24px;
            border-radius: 10px; color: white; font-weight: 500;
            transform: translateY(100px); opacity: 0; transition: all 0.3s;
            z-index: 200;
        }
        .toast.show { transform: translateY(0); opacity: 1; }
        .toast.success { background: #10b981; }
        .toast.error { background: #ef4444; }

        .empty-state { text-align: center; padding: 60px 20px; color: #9ca3af; }
        .qty-control { display: flex; align-items: center; gap: 8px; }
        .qty-control button { padding: 6px 12px; font-size: 0.85em; }
        .qty-control span { min-width: 40px; text-align: center; font-weight: 600; }

        @media (max-width: 768px) {
            .form-row { grid-template-columns: 1fr; }
            .toolbar { flex-direction: column; align-items: stretch; }
            .toolbar input, .toolbar select, .toolbar button { width: 100%; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📦 Inventory Management System</h1>
    </div>

    <div class="container">
        <div class="stats-grid" id="stats">
            <div class="stat-card"><h3>Total Items</h3><div class="value">-</div></div>
            <div class="stat-card success"><h3>Total Value</h3><div class="value">-</div></div>
            <div class="stat-card"><h3>Total Units</h3><div class="value">-</div></div>
            <div class="stat-card warning"><h3>Low Stock</h3><div class="value">-</div></div>
        </div>

        <div class="panel">
            <div class="panel-header">
                <h2>📋 Inventory Items</h2>
                <button onclick="openModal()">+ Add Item</button>
            </div>
            <div class="toolbar">
                <input type="text" id="searchInput" placeholder="🔍 Search items..." oninput="debouncedLoad()">
                <select id="categoryFilter" onchange="loadItems()">
                    <option value="">All Categories</option>
                </select>
                <label style="display:flex;align-items:center;gap:6px;">
                    <input type="checkbox" id="lowStockFilter" onchange="loadItems()">
                    Low Stock Only
                </label>
                <button class="secondary" onclick="loadItems()">🔄 Refresh</button>
            </div>
            <div id="itemsTable">
                <div class="empty-state"><p>Loading items...</p></div>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="itemModal">
        <div class="modal">
            <div class="modal-header">
                <h2 id="modalTitle">Add Item</h2>
                <button class="secondary" onclick="closeModal()">✕</button>
            </div>
            <div class="modal-body">
                <form id="itemForm" onsubmit="saveItem(event)">
                    <input type="hidden" id="itemId">
                    <div class="form-row">
                        <div class="form-group">
                            <label>SKU *</label>
                            <input type="text" id="sku" required placeholder="ITEM-001">
                        </div>
                        <div class="form-group">
                            <label>Name *</label>
                            <input type="text" id="name" required placeholder="Product name">
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea id="description" rows="2" placeholder="Optional description"></textarea>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Category *</label>
                            <input type="text" id="category" required placeholder="e.g. Electronics">
                        </div>
                        <div class="form-group">
                            <label>Location</label>
                            <input type="text" id="location" placeholder="e.g. Warehouse A">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Quantity *</label>
                            <input type="number" id="quantity" required min="0" value="0">
                        </div>
                        <div class="form-group">
                            <label>Unit Price ($) *</label>
                            <input type="number" id="unitPrice" required min="0" step="0.01" value="0">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Supplier</label>
                            <input type="text" id="supplier" placeholder="Supplier name">
                        </div>
                        <div class="form-group">
                            <label>Min Stock Level</label>
                            <input type="number" id="minStock" min="0" value="10">
                        </div>
                    </div>
                    <div style="display:flex; gap:12px; justify-content:flex-end; margin-top:8px;">
                        <button type="button" class="secondary" onclick="closeModal()">Cancel</button>
                        <button type="submit">Save Item</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="stockModal">
        <div class="modal" style="max-width:400px;">
            <div class="modal-header">
                <h2>Update Stock</h2>
                <button class="secondary" onclick="closeStockModal()">✕</button>
            </div>
            <div class="modal-body">
                <form id="stockForm" onsubmit="updateStock(event)">
                    <input type="hidden" id="stockItemId">
                    <div class="form-group">
                        <label>Transaction Type</label>
                        <select id="transType">
                            <option value="IN">📥 Stock In (Receive)</option>
                            <option value="OUT">📤 Stock Out (Ship)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Quantity</label>
                        <input type="number" id="transQty" required min="1" value="1">
                    </div>
                    <div class="form-group">
                        <label>Note</label>
                        <input type="text" id="transNote" placeholder="e.g. PO #12345">
                    </div>
                    <div style="display:flex; gap:12px; justify-content:flex-end;">
                        <button type="button" class="secondary" onclick="closeStockModal()">Cancel</button>
                        <button type="submit" class="success">Update Stock</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
        let debounceTimer;

        function debouncedLoad() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(loadItems, 300);
        }

        async function api(method, path, body) {
            const opts = { method, headers: {'Content-Type': 'application/json'} };
            if (body) opts.body = JSON.stringify(body);
            const res = await fetch('/api' + path, opts);
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
            return data;
        }

        function showToast(msg, type='success') {
            const t = document.getElementById('toast');
            t.textContent = msg;
            t.className = `toast ${type} show`;
            setTimeout(() => t.classList.remove('show'), 3000);
        }

        async function loadStats() {
            try {
                const stats = await api('GET', '/stats');
                const cards = document.querySelectorAll('#stats .stat-card');
                cards[0].querySelector('.value').textContent = stats.total_items.toLocaleString();
                cards[1].querySelector('.value').textContent = '$' + stats.total_value.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
                cards[2].querySelector('.value').textContent = stats.total_units.toLocaleString();
                cards[3].querySelector('.value').textContent = stats.low_stock.toLocaleString();
                if (stats.low_stock > 0) cards[3].classList.add('danger');
            } catch(e) { console.error(e); }
        }

        async function loadCategories() {
            try {
                const cats = await api('GET', '/categories');
                const sel = document.getElementById('categoryFilter');
                sel.innerHTML = '<option value="">All Categories</option>' + 
                    cats.map(c => `<option value="${c}">${c}</option>`).join('');
            } catch(e) { console.error(e); }
        }

        async function loadItems() {
            const search = document.getElementById('searchInput').value;
            const category = document.getElementById('categoryFilter').value;
            const lowStock = document.getElementById('lowStockFilter').checked;

            let url = '/items?limit=100';
            if (search) url += '&search=' + encodeURIComponent(search);
            if (category) url += '&category=' + encodeURIComponent(category);
            if (lowStock) url += '&low_stock=1';

            try {
                const data = await api('GET', url);
                renderItems(data.items || []);
            } catch(e) {
                document.getElementById('itemsTable').innerHTML = 
                    `<div class="empty-state"><p>Error loading items: ${e.message}</p></div>`;
            }
        }

        function renderItems(items) {
            const container = document.getElementById('itemsTable');
            if (!items.length) {
                container.innerHTML = `<div class="empty-state"><p>No items found.</p></div>`;
                return;
            }

            const rows = items.map(item => {
                const isLow = item.quantity <= item.min_stock;
                const stockBadge = isLow 
                    ? `<span class="badge badge-danger">LOW: ${item.quantity}</span>`
                    : `<span class="badge badge-success">${item.quantity}</span>`;

                return `<tr>
                    <td><strong>${item.sku}</strong><br><small style="color:#6b7280">${item.name}</small></td>
                    <td>${item.category}</td>
                    <td>${stockBadge}</td>
                    <td>$${item.unit_price.toFixed(2)}</td>
                    <td>${item.location || '-'}</td>
                    <td>
                        <div class="qty-control">
                            <button onclick="openStockModal(${item.id}, 'OUT')">−</button>
                            <span>${item.quantity}</span>
                            <button onclick="openStockModal(${item.id}, 'IN')">+</button>
                        </div>
                    </td>
                    <td>
                        <button class="secondary" onclick="editItem(${item.id})" style="padding:6px 12px;font-size:0.85em;">Edit</button>
                        <button class="danger" onclick="deleteItem(${item.id})" style="padding:6px 12px;font-size:0.85em;">Delete</button>
                    </td>
                </tr>`;
            }).join('');

            container.innerHTML = `<table>
                <thead><tr>
                    <th>Item</th><th>Category</th><th>Status</th><th>Price</th>
                    <th>Location</th><th>Stock</th><th>Actions</th>
                </tr></thead>
                <tbody>${rows}</tbody>
            </table>`;
        }

        function openModal() {
            document.getElementById('itemForm').reset();
            document.getElementById('itemId').value = '';
            document.getElementById('modalTitle').textContent = 'Add Item';
            document.getElementById('itemModal').classList.add('active');
        }

        function closeModal() {
            document.getElementById('itemModal').classList.remove('active');
        }

        function editItem(id) {
            api('GET', '/items/' + id).then(item => {
                document.getElementById('itemId').value = item.id;
                document.getElementById('sku').value = item.sku;
                document.getElementById('name').value = item.name;
                document.getElementById('description').value = item.description || '';
                document.getElementById('category').value = item.category;
                document.getElementById('quantity').value = item.quantity;
                document.getElementById('unitPrice').value = item.unit_price;
                document.getElementById('location').value = item.location || '';
                document.getElementById('supplier').value = item.supplier || '';
                document.getElementById('minStock').value = item.min_stock;
                document.getElementById('modalTitle').textContent = 'Edit Item';
                document.getElementById('itemModal').classList.add('active');
            });
        }

        async function saveItem(e) {
            e.preventDefault();
            const id = document.getElementById('itemId').value;
            const body = {
                sku: document.getElementById('sku').value,
                name: document.getElementById('name').value,
                description: document.getElementById('description').value,
                category: document.getElementById('category').value,
                quantity: parseInt(document.getElementById('quantity').value),
                unit_price: parseFloat(document.getElementById('unitPrice').value),
                location: document.getElementById('location').value,
                supplier: document.getElementById('supplier').value,
                min_stock: parseInt(document.getElementById('minStock').value)
            };

            try {
                if (id) {
                    await api('PUT', '/items/' + id, body);
                    showToast('Item updated successfully');
                } else {
                    await api('POST', '/items', body);
                    showToast('Item created successfully');
                }
                closeModal();
                loadItems();
                loadStats();
                loadCategories();
            } catch(e) {
                showToast(e.message, 'error');
            }
        }

        async function deleteItem(id) {
            if (!confirm('Are you sure you want to delete this item?')) return;
            try {
                await api('DELETE', '/items/' + id);
                showToast('Item deleted');
                loadItems();
                loadStats();
            } catch(e) {
                showToast(e.message, 'error');
            }
        }

        function openStockModal(id, type) {
            document.getElementById('stockItemId').value = id;
            document.getElementById('transType').value = type;
            document.getElementById('stockModal').classList.add('active');
        }

        function closeStockModal() {
            document.getElementById('stockModal').classList.remove('active');
        }

        async function updateStock(e) {
            e.preventDefault();
            const id = document.getElementById('stockItemId').value;
            const body = {
                type: document.getElementById('transType').value,
                quantity: parseInt(document.getElementById('transQty').value),
                note: document.getElementById('transNote').value
            };
            try {
                await api('POST', '/items/' + id + '/stock', body);
                showToast('Stock updated successfully');
                closeStockModal();
                loadItems();
                loadStats();
            } catch(e) {
                showToast(e.message, 'error');
            }
        }

        document.querySelectorAll('.modal-overlay').forEach(el => {
            el.addEventListener('click', e => { if(e.target === el) el.classList.remove('active'); });
        });

        loadStats();
        loadCategories();
        loadItems();
    </script>
</body>
</html>
"""


# ============================================================================
# API HANDLER
# ============================================================================

class InventoryHandler(BaseHTTPRequestHandler):
    """HTTP request handler for REST API and dashboard."""

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

    def _send_json(self, data: Any, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_error(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message}, status)

    def _read_json(self) -> Optional[Dict]:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                return {}
            body = self.rfile.read(content_length).decode()
            return json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return None

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/dashboard":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())
            return

        if not path.startswith("/api"):
            self._send_error("Not found", 404)
            return

        route = path[4:]

        if route == "/stats":
            self._send_json(ItemRepository.get_stats())
            return

        if route == "/categories":
            self._send_json(ItemRepository.get_categories())
            return

        if route == "/items":
            try:
                items, total = ItemRepository.list_all(
                    category=params.get("category", [None])[0],
                    low_stock=params.get("low_stock", ["0"])[0] == "1",
                    search=params.get("search", [None])[0],
                    sort_by=params.get("sort_by", ["id"])[0],
                    order=params.get("order", ["asc"])[0],
                    limit=int(params.get("limit", ["100"])[0]),
                    offset=int(params.get("offset", ["0"])[0])
                )
                self._send_json({
                    "items": [i.to_dict() for i in items],
                    "total": total,
                    "limit": int(params.get("limit", ["100"])[0]),
                    "offset": int(params.get("offset", ["0"])[0])
                })
            except Exception as e:
                self._send_error(str(e), 500)
            return

        import re
        match = re.match(r"^/items/(\d+)$", route)
        if match:
            item_id = int(match.group(1))
            item = ItemRepository.get_by_id(item_id)
            if item:
                self._send_json(item.to_dict())
            else:
                self._send_error("Item not found", 404)
            return

        match = re.match(r"^/items/(\d+)/transactions$", route)
        if match:
            item_id = int(match.group(1))
            transactions = TransactionRepository.get_by_item(item_id)
            self._send_json([t.to_dict() for t in transactions])
            return

        self._send_error("Not found", 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if not path.startswith("/api"):
            self._send_error("Not found", 404)
            return

        route = path[4:]
        data = self._read_json()
        if data is None:
            self._send_error("Invalid JSON", 400)
            return

        import re

        if route == "/items":
            required = {"sku", "name", "category"}
            if not required.issubset(data.keys()):
                self._send_error(f"Missing required fields: {required - set(data.keys())}", 400)
                return

            if ItemRepository.get_by_sku(data["sku"]):
                self._send_error(f"SKU '{data['sku']}' already exists", 409)
                return

            item = Item(
                sku=data["sku"],
                name=data["name"],
                description=data.get("description", ""),
                category=data["category"],
                quantity=data.get("quantity", 0),
                unit_price=data.get("unit_price", 0.0),
                location=data.get("location", ""),
                supplier=data.get("supplier", ""),
                min_stock=data.get("min_stock", 10)
            )
            created = ItemRepository.create(item)
            self._send_json(created.to_dict(), 201)
            return

        match = re.match(r"^/items/(\d+)/stock$", route)
        if match:
            item_id = int(match.group(1))
            item = ItemRepository.get_by_id(item_id)
            if not item:
                self._send_error("Item not found", 404)
                return

            trans_type = data.get("type", "")
            quantity = data.get("quantity", 0)

            if trans_type not in ("IN", "OUT", "ADJUST"):
                self._send_error("Type must be IN, OUT, or ADJUST", 400)
                return

            if not isinstance(quantity, int) or quantity <= 0:
                self._send_error("Quantity must be a positive integer", 400)
                return

            if trans_type == "OUT" and item.quantity < quantity:
                self._send_error(f"Insufficient stock. Available: {item.quantity}", 400)
                return

            transaction = TransactionRepository.create(
                item_id=item_id,
                trans_type=trans_type,
                quantity=quantity,
                note=data.get("note", "")
            )
            self._send_json(transaction.to_dict(), 201)
            return

        self._send_error("Not found", 404)

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if not path.startswith("/api"):
            self._send_error("Not found", 404)
            return

        route = path[4:]
        data = self._read_json()
        if data is None:
            self._send_error("Invalid JSON", 400)
            return

        import re
        match = re.match(r"^/items/(\d+)$", route)
        if match:
            item_id = int(match.group(1))
            item = ItemRepository.get_by_id(item_id)
            if not item:
                self._send_error("Item not found", 404)
                return

            if "sku" in data and data["sku"] != item.sku:
                if ItemRepository.get_by_sku(data["sku"]):
                    self._send_error(f"SKU '{data['sku']}' already exists", 409)
                    return

            updated = ItemRepository.update(item_id, data)
            self._send_json(updated.to_dict())
            return

        self._send_error("Not found", 404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if not path.startswith("/api"):
            self._send_error("Not found", 404)
            return

        route = path[4:]
        import re
        match = re.match(r"^/items/(\d+)$", route)
        if match:
            item_id = int(match.group(1))
            if ItemRepository.delete(item_id):
                self._send_json({"message": "Item deleted"})
            else:
                self._send_error("Item not found", 404)
            return

        self._send_error("Not found", 404)


# ============================================================================
# DEMO DATA
# ============================================================================

DEMO_ITEMS = [
    {"sku": "BOOK-001", "name": "The Python Cookbook", "description": "Comprehensive Python programming guide", 
     "category": "Books", "quantity": 45, "unit_price": 49.99, "location": "Shelf A1", "supplier": "O'Reilly", "min_stock": 10},
    {"sku": "BOOK-002", "name": "Clean Code", "description": "Software craftsmanship guide", 
     "category": "Books", "quantity": 12, "unit_price": 42.50, "location": "Shelf A2", "supplier": "Prentice Hall", "min_stock": 15},
    {"sku": "ELEC-001", "name": "Raspberry Pi 5", "description": "8GB RAM single board computer", 
     "category": "Electronics", "quantity": 8, "unit_price": 79.99, "location": "Shelf B1", "supplier": "Raspberry Pi Foundation", "min_stock": 10},
    {"sku": "ELEC-002", "name": "Arduino Uno R4", "description": "WiFi-enabled microcontroller board", 
     "category": "Electronics", "quantity": 25, "unit_price": 27.50, "location": "Shelf B2", "supplier": "Arduino", "min_stock": 15},
    {"sku": "ELEC-003", "name": "SSD 1TB NVMe", "description": "High-speed M.2 solid state drive", 
     "category": "Electronics", "quantity": 3, "unit_price": 89.99, "location": "Shelf B3", "supplier": "Samsung", "min_stock": 5},
    {"sku": "COMP-001", "name": "Mechanical Keyboard", "description": "Cherry MX Blue switches, RGB", 
     "category": "Components", "quantity": 18, "unit_price": 129.99, "location": "Shelf C1", "supplier": "Keychron", "min_stock": 8},
    {"sku": "COMP-002", "name": "27\" 4K Monitor", "description": "IPS panel, 144Hz, HDR400", 
     "category": "Components", "quantity": 6, "unit_price": 349.99, "location": "Shelf C2", "supplier": "LG", "min_stock": 5},
    {"sku": "COMP-003", "name": "USB-C Hub", "description": "7-in-1 adapter with HDMI", 
     "category": "Components", "quantity": 52, "unit_price": 35.00, "location": "Shelf C3", "supplier": "Anker", "min_stock": 20},
]


def init_demo_data() -> None:
    """Populate database with demo inventory items."""
    init_database()

    with get_db() as conn:
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM items")

    for item_data in DEMO_ITEMS:
        item = Item(**item_data)
        ItemRepository.create(item)

    print(f"✅ Demo data loaded: {len(DEMO_ITEMS)} items")

    stats = ItemRepository.get_stats()
    print(f"   📊 Total items: {stats['total_items']}")
    print(f"   💰 Total value: ${stats['total_value']:,.2f}")
    print(f"   📦 Total units: {stats['total_units']}")
    print(f"   ⚠️  Low stock: {stats['low_stock']}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Inventory Management REST API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Start server on port 8000
  %(prog)s --port 8080        # Start on custom port
  %(prog)s --init-demo        # Initialize with demo data and start
        """
    )
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--init-demo", action="store_true", help="Load demo data")

    args = parser.parse_args()

    if args.init_demo:
        init_demo_data()
    else:
        init_database()

    server = HTTPServer((args.host, args.port), InventoryHandler)
    print(f"\n🚀 Inventory API running at http://{args.host}:{args.port}")
    print(f"📊 Dashboard: http://{args.host}:{args.port}/")
    print(f"📡 API Base:  http://{args.host}:{args.port}/api")
    print("\nPress Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
