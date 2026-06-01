"""
AutoParts Intelligence Platform
src/utils/config.py

Centralized configuration management using environment variables.
All settings flow through here — no hardcoded values anywhere else.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Project Root ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class DatabaseConfig:
    host: str     = os.getenv("DB_HOST", "localhost")
    port: int     = int(os.getenv("DB_PORT", 5432))
    name: str     = os.getenv("DB_NAME", "autoparts_dw")
    user: str     = os.getenv("DB_USER", "analyst")
    password: str = os.getenv("DB_PASSWORD", "")

    @property
    def url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


@dataclass(frozen=True)
class PathConfig:
    root: Path        = PROJECT_ROOT
    data_raw: Path    = PROJECT_ROOT / "data" / "raw"
    data_proc: Path   = PROJECT_ROOT / "data" / "processed"
    data_sample: Path = PROJECT_ROOT / "data" / "sample"
    models: Path      = PROJECT_ROOT / "src" / "models" / "artifacts"
    logs: Path        = PROJECT_ROOT / "logs"

    def __post_init__(self) -> None:
        # Create all directories if they don't exist
        for path_field in [self.data_raw, self.data_proc, self.data_sample,
                           self.models, self.logs]:
            path_field.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class AnalyticsConfig:
    # ABC Classification thresholds (cumulative revenue %)
    abc_a_threshold: float = 80.0
    abc_b_threshold: float = 95.0

    # XYZ Classification (Coefficient of Variation)
    xyz_x_max_cov: float = 0.50   # X: stable demand (CoV < 50%)
    xyz_y_max_cov: float = 1.00   # Y: variable demand (CoV 50–100%)
    # Z: highly irregular (CoV > 100%)

    # Safety Stock Parameters
    default_service_level_z: float = 1.645  # 95% service level
    high_value_service_level_z: float = 2.054  # 98% for A-class & critical

    # Dead Stock Thresholds (days without movement)
    dead_stock_days: int = 365
    slow_moving_days: int = 180
    watch_list_days: int = 90

    # Forecasting
    forecast_horizon_months: int = 6
    train_test_split_months: int = 3

    # Performance — chunk size for large CSV ingestion
    chunk_size: int = 50_000


@dataclass(frozen=True)
class AppConfig:
    db: DatabaseConfig     = field(default_factory=DatabaseConfig)
    paths: PathConfig      = field(default_factory=PathConfig)
    analytics: AnalyticsConfig = field(default_factory=AnalyticsConfig)
    log_level: str         = os.getenv("LOG_LEVEL", "INFO")
    environment: str       = os.getenv("ENVIRONMENT", "development")


# Singleton — import this everywhere
config = AppConfig()
