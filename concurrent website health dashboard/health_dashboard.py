#!/usr/bin/env python3
"""
Concurrent Website Health Dashboard
A single-file TUI dashboard for monitoring website health, response times, and SSL certificates.

Usage:
    python health_dashboard.py

Requirements:
    pip install aiohttp rich

Press Ctrl+C to exit.
"""

import asyncio
import aiohttp
import ssl
import certifi
import datetime
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

# Rich imports for beautiful TUI
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import box
from rich.align import Align


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CheckResult:
    """Result of a single health check for a URL."""
    url: str
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    status: str = "PENDING"  # UP, DOWN, ERROR, TIMEOUT
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    ssl_expiry: Optional[datetime.datetime] = None
    ssl_days_remaining: Optional[int] = None


@dataclass  
class MonitoredTarget:
    """Configuration for a URL to monitor."""
    url: str
    name: str
    check_interval_seconds: float = 30.0
    timeout_seconds: float = 10.0
    follow_redirects: bool = True
    check_ssl: bool = True

    # Runtime state
    history: List[CheckResult] = field(default_factory=list)
    last_result: Optional[CheckResult] = None


# =============================================================================
# SSL CERTIFICATE CHECKER (runs in thread pool to avoid blocking)
# =============================================================================

def get_ssl_expiry(hostname: str, port: int = 443) -> Optional[datetime.datetime]:
    """
    Get SSL certificate expiration date.
    Runs synchronously - called via run_in_executor.
    """
    try:
        import socket
        context = ssl.create_default_context(cafile=certifi.where())

        with socket.create_connection((hostname, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                expiry_str = cert.get('notAfter')
                if expiry_str:
                    return datetime.datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
    except Exception:
        pass
    return None


# =============================================================================
# ASYNC HEALTH CHECKER
# =============================================================================

class HealthChecker:
    """Performs async HTTP health checks with SSL certificate monitoring."""

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self.session = session
        self._owned_session = session is None
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def __aenter__(self):
        if self._owned_session:
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=10,
                enable_cleanup_closed=True,
                force_close=True,
            )
            timeout = aiohttp.ClientTimeout(total=30, connect=5)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={'User-Agent': 'HealthDashboard/1.0'},
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._owned_session and self.session:
            await self.session.close()
        self.executor.shutdown(wait=False)

    async def check_target(self, target: MonitoredTarget) -> CheckResult:
        """Perform a single health check on a target."""
        result = CheckResult(url=target.url)
        start_time = asyncio.get_event_loop().time()

        try:
            async with self.session.get(
                target.url,
                allow_redirects=target.follow_redirects,
                ssl=ssl.create_default_context(cafile=certifi.where()),
            ) as response:
                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
                result.response_time_ms = round(elapsed, 2)
                result.status_code = response.status

                if 200 <= response.status < 400:
                    result.status = "UP"
                else:
                    result.status = "ERROR"
                    result.error_message = f"HTTP {response.status}"

        except asyncio.TimeoutError:
            result.status = "TIMEOUT"
            result.error_message = f"Request exceeded {target.timeout_seconds}s"

        except aiohttp.ClientConnectorError as e:
            result.status = "DOWN"
            result.error_message = f"Connection failed: {str(e)}"

        except aiohttp.ClientError as e:
            result.status = "ERROR"
            result.error_message = f"Client error: {str(e)}"

        except Exception as e:
            result.status = "ERROR"
            result.error_message = f"Unexpected: {str(e)}"

        # Check SSL certificate (in thread pool to avoid blocking)
        if target.check_ssl and result.status in ("UP", "ERROR"):
            try:
                parsed = urlparse(target.url)
                hostname = parsed.hostname
                port = parsed.port or 443

                if hostname and target.url.startswith('https'):
                    loop = asyncio.get_event_loop()
                    expiry = await asyncio.wait_for(
                        loop.run_in_executor(
                            self.executor, 
                            get_ssl_expiry, 
                            hostname, 
                            port
                        ),
                        timeout=5.0
                    )
                    if expiry:
                        result.ssl_expiry = expiry
                        result.ssl_days_remaining = (expiry - datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)).days
            except Exception:
                pass

        return result


# =============================================================================
# DASHBOARD UI (Rich-based TUI)
# =============================================================================

class DashboardUI:
    """Renders the live-updating terminal dashboard."""

    STATUS_COLORS = {
        "UP": "green",
        "DOWN": "red",
        "ERROR": "yellow",
        "TIMEOUT": "orange3",
        "PENDING": "blue",
    }

    def __init__(self):
        self.console = Console()
        self.layout = self._create_layout()

    def _create_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3),
        )
        layout["main"].split_row(
            Layout(name="stats", size=30),
            Layout(name="table"),
        )
        return layout

    def _make_header(self, targets: List[MonitoredTarget]) -> Panel:
        total = len(targets)
        up = sum(1 for t in targets if t.last_result and t.last_result.status == "UP")
        down = total - up

        title = Text("Website Health Dashboard", style="bold cyan")
        subtitle = Text(f"  Monitoring {total} sites | ", style="dim")
        subtitle.append(f"OK {up} UP", style="green")
        subtitle.append(" | ")
        subtitle.append(f"{down} DOWN/ERROR", style="red" if down > 0 else "dim")

        return Panel(
            Align.left(title + subtitle),
            box=box.ROUNDED,
            border_style="cyan",
        )

    def _make_stats(self, targets: List[MonitoredTarget]) -> Panel:
        if not targets or not any(t.last_result for t in targets):
            return Panel("Waiting for data...", title="Statistics", box=box.ROUNDED)

        response_times = [
            t.last_result.response_time_ms 
            for t in targets 
            if t.last_result and t.last_result.response_time_ms is not None
        ]

        avg_time = sum(response_times) / len(response_times) if response_times else 0
        max_time = max(response_times) if response_times else 0

        ssl_expiring = sum(
            1 for t in targets 
            if t.last_result and t.last_result.ssl_days_remaining is not None 
            and t.last_result.ssl_days_remaining < 30
        )

        content = Text()
        content.append(f"Total Sites\n", style="bold")
        content.append(f"  {len(targets)}\n\n")
        content.append(f"Avg Response\n", style="bold")
        content.append(f"  {avg_time:.1f}ms\n\n")
        content.append(f"Max Response\n", style="bold")
        content.append(f"  {max_time:.1f}ms\n\n")
        content.append(f"SSL Warnings\n", style="bold")
        content.append(f"  {ssl_expiring} < 30 days", style="yellow" if ssl_expiring > 0 else "green")

        return Panel(content, title="Statistics", box=box.ROUNDED, border_style="blue")

    def _make_table(self, targets: List[MonitoredTarget]) -> Table:
        table = Table(
            title="Monitored Endpoints",
            box=box.ROUNDED,
            expand=True,
            row_styles=["none", "dim"],
        )

        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("URL", style="blue", overflow="fold")
        table.add_column("Status", justify="center", width=10)
        table.add_column("Code", justify="right", width=6)
        table.add_column("Response", justify="right", width=10)
        table.add_column("SSL Expiry", width=12)
        table.add_column("SSL Days", justify="right", width=8)
        table.add_column("Last Check", width=12)
        table.add_column("Error", style="red", overflow="fold")

        for target in targets:
            r = target.last_result

            if r is None:
                table.add_row(
                    target.name, target.url, "PENDING",
                    "—", "—", "—", "—", "—", "Waiting..."
                )
                continue

            status_color = self.STATUS_COLORS.get(r.status, "white")
            status_icon = "OK" if r.status == "UP" else "FAIL" if r.status == "DOWN" else "WARN"

            resp_text = f"{r.response_time_ms:.1f}ms" if r.response_time_ms else "—"
            resp_style = "green" if r.response_time_ms and r.response_time_ms < 500 else \
                        "yellow" if r.response_time_ms and r.response_time_ms < 2000 else "red"

            ssl_expiry = r.ssl_expiry.strftime("%Y-%m-%d") if r.ssl_expiry else "—"
            ssl_days = str(r.ssl_days_remaining) if r.ssl_days_remaining is not None else "—"
            ssl_style = "red" if r.ssl_days_remaining is not None and r.ssl_days_remaining < 7 else \
                       "yellow" if r.ssl_days_remaining is not None and r.ssl_days_remaining < 30 else "green"

            age = datetime.datetime.now() - r.timestamp
            age_str = f"{age.seconds}s ago" if age.days == 0 else f"{age.days}d ago"

            table.add_row(
                target.name, target.url,
                Text(f"{status_icon} {r.status}", style=status_color),
                str(r.status_code) if r.status_code else "—",
                Text(resp_text, style=resp_style),
                ssl_expiry,
                Text(ssl_days, style=ssl_style),
                age_str,
                r.error_message or "—",
            )

        return table

    def _make_footer(self, targets: List[MonitoredTarget]) -> Panel:
        checked = sum(1 for t in targets if t.last_result is not None)
        total = len(targets)

        progress_text = Text()
        progress_text.append(f"Checked {checked}/{total} sites  -  ", style="dim")
        progress_text.append("Press Ctrl+C to exit", style="italic dim")

        return Panel(
            Align.center(progress_text),
            box=box.ROUNDED,
            border_style="dim",
        )

    def update(self, targets: List[MonitoredTarget]) -> Layout:
        self.layout["header"].update(self._make_header(targets))
        self.layout["stats"].update(self._make_stats(targets))
        self.layout["table"].update(self._make_table(targets))
        self.layout["footer"].update(self._make_footer(targets))
        return self.layout


# =============================================================================
# MAIN DASHBOARD CONTROLLER
# =============================================================================

class HealthDashboard:
    """Main dashboard controller that orchestrates checks and UI updates."""

    DEFAULT_TARGETS = [
        MonitoredTarget("https://www.google.com", "Google", check_interval_seconds=10),
        MonitoredTarget("https://www.github.com", "GitHub", check_interval_seconds=10),
        MonitoredTarget("https://httpbin.org/status/200", "HTTPBin-200", check_interval_seconds=15),
        MonitoredTarget("https://httpbin.org/status/500", "HTTPBin-500", check_interval_seconds=15),
        MonitoredTarget("https://this-domain-definitely-does-not-exist-12345.com", "Fake-Domain", check_interval_seconds=20),
        MonitoredTarget("https://expired.badssl.com", "BadSSL-Expired", check_interval_seconds=30),
        MonitoredTarget("https://www.cloudflare.com", "Cloudflare", check_interval_seconds=10),
    ]

    def __init__(self, targets: Optional[List[MonitoredTarget]] = None):
        self.targets = targets or [t for t in self.DEFAULT_TARGETS]
        self.ui = DashboardUI()
        self.running = False
        self.refresh_rate = 1.0

    async def _check_loop(self, checker: HealthChecker, target: MonitoredTarget):
        while self.running:
            try:
                result = await checker.check_target(target)
                target.last_result = result
                target.history.append(result)
                if len(target.history) > 100:
                    target.history = target.history[-50:]
            except Exception as e:
                target.last_result = CheckResult(
                    url=target.url,
                    status="ERROR",
                    error_message=f"Checker exception: {str(e)}"
                )
            await asyncio.sleep(target.check_interval_seconds)

    async def _ui_loop(self, live: Live):
        while self.running:
            live.update(self.ui.update(self.targets))
            await asyncio.sleep(self.refresh_rate)

    async def run(self):
        self.running = True
        console = Console()
        console.print(f"\n[bold cyan]Starting Health Dashboard[/bold cyan]")
        console.print(f"Monitoring {len(self.targets)} targets:\n")
        for t in self.targets:
            console.print(f"  * [blue]{t.name}[/blue]: {t.url} (every {t.check_interval_seconds}s)")
        console.print("\n[dim]Starting checks...[/dim]\n")
        await asyncio.sleep(1)

        async with HealthChecker() as checker:
            with Live(
                self.ui.update(self.targets),
                console=console,
                screen=True,
                refresh_per_second=4,
            ) as live:
                check_tasks = [
                    asyncio.create_task(self._check_loop(checker, target))
                    for target in self.targets
                ]
                ui_task = asyncio.create_task(self._ui_loop(live))

                try:
                    while self.running:
                        await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    pass
                finally:
                    for task in check_tasks:
                        task.cancel()
                    ui_task.cancel()
                    await asyncio.gather(*check_tasks, ui_task, return_exceptions=True)

    def stop(self):
        self.running = False


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    import signal
    dashboard = HealthDashboard()

    def handle_signal(sig, frame):
        dashboard.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        asyncio.run(dashboard.run())
    except KeyboardInterrupt:
        pass
    finally:
        Console().print("\n[bold green]Dashboard stopped.[/bold green]")


if __name__ == "__main__":
    main()
