#!/usr/bin/env python3
"""
Automated Log File Analyzer & Reporter
A single-file tool that monitors directories for log files, processes them
efficiently using generators, and generates automated reports with alerting.

Usage:
    python log_analyzer.py --demo                    # Run with sample logs
    python log_analyzer.py --watch ./logs --daemon   # Monitor continuously
    python log_analyzer.py --once --email            # Run once and email
"""

import os
import re
import sys
import json
import time
import hashlib
import argparse
import smtplib
import logging
import urllib.request
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from dataclasses import dataclass, field, asdict
from typing import Generator, Dict, List, Optional, Set, Tuple, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from logging.handlers import RotatingFileHandler

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class Config:
    """Configuration settings for the log analyzer."""
    # Directory settings (defaults anchored to the script location)
    def _base_dir() -> Path:
        try:
            return Path(__file__).parent
        except Exception:
            return Path('.')

    watch_dir: Path = field(default_factory=lambda: Config._base_dir() / "logs")
    report_dir: Path = field(default_factory=lambda: Config._base_dir() / "reports")
    state_file: Path = field(default_factory=lambda: Config._base_dir() / ".analyzer_state.json")

    # File patterns
    log_patterns: List[str] = field(default_factory=lambda: ["*.log", "*.txt"])
    processed_marker: str = ".processed"

    # Analysis thresholds
    critical_error_rate: float = 0.05  # 5% error rate triggers alert
    critical_error_count: int = 100      # Or 100+ errors absolute

    # Alert settings
    email_enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: List[str] = field(default_factory=list)

    webhook_enabled: bool = False
    webhook_url: str = ""  # Discord/Slack webhook URL

    # Monitoring settings
    check_interval: int = 30  # seconds
    max_file_size_mb: int = 500

    # Report settings
    top_ips_count: int = 10
    top_errors_count: int = 10
    retention_days: int = 7


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class LogEntry:
    """Represents a single parsed log entry."""
    timestamp: Optional[datetime] = None
    ip_address: Optional[str] = None
    level: str = "INFO"
    message: str = ""
    raw_line: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'ip_address': self.ip_address,
            'level': self.level,
            'message': self.message[:200],
        }


@dataclass 
class AnalysisResult:
    """Results from analyzing log files."""
    file_path: Path
    file_size: int
    line_count: int
    error_count: int
    warning_count: int
    unique_ips: Set[str] = field(default_factory=set)
    ip_requests: Counter = field(default_factory=Counter)
    error_types: Counter = field(default_factory=Counter)
    hourly_distribution: Counter = field(default_factory=Counter)
    entries: List[LogEntry] = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        if self.line_count == 0:
            return 0.0
        return self.error_count / self.line_count

    @property
    def is_critical(self) -> bool:
        return (self.error_rate > Config().critical_error_rate or 
                self.error_count >= Config().critical_error_count)


# ============================================================================
# LOG PARSERS
# ============================================================================

class LogParser:
    """Handles parsing of log files with regex patterns."""

    # Common log patterns
    PATTERNS = {
        'timestamp': re.compile(
            r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:?\d{2})?)'
        ),
        'ip_address': re.compile(
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        ),
        'log_level': re.compile(
            r'\b(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL|TRACE)\b',
            re.IGNORECASE
        ),
        'http_status': re.compile(r'\b(\d{3})\b'),
        'error_code': re.compile(r'(ERR_[A-Z_]+|E\d+|0x[0-9A-Fa-f]+)'),
    }

    def __init__(self):
        self.level_map = {
            'debug': 'DEBUG', 'info': 'INFO', 'warning': 'WARNING', 
            'warn': 'WARNING', 'error': 'ERROR', 'critical': 'CRITICAL',
            'fatal': 'CRITICAL', 'trace': 'TRACE'
        }

    def parse_line(self, line: str) -> LogEntry:
        """Parse a single log line into a LogEntry."""
        entry = LogEntry(raw_line=line.strip())

        # Extract timestamp
        ts_match = self.PATTERNS['timestamp'].search(line)
        if ts_match:
            try:
                ts_str = ts_match.group(1).replace('T', ' ')
                entry.timestamp = datetime.strptime(ts_str[:19], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass

        # Extract IP address
        ip_match = self.PATTERNS['ip_address'].search(line)
        if ip_match:
            entry.ip_address = ip_match.group(0)

        # Extract log level
        level_match = self.PATTERNS['log_level'].search(line)
        if level_match:
            entry.level = self.level_map.get(level_match.group(1).lower(), 'INFO')

        # Extract message
        entry.message = line.strip()

        return entry

    def parse_file_generator(self, file_path: Path) -> Generator[LogEntry, None, None]:
        """
        Memory-efficient generator that yields LogEntry objects one at a time.
        Handles files of any size without loading into memory.
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    if not line.strip():
                        continue
                    try:
                        entry = self.parse_line(line)
                        yield entry
                    except Exception as e:
                        yield LogEntry(
                            level="PARSE_ERROR",
                            message=f"Failed to parse line {line_num}: {line[:100]}",
                            raw_line=line.strip()
                        )
        except OSError as e:
            logging.error(f"Cannot read file {file_path}: {e}")
            return


# ============================================================================
# ANALYZER ENGINE
# ============================================================================

class LogAnalyzer:
    """Analyzes log files and produces statistics."""

    def __init__(self, config: Config):
        self.config = config
        self.parser = LogParser()
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load processing state to avoid re-processing files."""
        if self.config.state_file.exists():
            try:
                with open(self.config.state_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {'processed_files': {}, 'last_run': None}

    def _save_state(self) -> None:
        """Save processing state."""
        self.config.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config.state_file, 'w') as f:
            json.dump(self.state, f, indent=2, default=str)

    def _get_file_hash(self, file_path: Path) -> str:
        """Get MD5 hash of file (first 8KB for speed)."""
        h = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                h.update(f.read(8192))
            h.update(str(file_path.stat().st_size).encode())
            h.update(str(file_path.stat().st_mtime).encode())
        except OSError:
            pass
        return h.hexdigest()

    def _is_new_file(self, file_path: Path) -> bool:
        """Check if file needs processing."""
        file_id = str(file_path.resolve())
        current_hash = self._get_file_hash(file_path)
        stored_hash = self.state['processed_files'].get(file_id, {}).get('hash')
        return stored_hash != current_hash

    def _mark_processed(self, file_path: Path) -> None:
        """Mark file as processed."""
        file_id = str(file_path.resolve())
        self.state['processed_files'][file_id] = {
            'hash': self._get_file_hash(file_path),
            'processed_at': datetime.now().isoformat()
        }

    def find_log_files(self) -> List[Path]:
        """Find all log files matching patterns in watch directory."""
        files = []
        if not self.config.watch_dir.exists():
            try:
                self.config.watch_dir.mkdir(parents=True, exist_ok=True)
                logging.info(f"Created missing watch directory: {self.config.watch_dir}")
            except Exception as e:
                logging.warning(
                    f"Watch directory does not exist and could not be created: {self.config.watch_dir} ({e})"
                )
                return files

        for pattern in self.config.log_patterns:
            files.extend(self.config.watch_dir.glob(pattern))
            files.extend(self.config.watch_dir.rglob(pattern))

        # If no files found in the configured watch_dir, try falling back to
        # the script/project directory where the logs may be located.
        if not files:
            project_dir = Path(__file__).parent
            if project_dir != self.config.watch_dir:
                fallback_files = []
                for pattern in self.config.log_patterns:
                    fallback_files.extend(project_dir.glob(pattern))
                    fallback_files.extend(project_dir.rglob(pattern))

                if fallback_files:
                    logging.info(
                        f"No log files in {self.config.watch_dir}; falling back to {project_dir}"
                    )
                    files.extend(fallback_files)

        valid_files = []
        for f in files:
            if not f.is_file():
                continue
            size_mb = f.stat().st_size / (1024 * 1024)
            if size_mb > self.config.max_file_size_mb:
                logging.warning(f"Skipping large file {f} ({size_mb:.1f} MB)")
                continue
            valid_files.append(f)

        return sorted(set(valid_files))

    def analyze_file(self, file_path: Path) -> AnalysisResult:
        """Analyze a single log file using generator for memory efficiency."""
        result = AnalysisResult(
            file_path=file_path,
            file_size=file_path.stat().st_size,
            line_count=0,
            error_count=0,
            warning_count=0
        )

        logging.info(f"Analyzing: {file_path}")

        for entry in self.parser.parse_file_generator(file_path):
            result.line_count += 1

            if entry.level in ('ERROR', 'CRITICAL', 'FATAL'):
                result.error_count += 1
            elif entry.level in ('WARNING', 'WARN'):
                result.warning_count += 1

            if entry.ip_address:
                result.unique_ips.add(entry.ip_address)
                result.ip_requests[entry.ip_address] += 1

            if entry.level in ('ERROR', 'CRITICAL'):
                error_type = self._categorize_error(entry.message)
                result.error_types[error_type] += 1

            if entry.timestamp:
                hour_key = entry.timestamp.strftime('%Y-%m-%d %H:00')
                result.hourly_distribution[hour_key] += 1

            if entry.level in ('ERROR', 'CRITICAL', 'FATAL') and len(result.entries) < 1000:
                result.entries.append(entry)

        return result

    def _categorize_error(self, message: str) -> str:
        """Categorize error message into type."""
        message_lower = message.lower()

        categories = {
            'connection': ['connection', 'timeout', 'refused', 'reset'],
            'database': ['database', 'db', 'sql', 'query'],
            'memory': ['memory', 'oom', 'out of memory', 'heap'],
            'disk': ['disk', 'space', 'quota', 'io error'],
            'permission': ['permission', 'denied', 'unauthorized', 'forbidden'],
            'not_found': ['not found', '404', 'missing', 'no such'],
            'syntax': ['syntax', 'parse', 'invalid', 'malformed'],
        }

        for category, keywords in categories.items():
            if any(kw in message_lower for kw in keywords):
                return category

        return 'other'

    def analyze_all(self) -> List[AnalysisResult]:
        """Analyze all new/modified log files."""
        files = self.find_log_files()
        results = []

        for file_path in files:
            if not self._is_new_file(file_path):
                logging.debug(f"Skipping unchanged file: {file_path}")
                continue

            try:
                result = self.analyze_file(file_path)
                results.append(result)
                self._mark_processed(file_path)
            except Exception as e:
                logging.error(f"Failed to analyze {file_path}: {e}")

        self.state['last_run'] = datetime.now().isoformat()
        self._save_state()

        return results


# ============================================================================
# REPORT GENERATOR
# ============================================================================

class ReportGenerator:
    """Generates HTML and text reports."""

    def __init__(self, config: Config):
        self.config = config

    def _generate_css(self) -> str:
        """Generate CSS styles for HTML report."""
        return """
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #f5f7fa; color: #2d3748; line-height: 1.6; 
                padding: 20px;
            }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            .header h1 { font-size: 2em; margin-bottom: 10px; }
            .header .meta { opacity: 0.9; font-size: 0.95em; }
            .summary-grid { 
                display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px; margin-bottom: 30px;
            }
            .card { 
                background: white; padding: 20px; border-radius: 10px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-left: 4px solid #667eea;
            }
            .card.critical { border-left-color: #e53e3e; background: #fff5f5; }
            .card.warning { border-left-color: #dd6b20; background: #fffaf0; }
            .card.success { border-left-color: #38a169; background: #f0fff4; }
            .card h3 { font-size: 0.85em; text-transform: uppercase; color: #718096; margin-bottom: 8px; }
            .card .value { font-size: 2em; font-weight: bold; color: #2d3748; }
            .card .sub { font-size: 0.85em; color: #718096; margin-top: 4px; }
            .section { 
                background: white; padding: 25px; border-radius: 10px;
                margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }
            .section h2 { 
                font-size: 1.3em; margin-bottom: 15px; padding-bottom: 10px;
                border-bottom: 2px solid #e2e8f0; color: #2d3748;
            }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }
            th { background: #f7fafc; font-weight: 600; color: #4a5568; font-size: 0.85em; text-transform: uppercase; }
            tr:hover { background: #f7fafc; }
            .badge { 
                display: inline-block; padding: 4px 10px; border-radius: 20px;
                font-size: 0.75em; font-weight: 600;
            }
            .badge-error { background: #fed7d7; color: #c53030; }
            .badge-warning { background: #feebc8; color: #c05621; }
            .badge-info { background: #bee3f8; color: #2b6cb0; }
            .badge-success { background: #c6f6d5; color: #276749; }
            .alert-box { 
                background: #fff5f5; border: 1px solid #fc8181; border-radius: 8px;
                padding: 15px; margin-bottom: 20px; color: #c53030;
            }
            .alert-box h3 { margin-bottom: 8px; }
            .log-entry { 
                font-family: 'Courier New', monospace; font-size: 0.85em;
                background: #f7fafc; padding: 10px; border-radius: 6px;
                margin-bottom: 8px; border-left: 3px solid #e2e8f0;
            }
            .log-entry.error { border-left-color: #e53e3e; background: #fff5f5; }
            .log-entry.critical { border-left-color: #9b2c2c; background: #fed7d7; }
            .progress-bar { 
                height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden;
            }
            .progress-fill { height: 100%; background: #667eea; border-radius: 4px; }
            .progress-fill.danger { background: #e53e3e; }
            .progress-fill.warning { background: #dd6b20; }
            .footer { text-align: center; color: #a0aec0; margin-top: 40px; font-size: 0.85em; }
        </style>
        """

    def generate_html(self, results: List[AnalysisResult]) -> str:
        """Generate comprehensive HTML report."""
        if not results:
            return self._generate_empty_report()

        total_lines = sum(r.line_count for r in results)
        total_errors = sum(r.error_count for r in results)
        total_warnings = sum(r.warning_count for r in results)
        total_ips = len(set().union(*[r.unique_ips for r in results]))
        critical_files = [r for r in results if r.is_critical]

        all_ips = Counter()
        all_errors = Counter()
        all_hours = Counter()
        for r in results:
            all_ips.update(r.ip_requests)
            all_errors.update(r.error_types)
            all_hours.update(r.hourly_distribution)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Log Analysis Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
    {self._generate_css()}
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Log Analysis Report</h1>
            <div class="meta">
                Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 
                Files Analyzed: {len(results)} | 
                Watch Directory: {self.config.watch_dir}
            </div>
        </div>

        {self._generate_alerts_section(critical_files)}

        <div class="summary-grid">
            <div class="card {'critical' if total_errors > 100 else 'success'}">
                <h3>Total Errors</h3>
                <div class="value">{total_errors:,}</div>
                <div class="sub">{total_errors/max(total_lines,1)*100:.2f}% of lines</div>
            </div>
            <div class="card {'warning' if total_warnings > 50 else 'success'}">
                <h3>Warnings</h3>
                <div class="value">{total_warnings:,}</div>
            </div>
            <div class="card">
                <h3>Total Lines</h3>
                <div class="value">{total_lines:,}</div>
            </div>
            <div class="card">
                <h3>Unique IPs</h3>
                <div class="value">{total_ips:,}</div>
            </div>
            <div class="card {'critical' if critical_files else 'success'}">
                <h3>Critical Files</h3>
                <div class="value">{len(critical_files)}</div>
                <div class="sub">of {len(results)} total</div>
            </div>
        </div>

        <div class="section">
            <h2>📁 File Analysis</h2>
            <table>
                <tr>
                    <th>File</th>
                    <th>Size</th>
                    <th>Lines</th>
                    <th>Errors</th>
                    <th>Error Rate</th>
                    <th>Status</th>
                </tr>
                {''.join(self._file_row(r) for r in results)}
            </table>
        </div>

        <div class="section">
            <h2>🌐 Top IP Addresses</h2>
            <table>
                <tr><th>IP Address</th><th>Requests</th><th>Percentage</th></tr>
                {''.join(self._ip_row(ip, count, sum(all_ips.values())) 
                         for ip, count in all_ips.most_common(self.config.top_ips_count))}
            </table>
        </div>

        <div class="section">
            <h2>⚠️ Error Categories</h2>
            <table>
                <tr><th>Category</th><th>Count</th><th>Distribution</th></tr>
                {''.join(self._error_row(err, count, sum(all_errors.values()))
                         for err, count in all_errors.most_common(self.config.top_errors_count))}
            </table>
        </div>

        <div class="section">
            <h2>📈 Hourly Activity</h2>
            <table>
                <tr><th>Hour</th><th>Events</th></tr>
                {''.join(f'<tr><td>{hour}</td><td>{count:,}</td></tr>' 
                         for hour, count in sorted(all_hours.items())[-24:])}
            </table>
        </div>

        <div class="section">
            <h2>🔥 Critical Errors (Sample)</h2>
            {self._generate_error_samples(results)}
        </div>

        <div class="footer">
            Generated by Automated Log Analyzer | 
            Next check in {self.config.check_interval} seconds
        </div>
    </div>
</body>
</html>"""
        return html

    def _generate_empty_report(self) -> str:
        return f"""<!DOCTYPE html>
<html><head><title>Log Report</title>{self._generate_css()}</head>
<body><div class="container">
<div class="header"><h1>📊 Log Analysis Report</h1></div>
<div class="section"><h2>No new log files to analyze</h2>
<p>Watching: {self.config.watch_dir}</p>
<p>Patterns: {', '.join(self.config.log_patterns)}</p>
</div></div></body></html>"""

    def _generate_alerts_section(self, critical_files: List[AnalysisResult]) -> str:
        if not critical_files:
            return ""

        alerts = []
        for f in critical_files:
            alerts.append(
                f"<li><strong>{f.file_path.name}</strong>: "
                f"{f.error_count} errors ({f.error_rate*100:.1f}% rate)</li>"
            )

        return f"""
        <div class="alert-box">
            <h3>🚨 Critical Alert: High Error Rate Detected</h3>
            <ul>{''.join(alerts)}</ul>
        </div>"""

    def _file_row(self, result: AnalysisResult) -> str:
        status_class = "badge-error" if result.is_critical else "badge-success"
        status_text = "CRITICAL" if result.is_critical else "OK"
        size_str = self._format_size(result.file_size)

        return f"""
        <tr>
            <td>{result.file_path.name}</td>
            <td>{size_str}</td>
            <td>{result.line_count:,}</td>
            <td>{result.error_count:,}</td>
            <td>
                <div class="progress-bar">
                    <div class="progress-fill {'danger' if result.is_critical else ''}" 
                         style="width: {min(result.error_rate*100, 100)}%"></div>
                </div>
                {result.error_rate*100:.2f}%
            </td>
            <td><span class="badge {status_class}">{status_text}</span></td>
        </tr>"""

    def _ip_row(self, ip: str, count: int, total: int) -> str:
        pct = count / max(total, 1) * 100
        return f"<tr><td><code>{ip}</code></td><td>{count:,}</td><td>{pct:.1f}%</td></tr>"

    def _error_row(self, error: str, count: int, total: int) -> str:
        pct = count / max(total, 1) * 100
        return f"""
        <tr>
            <td>{error.title()}</td>
            <td>{count:,}</td>
            <td>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {pct}%"></div>
                </div>
                {pct:.1f}%
            </td>
        </tr>"""

    def _generate_error_samples(self, results: List[AnalysisResult]) -> str:
        samples = []
        for r in results:
            for entry in r.entries[:5]:
                level_class = entry.level.lower()
                ts = entry.timestamp.strftime('%H:%M:%S') if entry.timestamp else 'Unknown'
                samples.append(
                    f'<div class="log-entry {level_class}">'
                    f'<strong>[{ts}] {entry.level}</strong> '
                    f'{entry.ip_address or ""} {entry.message[:200]}'
                    f'</div>'
                )

        if not samples:
            return "<p>No critical errors found.</p>"

        return ''.join(samples[:20])

    def _format_size(self, size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def save_report(self, html_content: str) -> Path:
        """Save HTML report to file."""
        self.config.report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = self.config.report_dir / f"report_{timestamp}.html"
        report_path.write_text(html_content, encoding='utf-8')

        latest_path = self.config.report_dir / "latest_report.html"
        latest_path.write_text(html_content, encoding='utf-8')

        self._cleanup_old_reports()

        return report_path

    def _cleanup_old_reports(self) -> None:
        cutoff = datetime.now() - timedelta(days=self.config.retention_days)
        for report in self.config.report_dir.glob("report_*.html"):
            try:
                date_str = report.stem.split('_')[1]
                report_date = datetime.strptime(date_str, '%Y%m%d')
                if report_date < cutoff:
                    report.unlink()
            except (ValueError, OSError):
                pass


# ============================================================================
# ALERTERS
# ============================================================================

class Alerter:
    """Handles sending alerts via email and webhooks."""

    def __init__(self, config: Config):
        self.config = config

    def send_email(self, subject: str, html_body: str) -> bool:
        """Send email alert using SMTP."""
        if not self.config.email_enabled:
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.config.email_from
            msg['To'] = ', '.join(self.config.email_to)

            msg.attach(MIMEText(html_body, 'html'))

            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.send_message(msg)

            logging.info("Email alert sent successfully")
            return True

        except Exception as e:
            logging.error(f"Failed to send email: {e}")
            return False

    def send_webhook(self, message: Dict[str, Any]) -> bool:
        """Send alert to Discord/Slack webhook."""
        if not self.config.webhook_enabled or not self.config.webhook_url:
            return False

        try:
            payload = json.dumps(message).encode('utf-8')
            req = urllib.request.Request(
                self.config.webhook_url,
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                success = response.status in (200, 204)
                if success:
                    logging.info("Webhook alert sent successfully")
                return success

        except Exception as e:
            logging.error(f"Failed to send webhook: {e}")
            return False

    def alert_critical(self, results: List[AnalysisResult], report_path: Path) -> None:
        """Send critical error alerts."""
        critical = [r for r in results if r.is_critical]
        if not critical:
            return

        summary = f"🚨 CRITICAL: {len(critical)} file(s) exceed error threshold!\n\n"
        for r in critical:
            summary += f"• {r.file_path.name}: {r.error_count} errors ({r.error_rate*100:.1f}%)\n"

        if self.config.email_enabled:
            html = f"""
            <html><body>
            <h2>🚨 Critical Log Alert</h2>
            <p>{summary.replace(chr(10), '<br>')}</p>
            <p>Report: {report_path}</p>
            </body></html>
            """
            self.send_email("🚨 Critical Log Alert", html)

        if self.config.webhook_enabled:
            discord_msg = {
                "content": None,
                "embeds": [{
                    "title": "🚨 Critical Log Alert",
                    "description": summary,
                    "color": 15158332,
                    "timestamp": datetime.now().isoformat(),
                    "fields": [
                        {"name": "Files Affected", "value": str(len(critical)), "inline": True},
                        {"name": "Report", "value": str(report_path), "inline": True}
                    ]
                }]
            }
            self.send_webhook(discord_msg)


# ============================================================================
# MAIN APPLICATION
# ============================================================================

class LogAnalyzerApp:
    """Main application orchestrator."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.analyzer = LogAnalyzer(self.config)
        self.reporter = ReportGenerator(self.config)
        self.alerter = Alerter(self.config)
        self.running = False

        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure application logging."""
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.StreamHandler(sys.stdout),
                RotatingFileHandler(
                    'analyzer.log', maxBytes=5*1024*1024, backupCount=3
                )
            ]
        )

    def run_once(self) -> Optional[Path]:
        """Run single analysis cycle."""
        logging.info("=" * 50)
        logging.info("Starting log analysis cycle")

        results = self.analyzer.analyze_all()

        if not results:
            logging.info("No new files to analyze")
            return None

        html = self.reporter.generate_html(results)
        report_path = self.reporter.save_report(html)
        logging.info(f"Report saved: {report_path}")

        critical_count = len([r for r in results if r.is_critical])
        if critical_count > 0:
            logging.warning(f"CRITICAL: {critical_count} file(s) exceed error threshold!")
            self.alerter.alert_critical(results, report_path)

        total_errors = sum(r.error_count for r in results)
        total_lines = sum(r.line_count for r in results)
        logging.info(f"Analyzed {len(results)} files, {total_lines:,} lines, {total_errors:,} errors")

        return report_path

    def run_daemon(self) -> None:
        """Run continuous monitoring loop."""
        self.running = True
        logging.info(f"Starting daemon mode (interval: {self.config.check_interval}s)")

        try:
            while self.running:
                self.run_once()

                for _ in range(self.config.check_interval):
                    if not self.running:
                        break
                    time.sleep(1)

        except KeyboardInterrupt:
            logging.info("Shutting down...")
            self.running = False

    def stop(self) -> None:
        """Stop daemon mode."""
        self.running = False


# ============================================================================
# CLI INTERFACE
# ============================================================================

def create_sample_logs(watch_dir: Path) -> None:
    """Create sample log files for testing."""
    watch_dir.mkdir(parents=True, exist_ok=True)

    sample_logs = [
        ("server.log", """
2024-01-15 10:00:01 INFO 192.168.1.1 Server started successfully
2024-01-15 10:00:15 DEBUG 192.168.1.1 Connection pool initialized
2024-01-15 10:01:23 ERROR 192.168.1.45 Database connection timeout after 30s
2024-01-15 10:01:24 ERROR 192.168.1.45 Failed to process request: ERR_DB_TIMEOUT
2024-01-15 10:02:00 WARNING 192.168.1.100 High memory usage detected: 85%
2024-01-15 10:02:15 ERROR 10.0.0.5 Permission denied accessing /api/admin
2024-01-15 10:03:00 INFO 192.168.1.200 User login successful
2024-01-15 10:03:45 CRITICAL 192.168.1.1 Out of memory error - shutting down
2024-01-15 10:04:00 ERROR 192.168.1.45 Connection reset by peer
2024-01-15 10:05:00 INFO 192.168.1.1 Server restarted
"""),
        ("app.log", """
2024-01-15 10:00:05 INFO Application startup complete
2024-01-15 10:00:10 DEBUG Cache warmed up in 234ms
2024-01-15 10:01:00 ERROR Payment processing failed: ERR_INVALID_CARD
2024-01-15 10:01:01 ERROR Payment processing failed: ERR_INVALID_CARD
2024-01-15 10:01:02 ERROR Payment processing failed: ERR_NETWORK
2024-01-15 10:02:00 WARNING API rate limit approaching: 80/100
2024-01-15 10:03:00 INFO Background job completed
2024-01-15 10:04:00 ERROR 404 Not Found: /api/v1/missing
2024-01-15 10:05:00 FATAL Unhandled exception in worker thread
"""),
        ("access.log", """
192.168.1.1 - - [15/Jan/2024:10:00:01 +0000] "GET /index.html HTTP/1.1" 200 1234
192.168.1.45 - - [15/Jan/2024:10:01:23 +0000] "POST /api/data HTTP/1.1" 500 512
10.0.0.5 - - [15/Jan/2024:10:02:15 +0000] "GET /admin HTTP/1.1" 403 256
192.168.1.200 - - [15/Jan/2024:10:03:00 +0000] "GET /dashboard HTTP/1.1" 200 4096
192.168.1.45 - - [15/Jan/2024:10:04:00 +0000] "GET /api/error HTTP/1.1" 500 128
"""),
    ]

    for filename, content in sample_logs:
        filepath = watch_dir / filename
        if not filepath.exists():
            filepath.write_text(content.strip())
            print(f"Created sample log: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Automated Log File Analyzer & Reporter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --demo                    # Run with sample logs
  %(prog)s --watch ./logs --daemon   # Monitor directory continuously
  %(prog)s --once --email            # Run once and email report
        """
    )

    parser.add_argument('--watch', type=Path, default=Path('./logs'),
                       help='Directory to watch for log files')
    parser.add_argument('--report-dir', type=Path, default=Path('./reports'),
                       help='Directory to save reports')
    parser.add_argument('--patterns', nargs='+', default=['*.log', '*.txt'],
                       help='File patterns to match')
    parser.add_argument('--daemon', action='store_true',
                       help='Run continuously')
    parser.add_argument('--interval', type=int, default=30,
                       help='Check interval in seconds (daemon mode)')
    parser.add_argument('--once', action='store_true',
                       help='Run once and exit')
    parser.add_argument('--demo', action='store_true',
                       help='Create sample logs and run')

    parser.add_argument('--email', action='store_true',
                       help='Enable email alerts')
    parser.add_argument('--smtp-host', default='smtp.gmail.com')
    parser.add_argument('--smtp-port', type=int, default=587)
    parser.add_argument('--smtp-user', default='')
    parser.add_argument('--smtp-pass', default='')
    parser.add_argument('--email-from', default='')
    parser.add_argument('--email-to', nargs='+', default=[])

    parser.add_argument('--webhook', default='',
                       help='Discord/Slack webhook URL')

    parser.add_argument('--error-rate', type=float, default=0.05,
                       help='Critical error rate threshold (0.05 = 5%%)')
    parser.add_argument('--error-count', type=int, default=100,
                       help='Critical absolute error count')

    args = parser.parse_args()

    config = Config(
        watch_dir=args.watch,
        report_dir=args.report_dir,
        log_patterns=args.patterns,
        check_interval=args.interval,
        email_enabled=args.email,
        smtp_host=args.smtp_host,
        smtp_port=args.smtp_port,
        smtp_user=args.smtp_user,
        smtp_password=args.smtp_pass,
        email_from=args.email_from,
        email_to=args.email_to,
        webhook_enabled=bool(args.webhook),
        webhook_url=args.webhook,
        critical_error_rate=args.error_rate,
        critical_error_count=args.error_count,
    )

    if args.demo:
        print("🚀 Demo mode: Creating sample logs...")
        create_sample_logs(args.watch)
        args.once = True

    app = LogAnalyzerApp(config)

    if args.daemon:
        app.run_daemon()
    else:
        report_path = app.run_once()
        if report_path:
            print(f"\n✅ Report generated: {report_path}")
            print(f"📊 Open in browser: file://{report_path.resolve()}")
        else:
            print("\n⚠️  No new log files found to analyze.")


if __name__ == '__main__':
    main()
