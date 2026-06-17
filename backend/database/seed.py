"""
database/seed.py — Seeds the demo SQLite database with realistic data.

Generates:
  - sales: 2 years of daily sales records (region × product), ~17,520 rows.
  - sensor_readings: 6 months of hourly readings from 5 sensors, ~21,900 rows.

Anomalies are deliberately injected so the ML agent has something to detect.
"""

import random
import logging
import math
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import text

from database.connection import sync_engine

logger = logging.getLogger(__name__)

random.seed(42)
np.random.seed(42)

REGIONS = ["North", "South", "East", "West"]
PRODUCTS = ["Widget A", "Widget B", "Gadget X", "Gadget Y", "Tool Alpha", "Tool Beta"]
SENSORS = ["SEN-001", "SEN-002", "SEN-003", "SEN-004", "SEN-005"]


def _create_tables(conn) -> None:
    conn.execute(text("DROP TABLE IF EXISTS sales"))
    conn.execute(text("DROP TABLE IF EXISTS sensor_readings"))

    conn.execute(
        text(
            """
            CREATE TABLE sales (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT    NOT NULL,
                region      TEXT    NOT NULL,
                product     TEXT    NOT NULL,
                revenue     REAL    NOT NULL,
                units_sold  INTEGER NOT NULL,
                cost        REAL    NOT NULL,
                profit      REAL    NOT NULL
            )
            """
        )
    )

    conn.execute(
        text(
            """
            CREATE TABLE sensor_readings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                sensor_id   TEXT    NOT NULL,
                temperature REAL    NOT NULL,
                pressure    REAL    NOT NULL,
                vibration   REAL    NOT NULL,
                status      TEXT    NOT NULL
            )
            """
        )
    )
    conn.commit()


def _generate_sales() -> list[dict]:
    records: list[dict] = []
    start = datetime(2023, 1, 1)

    for day_offset in range(730):  # 2 years
        date = start + timedelta(days=day_offset)
        # Monthly seasonality (peak Q4)
        seasonal = 1.0 + 0.35 * math.sin(2 * math.pi * (date.month - 3) / 12)
        # Weekly effect (weekends slightly lower)
        weekly = 0.85 if date.weekday() >= 5 else 1.0

        for region in REGIONS:
            for product in PRODUCTS:
                base_revenue = random.uniform(4_000, 14_000)
                revenue = round(base_revenue * seasonal * weekly, 2)
                price_per_unit = random.uniform(45, 180)
                units_sold = max(1, int(revenue / price_per_unit))
                cost = round(revenue * random.uniform(0.38, 0.65), 2)
                profit = round(revenue - cost, 2)

                records.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "region": region,
                        "product": product,
                        "revenue": revenue,
                        "units_sold": units_sold,
                        "cost": cost,
                        "profit": profit,
                    }
                )

    # Inject 20 revenue anomalies (large spikes & drops)
    spike_indices = random.sample(range(len(records)), 12)
    drop_indices = random.sample(
        [i for i in range(len(records)) if i not in spike_indices], 8
    )
    for idx in spike_indices:
        multiplier = random.uniform(6.0, 12.0)
        records[idx]["revenue"] = round(records[idx]["revenue"] * multiplier, 2)
        records[idx]["units_sold"] = int(records[idx]["units_sold"] * multiplier)
        records[idx]["profit"] = round(records[idx]["revenue"] * 0.55, 2)
    for idx in drop_indices:
        records[idx]["revenue"] = round(records[idx]["revenue"] * 0.05, 2)
        records[idx]["units_sold"] = max(1, int(records[idx]["units_sold"] * 0.05))
        records[idx]["profit"] = round(records[idx]["revenue"] * 0.1, 2)

    return records


def _generate_sensor_readings() -> list[dict]:
    records: list[dict] = []
    start = datetime(2024, 1, 1)

    for hour_offset in range(180 * 24):  # 6 months, hourly
        ts = start + timedelta(hours=hour_offset)
        for sensor_id in SENSORS:
            # Normal operating ranges
            temp = round(random.gauss(72.0, 4.0), 2)
            pressure = round(random.gauss(14.7, 0.5), 2)
            vibration = round(abs(random.gauss(0.15, 0.05)), 4)
            status = "NORMAL"

            records.append(
                {
                    "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                    "sensor_id": sensor_id,
                    "temperature": temp,
                    "pressure": pressure,
                    "vibration": vibration,
                    "status": status,
                }
            )

    # Inject temperature spikes (equipment overheating events)
    spike_indices = random.sample(range(len(records)), 180)
    for idx in spike_indices:
        records[idx]["temperature"] = round(random.uniform(105.0, 145.0), 2)
        records[idx]["vibration"] = round(random.uniform(0.8, 2.5), 4)
        records[idx]["status"] = "ANOMALY"

    # Inject pressure drops (potential leak events)
    drop_indices = random.sample(
        [i for i in range(len(records)) if i not in spike_indices], 60
    )
    for idx in drop_indices:
        records[idx]["pressure"] = round(random.uniform(8.0, 10.5), 2)
        records[idx]["status"] = "WARNING"

    return records


def seed_database() -> None:
    """Create and populate tables. Safe to call multiple times (drops & recreates)."""
    logger.info("🌱 Seeding demo database...")

    with sync_engine.connect() as conn:
        _create_tables(conn)

        sales_data = _generate_sales()
        conn.execute(
            text(
                "INSERT INTO sales (date, region, product, revenue, units_sold, cost, profit) "
                "VALUES (:date, :region, :product, :revenue, :units_sold, :cost, :profit)"
            ),
            sales_data,
        )
        conn.commit()
        logger.info("  ✓ sales: %d rows inserted", len(sales_data))

        sensor_data = _generate_sensor_readings()
        conn.execute(
            text(
                "INSERT INTO sensor_readings (timestamp, sensor_id, temperature, pressure, vibration, status) "
                "VALUES (:timestamp, :sensor_id, :temperature, :pressure, :vibration, :status)"
            ),
            sensor_data,
        )
        conn.commit()
        logger.info("  ✓ sensor_readings: %d rows inserted", len(sensor_data))

    logger.info("✅ Database seeding complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_database()
