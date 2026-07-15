#!/usr/bin/env python3
"""
TaskMaster - A robust CLI Task Manager (Todo App on Steroids)

A single-file application with internal modular structure for:
- Task CRUD with categories, priorities, and status tracking
- Time tracking (start/stop/pause)
- Data persistence (JSON)
- Weekly productivity visualization (terminal bar charts)
- Advanced CLI with subcommands

Usage:
    python taskmaster.py add "Fix bug" --category work --priority high
    python taskmaster.py list --status todo --category work
    python taskmaster.py start <task_id>
    python taskmaster.py stop <task_id>
    python taskmaster.py done <task_id>
    python taskmaster.py stats --weekly
    python taskmaster.py chart

Storage: ~/.taskmaster/tasks.json
"""

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict
from pathlib import Path


# =============================================================================
# SECTION 1: ENUMS & DATA MODELS
# =============================================================================

class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __str__(self):
        return self.value

    @property
    def weight(self) -> int:
        return {"low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]


class Status(Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"

    def __str__(self):
        return self.value


@dataclass
class Task:
    id: str
    title: str
    description: str = ""
    category: str = "general"
    priority: Priority = field(default=Priority.MEDIUM)
    status: Status = field(default=Status.TODO)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    time_spent_seconds: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "time_spent_seconds": self.time_spent_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            category=data.get("category", "general"),
            priority=Priority(data.get("priority", "medium")),
            status=Status(data.get("status", "todo")),
            created_at=data.get("created_at", datetime.now().isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            time_spent_seconds=data.get("time_spent_seconds", 0),
        )

    @property
    def age(self) -> timedelta:
        return datetime.now() - datetime.fromisoformat(self.created_at)

    @property
    def time_spent_formatted(self) -> str:
        total = self.time_spent_seconds
        hours = total // 3600
        minutes = (total % 3600) // 60
        seconds = total % 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"


# =============================================================================
# SECTION 2: STORAGE / DATABASE LAYER
# =============================================================================

class TaskStore:
    """JSON-based persistent storage for tasks."""

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path.home() / ".taskmaster"
        self.data_dir = data_dir
        self.data_file = data_dir / "tasks.json"
        self._ensure_storage()
        self._tasks: Dict[str, Task] = {}
        self._load()

    def _ensure_storage(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self.data_file.write_text("[]")

    def _load(self):
        try:
            raw = json.loads(self.data_file.read_text())
            self._tasks = {t["id"]: Task.from_dict(t) for t in raw}
        except (json.JSONDecodeError, KeyError):
            self._tasks = {}

    def _save(self):
        data = [t.to_dict() for t in self._tasks.values()]
        self.data_file.write_text(json.dumps(data, indent=2))

    def get_all(self) -> List[Task]:
        return list(self._tasks.values())

    def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def get_by_status(self, status: Status) -> List[Task]:
        return [t for t in self._tasks.values() if t.status == status]

    def get_by_category(self, category: str) -> List[Task]:
        return [t for t in self._tasks.values() if t.category.lower() == category.lower()]

    def add(self, task: Task) -> Task:
        self._tasks[task.id] = task
        self._save()
        return task

    def update(self, task: Task) -> Task:
        if task.id not in self._tasks:
            raise KeyError(f"Task {task.id} not found")
        self._tasks[task.id] = task
        self._save()
        return task

    def delete(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._save()
            return True
        return False

    def get_categories(self) -> List[str]:
        cats = {t.category for t in self._tasks.values()}
        return sorted(cats)


# =============================================================================
# SECTION 3: BUSINESS LOGIC / SERVICE LAYER
# =============================================================================

class TaskService:
    """High-level operations on tasks."""

    def __init__(self, store: TaskStore):
        self.store = store

    def create(self, title: str, description: str = "", category: str = "general",
               priority: Priority = Priority.MEDIUM) -> Task:
        task = Task(
            id=str(uuid.uuid4())[:8],
            title=title,
            description=description,
            category=category,
            priority=priority,
        )
        return self.store.add(task)

    def start(self, task_id: str) -> Task:
        task = self._require_task(task_id)
        if task.status == Status.DONE:
            raise ValueError("Cannot start a completed task")
        task.status = Status.IN_PROGRESS
        task.started_at = datetime.now().isoformat()
        return self.store.update(task)

    def stop(self, task_id: str) -> Task:
        task = self._require_task(task_id)
        if task.status != Status.IN_PROGRESS:
            raise ValueError("Task is not in progress")
        if task.started_at:
            elapsed = (datetime.now() - datetime.fromisoformat(task.started_at)).total_seconds()
            task.time_spent_seconds += int(elapsed)
        task.status = Status.TODO
        task.started_at = None
        return self.store.update(task)

    def complete(self, task_id: str) -> Task:
        task = self._require_task(task_id)
        if task.status == Status.IN_PROGRESS and task.started_at:
            elapsed = (datetime.now() - datetime.fromisoformat(task.started_at)).total_seconds()
            task.time_spent_seconds += int(elapsed)
        task.status = Status.DONE
        task.completed_at = datetime.now().isoformat()
        task.started_at = None
        return self.store.update(task)

    def cancel(self, task_id: str) -> Task:
        task = self._require_task(task_id)
        task.status = Status.CANCELLED
        return self.store.update(task)

    def edit(self, task_id: str, **kwargs) -> Task:
        task = self._require_task(task_id)
        if "title" in kwargs:
            task.title = kwargs["title"]
        if "description" in kwargs:
            task.description = kwargs["description"]
        if "category" in kwargs:
            task.category = kwargs["category"]
        if "priority" in kwargs:
            task.priority = Priority(kwargs["priority"])
        return self.store.update(task)

    def _require_task(self, task_id: str) -> Task:
        task = self.store.get(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found")
        return task

    def get_stats(self) -> dict:
        tasks = self.store.get_all()
        total = len(tasks)
        by_status = {s.value: 0 for s in Status}
        by_category: Dict[str, int] = {}
        by_priority = {p.value: 0 for p in Priority}
        total_time = 0

        for t in tasks:
            by_status[t.status.value] += 1
            by_category[t.category] = by_category.get(t.category, 0) + 1
            by_priority[t.priority.value] += 1
            total_time += t.time_spent_seconds

        completion_rate = (by_status["done"] / total * 100) if total > 0 else 0

        return {
            "total": total,
            "by_status": by_status,
            "by_category": by_category,
            "by_priority": by_priority,
            "total_time_seconds": total_time,
            "completion_rate": completion_rate,
        }

    def get_weekly_data(self) -> Dict[str, Dict[str, int]]:
        """Returns {day: {category: seconds}} for the last 7 days."""
        tasks = self.store.get_all()
        now = datetime.now()
        week_ago = now - timedelta(days=7)

        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        data: Dict[str, Dict[str, int]] = {d: {} for d in days}

        for t in tasks:
            if t.status != Status.DONE or not t.completed_at:
                continue
            completed = datetime.fromisoformat(t.completed_at)
            if completed < week_ago:
                continue
            day_name = days[completed.weekday()]
            cat = t.category
            data[day_name][cat] = data[day_name].get(cat, 0) + t.time_spent_seconds

        return data


# =============================================================================
# SECTION 4: TERMINAL UI / RENDERING
# =============================================================================

class TerminalUI:
    """Renders tables, charts, and formatted output to the terminal."""

    # ANSI color codes
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "bg_red": "\033[101m",
        "bg_green": "\033[102m",
        "bg_yellow": "\033[103m",
        "bg_blue": "\033[104m",
    }

    STATUS_COLORS = {
        "todo": "yellow",
        "in_progress": "blue",
        "done": "green",
        "cancelled": "dim",
    }

    PRIORITY_COLORS = {
        "low": "dim",
        "medium": "white",
        "high": "yellow",
        "critical": "red",
    }

    def color(self, text: str, color: str) -> str:
        c = self.COLORS.get(color, "")
        r = self.COLORS["reset"]
        return f"{c}{text}{r}"

    def print_header(self, text: str):
        width = 60
        print()
        print(self.color("=" * width, "cyan"))
        print(self.color(f"  {text}", "bold"))
        print(self.color("=" * width, "cyan"))

    def print_task(self, task: Task, index: int = 0):
        status_color = self.STATUS_COLORS.get(task.status.value, "white")
        priority_color = self.PRIORITY_COLORS.get(task.priority.value, "white")
        status_icon = {
            "todo": "[ ]",
            "in_progress": "[~]",
            "done": "[x]",
            "cancelled": "[-]",
        }.get(task.status.value, "[?]")

        prefix = f"{index:2d}. " if index else "    "

        print(f"{prefix}{self.color(status_icon, status_color)} "
              f"{self.color(task.id, 'dim')} | "
              f"{self.color(task.title, 'bold')}")
        print(f"      {self.color(task.priority.value.upper(), priority_color)} | "
              f"{self.color(task.category, 'cyan')} | "
              f"Time: {task.time_spent_formatted}")
        if task.description:
            print(f"      {self.color(task.description, 'dim')}")
        print()

    def print_task_list(self, tasks: List[Task], title: str = "Tasks"):
        self.print_header(title)
        if not tasks:
            print(self.color("  No tasks found.", "dim"))
            return
        for i, task in enumerate(tasks, 1):
            self.print_task(task, i)

    def print_stats(self, stats: dict):
        self.print_header("Statistics")
        print(f"  Total Tasks:    {stats['total']}")
        print(f"  Completion:     {stats['completion_rate']:.1f}%")
        print(f"  Total Time:     {self._format_duration(stats['total_time_seconds'])}")
        print()
        print(self.color("  By Status:", "bold"))
        for status, count in stats["by_status"].items():
            icon = "●"
            color = self.STATUS_COLORS.get(status, "white")
            print(f"    {self.color(icon, color)} {status:12s} {count:3d}")
        print()
        print(self.color("  By Category:", "bold"))
        for cat, count in sorted(stats["by_category"].items()):
            print(f"    • {cat:12s} {count:3d}")
        print()
        print(self.color("  By Priority:", "bold"))
        for pri, count in stats["by_priority"].items():
            color = self.PRIORITY_COLORS.get(pri, "white")
            print(f"    {self.color('▲', color)} {pri:12s} {count:3d}")

    def print_chart(self, weekly_data: Dict[str, Dict[str, int]]):
        self.print_header("Weekly Productivity Chart")

        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        all_cats = set()
        for day_data in weekly_data.values():
            all_cats.update(day_data.keys())
        categories = sorted(all_cats)

        if not categories:
            print(self.color("  No completed tasks in the last 7 days.", "dim"))
            return

        cat_colors = ["bg_green", "bg_blue", "bg_yellow", "bg_red", "bg_magenta", "bg_cyan"]
        cat_color_map = {cat: cat_colors[i % len(cat_colors)] for i, cat in enumerate(categories)}

        # Print legend
        print("  " + self.color("Legend:", "bold"))
        for cat in categories:
            block = self.color("  ", cat_color_map[cat])
            print(f"    {block} {cat}")
        print()

        # Find max for scaling
        max_total = 0
        for day in days:
            day_total = sum(weekly_data.get(day, {}).values())
            max_total = max(max_total, day_total)

        bar_width = 40

        for day in days:
            day_data = weekly_data.get(day, {})
            day_total = sum(day_data.values())

            if day_total == 0:
                bar = self.color("░" * bar_width, "dim")
                label = self.color(f"{day:>3s}", "dim")
                print(f"  {label} │{bar}│ 0m")
                continue

            # Build stacked bar
            bar_segments = []
            for cat in categories:
                val = day_data.get(cat, 0)
                if val == 0:
                    continue
                seg_width = int((val / max_total) * bar_width) if max_total > 0 else 0
                if seg_width == 0 and val > 0:
                    seg_width = 1
                block = "█" * seg_width
                bar_segments.append(self.color(block, cat_color_map[cat]))

            bar = "".join(bar_segments)
            # Pad if needed
            if len(bar.replace('\033[', '').replace('m', '').replace('0', '').replace('9', '').replace('1', '').replace('2', '').replace('3', '').replace('4', '').replace('5', '').replace('6', '').replace('7', '').replace('8', '').replace('[', '').replace(']', '')) < bar_width:
                pass  # ANSI makes length tricky, visual is fine

            label = self.color(f"{day:>3s}", "bold")
            duration = self._format_duration(day_total)
            print(f"  {label} │{bar}│ {duration}")

        print()
        print(self.color(f"  Max daily total: {self._format_duration(max_total)}", "dim"))

    def _format_duration(self, seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        else:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            return f"{h}h {m}m"

    def print_success(self, message: str):
        print(self.color(f"✓ {message}", "green"))

    def print_error(self, message: str):
        print(self.color(f"✗ {message}", "red"), file=sys.stderr)

    def print_info(self, message: str):
        print(self.color(f"ℹ {message}", "blue"))


# =============================================================================
# SECTION 5: CLI ARGUMENT PARSING
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="taskmaster",
        description="A robust CLI task manager with time tracking and productivity charts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s add "Write report" --category work --priority high
  %(prog)s list --status done --category work
  %(prog)s start abc123
  %(prog)s stop abc123
  %(prog)s done abc123
  %(prog)s edit abc123 --title "Updated title"
  %(prog)s delete abc123
  %(prog)s stats
  %(prog)s chart
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add
    add_parser = subparsers.add_parser("add", help="Create a new task")
    add_parser.add_argument("title", help="Task title")
    add_parser.add_argument("--description", "-d", default="", help="Task description")
    add_parser.add_argument("--category", "-c", default="general", help="Task category")
    add_parser.add_argument("--priority", "-p", choices=["low", "medium", "high", "critical"],
                            default="medium", help="Task priority")

    # List
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("--status", "-s", choices=["todo", "in_progress", "done", "cancelled"],
                             help="Filter by status")
    list_parser.add_argument("--category", "-c", help="Filter by category")
    list_parser.add_argument("--priority", "-p", choices=["low", "medium", "high", "critical"],
                             help="Filter by priority")

    # Start
    start_parser = subparsers.add_parser("start", help="Start working on a task")
    start_parser.add_argument("task_id", help="Task ID")

    # Stop
    stop_parser = subparsers.add_parser("stop", help="Stop working on a task")
    stop_parser.add_argument("task_id", help="Task ID")

    # Done
    done_parser = subparsers.add_parser("done", help="Mark a task as completed")
    done_parser.add_argument("task_id", help="Task ID")

    # Cancel
    cancel_parser = subparsers.add_parser("cancel", help="Cancel a task")
    cancel_parser.add_argument("task_id", help="Task ID")

    # Edit
    edit_parser = subparsers.add_parser("edit", help="Edit a task")
    edit_parser.add_argument("task_id", help="Task ID")
    edit_parser.add_argument("--title", "-t", help="New title")
    edit_parser.add_argument("--description", "-d", help="New description")
    edit_parser.add_argument("--category", "-c", help="New category")
    edit_parser.add_argument("--priority", "-p", choices=["low", "medium", "high", "critical"],
                             help="New priority")

    # Delete
    delete_parser = subparsers.add_parser("delete", help="Delete a task")
    delete_parser.add_argument("task_id", help="Task ID")

    # Stats
    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    stats_parser.add_argument("--weekly", "-w", action="store_true", help="Show weekly breakdown")

    # Chart
    subparsers.add_parser("chart", help="Show weekly productivity chart")

    # Categories
    subparsers.add_parser("categories", help="List all categories")

    return parser


# =============================================================================
# SECTION 6: MAIN CONTROLLER
# =============================================================================

class TaskMasterApp:
    def __init__(self):
        self.store = TaskStore()
        self.service = TaskService(self.store)
        self.ui = TerminalUI()

    def run(self, args: Optional[List[str]] = None):
        parser = build_parser()
        parsed = parser.parse_args(args)

        if not parsed.command:
            parser.print_help()
            return

        try:
            handler = getattr(self, f"cmd_{parsed.command}", None)
            if handler:
                handler(parsed)
            else:
                self.ui.print_error(f"Unknown command: {parsed.command}")
                sys.exit(1)
        except KeyError as e:
            self.ui.print_error(str(e))
            sys.exit(1)
        except ValueError as e:
            self.ui.print_error(str(e))
            sys.exit(1)
        except Exception as e:
            self.ui.print_error(f"Unexpected error: {e}")
            sys.exit(1)

    def cmd_add(self, args):
        task = self.service.create(
            title=args.title,
            description=args.description,
            category=args.category,
            priority=Priority(args.priority),
        )
        self.ui.print_success(f"Created task '{task.title}' [{task.id}]")
        self.ui.print_task(task)

    def cmd_list(self, args):
        tasks = self.store.get_all()

        if args.status:
            tasks = [t for t in tasks if t.status.value == args.status]
        if args.category:
            tasks = [t for t in tasks if t.category.lower() == args.category.lower()]
        if args.priority:
            tasks = [t for t in tasks if t.priority.value == args.priority]

        # Sort: in_progress first, then by priority weight desc, then by creation
        tasks.sort(key=lambda t: (
            0 if t.status == Status.IN_PROGRESS else 1,
            -t.priority.weight,
            t.created_at,
        ))

        title = "All Tasks"
        if args.status:
            title = f"Tasks - {args.status}"
        if args.category:
            title += f" ({args.category})"

        self.ui.print_task_list(tasks, title)

    def cmd_start(self, args):
        task = self.service.start(args.task_id)
        self.ui.print_success(f"Started '{task.title}' - timer running")

    def cmd_stop(self, args):
        task = self.service.stop(args.task_id)
        self.ui.print_success(f"Stopped '{task.title}' - total time: {task.time_spent_formatted}")

    def cmd_done(self, args):
        task = self.service.complete(args.task_id)
        self.ui.print_success(f"Completed '{task.title}' - total time: {task.time_spent_formatted}")

    def cmd_cancel(self, args):
        task = self.service.cancel(args.task_id)
        self.ui.print_success(f"Cancelled '{task.title}'")

    def cmd_edit(self, args):
        kwargs = {}
        if args.title:
            kwargs["title"] = args.title
        if args.description:
            kwargs["description"] = args.description
        if args.category:
            kwargs["category"] = args.category
        if args.priority:
            kwargs["priority"] = args.priority

        if not kwargs:
            self.ui.print_error("No fields to update. Use --title, --description, --category, or --priority")
            return

        task = self.service.edit(args.task_id, **kwargs)
        self.ui.print_success(f"Updated task '{task.title}'")
        self.ui.print_task(task)

    def cmd_delete(self, args):
        if self.store.delete(args.task_id):
            self.ui.print_success(f"Deleted task {args.task_id}")
        else:
            self.ui.print_error(f"Task '{args.task_id}' not found")
            sys.exit(1)

    def cmd_stats(self, args):
        stats = self.service.get_stats()
        self.ui.print_stats(stats)

        if args.weekly:
            weekly = self.service.get_weekly_data()
            self.ui.print_chart(weekly)

    def cmd_chart(self, args):
        weekly = self.service.get_weekly_data()
        self.ui.print_chart(weekly)

    def cmd_categories(self, args):
        cats = self.store.get_categories()
        self.ui.print_header("Categories")
        if not cats:
            print(self.ui.color("  No categories yet.", "dim"))
        for cat in cats:
            count = len(self.store.get_by_category(cat))
            print(f"  • {cat:15s} ({count} tasks)")


# =============================================================================
# SECTION 7: ENTRY POINT
# =============================================================================

def main():
    app = TaskMasterApp()
    app.run()


if __name__ == "__main__":
    main() 
