# ui_qt/windows/dashboard_window_qt/repositories/stats_repository.py
"""
Statistics Repository - Quản lý thống kê và phân tích sử dụng Dashboard
Bao gồm: Usage tracking, Activity logs, Performance metrics, Analytics reports
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict, Counter
import logging

# Setup logger
logger = logging.getLogger(__name__)


# ========== ENUMS & CONSTANTS ==========

class EventType(Enum):
    """Loại sự kiện tracking"""
    APP_LAUNCH = "app_launch"
    APP_CLOSE = "app_close"
    APP_CRASH = "app_crash"
    LOGIN = "login"
    LOGOUT = "logout"
    WINDOW_OPEN = "window_open"
    WINDOW_CLOSE = "window_close"
    CLICK = "click"
    SEARCH = "search"
    FILE_OPEN = "file_open"
    FILE_SAVE = "file_save"
    SETTINGS_CHANGE = "settings_change"
    ERROR = "error"
    CUSTOM = "custom"


class MetricType(Enum):
    """Loại metric thống kê"""
    COUNT = "count"
    DURATION = "duration"
    FREQUENCY = "frequency"
    AVERAGE = "average"
    MAX = "max"
    MIN = "min"
    SUM = "sum"


class TimeRange(Enum):
    """Khoảng thời gian thống kê"""
    TODAY = "today"
    YESTERDAY = "yesterday"
    THIS_WEEK = "this_week"
    LAST_WEEK = "last_week"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    THIS_YEAR = "this_year"
    LAST_YEAR = "last_year"
    ALL_TIME = "all_time"
    CUSTOM = "custom"


# ========== DATA MODELS ==========

@dataclass
class ActivityLog:
    """Model cho activity log"""
    id: Optional[int] = None
    event_type: str = ""
    event_name: str = ""
    event_data: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    duration: Optional[int] = None  # in seconds
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['event_data'] = json.dumps(self.event_data)
        data['metadata'] = json.dumps(self.metadata)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActivityLog':
        """Create from dictionary"""
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if isinstance(data.get('event_data'), str):
            data['event_data'] = json.loads(data['event_data'])
        if isinstance(data.get('metadata'), str):
            data['metadata'] = json.loads(data['metadata'])
        return cls(**data)


@dataclass
class SessionInfo:
    """Model cho session information"""
    session_id: str
    user_id: Optional[str] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration: int = 0  # in seconds
    events_count: int = 0
    apps_used: List[str] = field(default_factory=list)
    active_time: int = 0  # in seconds
    idle_time: int = 0  # in seconds


@dataclass
class AppUsageStats:
    """Model cho app usage statistics"""
    app_id: str
    app_name: str
    launch_count: int = 0
    total_time: int = 0  # in seconds
    average_time: int = 0  # in seconds
    last_used: Optional[datetime] = None
    crash_count: int = 0
    error_count: int = 0
    daily_usage: Dict[str, int] = field(default_factory=dict)  # date -> seconds
    peak_hour: Optional[int] = None  # 0-23


@dataclass
class PerformanceMetric:
    """Model cho performance metrics"""
    metric_name: str
    metric_type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ========== REPOSITORY CLASS ==========

class StatsRepository:
    """
    Repository để quản lý statistics và analytics
    Sử dụng SQLite để lưu trữ logs và metrics
    """

    def __init__(self, db_path: str = None):
        """
        Initialize repository

        Args:
            db_path: Đường dẫn database file
        """
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path("dashboard_stats.db")

        # Current session
        self.current_session: Optional[SessionInfo] = None
        self.session_start_time = datetime.now()

        # Cache
        self._cache: Dict[str, Any] = {}
        self._cache_timeout = 300  # 5 minutes
        self._last_cache_update = datetime.now()

        # Initialize database
        self._init_database()

        # Start new session
        self.start_session()

    def _init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Activity logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                event_name TEXT NOT NULL,
                event_data TEXT,
                user_id TEXT,
                session_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                duration INTEGER,
                metadata TEXT
            )
        """)

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                duration INTEGER DEFAULT 0,
                events_count INTEGER DEFAULT 0,
                apps_used TEXT,
                active_time INTEGER DEFAULT 0,
                idle_time INTEGER DEFAULT 0
            )
        """)

        # App usage table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_id TEXT NOT NULL,
                app_name TEXT NOT NULL,
                session_id TEXT,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                duration INTEGER DEFAULT 0,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id)
            )
        """)

        # Performance metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON activity_logs(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_event_type ON activity_logs(event_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_session ON activity_logs(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_app ON app_usage(app_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_name ON performance_metrics(metric_name)")

        conn.commit()
        conn.close()

        logger.info("Statistics database initialized")

    # ========== SESSION MANAGEMENT ==========

    def start_session(self, user_id: Optional[str] = None) -> str:
        """
        Start new session

        Args:
            user_id: User ID

        Returns:
            Session ID
        """
        import uuid

        session_id = str(uuid.uuid4())
        self.current_session = SessionInfo(
            session_id=session_id,
            user_id=user_id,
            start_time=datetime.now()
        )

        # Save to database
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sessions (session_id, user_id, start_time)
            VALUES (?, ?, ?)
        """, (session_id, user_id, datetime.now()))

        conn.commit()
        conn.close()

        # Log session start
        self.log_event(EventType.LOGIN, "session_start", {"session_id": session_id})

        logger.info(f"Session started: {session_id}")
        return session_id

    def end_session(self):
        """End current session"""
        if not self.current_session:
            return

        end_time = datetime.now()
        duration = int((end_time - self.current_session.start_time).total_seconds())

        # Update database
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE sessions
            SET end_time = ?, duration = ?, events_count = ?, 
                apps_used = ?, active_time = ?, idle_time = ?
            WHERE session_id = ?
        """, (
            end_time,
            duration,
            self.current_session.events_count,
            json.dumps(self.current_session.apps_used),
            self.current_session.active_time,
            self.current_session.idle_time,
            self.current_session.session_id
        ))

        conn.commit()
        conn.close()

        # Log session end
        self.log_event(EventType.LOGOUT, "session_end", {"duration": duration})

        logger.info(f"Session ended: {self.current_session.session_id}")
        self.current_session = None

    def get_current_session(self) -> Optional[SessionInfo]:
        """Get current session info"""
        return self.current_session

    # ========== ACTIVITY LOGGING ==========

    def log_event(self, event_type: EventType, event_name: str,
                  event_data: Optional[Dict[str, Any]] = None,
                  duration: Optional[int] = None) -> int:
        """
        Log an activity event

        Args:
            event_type: Type of event
            event_name: Event name
            event_data: Additional event data
            duration: Event duration in seconds

        Returns:
            Log ID
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        log = ActivityLog(
            event_type=event_type.value if isinstance(event_type, EventType) else event_type,
            event_name=event_name,
            event_data=event_data or {},
            user_id=self.current_session.user_id if self.current_session else None,
            session_id=self.current_session.session_id if self.current_session else None,
            timestamp=datetime.now(),
            duration=duration
        )

        cursor.execute("""
            INSERT INTO activity_logs 
            (event_type, event_name, event_data, user_id, session_id, timestamp, duration, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log.event_type,
            log.event_name,
            json.dumps(log.event_data),
            log.user_id,
            log.session_id,
            log.timestamp,
            log.duration,
            json.dumps(log.metadata)
        ))

        log_id = cursor.lastrowid

        # Update session event count
        if self.current_session:
            self.current_session.events_count += 1

        conn.commit()
        conn.close()

        # Clear cache
        self._clear_cache()

        return log_id

    def log_app_usage(self, app_id: str, app_name: str,
                      start_time: datetime, end_time: datetime):
        """
        Log app usage

        Args:
            app_id: App ID
            app_name: App name
            start_time: Start time
            end_time: End time
        """
        duration = int((end_time - start_time).total_seconds())

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO app_usage 
            (app_id, app_name, session_id, start_time, end_time, duration)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            app_id,
            app_name,
            self.current_session.session_id if self.current_session else None,
            start_time,
            end_time,
            duration
        ))

        # Update session apps
        if self.current_session and app_id not in self.current_session.apps_used:
            self.current_session.apps_used.append(app_id)

        conn.commit()
        conn.close()

        # Log event
        self.log_event(
            EventType.APP_CLOSE,
            f"app_usage_{app_id}",
            {"app_name": app_name},
            duration
        )

    def log_performance_metric(self, metric_name: str, metric_type: MetricType,
                               value: float, metadata: Optional[Dict[str, Any]] = None):
        """
        Log performance metric

        Args:
            metric_name: Metric name
            metric_type: Metric type
            value: Metric value
            metadata: Additional metadata
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO performance_metrics 
            (metric_name, metric_type, value, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (
            metric_name,
            metric_type.value if isinstance(metric_type, MetricType) else metric_type,
            value,
            datetime.now(),
            json.dumps(metadata or {})
        ))

        conn.commit()
        conn.close()

    # ========== QUERY METHODS ==========

    def get_activity_logs(self, time_range: TimeRange = TimeRange.TODAY,
                          event_type: Optional[EventType] = None,
                          limit: int = 100) -> List[ActivityLog]:
        """
        Get activity logs

        Args:
            time_range: Time range
            event_type: Filter by event type
            limit: Maximum number of logs

        Returns:
            List of ActivityLog
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Build query
        query = "SELECT * FROM activity_logs WHERE 1=1"
        params = []

        # Time range filter
        start_date, end_date = self._get_date_range(time_range)
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        # Event type filter
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.value if isinstance(event_type, EventType) else event_type)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Convert to ActivityLog objects
        logs = []
        for row in rows:
            log_dict = {
                'id': row[0],
                'event_type': row[1],
                'event_name': row[2],
                'event_data': json.loads(row[3]) if row[3] else {},
                'user_id': row[4],
                'session_id': row[5],
                'timestamp': datetime.fromisoformat(row[6]) if isinstance(row[6], str) else row[6],
                'duration': row[7],
                'metadata': json.loads(row[8]) if row[8] else {}
            }
            logs.append(ActivityLog.from_dict(log_dict))

        conn.close()
        return logs

    def get_app_usage_stats(self, time_range: TimeRange = TimeRange.THIS_WEEK) -> List[AppUsageStats]:
        """
        Get app usage statistics

        Args:
            time_range: Time range

        Returns:
            List of AppUsageStats
        """
        # Check cache
        cache_key = f"app_usage_{time_range.value}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        start_date, end_date = self._get_date_range(time_range)

        # Get app usage data
        query = """
            SELECT 
                app_id,
                app_name,
                COUNT(*) as launch_count,
                SUM(duration) as total_time,
                AVG(duration) as average_time,
                MAX(end_time) as last_used
            FROM app_usage
            WHERE 1=1
        """

        params = []
        if start_date:
            query += " AND start_time >= ?"
            params.append(start_date)
        if end_date:
            query += " AND end_time <= ?"
            params.append(end_date)

        query += " GROUP BY app_id, app_name"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        stats = []
        for row in rows:
            stat = AppUsageStats(
                app_id=row[0],
                app_name=row[1],
                launch_count=row[2],
                total_time=row[3] or 0,
                average_time=row[4] or 0,
                last_used=datetime.fromisoformat(row[5]) if row[5] else None
            )

            # Get daily usage
            cursor.execute("""
                SELECT DATE(start_time) as date, SUM(duration) as daily_time
                FROM app_usage
                WHERE app_id = ? AND start_time >= ? AND end_time <= ?
                GROUP BY DATE(start_time)
            """, (stat.app_id, start_date, end_date))

            daily_rows = cursor.fetchall()
            for daily_row in daily_rows:
                stat.daily_usage[daily_row[0]] = daily_row[1]

            # Get crash/error counts
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN event_type = 'app_crash' THEN 1 ELSE 0 END) as crash_count,
                    SUM(CASE WHEN event_type = 'error' THEN 1 ELSE 0 END) as error_count
                FROM activity_logs
                WHERE event_data LIKE ? AND timestamp >= ? AND timestamp <= ?
            """, (f'%"{stat.app_id}"%', start_date, end_date))

            error_row = cursor.fetchone()
            if error_row:
                stat.crash_count = error_row[0] or 0
                stat.error_count = error_row[1] or 0

            stats.append(stat)

        conn.close()

        # Sort by total time
        stats.sort(key=lambda x: x.total_time, reverse=True)

        # Update cache
        self._cache[cache_key] = stats

        return stats

    def get_most_used_apps(self, limit: int = 10,
                           time_range: TimeRange = TimeRange.THIS_MONTH) -> List[Tuple[str, int]]:
        """
        Get most used apps

        Args:
            limit: Number of apps to return
            time_range: Time range

        Returns:
            List of (app_name, usage_count) tuples
        """
        stats = self.get_app_usage_stats(time_range)

        # Sort by launch count
        sorted_stats = sorted(stats, key=lambda x: x.launch_count, reverse=True)

        return [(s.app_name, s.launch_count) for s in sorted_stats[:limit]]

    def get_usage_by_hour(self, time_range: TimeRange = TimeRange.THIS_WEEK) -> Dict[int, int]:
        """
        Get usage by hour of day

        Args:
            time_range: Time range

        Returns:
            Dictionary of hour (0-23) -> event count
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        start_date, end_date = self._get_date_range(time_range)

        query = """
            SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
            FROM activity_logs
            WHERE timestamp >= ? AND timestamp <= ?
            GROUP BY hour
        """

        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        conn.close()

        # Convert to dictionary
        usage_by_hour = {i: 0 for i in range(24)}
        for row in rows:
            hour = int(row[0])
            count = row[1]
            usage_by_hour[hour] = count

        return usage_by_hour

    def get_usage_by_day(self, time_range: TimeRange = TimeRange.THIS_MONTH) -> Dict[str, int]:
        """
        Get usage by day

        Args:
            time_range: Time range

        Returns:
            Dictionary of date string -> event count
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        start_date, end_date = self._get_date_range(time_range)

        query = """
            SELECT DATE(timestamp) as date, COUNT(*) as count
            FROM activity_logs
            WHERE timestamp >= ? AND timestamp <= ?
            GROUP BY date
            ORDER BY date
        """

        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        conn.close()

        return {row[0]: row[1] for row in rows}

    def get_session_stats(self, session_id: Optional[str] = None) -> Optional[SessionInfo]:
        """
        Get session statistics

        Args:
            session_id: Session ID (None for current)

        Returns:
            SessionInfo or None
        """
        if not session_id and self.current_session:
            return self.current_session

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM sessions WHERE session_id = ?
        """, (session_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return SessionInfo(
            session_id=row[0],
            user_id=row[1],
            start_time=datetime.fromisoformat(row[2]) if isinstance(row[2], str) else row[2],
            end_time=datetime.fromisoformat(row[3]) if row[3] else None,
            duration=row[4] or 0,
            events_count=row[5] or 0,
            apps_used=json.loads(row[6]) if row[6] else [],
            active_time=row[7] or 0,
            idle_time=row[8] or 0
        )

    def get_performance_metrics(self, metric_name: Optional[str] = None,
                                time_range: TimeRange = TimeRange.TODAY) -> List[PerformanceMetric]:
        """
        Get performance metrics

        Args:
            metric_name: Filter by metric name
            time_range: Time range

        Returns:
            List of PerformanceMetric
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        start_date, end_date = self._get_date_range(time_range)

        query = "SELECT * FROM performance_metrics WHERE timestamp >= ? AND timestamp <= ?"
        params = [start_date, end_date]

        if metric_name:
            query += " AND metric_name = ?"
            params.append(metric_name)

        query += " ORDER BY timestamp DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        conn.close()

        metrics = []
        for row in rows:
            metric = PerformanceMetric(
                metric_name=row[1],
                metric_type=MetricType(row[2]),
                value=row[3],
                timestamp=datetime.fromisoformat(row[4]) if isinstance(row[4], str) else row[4],
                metadata=json.loads(row[5]) if row[5] else {}
            )
            metrics.append(metric)

        return metrics

    # ========== ANALYTICS METHODS ==========

    def get_summary_stats(self, time_range: TimeRange = TimeRange.TODAY) -> Dict[str, Any]:
        """
        Get summary statistics

        Args:
            time_range: Time range

        Returns:
            Dictionary of summary stats
        """
        start_date, end_date = self._get_date_range(time_range)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Total events
        cursor.execute("""
            SELECT COUNT(*) FROM activity_logs
            WHERE timestamp >= ? AND timestamp <= ?
        """, (start_date, end_date))
        total_events = cursor.fetchone()[0]

        # Total sessions
        cursor.execute("""
            SELECT COUNT(*) FROM sessions
            WHERE start_time >= ? AND start_time <= ?
        """, (start_date, end_date))
        total_sessions = cursor.fetchone()[0]

        # Total app launches
        cursor.execute("""
            SELECT COUNT(*) FROM app_usage
            WHERE start_time >= ? AND start_time <= ?
        """, (start_date, end_date))
        total_app_launches = cursor.fetchone()[0]

        # Total usage time
        cursor.execute("""
            SELECT SUM(duration) FROM app_usage
            WHERE start_time >= ? AND start_time <= ?
        """, (start_date, end_date))
        total_usage_time = cursor.fetchone()[0] or 0

        # Average session duration
        cursor.execute("""
            SELECT AVG(duration) FROM sessions
            WHERE start_time >= ? AND start_time <= ?
        """, (start_date, end_date))
        avg_session_duration = cursor.fetchone()[0] or 0

        # Most active hour
        cursor.execute("""
            SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
            FROM activity_logs
            WHERE timestamp >= ? AND timestamp <= ?
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 1
        """, (start_date, end_date))
        most_active_hour_row = cursor.fetchone()
        most_active_hour = int(most_active_hour_row[0]) if most_active_hour_row else None

        conn.close()

        # Get app usage stats
        app_stats = self.get_app_usage_stats(time_range)

        return {
            'time_range': time_range.value,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None,
            'total_events': total_events,
            'total_sessions': total_sessions,
            'total_app_launches': total_app_launches,
            'total_usage_time': total_usage_time,
            'average_session_duration': int(avg_session_duration),
            'most_active_hour': most_active_hour,
            'unique_apps_used': len(app_stats),
            'most_used_app': app_stats[0].app_name if app_stats else None
        }

    def get_trend_data(self, metric: str, time_range: TimeRange = TimeRange.THIS_MONTH) -> List[Tuple[str, float]]:
        """
        Get trend data for a metric

        Args:
            metric: Metric name (events, usage_time, app_launches)
            time_range: Time range

        Returns:
            List of (date, value) tuples
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        start_date, end_date = self._get_date_range(time_range)

        if metric == "events":
            query = """
                SELECT DATE(timestamp) as date, COUNT(*) as value
                FROM activity_logs
                WHERE timestamp >= ? AND timestamp <= ?
                GROUP BY date
                ORDER BY date
            """
        elif metric == "usage_time":
            query = """
                SELECT DATE(start_time) as date, SUM(duration) as value
                FROM app_usage
                WHERE start_time >= ? AND start_time <= ?
                GROUP BY date
                ORDER BY date
            """
        elif metric == "app_launches":
            query = """
                SELECT DATE(start_time) as date, COUNT(*) as value
                FROM app_usage
                WHERE start_time >= ? AND start_time <= ?
                GROUP BY date
                ORDER BY date
            """
        else:
            conn.close()
            return []

        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        conn.close()

        return [(row[0], row[1]) for row in rows]

    def get_search_stats(self, time_range: TimeRange = TimeRange.THIS_WEEK) -> Dict[str, Any]:
        """
        Get search statistics

        Args:
            time_range: Time range

        Returns:
            Dictionary of search stats
        """
        logs = self.get_activity_logs(time_range, EventType.SEARCH)

        # Extract search queries
        queries = []
        for log in logs:
            if 'query' in log.event_data:
                queries.append(log.event_data['query'])

        # Count queries
        query_counter = Counter(queries)

        return {
            'total_searches': len(logs),
            'unique_queries': len(set(queries)),
            'top_queries': query_counter.most_common(10),
            'average_searches_per_day': len(logs) / 7 if time_range == TimeRange.THIS_WEEK else len(logs)
        }

    # ========== CLEANUP METHODS ==========

    def clear_old_logs(self, days: int = 90):
        """
        Clear logs older than specified days

        Args:
            days: Number of days to keep
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Delete old activity logs
        cursor.execute("""
            DELETE FROM activity_logs WHERE timestamp < ?
        """, (cutoff_date,))

        deleted_logs = cursor.rowcount

        # Delete old sessions
        cursor.execute("""
            DELETE FROM sessions WHERE start_time < ?
        """, (cutoff_date,))

        deleted_sessions = cursor.rowcount

        # Delete old app usage
        cursor.execute("""
            DELETE FROM app_usage WHERE start_time < ?
        """, (cutoff_date,))

        deleted_usage = cursor.rowcount

        # Delete old metrics
        cursor.execute("""
            DELETE FROM performance_metrics WHERE timestamp < ?
        """, (cutoff_date,))

        deleted_metrics = cursor.rowcount

        # Vacuum database
        cursor.execute("VACUUM")

        conn.commit()
        conn.close()

        logger.info(f"Cleaned up old data: {deleted_logs} logs, {deleted_sessions} sessions, "
                    f"{deleted_usage} usage records, {deleted_metrics} metrics")

        return {
            'deleted_logs': deleted_logs,
            'deleted_sessions': deleted_sessions,
            'deleted_usage': deleted_usage,
            'deleted_metrics': deleted_metrics
        }

    def optimize_database(self):
        """Optimize database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Analyze tables
        cursor.execute("ANALYZE")

        # Rebuild indexes
        cursor.execute("REINDEX")

        # Vacuum
        cursor.execute("VACUUM")

        conn.commit()
        conn.close()

        logger.info("Database optimized")

    # ========== EXPORT METHODS ==========

    def export_to_json(self, file_path: str, time_range: TimeRange = TimeRange.ALL_TIME) -> bool:
        """
        Export statistics to JSON file

        Args:
            file_path: Output file path
            time_range: Time range to export

        Returns:
            True if successful
        """
        try:
            data = {
                'export_date': datetime.now().isoformat(),
                'time_range': time_range.value,
                'summary': self.get_summary_stats(time_range),
                'app_usage': [asdict(stat) for stat in self.get_app_usage_stats(time_range)],
                'activity_logs': [log.to_dict() for log in self.get_activity_logs(time_range, limit=1000)],
                'usage_by_hour': self.get_usage_by_hour(time_range),
                'usage_by_day': self.get_usage_by_day(time_range)
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)

            logger.info(f"Statistics exported to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting statistics: {e}")
            return False

    def export_to_csv(self, file_path: str, data_type: str = "app_usage",
                      time_range: TimeRange = TimeRange.THIS_MONTH) -> bool:
        """
        Export statistics to CSV file

        Args:
            file_path: Output file path
            data_type: Type of data to export (app_usage, activity_logs)
            time_range: Time range to export

        Returns:
            True if successful
        """
        import csv

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                if data_type == "app_usage":
                    stats = self.get_app_usage_stats(time_range)

                    writer = csv.writer(f)
                    writer.writerow(['App ID', 'App Name', 'Launch Count', 'Total Time (s)',
                                     'Average Time (s)', 'Last Used', 'Crash Count', 'Error Count'])

                    for stat in stats:
                        writer.writerow([
                            stat.app_id,
                            stat.app_name,
                            stat.launch_count,
                            stat.total_time,
                            stat.average_time,
                            stat.last_used.isoformat() if stat.last_used else '',
                            stat.crash_count,
                            stat.error_count
                        ])

                elif data_type == "activity_logs":
                    logs = self.get_activity_logs(time_range, limit=10000)

                    writer = csv.writer(f)
                    writer.writerow(['Timestamp', 'Event Type', 'Event Name', 'Duration (s)',
                                     'Session ID', 'User ID'])

                    for log in logs:
                        writer.writerow([
                            log.timestamp.isoformat(),
                            log.event_type,
                            log.event_name,
                            log.duration or '',
                            log.session_id or '',
                            log.user_id or ''
                        ])

            logger.info(f"Statistics exported to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return False

    # ========== HELPER METHODS ==========

    def _get_date_range(self, time_range: TimeRange) -> Tuple[datetime, datetime]:
        """
        Get date range for time range enum

        Args:
            time_range: Time range enum

        Returns:
            Tuple of (start_date, end_date)
        """
        now = datetime.now()
        today_start = datetime.combine(now.date(), datetime.min.time())

        if time_range == TimeRange.TODAY:
            return today_start, now

        elif time_range == TimeRange.YESTERDAY:
            yesterday = today_start - timedelta(days=1)
            return yesterday, today_start

        elif time_range == TimeRange.THIS_WEEK:
            week_start = today_start - timedelta(days=today_start.weekday())
            return week_start, now

        elif time_range == TimeRange.LAST_WEEK:
            week_start = today_start - timedelta(days=today_start.weekday() + 7)
            week_end = week_start + timedelta(days=7)
            return week_start, week_end

        elif time_range == TimeRange.THIS_MONTH:
            month_start = datetime(now.year, now.month, 1)
            return month_start, now

        elif time_range == TimeRange.LAST_MONTH:
            if now.month == 1:
                month_start = datetime(now.year - 1, 12, 1)
                month_end = datetime(now.year, 1, 1)
            else:
                month_start = datetime(now.year, now.month - 1, 1)
                month_end = datetime(now.year, now.month, 1)
            return month_start, month_end

        elif time_range == TimeRange.THIS_YEAR:
            year_start = datetime(now.year, 1, 1)
            return year_start, now

        elif time_range == TimeRange.LAST_YEAR:
            year_start = datetime(now.year - 1, 1, 1)
            year_end = datetime(now.year, 1, 1)
            return year_start, year_end

        else:  # ALL_TIME
            return datetime.min, now

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache is valid"""
        if key not in self._cache:
            return False

        cache_age = (datetime.now() - self._last_cache_update).total_seconds()
        return cache_age < self._cache_timeout

    def _clear_cache(self):
        """Clear cache"""
        self._cache.clear()
        self._last_cache_update = datetime.now()


# ========== SINGLETON INSTANCE ==========

_stats_repository_instance: Optional[StatsRepository] = None


def get_stats_repository() -> StatsRepository:
    """Get or create singleton StatsRepository instance"""
    global _stats_repository_instance
    if _stats_repository_instance is None:
        _stats_repository_instance = StatsRepository()
    return _stats_repository_instance


# ========== EXAMPLE USAGE ==========

if __name__ == "__main__":
    # Create repository
    repo = StatsRepository("test_stats.db")

    # Start session
    session_id = repo.start_session("user123")
    print(f"Session started: {session_id}")

    # Log some events
    repo.log_event(EventType.APP_LAUNCH, "question_bank", {"version": "1.0"})
    repo.log_event(EventType.CLICK, "button_save", {"screen": "main"})
    repo.log_event(EventType.SEARCH, "search_performed", {"query": "toán lớp 10"})

    # Log app usage
    start = datetime.now()
    end = start + timedelta(minutes=30)
    repo.log_app_usage("question_bank", "Ngân hàng câu hỏi", start, end)

    # Log performance metric
    repo.log_performance_metric("cpu_usage", MetricType.AVERAGE, 45.5)
    repo.log_performance_metric("memory_usage", MetricType.MAX, 512.0)

    # Get statistics
    summary = repo.get_summary_stats(TimeRange.TODAY)
    print("\nSummary Stats:")
    for key, value in summary.items():
        print(f"  {key}: {value}")

    # Get app usage
    app_stats = repo.get_app_usage_stats(TimeRange.THIS_WEEK)
    print("\nApp Usage Stats:")
    for stat in app_stats:
        print(f"  {stat.app_name}: {stat.launch_count} launches, {stat.total_time}s total")

    # Get most used apps
    most_used = repo.get_most_used_apps(5)
    print("\nMost Used Apps:")
    for app_name, count in most_used:
        print(f"  {app_name}: {count} launches")

    # Get usage by hour
    hourly = repo.get_usage_by_hour(TimeRange.TODAY)
    print("\nUsage by Hour:")
    for hour, count in hourly.items():
        if count > 0:
            print(f"  {hour:02d}:00 - {count} events")

    # Export to JSON
    repo.export_to_json("stats_export.json", TimeRange.TODAY)

    # End session
    repo.end_session()
    print("\nSession ended")