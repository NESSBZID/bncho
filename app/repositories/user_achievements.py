from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import insert
from sqlalchemy import select

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories import DIALECT
from app.repositories import Base


class UserAchievementsTable(Base):
    __tablename__ = "user_achievements"

    userid = Column("userid", Integer, nullable=False, primary_key=True)
    achid = Column("achid", Integer, nullable=False, primary_key=True)

    __table_args__ = (
        Index("user_achievements_achid_index", achid),
        Index("user_achievements_userid_index", userid),
    )


READ_PARAMS = (
    UserAchievementsTable.userid,
    UserAchievementsTable.achid,
)


class UserAchievement(TypedDict):
    userid: int
    achid: int


async def create(user_id: int, achievement_id: int) -> UserAchievement:
    """Creates a new user achievement entry."""
    insert_stmt = insert(UserAchievementsTable).values(
        userid=user_id,
        achid=achievement_id,
    )
    compiled = insert_stmt.compile(dialect=DIALECT)
    await app.state.services.database.execute(str(compiled), compiled.params)

    select_stmt = (
        select(READ_PARAMS)
        .where(UserAchievementsTable.userid == user_id)
        .where(UserAchievementsTable.achid == achievement_id)
    )
    compiled = select_stmt.compile(dialect=DIALECT)
    user_achievement = await app.state.services.database.fetch_one(
        str(compiled),
        compiled.params,
    )
    assert user_achievement is not None
    return cast(UserAchievement, dict(user_achievement._mapping))


async def fetch_many(
    user_id: int | _UnsetSentinel = UNSET,
    achievement_id: int | _UnsetSentinel = UNSET,
    page: int | None = None,
    page_size: int | None = None,
) -> list[UserAchievement]:
    """Fetch a list of user achievements."""
    select_stmt = select(READ_PARAMS)
    if not isinstance(user_id, _UnsetSentinel):
        select_stmt = select_stmt.where(UserAchievementsTable.userid == user_id)
    if not isinstance(achievement_id, _UnsetSentinel):
        select_stmt = select_stmt.where(UserAchievementsTable.achid == achievement_id)
    if page and page_size:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    compiled = select_stmt.compile(dialect=DIALECT)
    user_achievements = await app.state.services.database.fetch_all(
        str(compiled),
        compiled.params,
    )
    return cast(list[UserAchievement], [dict(a._mapping) for a in user_achievements])


# TODO: delete?
