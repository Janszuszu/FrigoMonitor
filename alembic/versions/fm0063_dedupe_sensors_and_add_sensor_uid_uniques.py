"""dedupe sensors and add unique constraint for device_id+sensor_id

Revision ID: fm0063_dedupe_sensors_and_add_sensor_uid_uniques
Revises: fm0062_registration_idempotency
Create Date: 2026-07-05 00:00:02.000000

"""
from __future__ import annotations

from collections import defaultdict

from alembic import op
import sqlalchemy as sa


revision = "fm0063_dedupe_sensors_and_add_sensor_uid_uniques"
down_revision = "fm0062_registration_idempotency"
branch_labels = None
depends_on = None


def _has_unique_index(bind, table_name: str, expected_columns: list[str]) -> bool:
    indexes = bind.execute(sa.text("PRAGMA index_list('%s')" % table_name)).fetchall()
    for idx in indexes:
        index_name = idx[1]
        is_unique = idx[2]
        if not is_unique:
            continue
        cols = bind.execute(sa.text("PRAGMA index_info('%s')" % index_name)).fetchall()
        index_columns = [row[2] for row in cols]
        if index_columns == expected_columns:
            return True
    return False


def _sensor_identity(sensor: dict) -> tuple[str, str | None]:
    rom = sensor.get("rom")
    if rom:
        return ("rom", str(rom))
    sensor_id = sensor.get("sensor_id")
    if sensor_id:
        return ("sensor_id", str(sensor_id))
    return ("name", str(sensor.get("name") or ""))


def _pick_canonical(candidates: list[dict]) -> dict:
    # Prefer rows with ROM first, then rows that already have measurements, then oldest id.
    return sorted(
        candidates,
        key=lambda row: (
            0 if row.get("rom") else 1,
            0 if row.get("measurement_count", 0) > 0 else 1,
            row["id"],
        ),
    )[0]


def _dedupe_sensors(bind) -> None:
    sensor_rows = bind.execute(
        sa.text(
            """
            SELECT s.id, s.device_id, s.name, s.sensor_id, s.rom,
                   (SELECT COUNT(1) FROM measurements m WHERE m.sensor_id = s.id) AS measurement_count
            FROM sensors s
            ORDER BY s.id ASC
            """
        )
    ).mappings().all()

    grouped: dict[tuple[int, tuple[str, str | None]], list[dict]] = defaultdict(list)
    for row in sensor_rows:
        key = (row["device_id"], _sensor_identity(row))
        grouped[key].append(dict(row))

    for _group_key, rows in grouped.items():
        if len(rows) <= 1:
            continue

        canonical = _pick_canonical(rows)
        duplicates = [row for row in rows if row["id"] != canonical["id"]]

        for dup in duplicates:
            bind.execute(
                sa.text("UPDATE measurements SET sensor_id = :canonical_id WHERE sensor_id = :dup_id"),
                {"canonical_id": canonical["id"], "dup_id": dup["id"]},
            )
            bind.execute(
                sa.text("UPDATE alarms SET sensor_id = :canonical_id WHERE sensor_id = :dup_id"),
                {"canonical_id": canonical["id"], "dup_id": dup["id"]},
            )

            if canonical.get("rom") is None and dup.get("rom") is not None:
                bind.execute(
                    sa.text("UPDATE sensors SET rom = :rom WHERE id = :canonical_id"),
                    {"rom": dup["rom"], "canonical_id": canonical["id"]},
                )
                canonical["rom"] = dup["rom"]

            if canonical.get("sensor_id") is None and dup.get("sensor_id") is not None:
                bind.execute(
                    sa.text("UPDATE sensors SET sensor_id = :sensor_id WHERE id = :canonical_id"),
                    {"sensor_id": dup["sensor_id"], "canonical_id": canonical["id"]},
                )
                canonical["sensor_id"] = dup["sensor_id"]

            bind.execute(sa.text("DELETE FROM sensors WHERE id = :dup_id"), {"dup_id": dup["id"]})


def upgrade() -> None:
    bind = op.get_bind()

    _dedupe_sensors(bind)

    if not _has_unique_index(bind, "sensors", ["device_id", "rom"]):
        with op.batch_alter_table("sensors", schema=None) as batch_op:
            batch_op.create_unique_constraint("uq_sensor_device_rom", ["device_id", "rom"])

    if not _has_unique_index(bind, "sensors", ["device_id", "sensor_id"]):
        with op.batch_alter_table("sensors", schema=None) as batch_op:
            batch_op.create_unique_constraint("uq_sensor_device_sensor_id", ["device_id", "sensor_id"])


def downgrade() -> None:
    bind = op.get_bind()

    if _has_unique_index(bind, "sensors", ["device_id", "sensor_id"]):
        with op.batch_alter_table("sensors", schema=None) as batch_op:
            batch_op.drop_constraint("uq_sensor_device_sensor_id", type_="unique")
