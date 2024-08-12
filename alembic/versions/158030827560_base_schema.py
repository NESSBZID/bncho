"""base schema

Revision ID: 158030827560
Revises:
Create Date: 2024-02-26 07:51:27.560677

"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "158030827560"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file", sa.String(length=128), nullable=False),
        sa.Column(
            "name",
            mysql.VARCHAR(
                charset="utf8mb3",
                collation="utf8mb3_general_ci",
                length=128,
            ),
            nullable=False,
        ),
        sa.Column(
            "desc",
            mysql.VARCHAR(
                charset="utf8mb3",
                collation="utf8mb3_general_ci",
                length=256,
            ),
            nullable=False,
        ),
        sa.Column("cond", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("achievements_desc_uindex", "achievements", ["desc"], unique=True)
    op.create_index("achievements_file_uindex", "achievements", ["file"], unique=True)
    op.create_index("achievements_name_uindex", "achievements", ["name"], unique=True)
    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("topic", sa.String(length=256), nullable=False),
        sa.Column("read_priv", sa.Integer(), server_default="1", nullable=False),
        sa.Column("write_priv", sa.Integer(), server_default="2", nullable=False),
        sa.Column(
            "auto_join",
            mysql.TINYINT(display_width=1),
            server_default="0",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("channels_auto_join_index", "channels", ["auto_join"], unique=False)
    op.create_index("channels_name_uindex", "channels", ["name"], unique=True)
    op.create_table(
        "clans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "name",
            mysql.VARCHAR(charset="utf8mb3", collation="utf8mb3_general_ci", length=16),
            nullable=False,
        ),
        sa.Column(
            "tag",
            mysql.VARCHAR(charset="utf8mb3", collation="utf8mb3_general_ci", length=6),
            nullable=False,
        ),
        sa.Column("owner", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("clans_name_uindex", "clans", ["name"], unique=True)
    op.create_index("clans_owner_uindex", "clans", ["owner"], unique=True)
    op.create_index("clans_tag_uindex", "clans", ["tag"], unique=True)
    op.create_table(
        "client_hashes",
        sa.Column("userid", sa.Integer(), nullable=False),
        sa.Column("osupath", sa.CHAR(length=32), nullable=False),
        sa.Column("adapters", sa.CHAR(length=32), nullable=False),
        sa.Column("uninstall_id", sa.CHAR(length=32), nullable=False),
        sa.Column("disk_serial", sa.CHAR(length=32), nullable=False),
        sa.Column("latest_time", sa.DateTime(), nullable=False),
        sa.Column("occurrences", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint(
            "userid",
            "osupath",
            "adapters",
            "uninstall_id",
            "disk_serial",
        ),
    )
    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("target_type", mysql.ENUM("replay", "map", "song"), nullable=False),
        sa.Column("userid", sa.Integer(), nullable=False),
        sa.Column("time", sa.Integer(), nullable=False),
        sa.Column(
            "comment",
            mysql.VARCHAR(charset="utf8mb3", collation="utf8mb3_general_ci", length=80),
            nullable=False,
        ),
        sa.Column("colour", sa.CHAR(length=6), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "favourites",
        sa.Column("userid", sa.Integer(), nullable=False),
        sa.Column("setid", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("userid", "setid"),
    )
    op.create_table(
        "ingame_logins",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("userid", sa.Integer(), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=False),
        sa.Column("osu_ver", sa.Date(), nullable=False),
        sa.Column("osu_stream", sa.String(length=11), nullable=False),
        sa.Column("datetime", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("from", sa.Integer(), nullable=False),
        sa.Column("to", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column(
            "msg",
            mysql.VARCHAR(
                charset="utf8mb3",
                collation="utf8mb3_general_ci",
                length=2048,
            ),
            nullable=True,
        ),
        sa.Column("time", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "mail",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("from_id", sa.Integer(), nullable=False),
        sa.Column("to_id", sa.Integer(), nullable=False),
        sa.Column(
            "msg",
            mysql.VARCHAR(
                charset="utf8mb3",
                collation="utf8mb3_general_ci",
                length=2048,
            ),
            nullable=False,
        ),
        sa.Column("time", sa.Integer(), nullable=True),
        sa.Column(
            "read",
            mysql.TINYINT(display_width=1),
            server_default="0",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "map_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("map_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("datetime", sa.DateTime(), nullable=False),
        sa.Column("active", mysql.TINYINT(display_width=1), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "maps",
        sa.Column(
            "server",
            mysql.ENUM("replay", "map", "song"),
            server_default="osu!",
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("set_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("md5", mysql.CHAR(length=32), nullable=False),
        sa.Column(
            "artist",
            mysql.VARCHAR(
                charset="utf8mb3",
                collation="utf8mb3_general_ci",
                length=128,
            ),
            nullable=False,
        ),
        sa.Column(
            "title",
            mysql.VARCHAR(
                charset="utf8mb3",
                collation="utf8mb3_general_ci",
                length=128,
            ),
            nullable=False,
        ),
        sa.Column(
            "version",
            mysql.VARCHAR(
                charset="utf8mb3",
                collation="utf8mb3_general_ci",
                length=128,
            ),
            nullable=False,
        ),
        sa.Column(
            "creator",
            mysql.VARCHAR(charset="utf8mb3", collation="utf8mb3_general_ci", length=19),
            nullable=False,
        ),
        sa.Column(
            "filename",
            mysql.VARCHAR(
                charset="utf8mb3",
                collation="utf8mb3_general_ci",
                length=256,
            ),
            nullable=False,
        ),
        sa.Column("last_update", sa.DateTime(), nullable=False),
        sa.Column("total_length", sa.Integer(), nullable=False),
        sa.Column("max_combo", sa.Integer(), nullable=False),
        sa.Column(
            "frozen",
            mysql.TINYINT(display_width=1),
            server_default="0",
            nullable=False,
        ),
        sa.Column("plays", sa.Integer(), server_default="0", nullable=False),
        sa.Column("passes", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "mode",
            mysql.TINYINT(display_width=1),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "bpm",
            mysql.FLOAT(precision=12, scale=2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column(
            "cs",
            mysql.FLOAT(precision=4, scale=2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column(
            "ar",
            mysql.FLOAT(precision=4, scale=2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column(
            "od",
            mysql.FLOAT(precision=4, scale=2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column(
            "hp",
            mysql.FLOAT(precision=4, scale=2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column(
            "diff",
            mysql.FLOAT(precision=6, scale=3),
            server_default="0.000",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("server", "id"),
    )
    op.create_index("maps_filename_index", "maps", ["filename"], unique=False)
    op.create_index("maps_frozen_index", "maps", ["frozen"], unique=False)
    op.create_index("maps_id_uindex", "maps", ["id"], unique=True)
    op.create_index("maps_md5_uindex", "maps", ["md5"], unique=True)
    op.create_index("maps_mode_index", "maps", ["mode"], unique=False)
    op.create_index("maps_plays_index", "maps", ["plays"], unique=False)
    op.create_index("maps_set_id_index", "maps", ["set_id"], unique=False)
    op.create_index("maps_status_index", "maps", ["status"], unique=False)
    op.create_table(
        "ratings",
        sa.Column("userid", sa.Integer(), nullable=False),
        sa.Column("map_md5", mysql.CHAR(length=32), nullable=False),
        sa.Column("rating", mysql.TINYINT(display_width=2), nullable=False),
        sa.PrimaryKeyConstraint("userid", "map_md5"),
    )
    op.create_table(
        "scores",
        sa.Column(
            "id",
            mysql.BIGINT(unsigned=True),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("map_md5", mysql.CHAR(length=32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("pp", mysql.FLOAT(precision=7, scale=3), nullable=False),
        sa.Column("acc", mysql.FLOAT(precision=6, scale=3), nullable=False),
        sa.Column("max_combo", sa.Integer(), nullable=False),
        sa.Column("mods", sa.Integer(), nullable=False),
        sa.Column("n300", sa.Integer(), nullable=False),
        sa.Column("n100", sa.Integer(), nullable=False),
        sa.Column("n50", sa.Integer(), nullable=False),
        sa.Column("nmiss", sa.Integer(), nullable=False),
        sa.Column("ngeki", sa.Integer(), nullable=False),
        sa.Column("nkatu", sa.Integer(), nullable=False),
        sa.Column("grade", sa.String(length=2), server_default="N", nullable=False),
        sa.Column("status", mysql.TINYINT(), nullable=False),
        sa.Column("mode", mysql.TINYINT(), nullable=False),
        sa.Column("play_time", sa.DateTime(), nullable=False),
        sa.Column("time_elapsed", sa.Integer(), nullable=False),
        sa.Column("client_flags", sa.Integer(), nullable=False),
        sa.Column("userid", sa.Integer(), nullable=False),
        sa.Column("perfect", mysql.TINYINT(display_width=1), nullable=False),
        sa.Column("online_checksum", mysql.CHAR(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("scores_map_md5_index", "scores", ["map_md5"], unique=False)
    op.create_index("scores_mode_index", "scores", ["mode"], unique=False)
    op.create_index("scores_mods_index", "scores", ["mods"], unique=False)
    op.create_index(
        "scores_online_checksum_index",
        "scores",
        ["online_checksum"],
        unique=False,
    )
    op.create_index("scores_play_time_index", "scores", ["play_time"], unique=False)
    op.create_index("scores_pp_index", "scores", ["pp"], unique=False)
    op.create_index("scores_score_index", "scores", ["score"], unique=False)
    op.create_index("scores_status_index", "scores", ["status"], unique=False)
    op.create_index("scores_userid_index", "scores", ["userid"], unique=False)
    op.create_index(
        "scores_fetch_leaderboard_generic_index",
        "scores",
        ["map_md5", "status", "mode"],
        unique=False,
    )
    op.create_table(
        "stats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mode", mysql.TINYINT(display_width=1), nullable=False),
        sa.Column(
            "tscore",
            mysql.BIGINT(unsigned=True),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "rscore",
            mysql.BIGINT(unsigned=True),
            server_default="0",
            nullable=False,
        ),
        sa.Column("pp", sa.Integer(), server_default="0", nullable=False),
        sa.Column("plays", sa.Integer(), server_default="0", nullable=False),
        sa.Column("playtime", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "acc",
            mysql.FLOAT(precision=6, scale=3),
            server_default="0.000",
            nullable=False,
        ),
        sa.Column("max_combo", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_hits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("replay_views", sa.Integer(), server_default="0", nullable=False),
        sa.Column("xh_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("x_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sh_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("s_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("a_count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", "mode"),
    )
    op.create_index("stats_mode_index", "stats", ["mode"], unique=False)
    op.create_index("stats_pp_index", "stats", ["pp"], unique=False)
    op.create_index("stats_rscore_index", "stats", ["rscore"], unique=False)
    op.create_index("stats_tscore_index", "stats", ["tscore"], unique=False)
    op.create_table(
        "tourney_pool_maps",
        sa.Column("map_id", sa.Integer(), nullable=False),
        sa.Column("pool_id", sa.Integer(), nullable=False),
        sa.Column("mods", mysql.BIGINT(), nullable=False),
        sa.Column("slot", mysql.TINYINT(), nullable=False),
        sa.PrimaryKeyConstraint("map_id", "pool_id"),
    )
    op.create_index(
        "tourney_pool_maps_mods_slot_index",
        "tourney_pool_maps",
        ["mods", "slot"],
        unique=False,
    )
    op.create_index(
        "tourney_pool_maps_tourney_pools_id_fk",
        "tourney_pool_maps",
        ["pool_id"],
        unique=False,
    )
    op.create_table(
        "tourney_pools",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", mysql.VARCHAR(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "tourney_pools_users_id_fk",
        "tourney_pools",
        ["created_by"],
        unique=False,
    )
    op.create_table(
        "user_achievements",
        sa.Column("userid", sa.Integer(), nullable=False),
        sa.Column("achid", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("userid", "achid"),
    )
    op.create_index(
        "user_achievements_achid_index",
        "user_achievements",
        ["achid"],
        unique=False,
    )
    op.create_index(
        "user_achievements_userid_index",
        "user_achievements",
        ["userid"],
        unique=False,
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", mysql.MEDIUMTEXT(), nullable=False),
        sa.Column("safe_name", mysql.MEDIUMTEXT(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("priv", sa.Integer(), server_default="1", nullable=False),
        sa.Column("pw_bcrypt", mysql.CHAR(length=60), nullable=False),
        sa.Column("country", mysql.CHAR(length=2), server_default="xx", nullable=False),
        sa.Column("silence_end", sa.Integer(), server_default="0", nullable=False),
        sa.Column("donor_end", sa.Integer(), server_default="0", nullable=False),
        sa.Column("creation_time", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latest_activity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("clan_id", sa.Integer(), server_default="0", nullable=False),
        sa.Column("clan_priv", mysql.TINYINT(), server_default="0", nullable=False),
        sa.Column("preferred_mode", sa.Integer(), server_default="0", nullable=False),
        sa.Column("play_style", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "custom_badge_name",
            mysql.VARCHAR(charset="utf8mb3", collation="utf8mb3_general_ci", length=16),
            nullable=True,
        ),
        sa.Column("custom_badge_icon", sa.String(length=64), nullable=True),
        sa.Column(
            "userpage_content",
            mysql.VARCHAR(
                charset="utf8mb3",
                collation="utf8mb3_general_ci",
                length=2048,
            ),
            nullable=True,
        ),
        sa.Column("api_key", mysql.CHAR(length=36), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("users_api_key_uindex", "users", ["api_key"], unique=True)
    op.create_index("users_clan_id_index", "users", ["clan_id"], unique=False)
    op.create_index("users_clan_priv_index", "users", ["clan_priv"], unique=False)
    op.create_index("users_country_index", "users", ["country"], unique=False)
    op.create_index("users_email_uindex", "users", ["email"], unique=True)
    op.create_index("users_name_uindex", "users", ["name"], unique=True)
    op.create_index("users_priv_index", "users", ["priv"], unique=False)
    op.create_index("users_safe_name_uindex", "users", ["safe_name"], unique=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("users_safe_name_uindex", table_name="users")
    op.drop_index("users_priv_index", table_name="users")
    op.drop_index("users_name_uindex", table_name="users")
    op.drop_index("users_email_uindex", table_name="users")
    op.drop_index("users_country_index", table_name="users")
    op.drop_index("users_clan_priv_index", table_name="users")
    op.drop_index("users_clan_id_index", table_name="users")
    op.drop_index("users_api_key_uindex", table_name="users")
    op.drop_table("users")
    op.drop_index("user_achievements_userid_index", table_name="user_achievements")
    op.drop_index("user_achievements_achid_index", table_name="user_achievements")
    op.drop_table("user_achievements")
    op.drop_index("tourney_pools_users_id_fk", table_name="tourney_pools")
    op.drop_table("tourney_pools")
    op.drop_index(
        "tourney_pool_maps_tourney_pools_id_fk",
        table_name="tourney_pool_maps",
    )
    op.drop_index("tourney_pool_maps_mods_slot_index", table_name="tourney_pool_maps")
    op.drop_table("tourney_pool_maps")
    op.drop_index("stats_tscore_index", table_name="stats")
    op.drop_index("stats_rscore_index", table_name="stats")
    op.drop_index("stats_pp_index", table_name="stats")
    op.drop_index("stats_mode_index", table_name="stats")
    op.drop_table("stats")
    op.drop_index("scores_fetch_leaderboard_generic_index", table_name="scores")
    op.drop_index("scores_userid_index", table_name="scores")
    op.drop_index("scores_status_index", table_name="scores")
    op.drop_index("scores_score_index", table_name="scores")
    op.drop_index("scores_pp_index", table_name="scores")
    op.drop_index("scores_play_time_index", table_name="scores")
    op.drop_index("scores_online_checksum_index", table_name="scores")
    op.drop_index("scores_mods_index", table_name="scores")
    op.drop_index("scores_mode_index", table_name="scores")
    op.drop_index("scores_map_md5_index", table_name="scores")
    op.drop_table("scores")
    op.drop_table("ratings")
    op.drop_index("maps_status_index", table_name="maps")
    op.drop_index("maps_set_id_index", table_name="maps")
    op.drop_index("maps_plays_index", table_name="maps")
    op.drop_index("maps_mode_index", table_name="maps")
    op.drop_index("maps_md5_uindex", table_name="maps")
    op.drop_index("maps_id_uindex", table_name="maps")
    op.drop_index("maps_frozen_index", table_name="maps")
    op.drop_index("maps_filename_index", table_name="maps")
    op.drop_table("maps")
    op.drop_table("map_requests")
    op.drop_table("mail")
    op.drop_table("logs")
    op.drop_table("ingame_logins")
    op.drop_table("favourites")
    op.drop_table("comments")
    op.drop_table("client_hashes")
    op.drop_index("clans_tag_uindex", table_name="clans")
    op.drop_index("clans_owner_uindex", table_name="clans")
    op.drop_index("clans_name_uindex", table_name="clans")
    op.drop_table("clans")
    op.drop_index("channels_name_uindex", table_name="channels")
    op.drop_index("channels_auto_join_index", table_name="channels")
    op.drop_table("channels")
    op.drop_index("achievements_name_uindex", table_name="achievements")
    op.drop_index("achievements_file_uindex", table_name="achievements")
    op.drop_index("achievements_desc_uindex", table_name="achievements")
    op.drop_table("achievements")
    # ### end Alembic commands ###
