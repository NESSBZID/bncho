from __future__ import annotations

from datetime import datetime
from typing import TypedDict
from typing import cast

from sqlalchemy import CHAR
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.dialects.mysql import Insert as MysqlInsert
from sqlalchemy.dialects.mysql import insert as mysql_insert

import app.state.services
from app.repositories import DIALECT
from app.repositories import Base
from app.repositories.users import UsersTable


class ClientHashesTable(Base):
    __tablename__ = "client_hashes"

    userid = Column("userid", Integer, nullable=False, primary_key=True)
    osupath = Column("osupath", CHAR(32), nullable=False, primary_key=True)
    adapters = Column("adapters", CHAR(32), nullable=False, primary_key=True)
    uninstall_id = Column("uninstall_id", CHAR(32), nullable=False, primary_key=True)
    disk_serial = Column("disk_serial", CHAR(32), nullable=False, primary_key=True)
    latest_time = Column("latest_time", DateTime, nullable=False)
    occurrences = Column("occurrences", Integer, nullable=False, server_default="0")


READ_PARAMS = (
    ClientHashesTable.userid,
    ClientHashesTable.osupath,
    ClientHashesTable.adapters,
    ClientHashesTable.uninstall_id,
    ClientHashesTable.disk_serial,
    ClientHashesTable.latest_time,
    ClientHashesTable.occurrences,
)


class ClientHash(TypedDict):
    userid: int
    osupath: str
    adapters: str
    uninstall_id: str
    disk_serial: str
    latest_time: datetime
    occurrences: int


class ClientHashWithPlayer(ClientHash):
    name: str
    priv: int


async def create(
    userid: int,
    osupath: str,
    adapters: str,
    uninstall_id: str,
    disk_serial: str,
) -> ClientHash:
    """Create a new client hash entry in the database."""
    insert_stmt: MysqlInsert = (
        mysql_insert(ClientHashesTable)
        .values(
            userid=userid,
            osupath=osupath,
            adapters=adapters,
            uninstall_id=uninstall_id,
            disk_serial=disk_serial,
            latest_time=func.now(),
            occurrences=1,
        )
        .on_duplicate_key_update(
            latest_time=func.now(),
            occurrences=ClientHashesTable.occurrences + 1,
        )
    )

    compiled = insert_stmt.compile(dialect=DIALECT)
    await app.state.services.database.execute(str(compiled), compiled.params)

    select_stmt = (
        select(READ_PARAMS)
        .where(ClientHashesTable.userid == userid)
        .where(ClientHashesTable.osupath == osupath)
        .where(ClientHashesTable.adapters == adapters)
        .where(ClientHashesTable.uninstall_id == uninstall_id)
        .where(ClientHashesTable.disk_serial == disk_serial)
    )
    compiled = select_stmt.compile(dialect=DIALECT)
    client_hash = await app.state.services.database.fetch_one(
        str(compiled),
        compiled.params,
    )

    assert client_hash is not None
    return cast(ClientHash, dict(client_hash._mapping))


async def fetch_any_hardware_matches_for_user(
    userid: int,
    running_under_wine: bool,
    adapters: str | None = None,
    uninstall_id: str | None = None,
    disk_serial: str | None = None,
) -> list[ClientHashWithPlayer]:
    """\
    Fetch a list of matching hardware addresses where any of
    `adapters`, `uninstall_id` or `disk_serial` match other users
    from the database.
    """
    select_stmt = (
        select(*READ_PARAMS, UsersTable.name, UsersTable.priv)
        .join(UsersTable, ClientHashesTable.userid == UsersTable.id)
        .where(ClientHashesTable.userid != userid)
    )

    if running_under_wine:
        select_stmt = select_stmt.where(ClientHashesTable.uninstall_id == uninstall_id)
    else:
        select_stmt = select_stmt.where(
            or_(
                ClientHashesTable.adapters == adapters,
                ClientHashesTable.uninstall_id == uninstall_id,
                ClientHashesTable.disk_serial == disk_serial,
            ),
        )

    compiled = select_stmt.compile(dialect=DIALECT)

    client_hashes = await app.state.services.database.fetch_all(
        str(compiled),
        compiled.params,
    )
    return cast(
        list[ClientHashWithPlayer],
        [dict(client_hash._mapping) for client_hash in client_hashes],
    )
