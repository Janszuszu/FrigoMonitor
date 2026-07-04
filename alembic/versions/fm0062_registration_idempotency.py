"""add idempotent registration fields and unique constraints

Revision ID: fm0062_registration_idempotency
Revises: fm0061_add_sensor_last_fields
Create Date: 2026-07-04 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fm0062_registration_idempotency"
down_revision = "fm0061_add_sensor_last_fields"
branch_labels = None
depends_on = None


def _table_columns(bind, table_name: str) -> list[str]:
    rows = bind.execute(sa.text("PRAGMA table_info('%s')" % table_name)).fetchall()
    return [row[1] for row in rows]


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


def upgrade() -> None:
    bind = op.get_bind()

    device_cols = _table_columns(bind, "devices")
    with op.batch_alter_table("devices", schema=None) as batch_op:
        if "device_id" not in device_cols:
            batch_op.add_column(sa.Column("device_id", sa.String(length=100), nullable=True))
        if "firmware" not in device_cols:
            batch_op.add_column(sa.Column("firmware", sa.String(length=50), nullable=True))
        if "build" not in device_cols:
            batch_op.add_column(sa.Column("build", sa.String(length=50), nullable=True))
        if "board" not in device_cols:
            batch_op.add_column(sa.Column("board", sa.String(length=100), nullable=True))
        if "chip_id" not in device_cols:
            batch_op.add_column(sa.Column("chip_id", sa.String(length=100), nullable=True))
        if "mac" not in device_cols:
            batch_op.add_column(sa.Column("mac", sa.String(length=50), nullable=True))
        if "ip" not in device_cols:
            batch_op.add_column(sa.Column("ip", sa.String(length=64), nullable=True))

    if not _has_unique_index(bind, "devices", ["device_id"]):
        with op.batch_alter_table("devices", schema=None) as batch_op:
            batch_op.create_unique_constraint("uq_devices_device_id", ["device_id"])

    sensor_cols = _table_columns(bind, "sensors")
    with op.batch_alter_table("sensors", schema=None) as batch_op:
        if "sensor_id" not in sensor_cols:
            batch_op.add_column(sa.Column("sensor_id", sa.String(length=120), nullable=True))
        if "rom" not in sensor_cols:
            batch_op.add_column(sa.Column("rom", sa.String(length=100), nullable=True))
        if "unit" not in sensor_cols:
            batch_op.add_column(sa.Column("unit", sa.String(length=20), nullable=True))
        if "last_seen" not in sensor_cols:
            batch_op.add_column(sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True))

    if not _has_unique_index(bind, "sensors", ["device_id", "rom"]):
        with op.batch_alter_table("sensors", schema=None) as batch_op:
            batch_op.create_unique_constraint("uq_sensor_device_rom", ["device_id", "rom"])


def downgrade() -> None:
    bind = op.get_bind()

    if _has_unique_index(bind, "sensors", ["device_id", "rom"]):
        with op.batch_alter_table("sensors", schema=None) as batch_op:
            batch_op.drop_constraint("uq_sensor_device_rom", type_="unique")

    sensor_cols = _table_columns(bind, "sensors")
    with op.batch_alter_table("sensors", schema=None) as batch_op:
        if "last_seen" in sensor_cols:
            batch_op.drop_column("last_seen")
        if "unit" in sensor_cols:
            batch_op.drop_column("unit")
        if "rom" in sensor_cols:
            batch_op.drop_column("rom")
        if "sensor_id" in sensor_cols:
            batch_op.drop_column("sensor_id")

    if _has_unique_index(bind, "devices", ["device_id"]):
        with op.batch_alter_table("devices", schema=None) as batch_op:
            batch_op.drop_constraint("uq_devices_device_id", type_="unique")

    device_cols = _table_columns(bind, "devices")
    with op.batch_alter_table("devices", schema=None) as batch_op:
        if "ip" in device_cols:
            batch_op.drop_column("ip")
        if "mac" in device_cols:
            batch_op.drop_column("mac")
        if "chip_id" in device_cols:
            batch_op.drop_column("chip_id")
        if "board" in device_cols:
            batch_op.drop_column("board")
        if "build" in device_cols:
            batch_op.drop_column("build")
        if "firmware" in device_cols:
            batch_op.drop_column("firmware")
        if "device_id" in device_cols:
            batch_op.drop_column("device_id")
