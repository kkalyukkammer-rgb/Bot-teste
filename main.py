import asyncio
from contextlib import closing
import io
import logging
import math
import os
import random
import re
import sqlite3
import subprocess
import tempfile
import time
from typing import Literal

import discord
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("discord_bot")

BOT_OWNER_ID = 1079199747019112520
UPDATE_ANNOUNCEMENT_GUILD_ID = 1467549007932030998
UPDATE_ANNOUNCEMENT_CHANNEL_ID = 1560451788254216343
UPDATE_ANNOUNCEMENT_ROLE_ID = 1559362476921987072
MAIN_HOUSE_STARTING_BALANCE = 1_000_000_000
MAIN_HOUSE_UPGRADE_MAX_LEVEL = 10
MAIN_HOUSE_UPGRADE_COST_PERCENT_PER_LEVEL = 1
MAIN_HOUSE_UPGRADE_NPC_BONUS = 10
PROJECT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIRECTORY = os.path.join(PROJECT_DIRECTORY, "backup")
DEFAULT_ECONOMY_DB_PATH = os.path.join(BACKUP_DIRECTORY, "economy.sqlite3")
LEGACY_ECONOMY_DB_PATH = os.path.join(PROJECT_DIRECTORY, "economy.sqlite3")
ECONOMY_DB_PATH = os.getenv(
    "ECONOMY_DB_PATH",
    DEFAULT_ECONOMY_DB_PATH,
)
REWARD_SETTINGS = {
    "daily": ("daily_claim_at", 24 * 60 * 60, 1, 100, "diária"),
    "weekly": ("weekly_claim_at", 7 * 24 * 60 * 60, 100, 1000, "semanal"),
    "monthly": ("monthly_claim_at", 30 * 24 * 60 * 60, 1000, 20000, "mensal"),
}
SLOT_SYMBOLS = ("🍒", "🍋", "🔔", "💎", "⭐", "7️⃣")
SLOT_WEIGHTS = (35, 30, 18, 10, 5, 2)
SLOT_TRIPLE_MULTIPLIERS = {
    "🍒": 2,
    "🍋": 3,
    "🔔": 5,
    "💎": 8,
    "⭐": 12,
    "7️⃣": 25,
}
SLOT_PAIR_MULTIPLIERS = {
    "🍒": 1,
    "🍋": 1,
    "🔔": 2,
    "💎": 3,
    "⭐": 4,
    "7️⃣": 6,
}
BETTING_ANIMALS = (
    "Leão 🦁",
    "Tigre 🐯",
    "Elefante 🐘",
    "Macaco 🐒",
    "Raposa 🦊",
    "Lobo 🐺",
    "Coelho 🐰",
    "Panda 🐼",
)
ANIMAL_BET_MULTIPLIERS = {1: 3, 2: 2, 3: 1.5}
ANIMAL_BET_COOLDOWN = 24 * 60 * 60
ROULETTE_RED_NUMBERS = frozenset(
    {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
)
DEFAULT_CASINO_CREATION_FEE = 1_000
DEFAULT_CASINO_TAX_PERCENT = 10
DEFAULT_MAIN_HOUSE_NPCS = 10
MAIN_HOUSE_NPC_BET_MIN = 5_000
MAIN_HOUSE_NPC_BET_MAX = 20_000
CASINO_STARTING_NPCS = 3
CASINO_MAX_NPCS = 100
CASINO_NPC_HIRE_COST = 1_000
CASINO_NPC_MIN_NET_EARNINGS = 1_000
CASINO_NPC_BET_MAX_MULTIPLIER = 4
NPC_ONLINE_INTERVAL_MIN_SECONDS = 15
NPC_ONLINE_INTERVAL_MAX_SECONDS = 45
NPC_OFFLINE_INTERVAL_SECONDS = 30 * 60
NPC_BET_POLL_INTERVAL_SECONDS = 5
CASINO_DAILY_REWARD = 100
CASINO_WEEKLY_REWARD = 500
CASINO_REWARD_SETTINGS = {
    "daily": ("daily_claim_at", 24 * 60 * 60, CASINO_DAILY_REWARD, "diária"),
    "weekly": (
        "weekly_claim_at",
        7 * 24 * 60 * 60,
        CASINO_WEEKLY_REWARD,
        "semanal",
    ),
}
CASINO_UPGRADE_COSTS = (5_000, 15_000, 35_000)
CASINO_TAX_REDUCTION_PER_LEVEL = 1
CASINO_MINIMUM_TAX_PERCENT = 1
CASINO_STARTING_TREASURY = 10_000
CASINO_GAME_UNLOCKS = {
    "moeda": 0,
    "dados": 1,
    "roleta": 2,
    "cacaniquel": 3,
}
PVP_HOUSE_TAX_PERCENT = 5
CASINO_PARTICIPANT_COMMANDS = frozenset(
    {
        "jogar_cassino",
        "cacaniquel",
        "corrida",
        "moeda",
        "dados",
        "roleta",
        "duelo",
        "blackjack",
    }
)
CASINO_ROLE_REFRESH_COMMANDS = CASINO_PARTICIPANT_COMMANDS | frozenset(
    {
        "daily",
        "weekly",
        "monthly",
        "daily_cassino",
        "weekly_cassino",
        "criar_cassino",
        "prestigio",
        "upgrade_prestigio",
    }
)
PRESTIGE_STARTING_REQUIREMENT = 1_000_000
PRESTIGE_MAX_LEVEL = 28
PRESTIGE_MAX_UPGRADE_LEVEL = 10
PLAYER_BASE_BET_LIMIT = 1_000_000
PLAYER_BET_LIMIT_PER_UPGRADE = 100_000
PLAYER_BET_PARAMETER_MAX = (
    PLAYER_BASE_BET_LIMIT
    + PRESTIGE_MAX_UPGRADE_LEVEL * PLAYER_BET_LIMIT_PER_UPGRADE
)
PRESTIGE_UPGRADES = {
    "gains": ("prestige_upgrade_gains", "Ganhos em apostas", 5),
    "rewards": ("prestige_upgrade_rewards", "Rewards diários e semanais", 10),
    "bet_limit": ("prestige_upgrade_bet_limit", "Limite de aposta", 100_000),
}
AUTOROLE_CONDITIONS = {
    "participation": "participação em jogos",
    "global_balance_rank": "posição no ranking global",
    "global_balance": "saldo global mínimo",
    "casino_balance_rank": "posição no ranking do cassino",
    "casino_balance": "saldo mínimo no cassino",
    "prestige": "nível mínimo de prestígio",
    "bet_volume": "volume total apostado",
    "bet_count": "quantidade de apostas",
}


def initialize_economy() -> None:
    database_directory = os.path.dirname(ECONOMY_DB_PATH)
    if database_directory:
        os.makedirs(database_directory, exist_ok=True)

    if (
        os.path.abspath(ECONOMY_DB_PATH)
        == os.path.abspath(DEFAULT_ECONOMY_DB_PATH)
        and migrate_legacy_economy_database(
            ECONOMY_DB_PATH,
            LEGACY_ECONOMY_DB_PATH,
        )
    ):
        logger.info(
            "Banco de economia existente copiado para o backup persistente: %s",
            ECONOMY_DB_PATH,
        )

    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS economy_accounts (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 0,
                total_earned INTEGER NOT NULL DEFAULT 0,
                total_lost INTEGER NOT NULL DEFAULT 0,
                prestige_level INTEGER NOT NULL DEFAULT 0,
                prestige_points INTEGER NOT NULL DEFAULT 0,
                prestige_upgrade_gains INTEGER NOT NULL DEFAULT 0,
                prestige_upgrade_rewards INTEGER NOT NULL DEFAULT 0,
                prestige_upgrade_bet_limit INTEGER NOT NULL DEFAULT 0,
                total_bet_volume INTEGER NOT NULL DEFAULT 0,
                total_bet_count INTEGER NOT NULL DEFAULT 0,
                daily_claim_at INTEGER,
                weekly_claim_at INTEGER,
                monthly_claim_at INTEGER,
                animal_bet_at INTEGER
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_betting_channels (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_casino_autoroles (
                guild_id INTEGER PRIMARY KEY,
                role_id INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_casino_autorole_rules (
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                condition TEXT NOT NULL,
                threshold INTEGER NOT NULL DEFAULT 0,
                UNIQUE (guild_id, role_id, condition, threshold)
            )
            """
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO guild_casino_autorole_rules
                (guild_id, role_id, condition, threshold)
            SELECT guild_id, role_id, 'participation', 0
            FROM guild_casino_autoroles
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS casino_settings (
                setting TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_update_state (
                setting TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            "INSERT OR IGNORE INTO casino_settings (setting, value) VALUES (?, ?)",
            (
                ("creation_fee", DEFAULT_CASINO_CREATION_FEE),
                ("tax_percent", DEFAULT_CASINO_TAX_PERCENT),
                ("main_house_npcs", DEFAULT_MAIN_HOUSE_NPCS),
                ("npc_last_cycle_at", int(time.time())),
                (
                    "main_house_npc_next_bet_at",
                    int(time.time()) + NPC_OFFLINE_INTERVAL_SECONDS,
                ),
                ("main_house_npc_owner_online", 0),
                ("main_house_games", 0),
                ("main_house_npc_games", 0),
                ("main_house_player_bet_volume", 0),
                ("main_house_player_bet_count", 0),
                ("main_house_player_bet_earned", 0),
                ("main_house_player_bet_lost", 0),
                ("main_house_upgrade_level", 0),
                ("main_house_upgrade_costs_paid", 0),
                ("main_house_npc_count_upgrade_level", 0),
                ("main_house_npc_count_upgrade_costs_paid", 0),
                ("main_house_npc_bet_upgrade_level", 0),
                ("main_house_npc_bet_upgrade_costs_paid", 0),
                ("main_house_upgrade_tracks_migrated", 0),
            ),
        )
        upgrade_tracks_migrated = connection.execute(
            """
            SELECT value FROM casino_settings
            WHERE setting = 'main_house_upgrade_tracks_migrated'
            """
        ).fetchone()[0]
        if not upgrade_tracks_migrated:
            legacy_upgrade_level = connection.execute(
                """
                SELECT value FROM casino_settings
                WHERE setting = 'main_house_upgrade_level'
                """
            ).fetchone()[0]
            connection.execute(
                """
                UPDATE casino_settings
                SET value = ?
                WHERE setting = 'main_house_npc_bet_upgrade_level'
                """,
                (legacy_upgrade_level,),
            )
            connection.execute(
                """
                UPDATE casino_settings
                SET value = 1
                WHERE setting = 'main_house_upgrade_tracks_migrated'
                """
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_casinos (
                guild_id INTEGER PRIMARY KEY,
                owner_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                currency_name TEXT NOT NULL,
                treasury INTEGER NOT NULL DEFAULT 0,
                upgrade_level INTEGER NOT NULL DEFAULT 0,
                npc_count INTEGER NOT NULL DEFAULT 3,
                games_played INTEGER NOT NULL DEFAULT 0,
                npc_games INTEGER NOT NULL DEFAULT 0,
                house_earned INTEGER NOT NULL DEFAULT 0,
                house_lost INTEGER NOT NULL DEFAULT 0,
                tax_paid INTEGER NOT NULL DEFAULT 0,
                upgrade_costs_paid INTEGER NOT NULL DEFAULT 0,
                npc_hiring_costs INTEGER NOT NULL DEFAULT 0,
                rewards_paid INTEGER NOT NULL DEFAULT 0,
                npc_next_bet_at INTEGER NOT NULL DEFAULT 0,
                npc_owner_online INTEGER NOT NULL DEFAULT 0,
                player_bet_volume INTEGER NOT NULL DEFAULT 0,
                player_bet_count INTEGER NOT NULL DEFAULT 0,
                player_bet_earned INTEGER NOT NULL DEFAULT 0,
                player_bet_lost INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        casino_columns = {
            column[1]
            for column in connection.execute("PRAGMA table_info(guild_casinos)")
        }
        casino_migrations = {
            "npc_count": CASINO_STARTING_NPCS,
            "games_played": 0,
            "npc_games": 0,
            "house_earned": 0,
            "house_lost": 0,
            "tax_paid": 0,
            "upgrade_costs_paid": 0,
            "npc_hiring_costs": 0,
            "rewards_paid": 0,
            "npc_next_bet_at": 0,
            "npc_owner_online": 0,
            "player_bet_volume": 0,
            "player_bet_count": 0,
            "player_bet_earned": 0,
            "player_bet_lost": 0,
        }
        for column, default in casino_migrations.items():
            if column not in casino_columns:
                connection.execute(
                    "ALTER TABLE guild_casinos "
                    f"ADD COLUMN {column} INTEGER NOT NULL DEFAULT {default}"
                )
        connection.execute(
            """
            UPDATE guild_casinos SET npc_next_bet_at = ?
            WHERE npc_next_bet_at = 0
            """,
            (int(time.time()) + NPC_OFFLINE_INTERVAL_SECONDS,),
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_casino_accounts (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                balance INTEGER NOT NULL DEFAULT 0,
                total_earned INTEGER NOT NULL DEFAULT 0,
                total_lost INTEGER NOT NULL DEFAULT 0,
                total_bet_volume INTEGER NOT NULL DEFAULT 0,
                total_bet_count INTEGER NOT NULL DEFAULT 0,
                daily_claim_at INTEGER,
                weekly_claim_at INTEGER,
                PRIMARY KEY (guild_id, user_id),
                FOREIGN KEY (guild_id) REFERENCES guild_casinos(guild_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS house_bet_reservations (
                reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                house_owner_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                exposure INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
            """
        )
        reservation_columns = {
            column[1]
            for column in connection.execute(
                "PRAGMA table_info(house_bet_reservations)"
            )
        }
        if "exposure" not in reservation_columns:
            connection.execute(
                "ALTER TABLE house_bet_reservations "
                "ADD COLUMN exposure INTEGER NOT NULL DEFAULT 0"
            )
        connection.execute(
            """
            UPDATE house_bet_reservations SET exposure = amount
            WHERE exposure = 0
            """
        )
        stale_reservations = connection.execute(
            """
            SELECT user_id, amount FROM house_bet_reservations
            """
        ).fetchall()
        for user_id, amount in stale_reservations:
            connection.execute(
                """
                INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)
                """,
                (user_id,),
            )
            connection.execute(
                """
                UPDATE economy_accounts
                SET balance = balance + ?, total_earned = total_earned + ?
                WHERE user_id = ?
                """,
                (amount, amount, user_id),
            )
        connection.execute("DELETE FROM house_bet_reservations")
        columns = {
            column[1]
            for column in connection.execute("PRAGMA table_info(economy_accounts)")
        }
        if "total_earned" not in columns:
            connection.execute(
                "ALTER TABLE economy_accounts "
                "ADD COLUMN total_earned INTEGER NOT NULL DEFAULT 0"
            )
        if "total_lost" not in columns:
            connection.execute(
                "ALTER TABLE economy_accounts "
                "ADD COLUMN total_lost INTEGER NOT NULL DEFAULT 0"
            )
        if "animal_bet_at" not in columns:
            connection.execute(
                "ALTER TABLE economy_accounts "
                "ADD COLUMN animal_bet_at INTEGER"
            )
        economy_migrations = {
            "prestige_level": 0,
            "prestige_points": 0,
            "prestige_upgrade_gains": 0,
            "prestige_upgrade_rewards": 0,
            "prestige_upgrade_bet_limit": 0,
            "total_bet_volume": 0,
            "total_bet_count": 0,
        }
        for column, default in economy_migrations.items():
            if column not in columns:
                connection.execute(
                    "ALTER TABLE economy_accounts "
                    f"ADD COLUMN {column} INTEGER NOT NULL DEFAULT {default}"
                )

        guild_account_columns = {
            column[1]
            for column in connection.execute(
                "PRAGMA table_info(guild_casino_accounts)"
            )
        }
        for column in ("total_bet_volume", "total_bet_count"):
            if column not in guild_account_columns:
                connection.execute(
                    "ALTER TABLE guild_casino_accounts "
                    f"ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0"
                )


def migrate_legacy_economy_database(
    database_path: str,
    legacy_database_path: str,
) -> bool:
    if (
        os.path.abspath(database_path) == os.path.abspath(legacy_database_path)
        or os.path.exists(database_path)
        or not os.path.isfile(legacy_database_path)
    ):
        return False

    database_directory = os.path.dirname(os.path.abspath(database_path))
    os.makedirs(database_directory, exist_ok=True)
    temporary_descriptor, temporary_path = tempfile.mkstemp(
        prefix=".economy-migration-",
        suffix=".sqlite3",
        dir=database_directory,
    )
    os.close(temporary_descriptor)
    try:
        with closing(sqlite3.connect(legacy_database_path)) as source:
            with closing(sqlite3.connect(temporary_path)) as destination:
                source.backup(destination)
        os.replace(temporary_path, database_path)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
    return True


def get_betting_channel_id(guild_id: int) -> int | None:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        setting = connection.execute(
            "SELECT channel_id FROM guild_betting_channels WHERE guild_id = ?",
            (guild_id,),
        ).fetchone()
    return setting[0] if setting else None


def set_betting_channel(guild_id: int, channel_id: int | None) -> None:
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        if channel_id is None:
            connection.execute(
                "DELETE FROM guild_betting_channels WHERE guild_id = ?",
                (guild_id,),
            )
        else:
            connection.execute(
                """
                INSERT INTO guild_betting_channels (guild_id, channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id)
                DO UPDATE SET channel_id = excluded.channel_id
                """,
                (guild_id, channel_id),
            )


def get_casino_autorole_rules(
    guild_id: int,
) -> list[tuple[int, str, int]]:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        rules = connection.execute(
            """
            SELECT role_id, condition, threshold
            FROM guild_casino_autorole_rules
            WHERE guild_id = ?
            ORDER BY rule_id
            """,
            (guild_id,),
        ).fetchall()
    return rules


def set_casino_autorole_rule(
    guild_id: int,
    role_id: int | None,
    condition: str,
    threshold: int = 0,
) -> None:
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        if role_id is None:
            connection.execute(
                """
                DELETE FROM guild_casino_autorole_rules
                WHERE guild_id = ? AND condition = ?
                """,
                (guild_id, condition),
            )
        else:
            connection.execute(
                """
                DELETE FROM guild_casino_autorole_rules
                WHERE guild_id = ? AND role_id = ? AND condition = ?
                """,
                (guild_id, role_id, condition),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO guild_casino_autorole_rules
                    (guild_id, role_id, condition, threshold)
                VALUES (?, ?, ?, ?)
                """,
                (guild_id, role_id, condition, threshold),
            )


async def synchronize_casino_autoroles(
    guild: discord.Guild,
    *,
    triggering_member: discord.Member | None = None,
) -> None:
    rules = get_casino_autorole_rules(guild.id)
    if not rules:
        return

    members = {member.id: member for member in guild.members}
    if triggering_member is not None:
        members[triggering_member.id] = triggering_member
    member_ids = set(members)
    if not member_ids:
        return

    member_id_list = list(member_ids)
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        global_accounts: list[tuple[int, int, int, int, int, int, int]] = []
        for start in range(0, len(member_id_list), 900):
            batch = member_id_list[start : start + 900]
            placeholders = ",".join("?" for _ in batch)
            global_accounts.extend(
                connection.execute(
                    f"""
                    SELECT user_id, balance, total_earned, total_lost,
                           prestige_level, total_bet_volume, total_bet_count
                    FROM economy_accounts
                    WHERE user_id IN ({placeholders})
                    """,
                    batch,
                ).fetchall()
            )
        global_accounts_by_user = {
            row[0]: {
                "balance": row[1],
                "total_earned": row[2],
                "total_lost": row[3],
                "prestige": row[4],
                "bet_volume": row[5],
                "bet_count": row[6],
            }
            for row in global_accounts
        }
        main_house_owner_id = get_house_owner_id()
        global_ranked = sorted(
            (
                row
                for row in global_accounts
                if row[0] != main_house_owner_id
            ),
            key=lambda row: (-row[1], -row[2], row[3], row[0]),
        )
        global_ranks = {
            row[0]: rank for rank, row in enumerate(global_ranked, start=1)
        }

        casino = connection.execute(
            "SELECT owner_id FROM guild_casinos WHERE guild_id = ?",
            (guild.id,),
        ).fetchone()
        casino_owner_id = casino[0] if casino else None
        local_accounts: list[tuple[int, int, int, int]] = []
        if casino is not None:
            for start in range(0, len(member_id_list), 900):
                batch = member_id_list[start : start + 900]
                placeholders = ",".join("?" for _ in batch)
                local_accounts.extend(
                    connection.execute(
                        f"""
                        SELECT user_id, balance, total_earned, total_lost
                        FROM guild_casino_accounts
                        WHERE guild_id = ? AND user_id IN ({placeholders})
                        """,
                        (guild.id, *batch),
                    ).fetchall()
                )
        local_accounts_by_user = {row[0]: row[1] for row in local_accounts}
        local_ranked = sorted(
            (
                row
                for row in local_accounts
                if row[0] not in (main_house_owner_id, casino_owner_id)
            ),
            key=lambda row: (-row[1], -row[2], row[3], row[0]),
        )
        local_ranks = {
            row[0]: rank for rank, row in enumerate(local_ranked, start=1)
        }

    desired_roles: dict[int, set[int]] = {
        member_id: set() for member_id in member_ids
    }
    configured_roles = {role_id for role_id, _, _ in rules}
    for role_id, condition, threshold in rules:
        role = guild.get_role(role_id)
        if role is None:
            logger.error(
                "O cargo de autorole %s configurado para o servidor %s não existe.",
                role_id,
                guild.id,
            )
            continue
        for member_id, member in members.items():
            account = global_accounts_by_user.get(member_id, {})
            if condition == "participation":
                qualifies = (
                    member_id == triggering_member.id
                    if triggering_member is not None
                    else role in member.roles
                )
            elif condition == "global_balance_rank":
                rank = global_ranks.get(member_id)
                qualifies = rank is not None and rank <= threshold
            elif condition == "global_balance":
                qualifies = account.get("balance", 0) >= threshold
            elif condition == "casino_balance_rank":
                rank = local_ranks.get(member_id)
                qualifies = rank is not None and rank <= threshold
            elif condition == "casino_balance":
                qualifies = local_accounts_by_user.get(member_id, 0) >= threshold
            elif condition == "prestige":
                qualifies = account.get("prestige", 0) >= threshold
            elif condition == "bet_volume":
                qualifies = account.get("bet_volume", 0) >= threshold
            elif condition == "bet_count":
                qualifies = account.get("bet_count", 0) >= threshold
            else:
                logger.error(
                    "Condição de autorole desconhecida %r no servidor %s.",
                    condition,
                    guild.id,
                )
                qualifies = False
            if qualifies:
                desired_roles[member_id].add(role_id)

    bot_member = guild.me
    if bot_member is None or not bot_member.guild_permissions.manage_roles:
        logger.error(
            "O bot não pode sincronizar autoroles no servidor %s: "
            "permissão Gerenciar cargos ausente.",
            guild.id,
        )
        return

    for member_id, member in members.items():
        currently_configured = {
            role.id for role in member.roles if role.id in configured_roles
        }
        should_have = desired_roles[member_id]
        to_add = [
            role
            for role_id in should_have - currently_configured
            if (role := guild.get_role(role_id)) is not None
            and not role.is_default()
            and not role.managed
            and role < bot_member.top_role
        ]
        to_remove = [
            role
            for role_id in currently_configured - should_have
            if (role := guild.get_role(role_id)) is not None
            and not role.managed
            and role < bot_member.top_role
        ]
        try:
            if to_add:
                await member.add_roles(
                    *to_add,
                    reason="Condição automática de cassino alcançada.",
                )
            if to_remove:
                await member.remove_roles(
                    *to_remove,
                    reason="Condição automática de cassino não atendida.",
                )
        except discord.HTTPException:
            logger.exception(
                "Falha ao sincronizar autoroles do membro %s no servidor %s.",
                member_id,
                guild.id,
            )


async def ensure_betting_channel(interaction: discord.Interaction) -> bool:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Os jogos de aposta só podem ser usados em um servidor.",
            ephemeral=True,
        )
        return False

    configured_channel_id = get_betting_channel_id(guild.id)
    if configured_channel_id is None or interaction.channel_id == configured_channel_id:
        return True

    await interaction.response.send_message(
        f"Os jogos de aposta deste servidor só podem ser usados em "
        f"<#{configured_channel_id}>.",
        ephemeral=True,
    )
    return False


async def ensure_not_house_owner(interaction: discord.Interaction) -> bool:
    if interaction.user.id != get_house_owner_id():
        return True
    await interaction.response.send_message(
        "O owner do bot é a banca principal e não pode apostar contra ela.",
        ephemeral=True,
    )
    return False


async def ensure_bet_limit(
    interaction: discord.Interaction,
    bet: int,
) -> bool:
    limit = get_player_bet_limit(interaction.user.id)
    if bet <= limit:
        return True
    await interaction.response.send_message(
        f"Seu limite atual de aposta é {format_coins(limit)} moedas. "
        "Compre upgrades no comando `/upgrade_prestigio` para aumentá-lo.",
        ephemeral=True,
    )
    return False


def get_balance(user_id: int) -> int:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        account = connection.execute(
            "SELECT balance FROM economy_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return account[0] if account else 0


def get_player_status(
    user_id: int,
    guild_id: int | None = None,
) -> tuple[
    tuple[
        int,
        int,
        int,
        int,
        int,
        int,
        int,
        int,
        int,
        int,
        int | None,
        int | None,
        int | None,
    ],
    tuple[
        str,
        str,
        int,
        int,
        int,
        int,
        int,
        int | None,
        int | None,
    ]
    | None,
]:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        account = connection.execute(
            """
            SELECT balance, total_earned, total_lost, prestige_level,
                   prestige_points, prestige_upgrade_gains,
                   prestige_upgrade_rewards, prestige_upgrade_bet_limit,
                   total_bet_volume, total_bet_count, daily_claim_at,
                   weekly_claim_at, monthly_claim_at
            FROM economy_accounts WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        global_status = account or (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, None, None, None)

        local_status = None
        if guild_id is not None:
            local_status = connection.execute(
                """
                SELECT c.name, c.currency_name,
                       COALESCE(a.balance, 0),
                       COALESCE(a.total_earned, 0),
                       COALESCE(a.total_lost, 0),
                       COALESCE(a.total_bet_volume, 0),
                       COALESCE(a.total_bet_count, 0),
                       a.daily_claim_at, a.weekly_claim_at
                FROM guild_casinos AS c
                LEFT JOIN guild_casino_accounts AS a
                    ON a.guild_id = c.guild_id AND a.user_id = ?
                WHERE c.guild_id = ?
                """,
                (user_id, guild_id),
            ).fetchone()

    return global_status, local_status


def get_prestige_status(user_id: int) -> tuple[int, int, int, int, int, int, int]:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        account = connection.execute(
            """
            SELECT balance, prestige_level, prestige_points,
                   prestige_upgrade_gains, prestige_upgrade_rewards,
                   prestige_upgrade_bet_limit, total_bet_volume
            FROM economy_accounts WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    if account is None:
        return 0, 0, 0, 0, 0, 0, 0
    return account


def prestige_requirement(prestige_level: int) -> int:
    return PRESTIGE_STARTING_REQUIREMENT * 3**prestige_level


def prestige_player(user_id: int) -> tuple[str, int, int, int, int]:
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            (user_id,),
        )
        balance, prestige_level = connection.execute(
            """
            SELECT balance, prestige_level
            FROM economy_accounts WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        points = connection.execute(
            "SELECT prestige_points FROM economy_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        if user_id == BOT_OWNER_ID:
            return "house_owner", balance, prestige_level, points, 0
        active_bet = connection.execute(
            "SELECT 1 FROM house_bet_reservations WHERE user_id = ? LIMIT 1",
            (user_id,),
        ).fetchone()
        if active_bet is not None:
            return "active_bet", balance, prestige_level, points, 0
        if prestige_level >= PRESTIGE_MAX_LEVEL:
            return "max_level", balance, prestige_level, points, 0

        requirement = prestige_requirement(prestige_level)
        if balance < requirement:
            return "insufficient", balance, prestige_level, points, requirement

        new_level = prestige_level + 1
        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = 0, prestige_level = ?, prestige_points = prestige_points + ?
            WHERE user_id = ?
            """,
            (new_level, new_level, user_id),
        )
        connection.execute(
            """
            UPDATE guild_casino_accounts SET balance = 0
            WHERE user_id = ?
            """,
            (user_id,),
        )
        return "prestiged", 0, new_level, points + new_level, requirement


def purchase_prestige_upgrade(
    user_id: int,
    upgrade_key: str,
) -> tuple[str, int, int, int]:
    if upgrade_key not in PRESTIGE_UPGRADES:
        raise ValueError("Upgrade de prestígio desconhecido.")
    upgrade_column, _, _ = PRESTIGE_UPGRADES[upgrade_key]
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            (user_id,),
        )
        points, level = connection.execute(
            f"""
            SELECT prestige_points, {upgrade_column}
            FROM economy_accounts WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        if user_id == BOT_OWNER_ID:
            return "house_owner", points, level, 0
        if connection.execute(
            "SELECT 1 FROM house_bet_reservations WHERE user_id = ? LIMIT 1",
            (user_id,),
        ).fetchone() is not None:
            return "active_bet", points, level, 0
        if level >= PRESTIGE_MAX_UPGRADE_LEVEL:
            return "max_level", points, level, 0
        cost = level + 1
        if points < cost:
            return "insufficient", points, level, cost
        connection.execute(
            f"""
            UPDATE economy_accounts
            SET prestige_points = prestige_points - ?, {upgrade_column} = ?
            WHERE user_id = ?
            """,
            (cost, level + 1, user_id),
        )
        return "upgraded", points - cost, level + 1, cost


def apply_positive_profit_bonus(profit: int, bonus_levels: int) -> int:
    if profit <= 0 or bonus_levels <= 0:
        return profit
    return profit + (profit * bonus_levels * 5 + 99) // 100


def adjust_player_bet_payout(user_id: int, bet: int, payout: int) -> int:
    if payout <= bet:
        return payout
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        account = connection.execute(
            """
            SELECT prestige_level, prestige_upgrade_gains
            FROM economy_accounts WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    if account is None:
        return payout
    profit = payout - bet
    return bet + apply_positive_profit_bonus(profit, sum(account))


def get_player_bet_limit(user_id: int) -> int:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        upgrade = connection.execute(
            "SELECT prestige_upgrade_bet_limit FROM economy_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    level = upgrade[0] if upgrade else 0
    return PLAYER_BASE_BET_LIMIT + level * PLAYER_BET_LIMIT_PER_UPGRADE


def set_house_owner_id(owner_id: int) -> None:
    if owner_id != BOT_OWNER_ID:
        raise ValueError("O proprietário da casa principal é definido pelo BOT_OWNER_ID.")
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute(
            """
            INSERT INTO casino_settings (setting, value) VALUES ('house_owner_id', ?)
            ON CONFLICT(setting) DO UPDATE SET value = excluded.value
            """,
            (owner_id,),
        )
        connection.execute(
            """
            INSERT INTO economy_accounts (user_id, balance) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET balance = excluded.balance
            WHERE economy_accounts.balance = 0
                AND economy_accounts.total_earned = 0
                AND economy_accounts.total_lost = 0
            """,
            (owner_id, MAIN_HOUSE_STARTING_BALANCE),
        )


def get_house_owner_id() -> int:
    return BOT_OWNER_ID


def increment_house_stat(
    connection: sqlite3.Connection,
    setting: str,
    amount: int = 1,
) -> None:
    if setting not in {
        "main_house_games",
        "main_house_npc_games",
        "main_house_player_bet_volume",
        "main_house_player_bet_count",
        "main_house_player_bet_earned",
        "main_house_player_bet_lost",
    }:
        raise ValueError(f"Estatística da casa desconhecida: {setting}")
    connection.execute(
        "UPDATE casino_settings SET value = value + ? WHERE setting = ?",
        (amount, setting),
    )


def record_main_house_player_bet(
    connection: sqlite3.Connection,
    volume: int,
    count: int,
    house_change: int,
) -> None:
    if volume < 0 or count < 0:
        raise ValueError("As métricas da aposta não podem ser negativas.")
    increment_house_stat(connection, "main_house_player_bet_volume", volume)
    increment_house_stat(connection, "main_house_player_bet_count", count)
    if house_change > 0:
        increment_house_stat(
            connection,
            "main_house_player_bet_earned",
            house_change,
        )
    elif house_change < 0:
        increment_house_stat(
            connection,
            "main_house_player_bet_lost",
            -house_change,
        )


def get_main_house_status() -> dict[str, int]:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        account = connection.execute(
            """
            SELECT balance, total_earned, total_lost
            FROM economy_accounts WHERE user_id = ?
            """,
            (BOT_OWNER_ID,),
        ).fetchone()
        house_stats = dict(
            connection.execute(
                """
                SELECT setting, value FROM casino_settings
                WHERE setting IN (
                    'main_house_games', 'main_house_npc_games', 'main_house_npcs',
                    'main_house_upgrade_costs_paid',
                    'main_house_player_bet_volume',
                    'main_house_player_bet_count',
                    'main_house_player_bet_earned',
                    'main_house_player_bet_lost',
                    'main_house_npc_count_upgrade_level',
                    'main_house_npc_count_upgrade_costs_paid',
                    'main_house_npc_bet_upgrade_level',
                    'main_house_npc_bet_upgrade_costs_paid'
                )
                """
            ).fetchall()
        )
        reservations = connection.execute(
            """
            SELECT COALESCE(SUM(exposure), 0) FROM house_bet_reservations
            WHERE house_owner_id = ?
            """,
            (BOT_OWNER_ID,),
        ).fetchone()[0]
        casino_count, local_treasury = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(treasury), 0) FROM guild_casinos"
        ).fetchone()
    balance, total_earned, total_lost = account or (0, 0, 0)
    npc_count_upgrade_level = house_stats.get(
        "main_house_npc_count_upgrade_level",
        0,
    )
    npc_bet_upgrade_level = house_stats.get(
        "main_house_npc_bet_upgrade_level",
        0,
    )
    npc_count = house_stats.get("main_house_npcs", DEFAULT_MAIN_HOUSE_NPCS)
    npc_bet_min, npc_bet_max = main_house_npc_bet_range(
        npc_bet_upgrade_level
    )
    return {
        "balance": balance,
        "total_earned": total_earned,
        "total_lost": total_lost,
        "games": house_stats.get("main_house_games", 0),
        "npc_games": house_stats.get("main_house_npc_games", 0),
        "player_bet_volume": house_stats.get(
            "main_house_player_bet_volume",
            0,
        ),
        "player_bet_count": house_stats.get(
            "main_house_player_bet_count",
            0,
        ),
        "player_bet_earned": house_stats.get(
            "main_house_player_bet_earned",
            0,
        ),
        "player_bet_lost": house_stats.get(
            "main_house_player_bet_lost",
            0,
        ),
        "npc_count": npc_count,
        "npc_count_upgrade_level": npc_count_upgrade_level,
        "npc_bet_upgrade_level": npc_bet_upgrade_level,
        "upgrade_costs_paid": house_stats.get(
            "main_house_upgrade_costs_paid",
            0,
        )
        + house_stats.get("main_house_npc_count_upgrade_costs_paid", 0)
        + house_stats.get("main_house_npc_bet_upgrade_costs_paid", 0),
        "npc_count_upgrade_costs_paid": house_stats.get(
            "main_house_npc_count_upgrade_costs_paid",
            0,
        ),
        "npc_bet_upgrade_costs_paid": house_stats.get(
            "main_house_npc_bet_upgrade_costs_paid",
            0,
        ),
        "next_npc_count_upgrade_cost": (
            main_house_upgrade_cost(npc_count_upgrade_level)
            if npc_count_upgrade_level < MAIN_HOUSE_UPGRADE_MAX_LEVEL
            and npc_count < CASINO_MAX_NPCS
            else 0
        ),
        "next_npc_bet_upgrade_cost": (
            main_house_upgrade_cost(npc_bet_upgrade_level)
            if npc_bet_upgrade_level < MAIN_HOUSE_UPGRADE_MAX_LEVEL
            else 0
        ),
        "npc_bet_min": npc_bet_min,
        "npc_bet_max": npc_bet_max,
        "reservations": reservations,
        "casino_count": casino_count,
        "local_treasury": local_treasury,
    }


def main_house_upgrade_cost(level: int) -> int:
    return (
        MAIN_HOUSE_STARTING_BALANCE
        * (level + 1)
        * MAIN_HOUSE_UPGRADE_COST_PERCENT_PER_LEVEL
        // 100
    )


def main_house_npc_bet_range(level: int) -> tuple[int, int]:
    return (
        MAIN_HOUSE_NPC_BET_MIN * (level + 1),
        MAIN_HOUSE_NPC_BET_MAX * (level + 1),
    )


def guild_casino_npc_bet_range(tax_percent: int) -> tuple[int, int]:
    if not 0 <= tax_percent <= 50:
        raise ValueError("A taxa do cassino precisa estar entre 0 e 50%.")
    net_multiplier = 100 - tax_percent
    minimum_bet = (
        CASINO_NPC_MIN_NET_EARNINGS * 100 + net_multiplier - 1
    ) // net_multiplier
    return (
        minimum_bet,
        minimum_bet * CASINO_NPC_BET_MAX_MULTIPLIER,
    )


def upgrade_main_house(
    user_id: int,
    upgrade_type: str,
    expected_level: int | None = None,
    expected_npc_count: int | None = None,
) -> tuple[str, int, int, int, int]:
    if user_id != BOT_OWNER_ID:
        return "not_owner", 0, 0, 0, 0
    if upgrade_type not in {"npc_count", "npc_bet"}:
        raise ValueError(f"Tipo de upgrade da casa principal inválido: {upgrade_type}")

    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        settings = dict(
            connection.execute(
                """
                SELECT setting, value FROM casino_settings
                WHERE setting IN (
                    'main_house_npcs', 'main_house_upgrade_costs_paid',
                    'main_house_npc_count_upgrade_level',
                    'main_house_npc_count_upgrade_costs_paid',
                    'main_house_npc_bet_upgrade_level',
                    'main_house_npc_bet_upgrade_costs_paid'
                )
                """
            ).fetchall()
        )
        npc_count = settings["main_house_npcs"]
        if upgrade_type == "npc_count":
            level_setting = "main_house_npc_count_upgrade_level"
            costs_setting = "main_house_npc_count_upgrade_costs_paid"
            level = settings[level_setting]
            if npc_count >= CASINO_MAX_NPCS:
                return "max_count", 0, level, npc_count, 0
        else:
            level_setting = "main_house_npc_bet_upgrade_level"
            costs_setting = "main_house_npc_bet_upgrade_costs_paid"
            level = settings[level_setting]

        account = connection.execute(
            "SELECT balance FROM economy_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        balance = account[0] if account is not None else 0
        if (
            expected_level is not None
            and level != expected_level
            or expected_npc_count is not None
            and npc_count != expected_npc_count
        ):
            return "changed", balance, level, npc_count, 0
        if level >= MAIN_HOUSE_UPGRADE_MAX_LEVEL:
            return "max_level", balance, level, npc_count, 0

        cost = main_house_upgrade_cost(level)
        if balance < cost:
            return "insufficient", balance, level, npc_count, cost

        new_level = level + 1
        new_npc_count = (
            min(
                CASINO_MAX_NPCS,
                npc_count + MAIN_HOUSE_UPGRADE_NPC_BONUS,
            )
            if upgrade_type == "npc_count"
            else npc_count
        )
        new_costs_paid = settings[costs_setting] + cost
        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = balance - ?, total_lost = total_lost + ?
            WHERE user_id = ?
            """,
            (cost, cost, user_id),
        )
        connection.execute(
            """
            UPDATE casino_settings
            SET value = ? WHERE setting = ?
            """,
            (new_level, level_setting),
        )
        connection.execute(
            "UPDATE casino_settings SET value = ? WHERE setting = ?",
            (new_costs_paid, costs_setting),
        )
        if upgrade_type == "npc_count":
            connection.execute(
                """
                UPDATE casino_settings SET value = ?
                WHERE setting = 'main_house_npcs'
                """,
                (new_npc_count,),
            )
        return "upgraded", balance - cost, new_level, new_npc_count, cost


def get_casino_settings() -> tuple[int, int]:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        settings = dict(
            connection.execute(
                """
                SELECT setting, value FROM casino_settings
                WHERE setting IN ('creation_fee', 'tax_percent')
                """
            ).fetchall()
        )
    return (
        settings["creation_fee"],
        settings["tax_percent"],
    )


def update_casino_settings(
    *,
    creation_fee: int | None = None,
    tax_percent: int | None = None,
) -> None:
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        if creation_fee is not None:
            connection.execute(
                "UPDATE casino_settings SET value = ? WHERE setting = 'creation_fee'",
                (creation_fee,),
            )
        if tax_percent is not None:
            connection.execute(
                "UPDATE casino_settings SET value = ? WHERE setting = 'tax_percent'",
                (tax_percent,),
            )


def format_coins(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")


async def send_bet_result(
    interaction: discord.Interaction,
    *,
    game: str,
    bet: int,
    choice: str,
    result: str,
    payout: int,
    balance: int,
) -> None:
    net_change = payout - bet if payout else -bet
    net_sign = "+" if net_change > 0 else ""
    won = payout > 0
    embed = discord.Embed(
        title=f"{'🎉 VOCÊ GANHOU!' if won else '❌ VOCÊ PERDEU'} — {game}",
        description=result,
        color=discord.Color.green() if won else discord.Color.red(),
    )
    embed.add_field(name="Sua aposta", value=choice, inline=False)
    embed.add_field(
        name="🪙 Valor apostado",
        value=f"{format_coins(bet)} moedas",
        inline=True,
    )
    embed.add_field(
        name="💰 Retorno total (inclui aposta)",
        value=f"{format_coins(payout)} moedas",
        inline=True,
    )
    embed.add_field(
        name="📊 Lucro / prejuízo",
        value=f"{net_sign}{format_coins(net_change)} moedas",
        inline=True,
    )
    embed.set_footer(text=f"Saldo atual: {format_coins(balance)} moedas")
    await interaction.response.send_message(embed=embed)


def get_leaderboard(user_ids: list[int]) -> list[tuple[int, int, int, int]]:
    accounts: list[tuple[int, int, int, int]] = []
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        owner_setting = connection.execute(
            "SELECT value FROM casino_settings WHERE setting = 'house_owner_id'"
        ).fetchone()
        house_owner_id = owner_setting[0] if owner_setting else None
        for start in range(0, len(user_ids), 900):
            batch = user_ids[start : start + 900]
            placeholders = ",".join("?" for _ in batch)
            accounts.extend(
                connection.execute(
                    f"""
                    SELECT user_id, balance, total_earned, total_lost
                    FROM economy_accounts
                    WHERE user_id IN ({placeholders})
                    """,
                    batch,
                ).fetchall()
            )

    if house_owner_id is not None:
        accounts = [
            account for account in accounts if account[0] != house_owner_id
        ]
    return sorted(
        accounts,
        key=lambda account: (-account[1], -account[2], account[3], account[0]),
    )[:10]


def change_balance(user_id: int, amount: int) -> tuple[bool, int]:
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            (user_id,),
        )
        if amount < 0:
            updated = connection.execute(
                """
                UPDATE economy_accounts
                SET balance = balance + ?, total_lost = total_lost + ?
                WHERE user_id = ? AND balance >= ?
                """,
                (amount, -amount, user_id, -amount),
            )
            if updated.rowcount == 0:
                balance = connection.execute(
                    "SELECT balance FROM economy_accounts WHERE user_id = ?",
                    (user_id,),
                ).fetchone()[0]
                return False, balance
        else:
            connection.execute(
                """
                UPDATE economy_accounts
                SET balance = balance + ?, total_earned = total_earned + ?
                WHERE user_id = ?
                """,
                (amount, amount, user_id),
            )

        balance = connection.execute(
            "SELECT balance FROM economy_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        return True, balance


def record_bet_activity(
    connection: sqlite3.Connection,
    user_id: int,
    amount: int,
    guild_id: int | None = None,
) -> None:
    connection.execute(
        """
        UPDATE economy_accounts
        SET total_bet_volume = total_bet_volume + ?,
            total_bet_count = total_bet_count + 1
        WHERE user_id = ?
        """,
        (amount, user_id),
    )
    if guild_id is not None:
        connection.execute(
            """
            UPDATE guild_casino_accounts
            SET total_bet_volume = total_bet_volume + ?,
                total_bet_count = total_bet_count + 1
            WHERE guild_id = ? AND user_id = ?
            """,
            (amount, guild_id, user_id),
        )


def settle_house_bet(
    user_id: int,
    house_owner_id: int,
    bet: int,
    payout: int,
) -> tuple[bool, int, int]:
    if user_id == house_owner_id:
        return False, get_balance(user_id), get_balance(house_owner_id)
    if bet <= 0 or payout < 0:
        raise ValueError("A aposta precisa ser positiva e o retorno não pode ser negativo.")

    player_change = payout - bet
    house_change = -player_change
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            ((user_id,), (house_owner_id,)),
        )
        balances = {
            account_id: balance
            for account_id, balance in connection.execute(
                """
                SELECT user_id, balance FROM economy_accounts
                WHERE user_id IN (?, ?)
                """,
                (user_id, house_owner_id),
            )
        }
        player_balance = balances[user_id]
        house_balance = balances[house_owner_id]
        if player_balance < bet:
            return False, player_balance, house_balance

        reservations = connection.execute(
            """
            SELECT COALESCE(SUM(exposure), 0) FROM house_bet_reservations
            WHERE house_owner_id = ?
            """,
            (house_owner_id,),
        ).fetchone()[0]
        if house_change < 0 and house_balance - reservations < -house_change:
            return False, player_balance, house_balance

        record_bet_activity(connection, user_id, bet)
        record_main_house_player_bet(connection, bet, 1, house_change)
        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = balance + ?,
                total_earned = total_earned + ?,
                total_lost = total_lost + ?
            WHERE user_id = ?
            """,
            (
                player_change,
                max(player_change, 0),
                max(-player_change, 0),
                user_id,
            ),
        )
        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = balance + ?,
                total_earned = total_earned + ?,
                total_lost = total_lost + ?
            WHERE user_id = ?
            """,
            (
                house_change,
                max(house_change, 0),
                max(-house_change, 0),
                house_owner_id,
            ),
        )
        increment_house_stat(connection, "main_house_games")
        player_balance += player_change
        house_balance += house_change
        return True, player_balance, house_balance


def reserve_blackjack_bet(
    user_id: int,
    house_owner_id: int,
    bet: int,
) -> tuple[bool, int, str]:
    if user_id == house_owner_id:
        return False, get_balance(user_id), "owner"
    if bet <= 0:
        raise ValueError("A aposta precisa ser positiva.")

    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            ((user_id,), (house_owner_id,)),
        )
        player_balance = connection.execute(
            "SELECT balance FROM economy_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        house_balance = connection.execute(
            "SELECT balance FROM economy_accounts WHERE user_id = ?",
            (house_owner_id,),
        ).fetchone()[0]
        bonus_levels = connection.execute(
            """
            SELECT prestige_level + prestige_upgrade_gains
            FROM economy_accounts WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()[0]
        exposure = apply_positive_profit_bonus(bet, bonus_levels)
        reserved = connection.execute(
            """
            SELECT COALESCE(SUM(exposure), 0) FROM house_bet_reservations
            WHERE house_owner_id = ?
            """,
            (house_owner_id,),
        ).fetchone()[0]
        if player_balance < bet:
            return False, player_balance, "player"
        if house_balance - reserved < exposure:
            return False, player_balance, "house"

        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = balance - ?, total_lost = total_lost + ?
            WHERE user_id = ?
            """,
            (bet, bet, user_id),
        )
        reservation = connection.execute(
            """
            INSERT INTO house_bet_reservations
                (user_id, house_owner_id, amount, exposure, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, house_owner_id, bet, exposure, int(time.time())),
        )
        record_bet_activity(connection, user_id, bet)
        return True, player_balance - bet, str(reservation.lastrowid)


def settle_blackjack_bet(
    reservation_id: str,
    user_id: int,
    house_owner_id: int,
    bet: int,
    payout: int,
) -> int:
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        reservation = connection.execute(
            """
            SELECT amount, exposure FROM house_bet_reservations
            WHERE reservation_id = ? AND user_id = ? AND house_owner_id = ?
            """,
            (int(reservation_id), user_id, house_owner_id),
        ).fetchone()
        if reservation is None or reservation[0] != bet:
            raise RuntimeError("A reserva desta partida de blackjack não foi encontrada.")

        house_balance = connection.execute(
            "SELECT balance FROM economy_accounts WHERE user_id = ?",
            (house_owner_id,),
        ).fetchone()[0]
        other_reservations = connection.execute(
            """
            SELECT COALESCE(SUM(exposure), 0) FROM house_bet_reservations
            WHERE house_owner_id = ? AND reservation_id != ?
            """,
            (house_owner_id, int(reservation_id)),
        ).fetchone()[0]
        house_change = bet - payout
        if house_change < 0 and house_balance - other_reservations < -house_change:
            raise RuntimeError(
                "A reserva de blackjack não cobre o prêmio desta partida."
            )
        record_main_house_player_bet(connection, bet, 1, house_change)
        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = balance + ?, total_earned = total_earned + ?
            WHERE user_id = ?
            """,
            (payout, payout, user_id),
        )
        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = balance + ?,
                total_earned = total_earned + ?,
                total_lost = total_lost + ?
            WHERE user_id = ?
            """,
            (
                house_change,
                max(house_change, 0),
                max(-house_change, 0),
                house_owner_id,
            ),
        )
        connection.execute(
            "DELETE FROM house_bet_reservations WHERE reservation_id = ?",
            (int(reservation_id),),
        )
        increment_house_stat(connection, "main_house_games")
        return connection.execute(
            "SELECT balance FROM economy_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]


def place_duel_bets(
    challenger_id: int,
    opponent_id: int,
    amount: int,
) -> tuple[bool, int, int]:
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            ((challenger_id,), (opponent_id,)),
        )
        balances = {
            user_id: balance
            for user_id, balance in connection.execute(
                """
                SELECT user_id, balance FROM economy_accounts
                WHERE user_id IN (?, ?)
                """,
                (challenger_id, opponent_id),
            )
        }
        challenger_balance = balances[challenger_id]
        opponent_balance = balances[opponent_id]
        if challenger_balance < amount or opponent_balance < amount:
            return False, challenger_balance, opponent_balance

        record_bet_activity(connection, challenger_id, amount)
        record_bet_activity(connection, opponent_id, amount)
        connection.executemany(
            """
            UPDATE economy_accounts
            SET balance = balance - ?, total_lost = total_lost + ?
            WHERE user_id = ?
            """,
            (
                (amount, amount, challenger_id),
                (amount, amount, opponent_id),
            ),
        )
        return True, challenger_balance - amount, opponent_balance - amount


def settle_duel_bets(
    challenger_id: int,
    opponent_id: int,
    amount: int,
    winner_id: int | None,
) -> tuple[int, int, int]:
    if winner_id not in (None, challenger_id, opponent_id):
        raise ValueError("O vencedor precisa ser um dos jogadores do desafio.")

    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        house_owner_id = get_house_owner_id()
        connection.execute(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            (house_owner_id,),
        )
        if winner_id is None:
            winner_winnings = 0
            house_change = 0
            connection.executemany(
                """
                UPDATE economy_accounts
                SET balance = balance + ?, total_earned = total_earned + ?
                WHERE user_id = ?
                """,
                (
                    (amount, amount, challenger_id),
                    (amount, amount, opponent_id),
                ),
            )
        else:
            pot = amount * 2
            house_fee = pot * PVP_HOUSE_TAX_PERCENT // 100
            base_winnings = pot - house_fee
            bonus_levels = connection.execute(
                """
                SELECT prestige_level + prestige_upgrade_gains
                FROM economy_accounts WHERE user_id = ?
                """,
                (winner_id,),
            ).fetchone()[0]
            profit = max(0, base_winnings - amount)
            requested_bonus = apply_positive_profit_bonus(
                profit,
                bonus_levels,
            ) - profit
            house_balance = connection.execute(
                "SELECT balance FROM economy_accounts WHERE user_id = ?",
                (house_owner_id,),
            ).fetchone()[0]
            actual_bonus = min(requested_bonus, house_balance + house_fee)
            winner_winnings = base_winnings + actual_bonus
            house_change = house_fee - actual_bonus
            connection.execute(
                """
                UPDATE economy_accounts
                SET balance = balance + ?, total_earned = total_earned + ?
                WHERE user_id = ?
                """,
                (winner_winnings, winner_winnings, winner_id),
            )
            connection.execute(
                """
                UPDATE economy_accounts
                SET balance = balance + ?,
                    total_earned = total_earned + ?,
                    total_lost = total_lost + ?
                WHERE user_id = ?
                """,
                (
                    house_change,
                    max(house_change, 0),
                    max(-house_change, 0),
                    house_owner_id,
                ),
            )

        record_main_house_player_bet(
            connection,
            amount * 2,
            2,
            house_change,
        )
        increment_house_stat(connection, "main_house_games")
        balances = {
            user_id: balance
            for user_id, balance in connection.execute(
                """
                SELECT user_id, balance FROM economy_accounts
                WHERE user_id IN (?, ?)
                """,
                (challenger_id, opponent_id),
            )
        }
        return (
            balances[challenger_id],
            balances[opponent_id],
            winner_winnings,
        )


def settle_animal_house_bet(
    user_id: int,
    house_owner_id: int,
    amount: int,
    payout: int,
) -> tuple[str, int, int]:
    now = int(time.time())
    if user_id == house_owner_id:
        return "owner", get_balance(user_id), get_balance(house_owner_id)
    if amount <= 0 or payout < 0:
        raise ValueError("A aposta precisa ser positiva e o retorno não pode ser negativo.")

    player_change = payout - amount
    house_change = -player_change
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            ((user_id,), (house_owner_id,)),
        )
        player = connection.execute(
            """
            SELECT balance, animal_bet_at FROM economy_accounts
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        player_balance, last_bet = player
        if last_bet is not None and now - last_bet < ANIMAL_BET_COOLDOWN:
            return (
                "cooldown",
                player_balance,
                ANIMAL_BET_COOLDOWN - (now - last_bet),
            )
        house_balance = connection.execute(
            "SELECT balance FROM economy_accounts WHERE user_id = ?",
            (house_owner_id,),
        ).fetchone()[0]
        reservations = connection.execute(
            """
            SELECT COALESCE(SUM(exposure), 0) FROM house_bet_reservations
            WHERE house_owner_id = ?
            """,
            (house_owner_id,),
        ).fetchone()[0]
        if player_balance < amount:
            return "insufficient", player_balance, 0
        if house_change < 0 and house_balance - reservations < -house_change:
            return "house", player_balance, house_balance

        record_bet_activity(connection, user_id, amount)
        record_main_house_player_bet(connection, amount, 1, house_change)
        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = balance + ?,
                total_earned = total_earned + ?,
                total_lost = total_lost + ?,
                animal_bet_at = ?
            WHERE user_id = ?
            """,
            (
                player_change,
                max(player_change, 0),
                max(-player_change, 0),
                now,
                user_id,
            ),
        )
        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = balance + ?,
                total_earned = total_earned + ?,
                total_lost = total_lost + ?
            WHERE user_id = ?
            """,
            (
                house_change,
                max(house_change, 0),
                max(-house_change, 0),
                house_owner_id,
            ),
        )
        increment_house_stat(connection, "main_house_games")
        return "accepted", player_balance + player_change, house_balance + house_change


def get_guild_casino(guild_id: int) -> tuple[int, str, str, int, int] | None:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        casino = connection.execute(
            """
            SELECT owner_id, name, currency_name, treasury, upgrade_level
            FROM guild_casinos WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()
    return casino


def get_guild_casino_status(
    guild_id: int,
) -> tuple[
    int,
    str,
    str,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
] | None:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        return connection.execute(
            """
            SELECT owner_id, name, currency_name, treasury, upgrade_level,
                   npc_count, games_played, npc_games, house_earned,
                   house_lost, tax_paid, upgrade_costs_paid,
                   npc_hiring_costs, rewards_paid, player_bet_volume,
                   player_bet_count, player_bet_earned, player_bet_lost
            FROM guild_casinos WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()


def hire_guild_casino_npcs(
    guild_id: int,
    user_id: int,
    amount: int,
) -> tuple[str, int, int]:
    if amount <= 0:
        raise ValueError("A quantidade de NPCs precisa ser positiva.")

    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        casino = connection.execute(
            """
            SELECT owner_id, treasury, npc_count
            FROM guild_casinos WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()
        if casino is None:
            return "missing", 0, 0

        owner_id, treasury, current_npcs = casino
        if owner_id != user_id:
            return "not_owner", treasury, current_npcs
        if current_npcs + amount > CASINO_MAX_NPCS:
            return "max_npcs", treasury, current_npcs

        cost = amount * CASINO_NPC_HIRE_COST
        if treasury < cost:
            return "insufficient", treasury, current_npcs

        new_npc_count = current_npcs + amount
        new_treasury = treasury - cost
        connection.execute(
            """
            UPDATE guild_casinos
            SET treasury = ?, npc_count = ?, npc_hiring_costs = npc_hiring_costs + ?
            WHERE guild_id = ?
            """,
            (new_treasury, new_npc_count, cost, guild_id),
        )
        return "hired", new_treasury, new_npc_count


def set_main_house_npc_count(amount: int) -> None:
    if not 1 <= amount <= CASINO_MAX_NPCS:
        raise ValueError("A casa principal precisa ter entre 1 e 100 NPCs.")
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute(
            """
            INSERT INTO casino_settings (setting, value)
            VALUES ('main_house_npcs', ?)
            ON CONFLICT(setting) DO UPDATE SET value = excluded.value
            """,
            (amount,),
        )


def npc_interval_seconds(owner_online: bool) -> int:
    if owner_online:
        return random.randint(
            NPC_ONLINE_INTERVAL_MIN_SECONDS,
            NPC_ONLINE_INTERVAL_MAX_SECONDS,
        )
    return NPC_OFFLINE_INTERVAL_SECONDS


def run_npc_betting_cycle(
    now: int | None = None,
    main_house_online: bool = False,
    online_owner_ids_by_guild: dict[int, set[int]] | None = None,
) -> tuple[int, int]:
    current_time = int(time.time()) if now is None else now
    online_owner_ids_by_guild = online_owner_ids_by_guild or {}
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        settings = dict(
            connection.execute(
                """
                SELECT setting, value FROM casino_settings
                WHERE setting IN (
                    'house_owner_id', 'main_house_npcs',
                    'main_house_npc_bet_upgrade_level',
                    'main_house_npc_next_bet_at',
                    'main_house_npc_owner_online', 'tax_percent'
                )
                """
            ).fetchall()
        )
        if "house_owner_id" not in settings:
            return 0, 0

        house_owner_id = settings["house_owner_id"]
        main_npc_count = settings["main_house_npcs"]
        main_npc_bet_min, main_npc_bet_max = main_house_npc_bet_range(
            settings["main_house_npc_bet_upgrade_level"]
        )
        main_house_tax = settings["tax_percent"]
        main_house_next_bet_at = settings["main_house_npc_next_bet_at"]
        previous_main_house_online = bool(
            settings["main_house_npc_owner_online"]
        )
        if previous_main_house_online != main_house_online:
            main_house_next_bet_at = (
                current_time + npc_interval_seconds(main_house_online)
            )
            connection.execute(
                """
                UPDATE casino_settings
                SET value = CASE setting
                    WHEN 'main_house_npc_next_bet_at' THEN ?
                    WHEN 'main_house_npc_owner_online' THEN ?
                END
                WHERE setting IN (
                    'main_house_npc_next_bet_at',
                    'main_house_npc_owner_online'
                )
                """,
                (main_house_next_bet_at, int(main_house_online)),
            )

        connection.execute(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            (house_owner_id,),
        )
        house_balance = connection.execute(
            "SELECT balance FROM economy_accounts WHERE user_id = ?",
            (house_owner_id,),
        ).fetchone()[0]
        main_house_prestige_bonus = connection.execute(
            """
            SELECT COALESCE(SUM(prestige_level), 0)
            FROM economy_accounts WHERE user_id != ?
            """,
            (house_owner_id,),
        ).fetchone()[0]
        reservations = connection.execute(
            """
            SELECT COALESCE(SUM(exposure), 0) FROM house_bet_reservations
            WHERE house_owner_id = ?
            """,
            (house_owner_id,),
        ).fetchone()[0]
        casinos = connection.execute(
            """
            SELECT c.guild_id, c.owner_id, c.treasury, c.upgrade_level,
                   c.npc_count, c.npc_next_bet_at, c.npc_owner_online,
                   COALESCE(a.prestige_level, 0)
            FROM guild_casinos AS c
            LEFT JOIN economy_accounts AS a ON a.user_id = c.owner_id
            """
        ).fetchall()
        casino_progress = {
            guild_id: {
                "treasury": treasury,
                "level": level,
                "npc_count": npc_count,
                "next_bet_at": next_bet_at,
                "owner_online": bool(owner_online),
                "npc_games": 0,
                "house_earned": 0,
                "house_lost": 0,
                "tax_paid": 0,
                "prestige_bonus": owner_prestige,
            }
            for (
                guild_id,
                _,
                treasury,
                level,
                npc_count,
                next_bet_at,
                owner_online,
                owner_prestige,
            ) in casinos
        }

        main_house_earned = 0
        main_house_lost = 0
        main_bets = 0
        local_bets = 0

        if main_house_next_bet_at <= current_time:
            for _ in range(main_npc_count):
                bet = random.randint(main_npc_bet_min, main_npc_bet_max)
                house_change = bet if random.randint(1, 37) > 18 else -bet
                if house_change > 0:
                    house_change = apply_positive_profit_bonus(
                        house_change,
                        main_house_prestige_bonus,
                    )
                if (
                    house_change < 0
                    and house_balance - reservations < -house_change
                ):
                    continue
                house_balance += house_change
                main_house_earned += max(house_change, 0)
                main_house_lost += max(-house_change, 0)
                main_bets += 1
            main_house_next_bet_at = (
                current_time + npc_interval_seconds(main_house_online)
            )
            connection.execute(
                """
                UPDATE casino_settings SET value = ?
                WHERE setting = 'main_house_npc_next_bet_at'
                """,
                (main_house_next_bet_at,),
            )

        for guild_id, owner_id, *_ in casinos:
            progress = casino_progress[guild_id]
            owner_online = owner_id in online_owner_ids_by_guild.get(
                guild_id,
                set(),
            )
            if progress["owner_online"] != owner_online:
                progress["owner_online"] = owner_online
                progress["next_bet_at"] = (
                    current_time + npc_interval_seconds(owner_online)
                )
            if progress["next_bet_at"] > current_time:
                continue

            treasury = progress["treasury"]
            level = progress["level"]
            tax_percent = (
                max(
                    CASINO_MINIMUM_TAX_PERCENT,
                    main_house_tax
                    - level * CASINO_TAX_REDUCTION_PER_LEVEL,
                )
                if main_house_tax > 0
                else 0
            )
            npc_bet_min, npc_bet_max = guild_casino_npc_bet_range(
                tax_percent
            )
            for _ in range(progress["npc_count"]):
                bet = random.randint(npc_bet_min, npc_bet_max)
                house_change = bet if random.randint(1, 37) > 18 else -bet
                if house_change > 0:
                    house_change = apply_positive_profit_bonus(
                        house_change,
                        progress["prestige_bonus"],
                    )
                if house_change < 0:
                    if treasury < -house_change:
                        continue
                    treasury += house_change
                    progress["house_lost"] += -house_change
                else:
                    progress["house_earned"] += house_change
                    tax = (
                        (house_change * tax_percent + 99) // 100
                        if tax_percent > 0
                        else 0
                    )
                    treasury += house_change - tax
                    house_balance += tax
                    main_house_earned += tax
                    progress["tax_paid"] += tax
                local_bets += 1
                progress["npc_games"] += 1
            progress["treasury"] = treasury
            progress["next_bet_at"] = (
                current_time + npc_interval_seconds(owner_online)
            )

        treasury_updates = [
            (
                progress["treasury"],
                progress["npc_games"],
                progress["npc_games"],
                progress["house_earned"],
                progress["house_lost"],
                progress["tax_paid"],
                progress["next_bet_at"],
                int(progress["owner_online"]),
                guild_id,
            )
            for guild_id, progress in casino_progress.items()
        ]

        connection.executemany(
            """
            UPDATE guild_casinos
            SET treasury = ?, games_played = games_played + ?,
                npc_games = npc_games + ?, house_earned = house_earned + ?,
                house_lost = house_lost + ?, tax_paid = tax_paid + ?,
                npc_next_bet_at = ?, npc_owner_online = ?
            WHERE guild_id = ?
            """,
            treasury_updates,
        )
        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = ?, total_earned = total_earned + ?,
                total_lost = total_lost + ?
            WHERE user_id = ?
            """,
            (house_balance, main_house_earned, main_house_lost, house_owner_id),
        )
        increment_house_stat(connection, "main_house_games", main_bets)
        increment_house_stat(connection, "main_house_npc_games", main_bets)
        return main_bets, local_bets


def get_guild_casino_balance(guild_id: int, user_id: int) -> int:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        account = connection.execute(
            """
            SELECT balance FROM guild_casino_accounts
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
    return account[0] if account else 0


def create_guild_casino(
    guild_id: int,
    creator_id: int,
    house_owner_id: int,
    name: str,
    currency_name: str,
) -> tuple[str, int, int]:
    creation_fee, _ = get_casino_settings()
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute(
            "SELECT 1 FROM guild_casinos WHERE guild_id = ?",
            (guild_id,),
        ).fetchone():
            return "exists", get_balance(creator_id), get_balance(house_owner_id)

        connection.executemany(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            ((creator_id,), (house_owner_id,)),
        )
        balances = {
            account_id: balance
            for account_id, balance in connection.execute(
                """
                SELECT user_id, balance FROM economy_accounts
                WHERE user_id IN (?, ?)
                """,
                (creator_id, house_owner_id),
            )
        }
        creator_balance = balances[creator_id]
        house_balance = balances[house_owner_id]
        if creator_id != house_owner_id and creator_balance < creation_fee:
            return "insufficient", creator_balance, house_balance

        if creator_id != house_owner_id:
            connection.execute(
                """
                UPDATE economy_accounts
                SET balance = balance - ?, total_lost = total_lost + ?
                WHERE user_id = ?
                """,
                (creation_fee, creation_fee, creator_id),
            )
            connection.execute(
                """
                UPDATE economy_accounts
                SET balance = balance + ?, total_earned = total_earned + ?
                WHERE user_id = ?
                """,
                (creation_fee, creation_fee, house_owner_id),
            )
            creator_balance -= creation_fee
        connection.execute(
            """
            INSERT INTO guild_casinos
                (
                    guild_id, owner_id, name, currency_name, treasury,
                    npc_next_bet_at
                )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                creator_id,
                name,
                currency_name,
                CASINO_STARTING_TREASURY,
                int(time.time()) + NPC_OFFLINE_INTERVAL_SECONDS,
            ),
        )
        return "created", creator_balance, house_balance + (
            creation_fee if creator_id != house_owner_id else 0
        )


def delete_guild_casino(
    guild_id: int,
    user_id: int,
) -> tuple[str, int, int]:
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        casino = connection.execute(
            """
            SELECT owner_id, treasury
            FROM guild_casinos WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()
        if casino is None:
            return "missing", 0, 0

        owner_id, treasury = casino
        if owner_id != user_id:
            return "not_owner", 0, 0
        if treasury < 0:
            raise RuntimeError(
                f"O caixa do cassino {guild_id} não pode ser negativo."
            )

        connection.execute(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            (user_id,),
        )
        global_balance = connection.execute(
            "SELECT balance FROM economy_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = balance + ?, total_earned = total_earned + ?
            WHERE user_id = ?
            """,
            (treasury, treasury, user_id),
        )
        connection.execute(
            "DELETE FROM guild_casino_accounts WHERE guild_id = ?",
            (guild_id,),
        )
        connection.execute(
            "DELETE FROM guild_casinos WHERE guild_id = ?",
            (guild_id,),
        )
        return "deleted", global_balance + treasury, treasury


def claim_guild_casino_reward(
    guild_id: int,
    user_id: int,
    reward_type: str,
) -> tuple[str, int, int]:
    claim_column, cooldown, reward, _ = CASINO_REWARD_SETTINGS[reward_type]
    now = int(time.time())
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute(
            "SELECT 1 FROM guild_casinos WHERE guild_id = ?",
            (guild_id,),
        ).fetchone() is None:
            return "missing", 0, 0
        connection.execute(
            """
            INSERT OR IGNORE INTO guild_casino_accounts (guild_id, user_id)
            VALUES (?, ?)
            """,
            (guild_id, user_id),
        )
        account = connection.execute(
            f"""
            SELECT balance, {claim_column} FROM guild_casino_accounts
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        balance, last_claim = account
        if last_claim is not None and now - last_claim < cooldown:
            return "cooldown", balance, cooldown - (now - last_claim)
        treasury = connection.execute(
            "SELECT treasury FROM guild_casinos WHERE guild_id = ?",
            (guild_id,),
        ).fetchone()[0]
        if treasury < reward:
            return "insufficient_treasury", balance, 0
        reward_upgrade = connection.execute(
            """
            SELECT prestige_upgrade_rewards FROM economy_accounts
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        if reward_type == "daily" or reward_type == "weekly":
            reward_level = reward_upgrade[0] if reward_upgrade else 0
            reward = (reward * (100 + 10 * reward_level) + 99) // 100
            if treasury < reward:
                return "insufficient_treasury", balance, 0
        connection.execute(
            """
            UPDATE guild_casinos
            SET treasury = treasury - ?, rewards_paid = rewards_paid + ?
            WHERE guild_id = ?
            """,
            (reward, reward, guild_id),
        )
        connection.execute(
            f"""
            UPDATE guild_casino_accounts
            SET balance = balance + ?, total_earned = total_earned + ?,
                {claim_column} = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (reward, reward, now, guild_id, user_id),
        )
        return "claimed", balance + reward, reward


def get_guild_casino_leaderboard(
    guild_id: int,
) -> tuple[str, str, list[tuple[int, int, int, int]]] | None:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        casino = connection.execute(
            "SELECT owner_id, name, currency_name FROM guild_casinos WHERE guild_id = ?",
            (guild_id,),
        ).fetchone()
        if casino is None:
            return None
        owner_id, name, currency_name = casino
        main_house_owner = connection.execute(
            "SELECT value FROM casino_settings WHERE setting = 'house_owner_id'"
        ).fetchone()
        main_house_owner_id = (
            main_house_owner[0] if main_house_owner is not None else -1
        )
        ranking = connection.execute(
            """
            SELECT user_id, balance, total_earned, total_lost
            FROM guild_casino_accounts
            WHERE guild_id = ? AND user_id NOT IN (?, ?)
            ORDER BY balance DESC, total_earned DESC, total_lost ASC, user_id ASC
            LIMIT 10
            """,
            (guild_id, owner_id, main_house_owner_id),
        ).fetchall()
    return name, currency_name, ranking


def upgrade_guild_casino(
    guild_id: int,
    user_id: int,
    expected_level: int | None = None,
) -> tuple[str, int, int, int]:
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        casino = connection.execute(
            """
            SELECT owner_id, treasury, upgrade_level
            FROM guild_casinos WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()
        if casino is None:
            return "missing", 0, 0, 0
        owner_id, treasury, level = casino
        if user_id != owner_id:
            return "not_owner", treasury, level, 0
        if expected_level is not None and level != expected_level:
            return "changed", treasury, level, 0
        if level >= len(CASINO_UPGRADE_COSTS):
            return "max_level", treasury, level, 0
        cost = CASINO_UPGRADE_COSTS[level]
        if treasury < cost:
            return "insufficient", treasury, level, cost
        house_owner = connection.execute(
            "SELECT value FROM casino_settings WHERE setting = 'house_owner_id'"
        ).fetchone()
        if house_owner is None:
            raise RuntimeError("O owner do bot ainda não foi carregado para a banca.")
        house_owner_id = house_owner[0]
        connection.execute(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            (house_owner_id,),
        )
        new_level = level + 1
        new_treasury = treasury - cost
        connection.execute(
            """
            UPDATE guild_casinos
            SET treasury = ?, upgrade_level = ?,
                upgrade_costs_paid = upgrade_costs_paid + ?
            WHERE guild_id = ?
            """,
            (new_treasury, new_level, cost, guild_id),
        )
        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = balance + ?, total_earned = total_earned + ?
            WHERE user_id = ?
            """,
            (cost, cost, house_owner_id),
        )
        return "upgraded", new_treasury, new_level, cost


def settle_guild_casino_bet(
    guild_id: int,
    user_id: int,
    house_owner_id: int,
    bet: int,
    payout: int,
) -> tuple[str, int, int, int, int]:
    if bet <= 0 or payout < 0:
        raise ValueError("A aposta precisa ser positiva e o retorno não pode ser negativo.")
    player_change = payout - bet
    casino_gain = -player_change

    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        casino = connection.execute(
            """
            SELECT treasury, upgrade_level
            FROM guild_casinos WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()
        if casino is None:
            return "missing", 0, 0, 0, 0
        treasury, level = casino
        connection.execute(
            """
            INSERT OR IGNORE INTO guild_casino_accounts (guild_id, user_id)
            VALUES (?, ?)
            """,
            (guild_id, user_id),
        )
        player_balance = connection.execute(
            """
            SELECT balance FROM guild_casino_accounts
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()[0]
        if player_balance < bet:
            return "insufficient_player", player_balance, treasury, 0, 0

        base_tax = connection.execute(
            "SELECT value FROM casino_settings WHERE setting = 'tax_percent'"
        ).fetchone()[0]
        tax_percent = (
            max(
                CASINO_MINIMUM_TAX_PERCENT,
                base_tax - level * CASINO_TAX_REDUCTION_PER_LEVEL,
            )
            if base_tax > 0
            else 0
        )
        tax = (
            (casino_gain * tax_percent + 99) // 100
            if casino_gain > 0 and tax_percent > 0
            else 0
        )
        treasury_change = casino_gain - tax
        if treasury + treasury_change < 0:
            return "insufficient_treasury", player_balance, treasury, tax_percent, 0

        connection.execute(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            (user_id,),
        )
        record_bet_activity(connection, user_id, bet, guild_id)
        connection.execute(
            """
            UPDATE guild_casino_accounts
            SET balance = balance + ?,
                total_earned = total_earned + ?,
                total_lost = total_lost + ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (
                player_change,
                max(player_change, 0),
                max(-player_change, 0),
                guild_id,
                user_id,
            ),
        )
        record_main_house_player_bet(connection, bet, 1, tax)
        connection.execute(
            """
            UPDATE guild_casinos
            SET treasury = treasury + ?, games_played = games_played + 1,
                house_earned = house_earned + ?,
                house_lost = house_lost + ?, tax_paid = tax_paid + ?,
                player_bet_volume = player_bet_volume + ?,
                player_bet_count = player_bet_count + 1,
                player_bet_earned = player_bet_earned + ?,
                player_bet_lost = player_bet_lost + ?
            WHERE guild_id = ?
            """,
            (
                treasury_change,
                max(casino_gain, 0),
                max(-casino_gain, 0),
                tax,
                bet,
                max(casino_gain, 0),
                max(-casino_gain, 0),
                guild_id,
            ),
        )
        if tax:
            connection.execute(
                "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
                (house_owner_id,),
            )
            connection.execute(
                """
                UPDATE economy_accounts
                SET balance = balance + ?, total_earned = total_earned + ?
                WHERE user_id = ?
                """,
                (tax, tax, house_owner_id),
            )
        return "settled", player_balance + player_change, treasury + treasury_change, tax_percent, tax


def place_animal_bet(user_id: int, amount: int) -> tuple[str, int, int]:
    now = int(time.time())
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            (user_id,),
        )
        account = connection.execute(
            "SELECT balance, animal_bet_at FROM economy_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        balance, last_bet = account
        if last_bet is not None and now - last_bet < ANIMAL_BET_COOLDOWN:
            return "cooldown", balance, ANIMAL_BET_COOLDOWN - (now - last_bet)
        if balance < amount:
            return "insufficient", balance, 0

        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = balance - ?, total_lost = total_lost + ?,
                animal_bet_at = ?
            WHERE user_id = ?
            """,
            (amount, amount, now, user_id),
        )
        record_bet_activity(connection, user_id, amount)
        return "accepted", balance - amount, 0


def claim_reward(user_id: int, reward_type: str) -> tuple[bool, int, int]:
    claim_column, cooldown, minimum, maximum, _ = REWARD_SETTINGS[reward_type]
    now = int(time.time())

    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            (user_id,),
        )
        last_claim = connection.execute(
            f"SELECT {claim_column} FROM economy_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        if last_claim is not None and now - last_claim < cooldown:
            remaining = cooldown - (now - last_claim)
            balance = connection.execute(
                "SELECT balance FROM economy_accounts WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
            return False, balance, remaining

        reward = random.randint(minimum, maximum)
        if reward_type in ("daily", "weekly"):
            reward_upgrade = connection.execute(
                """
                SELECT prestige_upgrade_rewards
                FROM economy_accounts WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()[0]
            reward = (reward * (100 + 10 * reward_upgrade) + 99) // 100
        connection.execute(
            f"""
            UPDATE economy_accounts
            SET balance = balance + ?, total_earned = total_earned + ?,
                {claim_column} = ?
            WHERE user_id = ?
            """,
            (reward, reward, now, user_id),
        )
        balance = connection.execute(
            "SELECT balance FROM economy_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        return True, balance, reward


def reset_player_data(reset_type: str) -> tuple[int, int]:
    if reset_type not in {"balances", "reward_cooldowns"}:
        raise ValueError(f"Tipo de reset inválido: {reset_type}")

    with closing(
        sqlite3.connect(ECONOMY_DB_PATH, timeout=10)
    ) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        if reset_type == "balances":
            global_rows = connection.execute(
                """
                UPDATE economy_accounts SET balance = 0
                WHERE user_id != ? AND balance != 0
                """,
                (BOT_OWNER_ID,),
            ).rowcount
            local_rows = connection.execute(
                """
                UPDATE guild_casino_accounts SET balance = 0
                WHERE user_id != ? AND balance != 0
                """,
                (BOT_OWNER_ID,),
            ).rowcount
            return global_rows, local_rows

        global_rows = connection.execute(
            """
            UPDATE economy_accounts
            SET daily_claim_at = NULL,
                weekly_claim_at = NULL,
                monthly_claim_at = NULL
            WHERE daily_claim_at IS NOT NULL
               OR weekly_claim_at IS NOT NULL
               OR monthly_claim_at IS NOT NULL
            """
        ).rowcount
        local_rows = connection.execute(
            """
            UPDATE guild_casino_accounts
            SET daily_claim_at = NULL, weekly_claim_at = NULL
            WHERE daily_claim_at IS NOT NULL OR weekly_claim_at IS NOT NULL
            """
        ).rowcount
        return global_rows, local_rows


def format_remaining(seconds: int) -> str:
    minutes = max(1, (seconds + 59) // 60)
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}min"
    return f"{minutes}min"


def reward_cooldown_status(
    last_claim_at: int | None,
    cooldown: int,
    now: int | None = None,
) -> str:
    if last_claim_at is None:
        return "Disponível agora"
    current_time = int(time.time()) if now is None else now
    remaining = cooldown - (current_time - last_claim_at)
    if remaining <= 0:
        return "Disponível agora"
    return f"em {format_remaining(remaining)}"


def hand_total(cards: list[str]) -> int:
    total = sum(
        10 if card in ("J", "Q", "K") else 11 if card == "A" else int(card)
        for card in cards
    )
    aces = cards.count("A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


class BlackjackView(discord.ui.View):
    def __init__(
        self,
        user: discord.User | discord.Member,
        bet: int,
        player_cards: list[str],
        dealer_cards: list[str],
        balance: int,
        house_owner_id: int,
        reservation_id: str,
    ) -> None:
        super().__init__(timeout=90)
        self.user = user
        self.bet = bet
        self.player_cards = player_cards
        self.dealer_cards = dealer_cards
        self.balance = balance
        self.house_owner_id = house_owner_id
        self.reservation_id = reservation_id
        self.message: discord.InteractionMessage | None = None
        self.finished = False
        self.result = "Escolha uma ação nos botões abaixo."
        self.payout = 0
        self.net_change = 0
        self.turn_lock = asyncio.Lock()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "Esta partida pertence a outra pessoa.",
                ephemeral=True,
            )
            return False
        return True

    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=(
                "🎉 Você venceu!"
                if self.finished and self.net_change > 0
                else "❌ Você perdeu"
                if self.finished and self.net_change < 0
                else "🏁 Partida encerrada"
                if self.finished
                else "🃏 Blackjack"
            ),
            description=self.result,
            color=(
                discord.Color.green()
                if self.finished and self.net_change > 0
                else discord.Color.red()
                if self.finished and self.net_change < 0
                else discord.Color.gold()
                if self.finished
                else discord.Color.blue()
            ),
        )
        embed.add_field(
            name=f"Suas cartas — {hand_total(self.player_cards)}",
            value="  •  ".join(self.player_cards),
            inline=True,
        )
        if self.finished:
            dealer_cards = "  •  ".join(self.dealer_cards)
            dealer_total = hand_total(self.dealer_cards)
        else:
            dealer_cards = f"{self.dealer_cards[0]}  •  🂠"
            dealer_total = "carta oculta"
        embed.add_field(
            name=f"Dealer — {dealer_total}",
            value=dealer_cards,
            inline=True,
        )
        embed.add_field(
            name="Aposta",
            value=f"🪙 {format_coins(self.bet)} moedas",
            inline=False,
        )
        if self.finished:
            embed.add_field(
                name="💰 Retorno total (inclui aposta)",
                value=f"{format_coins(self.payout)} moedas",
                inline=True,
            )
            net_sign = "+" if self.net_change > 0 else ""
            embed.add_field(
                name="📊 Lucro / prejuízo",
                value=f"{net_sign}{format_coins(self.net_change)} moedas",
                inline=True,
            )
        else:
            embed.description = (
                f"{self.result}\n\n"
                "Use **Comprar carta** para pedir outra ou **Parar** "
                "para encerrar sua mão. O dealer compra até chegar a 17."
            )
        embed.set_footer(
            text=f"Saldo atual: {format_coins(self.balance)} moedas"
        )
        return embed

    def _resolve(self) -> None:
        player_total = hand_total(self.player_cards)
        if player_total > 21:
            self.result = "Você estourou! O dealer venceu e a aposta foi perdida."
            self.payout = 0
        else:
            while hand_total(self.dealer_cards) < 17:
                self.dealer_cards.append(
                    random.choice(
                        ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
                    )
                )

            dealer_total = hand_total(self.dealer_cards)
            if dealer_total > 21 or player_total > dealer_total:
                self.payout = self.bet * 2
                self.result = (
                    f"🏆 Você venceu! Sua mão fez **{player_total}** "
                    f"contra **{dealer_total}** do dealer."
                )
            elif player_total == dealer_total:
                self.payout = self.bet
                self.result = (
                    f"🤝 Empate: ambos fizeram **{player_total}**. "
                    "A aposta foi devolvida."
                )
            else:
                self.payout = 0
                self.result = (
                    f"❌ O dealer venceu com **{dealer_total}** contra "
                    f"**{player_total}**. A aposta foi perdida."
                )

            self.payout = adjust_player_bet_payout(
                self.user.id,
                self.bet,
                self.payout,
            )
            self.balance = settle_blackjack_bet(
            self.reservation_id,
            self.user.id,
            self.house_owner_id,
            self.bet,
            self.payout,
        )
        self.net_change = self.payout - self.bet
        self.finished = True
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    async def _apply_action(
        self,
        interaction: discord.Interaction,
        *,
        draw_card: bool,
    ) -> None:
        async with self.turn_lock:
            if self.finished:
                await interaction.response.send_message(
                    "Esta partida já terminou.",
                    ephemeral=True,
                )
                return

            if draw_card:
                cards = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
                self.player_cards.append(random.choice(cards))
                player_total = hand_total(self.player_cards)
                if player_total > 21:
                    self._resolve()
                elif player_total == 21:
                    self.result = "Você chegou a 21! Vez do dealer..."
                    self._resolve()
                else:
                    self.result = "Carta comprada. Compre outra ou pare."
            else:
                self._resolve()

            await interaction.response.edit_message(
                embed=self.create_embed(),
                view=None if self.finished else self,
            )

    @discord.ui.button(
        label="Comprar carta",
        emoji="🃏",
        style=discord.ButtonStyle.primary,
    )
    async def hit(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        button.label = "Comprar outra"
        await self._apply_action(interaction, draw_card=True)

    @discord.ui.button(
        label="Parar",
        emoji="✋",
        style=discord.ButtonStyle.secondary,
    )
    async def stand(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        button.label = "Parar"
        await self._apply_action(interaction, draw_card=False)

    async def on_timeout(self) -> None:
        async with self.turn_lock:
            if self.finished:
                return

            self.finished = True
            self.balance = settle_blackjack_bet(
                self.reservation_id,
                self.user.id,
                self.house_owner_id,
                self.bet,
                self.bet,
            )
            self.payout = self.bet
            self.net_change = 0
            self.result = "Partida encerrada por inatividade. Sua aposta foi devolvida."
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True

            if self.message is not None:
                await self.message.edit(embed=self.create_embed(), view=self)


class PrestigeConfirmView(discord.ui.View):
    def __init__(self, user_id: int) -> None:
        super().__init__(timeout=60)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            "Este botão pertence a outra pessoa.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="Confirmar prestígio", style=discord.ButtonStyle.success)
    async def confirm(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        status, _, level, points, requirement = prestige_player(self.user_id)
        if status == "prestiged":
            if interaction.guild is not None:
                await synchronize_casino_autoroles(interaction.guild)
            else:
                await synchronize_user_autoroles(self.user_id)
            message = (
                f"✨ Prestígio **{level}** alcançado! Seu saldo global e saldos "
                f"nos cassinos foram zerados. Você ganhou **{level} pontos** "
                f"(total: **{points}**). Seu histórico e cooldowns foram preservados."
            )
        elif status == "insufficient":
            message = (
                f"Seu saldo mudou antes da confirmação. Você precisa de "
                f"{format_coins(requirement)} moedas globais para prestigiar."
            )
        elif status == "active_bet":
            message = (
                "Encerre sua partida de blackjack antes de prestigiar; "
                "a aposta ainda está reservada."
            )
        elif status == "house_owner":
            message = "A conta da casa principal não pode ser prestigada."
        else:
            message = f"Você já alcançou o prestígio máximo ({PRESTIGE_MAX_LEVEL})."
        await interaction.response.edit_message(content=message, embed=None, view=None)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        await interaction.response.edit_message(
            content="Prestígio cancelado.",
            embed=None,
            view=None,
        )


class PrestigeUpgradeView(discord.ui.View):
    def __init__(self, user_id: int, upgrade_key: str) -> None:
        super().__init__(timeout=60)
        self.user_id = user_id
        self.upgrade_key = upgrade_key

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            "Este botão pertence a outra pessoa.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="Comprar upgrade", style=discord.ButtonStyle.success)
    async def confirm(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        status, points, level, cost = purchase_prestige_upgrade(
            self.user_id,
            self.upgrade_key,
        )
        if status == "upgraded":
            upgrade_name = PRESTIGE_UPGRADES[self.upgrade_key][1]
            message = (
                f"✅ Upgrade **{upgrade_name}** elevado ao nível **{level}** "
                f"por **{cost} pontos**. Saldo: **{points} pontos**."
            )
            next_cost = level + 1
            if (
                level < PRESTIGE_MAX_UPGRADE_LEVEL
                and points >= next_cost
            ):
                message += (
                    f"\n\nVocê já pode comprar o nível **{level + 1}** "
                    f"por **{next_cost} pontos**. Deseja continuar?"
                )
                next_view = PrestigeUpgradeView(
                    self.user_id,
                    self.upgrade_key,
                )
                await interaction.response.edit_message(
                    content=message,
                    embed=None,
                    view=next_view,
                )
                self.stop()
                return
            if level < PRESTIGE_MAX_UPGRADE_LEVEL:
                message += (
                    f"\nPróximo nível: **{level + 1}**, custo de "
                    f"**{next_cost} pontos**."
                )
        elif status == "insufficient":
            message = (
                f"Pontos insuficientes: a melhoria custa **{cost} pontos** "
                f"e você tem **{points}**."
            )
        elif status == "active_bet":
            message = (
                "Encerre sua partida de blackjack antes de comprar upgrades."
            )
        elif status == "house_owner":
            message = "A casa principal não usa upgrades de prestígio dos jogadores."
        else:
            message = (
                f"Este upgrade já está no nível máximo "
                f"({PRESTIGE_MAX_UPGRADE_LEVEL})."
            )
        await interaction.response.edit_message(content=message, embed=None, view=None)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        await interaction.response.edit_message(
            content="Compra cancelada.",
            embed=None,
            view=None,
        )


class DeleteGuildCasinoView(discord.ui.View):
    def __init__(
        self,
        guild_id: int,
        owner_id: int,
        casino_name: str,
    ) -> None:
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.casino_name = casino_name

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "Somente quem iniciou a exclusão pode confirmá-la.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(
        label="Excluir cassino",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.defer()
        status, balance, treasury = delete_guild_casino(
            self.guild_id,
            interaction.user.id,
        )
        if status == "deleted":
            if interaction.guild is not None:
                await synchronize_casino_autoroles(interaction.guild)
            message = (
                f"🗑️ O cassino **{self.casino_name}** foi excluído. "
                f"As {format_coins(treasury)} moedas locais restantes foram "
                f"convertidas na proporção de 1:1 para o saldo global do dono. "
                f"Novo saldo global: **{format_coins(balance)} moedas**. "
                "Os saldos locais dos jogadores e o histórico do cassino "
                "foram apagados."
            )
        elif status == "missing":
            message = "Este servidor não possui mais um cassino para excluir."
        else:
            message = (
                "A propriedade do cassino mudou. Somente o dono atual pode "
                "excluí-lo."
            )
        button.disabled = True
        self.stop()
        await interaction.edit_original_response(
            content=message,
            embed=None,
            view=None,
        )

    @discord.ui.button(
        label="Cancelar",
        emoji="✖️",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        button.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content="Exclusão cancelada; nenhum dado foi alterado.",
            embed=None,
            view=None,
        )


def slot_payout(reels: list[str], bet: int) -> tuple[int, str, int]:
    if len(reels) != 3 or bet <= 0:
        raise ValueError("A máquina exige três símbolos e uma aposta positiva.")

    if reels[0] == reels[1] == reels[2]:
        multiplier = SLOT_TRIPLE_MULTIPLIERS[reels[0]]
        return bet * multiplier, f"Trinca de {reels[0]}", multiplier

    for symbol in SLOT_SYMBOLS:
        if reels.count(symbol) == 2:
            multiplier = SLOT_PAIR_MULTIPLIERS[symbol]
            return bet * multiplier, f"Par de {symbol}", multiplier

    return 0, "Sem combinação premiada", 0


def animal_bet_payout(
    selected_animals: list[str],
    drawn_animal: str,
    bet: int,
) -> tuple[int, float]:
    if not 1 <= len(selected_animals) <= 3:
        raise ValueError("Escolha de um a três animais.")
    if len(set(selected_animals)) != len(selected_animals):
        raise ValueError("Os animais escolhidos precisam ser diferentes.")
    if any(animal not in BETTING_ANIMALS for animal in selected_animals):
        raise ValueError("Um ou mais animais escolhidos são inválidos.")
    if drawn_animal not in BETTING_ANIMALS or bet <= 0:
        raise ValueError("Animal sorteado ou aposta inválidos.")

    multiplier = ANIMAL_BET_MULTIPLIERS[len(selected_animals)]
    payout = bet * 3 // 2 if len(selected_animals) == 3 else bet * int(multiplier)
    return (payout if drawn_animal in selected_animals else 0), multiplier


def draw_slot_symbol(
    draw: ImageDraw.ImageDraw,
    symbol: str,
    center_x: int,
    center_y: int,
    symbol_font: ImageFont.ImageFont,
    scale: int = 1,
) -> None:
    if symbol == "🍒":
        draw.ellipse(
            (center_x - 28 * scale, center_y, center_x, center_y + 34 * scale),
            fill="#ed4264",
        )
        draw.ellipse(
            (center_x - 2 * scale, center_y + 4 * scale, center_x + 26 * scale, center_y + 38 * scale),
            fill="#ff5277",
        )
        draw.line(
            (center_x - 8 * scale, center_y + 5 * scale, center_x + 3 * scale, center_y - 22 * scale, center_x + 19 * scale, center_y - 16 * scale),
            fill="#55c878",
            width=5 * scale,
        )
        draw.ellipse(
            (center_x - 1 * scale, center_y - 25 * scale, center_x + 20 * scale, center_y - 13 * scale),
            fill="#70dc84",
        )
    elif symbol == "🍋":
        draw.ellipse(
            (center_x - 31 * scale, center_y - 19 * scale, center_x + 31 * scale, center_y + 21 * scale),
            fill="#ffdf53",
            outline="#f3ae36",
            width=3 * scale,
        )
        draw.polygon(
            [(center_x - 30 * scale, center_y), (center_x - 39 * scale, center_y - 5 * scale), (center_x - 37 * scale, center_y + 6 * scale)],
            fill="#ffdf53",
        )
        draw.polygon(
            [(center_x + 30 * scale, center_y), (center_x + 39 * scale, center_y - 5 * scale), (center_x + 37 * scale, center_y + 6 * scale)],
            fill="#ffdf53",
        )
    elif symbol == "🔔":
        draw.ellipse(
            (center_x - 25 * scale, center_y - 20 * scale, center_x + 25 * scale, center_y + 24 * scale),
            fill="#ffc94f",
            outline="#e99e32",
            width=3 * scale,
        )
        draw.rectangle(
            (center_x - 25 * scale, center_y, center_x + 25 * scale, center_y + 21 * scale),
            fill="#ffc94f",
        )
        draw.rounded_rectangle(
            (center_x - 32 * scale, center_y + 19 * scale, center_x + 32 * scale, center_y + 29 * scale),
            radius=5 * scale,
            fill="#e99e32",
        )
        draw.ellipse(
            (center_x - 7 * scale, center_y + 26 * scale, center_x + 7 * scale, center_y + 39 * scale),
            fill="#ffdc70",
        )
    elif symbol == "💎":
        draw.polygon(
            [
                (center_x - 34 * scale, center_y - 12 * scale),
                (center_x - 19 * scale, center_y - 30 * scale),
                (center_x + 19 * scale, center_y - 30 * scale),
                (center_x + 34 * scale, center_y - 12 * scale),
                (center_x, center_y + 34 * scale),
            ],
            fill="#48d9ed",
            outline="#b4f5ff",
        )
        draw.line(
            (center_x - 19 * scale, center_y - 28 * scale, center_x, center_y + 30 * scale, center_x + 19 * scale, center_y - 28 * scale),
            fill="#b4f5ff",
            width=2 * scale,
        )
    elif symbol == "⭐":
        points = []
        for point in range(10):
            angle = -90 + point * 36
            radius = (34 if point % 2 == 0 else 15) * scale
            points.append(
                (
                    center_x + int(radius * math.cos(math.radians(angle))),
                    center_y + int(radius * math.sin(math.radians(angle))),
                )
            )
        draw.polygon(points, fill="#ffd84d", outline="#fff0a6")
    else:
        draw.text(
            (center_x, center_y),
            "7",
            font=symbol_font,
            fill="#ff5478",
            anchor="mm",
            stroke_width=2 * scale,
            stroke_fill="#a72850",
        )


def render_slot_gif(reels: list[str], payout: int, multiplier: int) -> io.BytesIO:
    width, height = 600, 330
    background = (18, 23, 48)
    reel_stops = (9, 14, 19)
    frame_count = 20
    frames: list[Image.Image] = []
    font_path = r"C:\Windows\Fonts\arial.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 27)
        caption_font = ImageFont.truetype(font_path, 18)
        small_font = ImageFont.truetype(font_path, 14)
        symbol_font = ImageFont.truetype(font_path, 66)
    except OSError:
        title_font = ImageFont.load_default()
        caption_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
        symbol_font = ImageFont.load_default()

    for frame_index in range(frame_count):
        image = Image.new("RGB", (width, height), background)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (30, 20, width - 30, height - 20),
            radius=28,
            fill="#252c52",
            outline="#f7c957",
            width=5,
        )
        draw.text((width // 2, 54), "CAÇA-NÍQUEL", font=title_font, fill="#ffe18a", anchor="mm")
        draw.rounded_rectangle(
            (67, 82, width - 67, 235),
            radius=20,
            fill="#11152e",
            outline="#d9ad56",
            width=4,
        )

        for reel_index, center_x in enumerate((160, 300, 440)):
            draw.rounded_rectangle(
                (center_x - 57, 96, center_x + 57, 221),
                radius=14,
                fill="#f6f1df",
                outline="#ffffff",
                width=3,
            )
            if frame_index >= reel_stops[reel_index]:
                symbol = reels[reel_index]
            else:
                symbol = random.choice(SLOT_SYMBOLS)
            draw_slot_symbol(draw, symbol, center_x, 157, symbol_font)

        if frame_index == frame_count - 1:
            banner_color = "#53d89a" if payout else "#c6c9d8"
            banner_text = f"PREMIO  x{multiplier}" if payout else "TENTE DE NOVO"
            draw.rounded_rectangle(
                (130, 254, 470, 298),
                radius=18,
                fill="#171b36",
                outline=banner_color,
                width=2,
            )
            draw.text(
                (width // 2, 276),
                banner_text,
                font=caption_font,
                fill=banner_color,
                anchor="mm",
            )
        else:
            draw.text(
                (width // 2, 276),
                "GIRANDO...",
                font=small_font,
                fill="#cbd0e8",
                anchor="mm",
            )

        frames.append(image)

    output = io.BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=[75] * (frame_count - 1) + [1200],
        optimize=False,
        disposal=2,
    )
    output.seek(0)
    return output


initialize_economy()


def get_last_announced_commit() -> str | None:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        state = connection.execute(
            """
            SELECT value FROM bot_update_state
            WHERE setting = 'last_announced_commit'
            """
        ).fetchone()
    return state[0] if state is not None else None


def set_last_announced_commit(commit_hash: str) -> None:
    with closing(
        sqlite3.connect(ECONOMY_DB_PATH, timeout=10)
    ) as connection, connection:
        connection.execute(
            """
            INSERT INTO bot_update_state (setting, value)
            VALUES ('last_announced_commit', ?)
            ON CONFLICT(setting) DO UPDATE SET value = excluded.value
            """,
            (commit_hash,),
        )


def get_git_update_info(
    previous_commit: str | None,
) -> tuple[str, list[str]] | None:
    try:
        head_result = subprocess.run(
            ["git", "-C", PROJECT_DIRECTORY, "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.exception("Não foi possível consultar o commit atual do bot.")
        return None

    if head_result.returncode != 0:
        logger.error(
            "O repositório Git do bot não retornou HEAD: %s",
            head_result.stderr.strip(),
        )
        return None
    head_commit = head_result.stdout.strip()
    if re.fullmatch(r"[0-9a-fA-F]{40,64}", head_commit) is None:
        logger.error("O repositório Git retornou um hash HEAD inválido.")
        return None
    if previous_commit == head_commit:
        return head_commit, []
    if previous_commit is not None and re.fullmatch(
        r"[0-9a-fA-F]{40,64}",
        previous_commit,
    ) is None:
        logger.error("O hash do último commit anunciado está inválido.")
        return None

    revision_range = (
        [head_commit]
        if previous_commit is None
        else [f"{previous_commit}..{head_commit}"]
    )
    max_commits = "1" if previous_commit is None else "11"
    try:
        log_result = subprocess.run(
            [
                "git",
                "-C",
                PROJECT_DIRECTORY,
                "log",
                "--format=%h%x09%s",
                f"--max-count={max_commits}",
                *revision_range,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.exception("Não foi possível ler os commits novos do bot.")
        return None

    if log_result.returncode != 0:
        logger.error(
            "Não foi possível listar os commits novos do bot: %s",
            log_result.stderr.strip(),
        )
        return None
    updates = [
        f"`{commit_hash}` — {subject[:250]}"
        for line in log_result.stdout.splitlines()
        if "\t" in line
        for commit_hash, subject in [line.split("\t", 1)]
    ]
    if not updates:
        logger.error(
            "O commit atual mudou, mas não há commits novos no histórico "
            "desde o último anúncio."
        )
        return None
    if len(updates) > 10:
        updates = updates[:10]
        updates.append(
            "Há mais atualizações; foram listados os 10 commits mais recentes."
        )
    return head_commit, updates


class BotDiscord(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.house_owner_id: int | None = None
        self.npc_betting_task: asyncio.Task[None] | None = None
        self.pending_update_announcement: tuple[str, list[str]] | None = None

    async def setup_hook(self) -> None:
        self.house_owner_id = BOT_OWNER_ID
        set_house_owner_id(self.house_owner_id)

        try:
            previous_commit = get_last_announced_commit()
        except sqlite3.Error:
            logger.exception(
                "Não foi possível carregar o estado dos anúncios de atualização."
            )
            previous_commit = None
        update_info = get_git_update_info(previous_commit)
        if update_info is not None:
            head_commit, updates = update_info
            if previous_commit is None:
                if updates:
                    self.pending_update_announcement = (head_commit, updates)
                else:
                    try:
                        set_last_announced_commit(head_commit)
                    except sqlite3.Error:
                        logger.exception(
                            "Não foi possível inicializar o estado dos anúncios "
                            "de atualização."
                        )
            elif updates:
                self.pending_update_announcement = (head_commit, updates)

        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            try:
                guild = discord.Object(id=int(guild_id))
            except ValueError as error:
                raise RuntimeError("DISCORD_GUILD_ID precisa ser um ID numérico.") from error

            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Sincronizados %d comandos slash no servidor %s.", len(synced), guild_id)
            return

        synced = await self.tree.sync()
        logger.info("Sincronizados %d comandos slash globalmente.", len(synced))

    async def on_ready(self) -> None:
        if self.user is not None:
            logger.info("Bot conectado como %s (%s).", self.user, self.user.id)
        await self.announce_git_updates()
        if self.npc_betting_task is None or self.npc_betting_task.done():
            self.npc_betting_task = asyncio.create_task(
                self.npc_betting_loop(),
                name="npc-betting-loop",
            )

    async def announce_git_updates(self) -> None:
        pending = self.pending_update_announcement
        if pending is None:
            return

        head_commit, updates = pending
        await self.publish_git_updates(head_commit, updates)

    async def publish_git_updates(
        self,
        head_commit: str,
        updates: list[str],
        *,
        mention_role: bool = False,
    ) -> bool:
        channel = self.get_channel(UPDATE_ANNOUNCEMENT_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.fetch_channel(
                    UPDATE_ANNOUNCEMENT_CHANNEL_ID
                )
            except discord.HTTPException as error:
                logger.error(
                    "Não foi possível localizar o canal de anúncios %s.",
                    UPDATE_ANNOUNCEMENT_CHANNEL_ID,
                    exc_info=(type(error), error, error.__traceback__),
                )
                return False

        channel_guild = getattr(channel, "guild", None)
        if (
            channel_guild is None
            or channel_guild.id != UPDATE_ANNOUNCEMENT_GUILD_ID
        ):
            logger.error(
                "O canal de anúncios %s não pertence ao servidor configurado %s.",
                UPDATE_ANNOUNCEMENT_CHANNEL_ID,
                UPDATE_ANNOUNCEMENT_GUILD_ID,
            )
            return False

        embed = discord.Embed(
            title="Atualizações do bot",
            description="\n".join(f"• {update}" for update in updates),
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        try:
            await channel.send(
                content=(
                    f"<@&{UPDATE_ANNOUNCEMENT_ROLE_ID}>"
                    if mention_role
                    else None
                ),
                embed=embed,
                allowed_mentions=(
                    discord.AllowedMentions(
                        roles=True,
                        users=False,
                        everyone=False,
                    )
                    if mention_role
                    else discord.AllowedMentions.none()
                ),
            )
        except discord.HTTPException as error:
            logger.error(
                "Não foi possível publicar as atualizações no canal %s.",
                UPDATE_ANNOUNCEMENT_CHANNEL_ID,
                exc_info=(type(error), error, error.__traceback__),
            )
            return False

        try:
            set_last_announced_commit(head_commit)
        except sqlite3.Error:
            logger.exception(
                "As atualizações foram publicadas, mas o commit anunciado "
                "não pôde ser salvo."
            )
            return False
        if self.pending_update_announcement == (head_commit, updates):
            self.pending_update_announcement = None
        return True

    async def npc_betting_loop(self) -> None:
        while not self.is_closed():
            try:
                online_owner_ids_by_guild = {
                    guild.id: {
                        member.id
                        for member in guild.members
                        if member.status is not discord.Status.offline
                    }
                    for guild in self.guilds
                }
                main_house_online = any(
                    BOT_OWNER_ID in owner_ids
                    for owner_ids in online_owner_ids_by_guild.values()
                )
                main_bets, local_bets = run_npc_betting_cycle(
                    main_house_online=main_house_online,
                    online_owner_ids_by_guild=online_owner_ids_by_guild,
                )
                if main_bets or local_bets:
                    logger.info(
                        "Ciclo de apostas NPC concluído: %d apostas na casa "
                        "principal e %d em cassinos locais.",
                        main_bets,
                        local_bets,
                    )
            except sqlite3.Error:
                logger.exception("Falha ao processar as apostas periódicas dos NPCs.")
            await asyncio.sleep(NPC_BET_POLL_INTERVAL_SECONDS)


bot = BotDiscord()


async def synchronize_user_autoroles(user_id: int) -> None:
    for guild in bot.guilds:
        if guild.get_member(user_id) is not None:
            await synchronize_casino_autoroles(guild)


@bot.event
async def on_app_command_completion(
    interaction: discord.Interaction,
    command: app_commands.Command,
) -> None:
    guild = interaction.guild
    if command.name not in CASINO_ROLE_REFRESH_COMMANDS:
        return
    if guild is None:
        await synchronize_user_autoroles(interaction.user.id)
        return

    if command.name in CASINO_PARTICIPANT_COMMANDS:
        configured_channel_id = get_betting_channel_id(guild.id)
        if (
            configured_channel_id is not None
            and interaction.channel_id != configured_channel_id
        ):
            return

    member = (
        interaction.user
        if command.name in CASINO_PARTICIPANT_COMMANDS
        and isinstance(interaction.user, discord.Member)
        else None
    )
    await synchronize_casino_autoroles(guild, triggering_member=member)


class DuelView(discord.ui.View):
    def __init__(
        self,
        challenger: discord.User | discord.Member,
        opponent: discord.User | discord.Member,
        bet: int,
        game: str,
    ) -> None:
        super().__init__(timeout=120)
        self.challenger = challenger
        self.opponent = opponent
        self.bet = bet
        self.game = game
        self.accepted = False
        self.finished = False
        self.choices: dict[int, str] = {}
        self.challenger_balance = get_balance(challenger.id)
        self.opponent_balance = get_balance(opponent.id)
        self.result = (
            f"{opponent.mention}, aceite ou recuse o desafio. "
            f"Cada jogador aposta **{format_coins(bet)} moedas**. "
            "Quem vencer recebe o pote; em caso de empate, as apostas voltam."
        )
        self.message: discord.InteractionMessage | None = None
        self.turn_lock = asyncio.Lock()

    def create_embed(self) -> discord.Embed:
        if self.finished and self.result.startswith("🤝"):
            title = "🤝 EMPATE"
            color = discord.Color.gold()
        elif self.finished and self.result.startswith("🎉"):
            title = "🎉 DESAFIO CONCLUÍDO"
            color = discord.Color.green()
        elif self.finished and self.result.startswith("⏰"):
            title = "⏰ DESAFIO EXPIRADO"
            color = discord.Color.gold()
        elif self.finished:
            title = "🏁 DESAFIO ENCERRADO"
            color = discord.Color.red()
        else:
            title = f"⚔️ DESAFIO — {self.game.upper()}"
            color = discord.Color.blue()

        embed = discord.Embed(title=title, description=self.result, color=color)
        embed.add_field(
            name="Jogadores",
            value=f"{self.challenger.mention} vs. {self.opponent.mention}",
            inline=False,
        )
        embed.add_field(
            name="Aposta de cada jogador",
            value=f"{format_coins(self.bet)} moedas",
            inline=True,
        )
        embed.add_field(
            name="Pote",
            value=f"{format_coins(self.bet * 2)} moedas",
            inline=True,
        )
        if self.accepted or self.finished:
            embed.add_field(
                name=f"Saldo de {self.challenger.display_name}",
                value=f"{format_coins(self.challenger_balance)} moedas",
                inline=True,
            )
            embed.add_field(
                name=f"Saldo de {self.opponent.display_name}",
                value=f"{format_coins(self.opponent_balance)} moedas",
                inline=True,
            )
        return embed

    def _disable_all_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    async def _finish_round(self, winner_id: int | None, result: str) -> None:
        self.finished = True
        self.result = result
        (
            self.challenger_balance,
            self.opponent_balance,
            winner_winnings,
        ) = settle_duel_bets(
            self.challenger.id,
            self.opponent.id,
            self.bet,
            winner_id,
        )
        if winner_id is not None:
            base_house_fee = (
                self.bet * 2 * PVP_HOUSE_TAX_PERCENT // 100
            )
            base_winnings = self.bet * 2 - base_house_fee
            actual_house_fee = self.bet * 2 - winner_winnings
            house_fee_text = (
                f"**{format_coins(actual_house_fee)}** vão para a casa principal"
                if actual_house_fee >= 0
                else f"**{format_coins(-actual_house_fee)}** são pagos pela casa principal"
            )
            self.result = self.result.replace(
                f"**{format_coins(base_house_fee)}** vão para a casa principal",
                house_fee_text,
            )
            self.result = self.result.replace(
                f"**{format_coins(base_winnings)} moedas**.",
                f"**{format_coins(winner_winnings)} moedas**.",
            )
        self._disable_all_buttons()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in (self.challenger.id, self.opponent.id):
            await interaction.response.send_message(
                "Este desafio é privado entre os dois jogadores mencionados.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(
        label="Aceitar desafio",
        emoji="✅",
        style=discord.ButtonStyle.success,
    )
    async def accept(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if not await ensure_betting_channel(interaction):
            return
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message(
                "Somente a pessoa desafiada pode aceitar.",
                ephemeral=True,
            )
            return

        async with self.turn_lock:
            if self.accepted or self.finished:
                await interaction.response.send_message(
                    "Este desafio já foi respondido.",
                    ephemeral=True,
                )
                return

            debited, challenger_balance, opponent_balance = place_duel_bets(
                self.challenger.id,
                self.opponent.id,
                self.bet,
            )
            if not debited:
                self.finished = True
                self.result = (
                    "❌ Desafio cancelado: um ou ambos os jogadores não têm "
                    f"{format_coins(self.bet)} moedas disponíveis."
                )
                self.challenger_balance = challenger_balance
                self.opponent_balance = opponent_balance
                self._disable_all_buttons()
                self.stop()
                await interaction.response.edit_message(
                    embed=self.create_embed(),
                    view=None,
                )
                return

            self.accepted = True
            self.challenger_balance = challenger_balance
            self.opponent_balance = opponent_balance
            _button.disabled = True
            self.decline.disabled = True
            if self.game == "dados":
                challenger_roll = random.randint(1, 6)
                opponent_roll = random.randint(1, 6)
                if challenger_roll == opponent_roll:
                    await self._finish_round(
                        None,
                        f"🤝 Ambos tiraram **{challenger_roll}**. "
                        "As duas apostas foram devolvidas.",
                    )
                else:
                    winner = (
                        self.challenger
                        if challenger_roll > opponent_roll
                        else self.opponent
                    )
                    house_fee = (
                        self.bet * 2 * PVP_HOUSE_TAX_PERCENT // 100
                    )
                    await self._finish_round(
                        winner.id,
                        f"🎉 {winner.mention} venceu! "
                        f"Resultados: {self.challenger.mention} tirou "
                        f"**{challenger_roll}** e {self.opponent.mention} "
                        f"tirou **{opponent_roll}**. Do pote de "
                        f"**{format_coins(self.bet * 2)} moedas**, "
                        f"**{format_coins(house_fee)}** vão para a casa principal "
                        f"e o vencedor recebe **"
                        f"{format_coins(self.bet * 2 - house_fee)} moedas**.",
                    )
            else:
                self.pedra.disabled = False
                self.papel.disabled = False
                self.tesoura.disabled = False
                self.result = (
                    "Desafio aceito! Os dois jogadores devem escolher "
                    "pedra, papel ou tesoura. As escolhas ficam ocultas "
                    "até ambos confirmarem."
                )
            await interaction.response.edit_message(
                embed=self.create_embed(),
                view=None if self.finished else self,
            )

    @discord.ui.button(
        label="Recusar",
        emoji="✖️",
        style=discord.ButtonStyle.danger,
    )
    async def decline(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if _button.disabled:
            await interaction.response.send_message(
                "Este desafio já foi respondido.",
                ephemeral=True,
            )
            return
        if not await ensure_betting_channel(interaction):
            return
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message(
                "Somente a pessoa desafiada pode recusar.",
                ephemeral=True,
            )
            return

        async with self.turn_lock:
            if self.accepted or self.finished:
                await interaction.response.send_message(
                    "Este desafio já foi respondido.",
                    ephemeral=True,
                )
                return
            self.finished = True
            self.result = f"❌ {self.opponent.mention} recusou o desafio."
            self._disable_all_buttons()
            self.stop()
            await interaction.response.edit_message(
                embed=self.create_embed(),
                view=None,
            )

    async def _choose(
        self,
        interaction: discord.Interaction,
        choice: str,
    ) -> None:
        if not await ensure_betting_channel(interaction):
            return
        async with self.turn_lock:
            if not self.accepted or self.finished:
                await interaction.response.send_message(
                    "Este desafio não está aceitando escolhas.",
                    ephemeral=True,
                )
                return
            if interaction.user.id in self.choices:
                await interaction.response.send_message(
                    "Você já confirmou sua escolha.",
                    ephemeral=True,
                )
                return

            self.choices[interaction.user.id] = choice
            if len(self.choices) == 2:
                challenger_choice = self.choices[self.challenger.id]
                opponent_choice = self.choices[self.opponent.id]
                if challenger_choice == opponent_choice:
                    await self._finish_round(
                        None,
                        f"🤝 Empate! Ambos escolheram **{challenger_choice}**. "
                        "As duas apostas foram devolvidas.",
                    )
                else:
                    beats = {
                        "pedra": "tesoura",
                        "papel": "pedra",
                        "tesoura": "papel",
                    }
                    winner = (
                        self.challenger
                        if beats[challenger_choice] == opponent_choice
                        else self.opponent
                    )
                    house_fee = (
                        self.bet * 2 * PVP_HOUSE_TAX_PERCENT // 100
                    )
                    await self._finish_round(
                        winner.id,
                        f"🎉 {winner.mention} venceu! "
                        f"{self.challenger.mention} escolheu **{challenger_choice}** "
                        f"e {self.opponent.mention} escolheu **{opponent_choice}**. "
                        f"Do pote de **{format_coins(self.bet * 2)} moedas**, "
                        f"**{format_coins(house_fee)}** vão para a casa principal "
                        f"e o vencedor recebe **"
                        f"{format_coins(self.bet * 2 - house_fee)} moedas**.",
                    )
            else:
                self.result = (
                    f"{interaction.user.mention} já escolheu em segredo. "
                    "Aguardando o outro jogador."
                )

            await interaction.response.edit_message(
                embed=self.create_embed(),
                view=None if self.finished else self,
            )

    @discord.ui.button(
        label="Pedra",
        emoji="🪨",
        style=discord.ButtonStyle.secondary,
        disabled=True,
    )
    async def pedra(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if _button.disabled:
            await interaction.response.send_message(
                "As escolhas ainda não estão disponíveis.",
                ephemeral=True,
            )
            return
        await self._choose(interaction, "pedra")

    @discord.ui.button(
        label="Papel",
        emoji="📄",
        style=discord.ButtonStyle.secondary,
        disabled=True,
    )
    async def papel(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if _button.disabled:
            await interaction.response.send_message(
                "As escolhas ainda não estão disponíveis.",
                ephemeral=True,
            )
            return
        await self._choose(interaction, "papel")

    @discord.ui.button(
        label="Tesoura",
        emoji="✂️",
        style=discord.ButtonStyle.secondary,
        disabled=True,
    )
    async def tesoura(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if _button.disabled:
            await interaction.response.send_message(
                "As escolhas ainda não estão disponíveis.",
                ephemeral=True,
            )
            return
        await self._choose(interaction, "tesoura")

    async def on_timeout(self) -> None:
        async with self.turn_lock:
            if self.finished:
                return
            if self.accepted:
                await self._finish_round(
                    None,
                    "⏰ Tempo esgotado. As duas apostas foram devolvidas.",
                )
            else:
                self.finished = True
                self.result = "⏰ O desafio expirou sem ser aceito."
                self._disable_all_buttons()
                self.stop()
            if self.message is not None:
                await self.message.edit(embed=self.create_embed(), view=None)


async def is_bot_owner(interaction: discord.Interaction) -> bool:
    return interaction.user.id == BOT_OWNER_ID


def violates_moderation_hierarchy(
    interaction: discord.Interaction,
    target: discord.Member,
) -> bool:
    guild = interaction.guild
    actor = interaction.user
    bot_member = guild.me if guild else None
    if guild is None or bot_member is None or not isinstance(actor, discord.Member):
        return True

    if target == guild.owner or target.top_role >= bot_member.top_role:
        return True

    return actor != guild.owner and target.top_role >= actor.top_role


@bot.tree.command(
    name="prestigio",
    description="Reinicie seus saldos em troca de bônus permanentes.",
)
async def prestigio(interaction: discord.Interaction) -> None:
    if interaction.user.id == BOT_OWNER_ID:
        await interaction.response.send_message(
            "A conta do owner representa o saldo da casa principal e não pode "
            "ser prestigada.",
            ephemeral=True,
        )
        return
    (
        balance,
        level,
        points,
        gains_level,
        rewards_level,
        bet_limit_level,
        bet_volume,
    ) = get_prestige_status(interaction.user.id)
    if level >= PRESTIGE_MAX_LEVEL:
        await interaction.response.send_message(
            f"Você já alcançou o prestígio máximo (**{level}**). "
            f"Você tem **{points} pontos** de upgrade.",
            ephemeral=True,
        )
        return

    requirement = prestige_requirement(level)
    next_level = level + 1
    embed = discord.Embed(
        title=f"✨ Prestígio {next_level}",
        description=(
            f"Saldo global: **{format_coins(balance)} moedas**\n"
            f"Requisito: **{format_coins(requirement)} moedas**\n"
            f"Recompensa: **{next_level} pontos de upgrade**\n\n"
            "Ao confirmar, seu saldo global e todos os saldos em cassinos "
            "serão zerados. Histórico, cooldowns, métricas de apostas e níveis "
            "de upgrade serão preservados."
        ),
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Bônus atual",
        value=(
            f"Ganhos em apostas: +{5 * (level + gains_level)}%\n"
            f"Recompensas diárias/semanais: nível {rewards_level} "
            f"(+{10 * rewards_level}%)\n"
            f"Limite de aposta: {format_coins(get_player_bet_limit(interaction.user.id))} "
            f"(nível {bet_limit_level})\n"
            f"Volume apostado: {format_coins(bet_volume)}"
        ),
        inline=False,
    )
    if balance < requirement:
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    await interaction.response.send_message(
        embed=embed,
        view=PrestigeConfirmView(interaction.user.id),
        ephemeral=True,
    )


@bot.tree.command(
    name="upgrade_prestigio",
    description="Gaste pontos para aprimorar bônus permanentes.",
)
@app_commands.choices(
    upgrade=[
        app_commands.Choice(name="Ganhos em apostas (+5% por nível)", value="gains"),
        app_commands.Choice(name="Rewards daily/weekly (+10% por nível)", value="rewards"),
        app_commands.Choice(name="Limite de aposta (+100.000 por nível)", value="bet_limit"),
    ]
)
async def upgrade_prestigio(
    interaction: discord.Interaction,
    upgrade: app_commands.Choice[str],
) -> None:
    if interaction.user.id == BOT_OWNER_ID:
        await interaction.response.send_message(
            "A casa principal não usa a árvore de upgrades de prestígio dos jogadores.",
            ephemeral=True,
        )
        return
    upgrade_column, upgrade_name, effect = PRESTIGE_UPGRADES[upgrade.value]
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        status = connection.execute(
            f"""
            SELECT prestige_points, {upgrade_column}
            FROM economy_accounts WHERE user_id = ?
            """,
            (interaction.user.id,),
        ).fetchone()
    points, level = status if status is not None else (0, 0)
    if level >= PRESTIGE_MAX_UPGRADE_LEVEL:
        await interaction.response.send_message(
            f"**{upgrade_name}** já está no nível máximo "
            f"({PRESTIGE_MAX_UPGRADE_LEVEL}).",
            ephemeral=True,
        )
        return

    cost = level + 1
    if points < cost:
        await interaction.response.send_message(
            f"Você tem **{points} pontos**, mas o próximo nível de "
            f"**{upgrade_name}** custa **{cost} pontos**. "
            "Cada nível custa um ponto a mais que o anterior.",
            ephemeral=True,
        )
        return

    effect_text = (
        f"+{effect}% nos ganhos positivos"
        if upgrade.value == "gains"
        else f"+{effect}% nas recompensas daily/weekly"
        if upgrade.value == "rewards"
        else f"+{format_coins(effect)} no limite de aposta"
    )
    await interaction.response.send_message(
        f"Comprar **{upgrade_name}** nível **{level + 1}** por "
        f"**{cost} pontos**? Efeito: {effect_text}.",
        view=PrestigeUpgradeView(interaction.user.id, upgrade.value),
        ephemeral=True,
    )


@bot.tree.command(name="daily", description="Recebe sua recompensa diária de moedas.")
async def daily(interaction: discord.Interaction) -> None:
    success, balance, amount = claim_reward(interaction.user.id, "daily")
    if not success:
        await interaction.response.send_message(
            f"Você já resgatou sua recompensa diária. "
            f"Tente novamente em {format_remaining(amount)}.",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        f"{interaction.user.mention} recebeu {amount} moedas de recompensa diária. "
        f"Saldo: {balance} moedas!"
    )


@bot.tree.command(name="weekly", description="Recebe sua recompensa semanal de moedas.")
async def weekly(interaction: discord.Interaction) -> None:
    success, balance, amount = claim_reward(interaction.user.id, "weekly")
    if not success:
        await interaction.response.send_message(
            f"Você já resgatou sua recompensa semanal. "
            f"Tente novamente em {format_remaining(amount)}.",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        f"{interaction.user.mention} recebeu {amount} moedas de recompensa semanal. "
        f"Saldo: {balance} moedas!"
    )


@bot.tree.command(name="monthly", description="Recebe sua recompensa mensal de moedas.")
async def monthly(interaction: discord.Interaction) -> None:
    success, balance, amount = claim_reward(interaction.user.id, "monthly")
    if not success:
        await interaction.response.send_message(
            f"Você já resgatou sua recompensa mensal. "
            f"Tente novamente em {format_remaining(amount)}.",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        f"{interaction.user.mention} recebeu {amount} moedas de recompensa mensal. "
        f"Saldo: {balance} moedas!"
    )


@bot.tree.command(name="saldo", description="Mostra seu saldo de moedas.")
async def saldo(interaction: discord.Interaction) -> None:
    balance = get_balance(interaction.user.id)
    await interaction.response.send_message(
        f"{interaction.user.mention}, seu saldo é de {balance} moedas.",
        ephemeral=True,
    )


class PlayerDataResetView(discord.ui.View):
    def __init__(self, owner_id: int, reset_type: str) -> None:
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.reset_type = reset_type

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id == BOT_OWNER_ID:
            return True
        await interaction.response.send_message(
            "Somente o owner do bot pode confirmar este reset.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(
        label="Confirmar reset",
        emoji="⚠️",
        style=discord.ButtonStyle.danger,
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        global_rows, local_rows = reset_player_data(self.reset_type)
        if self.reset_type == "balances":
            message = (
                "✅ Saldos dos jogadores zerados: "
                f"**{global_rows}** contas globais e **{local_rows}** contas "
                "de cassinos locais. O saldo da casa principal, os caixas "
                "dos cassinos e o histórico estatístico foram preservados."
            )
        else:
            message = (
                "✅ Cooldowns das recompensas foram liberados para todos: "
                f"**{global_rows}** contas globais e **{local_rows}** contas "
                "de cassinos locais. Os cooldowns de apostas em animais e "
                "todo o histórico foram preservados."
            )
        button.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content=message,
            view=None,
        )

    @discord.ui.button(
        label="Cancelar",
        emoji="✖️",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        button.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content="Reset cancelado; nenhum dado foi alterado.",
            view=None,
        )


@bot.tree.command(
    name="resetar_dados_jogadores",
    description="Reseta saldos ou cooldowns de recompensas dos jogadores.",
)
@app_commands.check(is_bot_owner)
@app_commands.choices(
    tipo=[
        app_commands.Choice(name="Zerar saldos dos jogadores", value="balances"),
        app_commands.Choice(
            name="Liberar cooldowns das recompensas",
            value="reward_cooldowns",
        ),
    ]
)
async def resetar_dados_jogadores(
    interaction: discord.Interaction,
    tipo: app_commands.Choice[str],
) -> None:
    if tipo.value == "balances":
        description = (
            "Isso zerará os saldos globais e os saldos locais dos jogadores "
            "em todos os cassinos. O saldo da casa principal, os caixas dos "
            "cassinos e o histórico estatístico não serão alterados."
        )
    else:
        description = (
            "Isso liberará os cooldowns de daily, weekly e monthly globais, "
            "além de daily e weekly dos cassinos locais, para todos os "
            "jogadores. Cooldowns de apostas em animais não serão alterados."
        )
    embed = discord.Embed(
        title="Confirmar reset de dados dos jogadores",
        description=description,
        color=discord.Color.red(),
    )
    await interaction.response.send_message(
        embed=embed,
        view=PlayerDataResetView(interaction.user.id, tipo.value),
        ephemeral=True,
    )


@bot.tree.command(
    name="status_apostador",
    description="Mostra suas estatísticas pessoais de moedas e apostas.",
)
async def status_apostador(interaction: discord.Interaction) -> None:
    guild_id = interaction.guild.id if interaction.guild is not None else None
    global_status, local_status = get_player_status(
        interaction.user.id,
        guild_id,
    )
    (
        balance,
        total_earned,
        total_lost,
        prestige_level,
        prestige_points,
        prestige_upgrade_gains,
        prestige_upgrade_rewards,
        prestige_upgrade_bet_limit,
        bet_volume,
        bet_count,
        daily_claim_at,
        weekly_claim_at,
        monthly_claim_at,
    ) = global_status

    embed = discord.Embed(
        title=f"Seu status de apostador — {interaction.user.display_name}",
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Saldo global",
        value=f"**{format_coins(balance)} moedas**",
        inline=True,
    )
    embed.add_field(
        name="Ganhos e perdas acumulados",
        value=(
            f"Ganhos totais: **{format_coins(total_earned)} moedas**\n"
            f"Perdas totais: **{format_coins(total_lost)} moedas**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Suas apostas globais",
        value=(
            f"Volume apostado: **{format_coins(bet_volume)} moedas**\n"
            f"Quantidade de apostas: **{format_coins(bet_count)}**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Prestígio e upgrades",
        value=(
            f"Prestígio: **{prestige_level}/{PRESTIGE_MAX_LEVEL}**\n"
            f"Pontos disponíveis: **{format_coins(prestige_points)}**\n"
            f"Bônus de ganhos: **nível {prestige_upgrade_gains}**\n"
            f"Bônus de recompensas: **nível {prestige_upgrade_rewards}**\n"
            f"Limite extra de aposta: **"
            f"{format_coins(prestige_upgrade_bet_limit * PLAYER_BET_LIMIT_PER_UPGRADE)} moedas**\n"
            f"Limite atual: **"
            f"{format_coins(get_player_bet_limit(interaction.user.id))} moedas**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Recompensas globais",
        value=(
            f"Daily: **{reward_cooldown_status(daily_claim_at, REWARD_SETTINGS['daily'][1])}**\n"
            f"Weekly: **{reward_cooldown_status(weekly_claim_at, REWARD_SETTINGS['weekly'][1])}**\n"
            f"Monthly: **{reward_cooldown_status(monthly_claim_at, REWARD_SETTINGS['monthly'][1])}**"
        ),
        inline=False,
    )
    if local_status is not None:
        (
            casino_name,
            currency_name,
            local_balance,
            local_earned,
            local_lost,
            local_bet_volume,
            local_bet_count,
            local_daily_claim_at,
            local_weekly_claim_at,
        ) = local_status
        embed.add_field(
            name=f"Seu status em {casino_name}",
            value=(
                f"Saldo: **{format_coins(local_balance)} {currency_name}**\n"
                f"Ganhos acumulados: **{format_coins(local_earned)} {currency_name}**\n"
                f"Perdas acumuladas: **{format_coins(local_lost)} {currency_name}**\n"
                f"Volume apostado: **{format_coins(local_bet_volume)} {currency_name}**\n"
                f"Apostas: **{format_coins(local_bet_count)}**\n"
                f"Daily do cassino: **"
                f"{reward_cooldown_status(local_daily_claim_at, CASINO_REWARD_SETTINGS['daily'][1])}**\n"
                f"Weekly do cassino: **"
                f"{reward_cooldown_status(local_weekly_claim_at, CASINO_REWARD_SETTINGS['weekly'][1])}**"
            ),
            inline=False,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="leaderboard", description="Mostra o ranking de moedas deste servidor.")
@app_commands.guild_only()
async def leaderboard(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Este comando só pode ser usado em um servidor.",
            ephemeral=True,
        )
        return

    ranking = get_leaderboard([member.id for member in guild.members])
    if not ranking:
        await interaction.response.send_message(
            "Ainda não há dados de moedas para os membros deste servidor.",
            ephemeral=True,
        )
        return

    lines = [
        f"**{position}.** <@{user_id}> — **{balance}** moedas"
        f" | Ganho: {earned} | Perdido: {lost}"
        for position, (user_id, balance, earned, lost) in enumerate(ranking, start=1)
    ]
    embed = discord.Embed(
        title=f"Leaderboard de moedas — {guild.name}",
        description="\n".join(lines),
        color=discord.Color.gold(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="canal_apostas",
    description="Define o canal dos jogos de aposta; sem canal, remove a restrição.",
)
@app_commands.guild_only()
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(canal="Canal autorizado; deixe vazio para liberar todos os canais.")
async def canal_apostas(
    interaction: discord.Interaction,
    canal: discord.TextChannel | None = None,
) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Este comando só pode ser usado em um servidor.",
            ephemeral=True,
        )
        return

    set_betting_channel(guild.id, canal.id if canal is not None else None)
    if canal is None:
        message = "Restrição removida: jogos de aposta liberados em todos os canais."
    else:
        message = f"Jogos de aposta limitados ao canal {canal.mention}."
    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(
    name="configurar_autorole_cassino",
    description="Configura cargos automáticos por condições do cassino.",
)
@app_commands.guild_only()
@app_commands.check(is_bot_owner)
@app_commands.describe(
    condicao="Condição que concede ou remove o cargo.",
    limite="Posição, saldo, prestígio ou métrica mínima exigida.",
    cargo="Cargo concedido; deixe vazio para remover a regra da condição.",
)
@app_commands.choices(
    condicao=[
        app_commands.Choice(name="Participou de jogos", value="participation"),
        app_commands.Choice(name="Ranking global: posição", value="global_balance_rank"),
        app_commands.Choice(name="Saldo global mínimo", value="global_balance"),
        app_commands.Choice(name="Ranking do cassino: posição", value="casino_balance_rank"),
        app_commands.Choice(name="Saldo no cassino mínimo", value="casino_balance"),
        app_commands.Choice(name="Prestígio mínimo", value="prestige"),
        app_commands.Choice(name="Volume apostado mínimo", value="bet_volume"),
        app_commands.Choice(name="Número de apostas mínimo", value="bet_count"),
    ]
)
async def configurar_autorole_cassino(
    interaction: discord.Interaction,
    condicao: app_commands.Choice[str],
    limite: app_commands.Range[int, 1, 9_000_000_000_000_000] | None = None,
    cargo: discord.Role | None = None,
) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Este comando só pode ser usado em um servidor.",
            ephemeral=True,
        )
        return

    condition = condicao.value
    if condition not in AUTOROLE_CONDITIONS:
        await interaction.response.send_message(
            "A condição informada não é válida.",
            ephemeral=True,
        )
        return
    if condition in ("global_balance_rank", "casino_balance_rank"):
        if limite is None or not 1 <= limite <= 10:
            await interaction.response.send_message(
                "Para uma regra de posição, informe um número entre 1 e 10.",
                ephemeral=True,
            )
            return
    elif condition != "participation" and limite is None:
        await interaction.response.send_message(
            "Informe o limite mínimo exigido para esta condição.",
            ephemeral=True,
        )
        return

    previous_rules = get_casino_autorole_rules(guild.id)
    if cargo is None:
        set_casino_autorole_rule(guild.id, None, condition)
        active_roles = {
            role_id for role_id, _, _ in get_casino_autorole_rules(guild.id)
        }
        obsolete_roles = {
            role_id
            for role_id, rule_condition, _ in previous_rules
            if rule_condition == condition and role_id not in active_roles
        }
        await interaction.response.defer(ephemeral=True)
        bot_member = guild.me
        if bot_member is not None and bot_member.guild_permissions.manage_roles:
            for member in guild.members:
                roles = [
                    role
                    for role in member.roles
                    if role.id in obsolete_roles
                    and not role.managed
                    and role < bot_member.top_role
                ]
                if roles:
                    try:
                        await member.remove_roles(
                            *roles,
                            reason="Regra automática de cassino removida.",
                        )
                    except discord.HTTPException:
                        logger.exception(
                            "Falha ao remover autorole desativado do membro %s "
                            "no servidor %s.",
                            member.id,
                            guild.id,
                        )
        await interaction.followup.send(
            f"Regra de autorole para **{AUTOROLE_CONDITIONS[condition]}** removida.",
            ephemeral=True,
        )
        return

    bot_member = guild.me
    if bot_member is None or not bot_member.guild_permissions.manage_roles:
        await interaction.response.send_message(
            "O bot precisa da permissão **Gerenciar cargos** para atribuir "
            "o autorole.",
            ephemeral=True,
        )
        return
    if cargo.is_default() or cargo.managed:
        await interaction.response.send_message(
            "Escolha um cargo normal, que possa ser atribuído pelo bot.",
            ephemeral=True,
        )
        return
    if cargo >= bot_member.top_role:
        await interaction.response.send_message(
            "O cargo do autorole precisa ficar abaixo do cargo mais alto do bot.",
            ephemeral=True,
        )
        return

    threshold = limite or 0
    set_casino_autorole_rule(guild.id, cargo.id, condition, threshold)
    await interaction.response.defer(ephemeral=True)
    await synchronize_casino_autoroles(guild)
    condition_description = AUTOROLE_CONDITIONS[condition]
    threshold_description = (
        ""
        if condition == "participation"
        else f" com limite **{format_coins(threshold)}**"
        if condition in ("global_balance", "casino_balance", "bet_volume")
        else f" na posição **{threshold}**"
        if condition in ("global_balance_rank", "casino_balance_rank")
        else f" **{threshold}**"
    )
    await interaction.followup.send(
        f"Regra configurada: {cargo.mention} para **{condition_description}**"
        f"{threshold_description}. O bot também removerá o cargo quando a "
        "condição deixar de ser atendida.",
        ephemeral=True,
    )


@bot.tree.command(
    name="configurar_cassinos",
    description="Define a taxa de criação e a taxa da casa principal.",
)
@app_commands.check(is_bot_owner)
@app_commands.describe(
    taxa_criacao="Moedas globais cobradas de quem criar um cassino.",
    taxa_casa="Percentual cobrado sobre lucro de cassinos de servidor (0 a 50).",
)
async def configurar_cassinos(
    interaction: discord.Interaction,
    taxa_criacao: app_commands.Range[int, 0, 1_000_000],
    taxa_casa: app_commands.Range[int, 0, 50],
) -> None:
    update_casino_settings(
        creation_fee=taxa_criacao,
        tax_percent=taxa_casa,
    )
    await interaction.response.send_message(
        f"Configuração atualizada: criação por **{format_coins(taxa_criacao)} "
        f"moedas** e taxa da casa principal de **{taxa_casa}%**. "
        "Upgrades reduzem a taxa em 1 ponto percentual por nível, "
        "até o mínimo de 1% (ou 0% se a taxa base for 0).",
        ephemeral=True,
    )


@bot.tree.command(
    name="configurar_npcs_principais",
    description="Define quantos NPCs apostam na casa principal.",
)
@app_commands.check(is_bot_owner)
@app_commands.describe(
    quantidade="Quantidade de NPCs da casa principal (de 1 a 100)."
)
async def configurar_npcs_principais(
    interaction: discord.Interaction,
    quantidade: app_commands.Range[int, 1, CASINO_MAX_NPCS],
) -> None:
    set_main_house_npc_count(quantidade)
    await interaction.response.send_message(
        f"A casa principal agora tem **{quantidade} NPCs**. Os intervalos "
        "das apostas variam conforme a presença do dono.",
        ephemeral=True,
    )


class MainHouseUpgradeView(discord.ui.View):
    def __init__(
        self,
        user_id: int,
        upgrade_type: str,
        expected_level: int,
        expected_npc_count: int | None,
    ) -> None:
        super().__init__(timeout=120)
        self.user_id = user_id
        self.upgrade_type = upgrade_type
        self.expected_level = expected_level
        self.expected_npc_count = expected_npc_count

    @discord.ui.button(
        label="Confirmar upgrade",
        emoji="✅",
        style=discord.ButtonStyle.success,
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Somente quem iniciou o upgrade pode confirmá-lo.",
                ephemeral=True,
            )
            return

        status, balance, level, npc_count, cost = upgrade_main_house(
            interaction.user.id,
            self.upgrade_type,
            self.expected_level,
            self.expected_npc_count,
        )
        if status == "changed":
            message = (
                "O estado da casa mudou desde a prévia. Nenhum valor foi "
                "debitado; execute o comando novamente para conferir o novo "
                "custo e confirmar."
            )
        elif status == "insufficient":
            message = (
                f"Saldo insuficiente: o upgrade custa "
                f"**{format_coins(cost)} moedas** e o saldo atual é "
                f"**{format_coins(balance)} moedas**."
            )
        elif status == "max_count":
            message = f"A casa principal já atingiu o limite de {CASINO_MAX_NPCS} NPCs."
        elif status == "max_level":
            message = (
                f"Este tipo de upgrade já atingiu o nível máximo "
                f"({MAIN_HOUSE_UPGRADE_MAX_LEVEL})."
            )
        else:
            message = (
                f"✅ Upgrade concluído! Saldo restante: "
                f"**{format_coins(balance)} moedas**."
            )
            if self.upgrade_type == "npc_count":
                message += f" A casa agora tem **{npc_count} NPCs**."
            else:
                npc_bet_min, npc_bet_max = main_house_npc_bet_range(level)
                message += (
                    f" Nível de apostas por NPC: **{level}/"
                    f"{MAIN_HOUSE_UPGRADE_MAX_LEVEL}**; cada NPC aposta "
                    f"entre **{format_coins(npc_bet_min)} e "
                    f"{format_coins(npc_bet_max)} moedas**."
                )

            updated_status = get_main_house_status()
            next_level = updated_status[
                "npc_count_upgrade_level"
                if self.upgrade_type == "npc_count"
                else "npc_bet_upgrade_level"
            ]
            next_cost = updated_status[
                "next_npc_count_upgrade_cost"
                if self.upgrade_type == "npc_count"
                else "next_npc_bet_upgrade_cost"
            ]
            can_continue = (
                next_cost > 0
                and updated_status["balance"] >= next_cost
                and (
                    self.upgrade_type != "npc_count"
                    or updated_status["npc_count"] < CASINO_MAX_NPCS
                )
            )
            if can_continue:
                if self.upgrade_type == "npc_count":
                    next_effect = (
                        f"A quantidade de NPCs passará de **"
                        f"{updated_status['npc_count']}** para **"
                        f"{min(CASINO_MAX_NPCS, updated_status['npc_count'] + MAIN_HOUSE_UPGRADE_NPC_BONUS)}**."
                    )
                    next_expected_npc_count = updated_status["npc_count"]
                else:
                    next_min, next_max = main_house_npc_bet_range(next_level + 1)
                    next_effect = (
                        f"A faixa de aposta de cada NPC passará para "
                        f"**{format_coins(next_min)}–{format_coins(next_max)} moedas**."
                    )
                    next_expected_npc_count = None
                message += (
                    f"\n\nPróximo upgrade (nível **{next_level + 1}**): "
                    f"{next_effect}\nCusto: **{format_coins(next_cost)} "
                    "moedas**. Deseja continuar?"
                )
                next_view = MainHouseUpgradeView(
                    self.user_id,
                    self.upgrade_type,
                    next_level,
                    next_expected_npc_count,
                )
                await interaction.response.edit_message(
                    content=message,
                    embed=None,
                    view=next_view,
                )
                self.stop()
                return
            if next_cost > 0 and updated_status["balance"] < next_cost:
                message += (
                    f"\nPróximo upgrade custa **{format_coins(next_cost)} "
                    "moedas**; saldo insuficiente para continuar."
                )

        _button.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content=message,
            embed=None,
            view=None,
        )

    @discord.ui.button(
        label="Cancelar",
        emoji="✖️",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Somente quem iniciou o upgrade pode cancelá-lo.",
                ephemeral=True,
            )
            return
        _button.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content="Upgrade cancelado; nenhum valor foi debitado.",
            embed=None,
            view=None,
        )


@bot.tree.command(
    name="upgrade_casa_principal",
    description="Escolhe um upgrade para a casa principal e confirma a compra.",
)
@app_commands.check(is_bot_owner)
@app_commands.choices(
    tipo=[
        app_commands.Choice(name="Aumentar quantidade de NPCs", value="npc_count"),
        app_commands.Choice(name="Aumentar apostas por NPC", value="npc_bet"),
    ]
)
async def upgrade_casa_principal(
    interaction: discord.Interaction,
    tipo: app_commands.Choice[str],
) -> None:
    status = get_main_house_status()
    if tipo.value == "npc_count":
        level = status["npc_count_upgrade_level"]
        current_value = status["npc_count"]
        next_value = min(
            CASINO_MAX_NPCS,
            current_value + MAIN_HOUSE_UPGRADE_NPC_BONUS,
        )
        cost = status["next_npc_count_upgrade_cost"]
        title = "Upgrade de quantidade de NPCs"
        effect = (
            f"A quantidade de NPCs passará de **{current_value}** para "
            f"**{next_value}**."
        )
        if current_value >= CASINO_MAX_NPCS:
            await interaction.response.send_message(
                f"A casa principal já atingiu o limite de "
                f"{CASINO_MAX_NPCS} NPCs.",
                ephemeral=True,
            )
            return
    else:
        level = status["npc_bet_upgrade_level"]
        current_min = status["npc_bet_min"]
        current_max = status["npc_bet_max"]
        next_min, next_max = main_house_npc_bet_range(level + 1)
        cost = status["next_npc_bet_upgrade_cost"]
        title = "Upgrade de apostas por NPC"
        effect = (
            f"A faixa de aposta de cada NPC passará de "
            f"**{format_coins(current_min)}–{format_coins(current_max)}** "
            f"para **{format_coins(next_min)}–{format_coins(next_max)} moedas**."
        )

    if cost == 0:
        await interaction.response.send_message(
            f"Este tipo de upgrade já atingiu o nível máximo "
            f"({MAIN_HOUSE_UPGRADE_MAX_LEVEL}).",
            ephemeral=True,
        )
        return
    if status["balance"] < cost:
        await interaction.response.send_message(
            f"O upgrade custa **{format_coins(cost)} moedas**, mas o saldo "
            f"da casa principal é **{format_coins(status['balance'])} moedas**.",
            ephemeral=True,
        )
        return

    next_level = level + 1
    embed = discord.Embed(
        title=f"Confirmar {title.lower()}",
        description=(
            f"{effect}\n\n"
            f"Nível: **{level} → {next_level}**\n"
            f"Custo: **{format_coins(cost)} moedas**\n"
            f"Saldo após a compra: "
            f"**{format_coins(status['balance'] - cost)} moedas**"
        ),
        color=discord.Color.gold(),
    )
    view = MainHouseUpgradeView(
        interaction.user.id,
        tipo.value,
        level,
        current_value if tipo.value == "npc_count" else None,
    )
    await interaction.response.send_message(
        embed=embed,
        view=view,
        ephemeral=True,
    )


@bot.tree.command(
    name="status_casa_principal",
    description="Mostra saldo e estatísticas privadas da casa principal.",
)
@app_commands.check(is_bot_owner)
async def status_casa_principal(interaction: discord.Interaction) -> None:
    status = get_main_house_status()
    embed = discord.Embed(
        title="Status da casa principal",
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Saldo atual",
        value=f"**{format_coins(status['balance'])} moedas**",
        inline=True,
    )
    embed.add_field(
        name="Ganhos acumulados",
        value=f"{format_coins(status['total_earned'])} moedas",
        inline=True,
    )
    embed.add_field(
        name="Perdas acumuladas",
        value=f"{format_coins(status['total_lost'])} moedas",
        inline=True,
    )
    embed.add_field(
        name="Jogos da casa",
        value=format_coins(status["games"]),
        inline=True,
    )
    embed.add_field(
        name="Atividade de NPCs",
        value=(
            f"{format_coins(status['npc_games'])} apostas históricas | "
            f"{status['npc_count']} NPCs ativos | "
            f"apostas de {format_coins(status['npc_bet_min'])} a "
            f"{format_coins(status['npc_bet_max'])}"
        ),
        inline=True,
    )
    player_bet_net = (
        status["player_bet_earned"] - status["player_bet_lost"]
    )
    player_bet_net_sign = "+" if player_bet_net > 0 else ""
    embed.add_field(
        name="Apostas de jogadores — todas as casas",
        value=(
            f"Volume apostado: **{format_coins(status['player_bet_volume'])} moedas**\n"
            f"Apostas: **{format_coins(status['player_bet_count'])}**\n"
            f"Ganhos da casa com apostas: **"
            f"{format_coins(status['player_bet_earned'])} moedas**\n"
            f"Prêmios pagos pela casa principal: **"
            f"{format_coins(status['player_bet_lost'])} moedas**\n"
            f"Resultado líquido das apostas: **{player_bet_net_sign}"
            f"{format_coins(player_bet_net)} moedas**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Upgrades da casa",
        value=(
            f"NPCs: nível **{status['npc_count_upgrade_level']}/"
            f"{MAIN_HOUSE_UPGRADE_MAX_LEVEL}**, "
            f"investido **{format_coins(status['npc_count_upgrade_costs_paid'])}**"
            + (
                f", próximo **{format_coins(status['next_npc_count_upgrade_cost'])}**"
                if status["next_npc_count_upgrade_cost"]
                else ", limite de NPCs/nível atingido"
            )
            + f"\nApostas por NPC: nível **{status['npc_bet_upgrade_level']}/"
            f"{MAIN_HOUSE_UPGRADE_MAX_LEVEL}**, "
            f"investido **{format_coins(status['npc_bet_upgrade_costs_paid'])}**"
            + (
                f", próximo **{format_coins(status['next_npc_bet_upgrade_cost'])}**"
                if status["next_npc_bet_upgrade_cost"]
                else ", nível máximo atingido"
            )
            + f"\nTotal investido: "
            f"**{format_coins(status['upgrade_costs_paid'])} moedas**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Exposição reservada",
        value=f"{format_coins(status['reservations'])} moedas",
        inline=True,
    )
    embed.add_field(
        name="Cassinos de servidor",
        value=(
            f"{status['casino_count']} cassinos | "
            f"{format_coins(status['local_treasury'])} moedas nos caixas locais"
        ),
        inline=False,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(
    name="criar_cassino",
    description="Cria o cassino e a moeda próprios deste servidor.",
)
@app_commands.guild_only()
@app_commands.describe(
    nome="Nome do cassino (2 a 40 caracteres).",
    moeda="Nome da moeda exclusiva deste servidor (2 a 16 caracteres).",
)
async def criar_cassino(
    interaction: discord.Interaction,
    nome: app_commands.Range[str, 2, 40],
    moeda: app_commands.Range[str, 2, 16],
) -> None:
    if not await ensure_betting_channel(interaction):
        return
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Este comando só pode ser usado em um servidor.",
            ephemeral=True,
        )
        return

    status, balance, _ = create_guild_casino(
        guild.id,
        interaction.user.id,
        get_house_owner_id(),
        nome.strip(),
        moeda.strip(),
    )
    if status == "exists":
        await interaction.response.send_message(
            "Este servidor já tem um cassino. O proprietário pode melhorá-lo "
            "com `/upgrade_cassino`.",
            ephemeral=True,
        )
        return
    if status == "insufficient":
        fee, _ = get_casino_settings()
        await interaction.response.send_message(
            f"Criar um cassino custa {format_coins(fee)} moedas globais. "
            f"Seu saldo é {format_coins(balance)}.",
            ephemeral=True,
        )
        return

    fee, _ = get_casino_settings()
    await interaction.response.send_message(
        f"🎰 **{nome.strip()}** foi criado para **{guild.name}**! "
        f"Moeda: **{moeda.strip()}**. Taxa paga à casa principal: "
        f"**{format_coins(fee)} moedas**. O cassino começa com "
        f"**{format_coins(CASINO_STARTING_TREASURY)} {moeda.strip()}** "
        f"no caixa, {CASINO_STARTING_NPCS} NPCs apostando conforme a presença "
        "do dono e com o "
        "jogo cara ou coroa liberado.",
    )


@bot.tree.command(
    name="excluir_cassino",
    description="Exclui seu cassino, converte o caixa e remove os dados locais.",
)
@app_commands.guild_only()
async def excluir_cassino(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Este comando só pode ser usado em um servidor.",
            ephemeral=True,
        )
        return

    casino = get_guild_casino(guild.id)
    if casino is None:
        await interaction.response.send_message(
            "Este servidor ainda não tem um cassino para excluir.",
            ephemeral=True,
        )
        return

    owner_id, name, currency_name, treasury, _ = casino
    if interaction.user.id != owner_id:
        await interaction.response.send_message(
            "Somente o proprietário do cassino pode excluí-lo.",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        f"Tem certeza que deseja excluir **{name}**? Ao confirmar, o caixa "
        f"atual de **{format_coins(treasury)} {currency_name}** será convertido "
        "em moedas globais na proporção de 1:1 para você. Todos os saldos "
        "locais dos jogadores e o histórico deste cassino serão apagados "
        "permanentemente. O valor transferido será o caixa no momento da "
        "confirmação.",
        view=DeleteGuildCasinoView(guild.id, owner_id, name),
        ephemeral=True,
    )


@bot.tree.command(
    name="contratar_npcs_cassino",
    description="Aumenta a quantidade de NPCs que apostam no seu cassino.",
)
@app_commands.guild_only()
@app_commands.describe(
    quantidade="NPCs para contratar (de 1 a 10), por 1.000 moedas cada."
)
async def contratar_npcs_cassino(
    interaction: discord.Interaction,
    quantidade: app_commands.Range[int, 1, 10],
) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Este comando só pode ser usado em um servidor.",
            ephemeral=True,
        )
        return

    status, treasury, npc_count = hire_guild_casino_npcs(
        guild.id,
        interaction.user.id,
        quantidade,
    )
    if status == "missing":
        message = "Este servidor ainda não tem um cassino. Use `/criar_cassino`."
    elif status == "not_owner":
        message = "Somente o proprietário do cassino pode contratar NPCs."
    elif status == "max_npcs":
        message = (
            f"O cassino pode ter no máximo {CASINO_MAX_NPCS} NPCs. "
            f"Atualmente tem {npc_count}."
        )
    elif status == "insufficient":
        cost = quantidade * CASINO_NPC_HIRE_COST
        message = (
            f"Contratar {quantidade} NPCs custa {format_coins(cost)} moedas. "
            f"O caixa do cassino tem {format_coins(treasury)}."
        )
    else:
        cost = quantidade * CASINO_NPC_HIRE_COST
        casino = get_guild_casino(guild.id)
        currency_name = casino[2] if casino is not None else "moedas"
        message = (
            f"✅ NPCs contratados! Seu cassino agora tem **{npc_count} NPCs** "
            f"apostando conforme a presença do dono. Custo: {format_coins(cost)} "
            f"{currency_name}. Caixa restante: {format_coins(treasury)} "
            f"{currency_name}."
        )
    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(
    name="solicitar_jogo_cassino",
    description="Envia ao dono do bot uma ideia de jogo para o seu cassino.",
)
@app_commands.guild_only()
@app_commands.describe(
    nome_jogo="Nome do jogo que você gostaria de adicionar.",
    pedido="Descreva como o jogo funcionaria (10 a 1500 caracteres).",
)
async def solicitar_jogo_cassino(
    interaction: discord.Interaction,
    nome_jogo: app_commands.Range[str, 2, 80],
    pedido: app_commands.Range[str, 10, 1500],
) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Este comando só pode ser usado em um servidor.",
            ephemeral=True,
        )
        return

    casino = get_guild_casino(guild.id)
    if casino is None:
        await interaction.response.send_message(
            "Este servidor ainda não tem um cassino.",
            ephemeral=True,
        )
        return
    if casino[0] != interaction.user.id:
        await interaction.response.send_message(
            "Somente o proprietário do cassino pode enviar pedidos de jogos.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    house_owner_id = get_house_owner_id()
    owner = bot.get_user(house_owner_id)
    if owner is None:
        try:
            owner = await bot.fetch_user(house_owner_id)
        except discord.HTTPException as error:
            logger.error(
                "Não foi possível localizar o dono do bot para encaminhar um pedido de jogo.",
                exc_info=(type(error), error, error.__traceback__),
            )
            await interaction.followup.send(
                "Não foi possível localizar o dono do bot para entregar seu pedido.",
                ephemeral=True,
            )
            return

    embed = discord.Embed(
        title="Pedido de novo jogo para cassino",
        description=pedido.strip(),
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Jogo solicitado",
        value=nome_jogo.strip(),
        inline=True,
    )
    embed.add_field(
        name="Cassino / servidor",
        value=f"{casino[1]} — {guild.name} (`{guild.id}`)",
        inline=False,
    )
    embed.add_field(
        name="Proprietário do cassino",
        value=(
            f"**{interaction.user.display_name}** "
            f"({interaction.user.mention}) (`{interaction.user.id}`)"
        ),
        inline=False,
    )

    try:
        await owner.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "Não consegui entregar o pedido por mensagem direta. "
            "Peça ao dono do bot para permitir DMs do bot e tente novamente.",
            ephemeral=True,
        )
        return
    except discord.HTTPException as error:
        logger.error(
            "Falha ao enviar por DM um pedido de jogo do cassino %s no servidor %s.",
            casino[1],
            guild.id,
            exc_info=(type(error), error, error.__traceback__),
        )
        await interaction.followup.send(
            "Ocorreu um erro ao enviar seu pedido por DM. Tente novamente mais tarde.",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        "Seu pedido de jogo foi enviado por DM ao dono do bot.",
        ephemeral=True,
    )


@bot.tree.command(
    name="feedback",
    description="Envia uma sugestão ou feedback do cassino ao dono do bot.",
)
@app_commands.describe(
    mensagem="Escreva seu feedback ou sugestão (10 a 1500 caracteres).",
)
async def feedback(
    interaction: discord.Interaction,
    mensagem: app_commands.Range[str, 10, 1500],
) -> None:
    cleaned_message = mensagem.strip()
    if len(cleaned_message) < 10:
        await interaction.response.send_message(
            "Escreva pelo menos 10 caracteres de feedback, sem contar espaços.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    house_owner_id = get_house_owner_id()
    owner = bot.get_user(house_owner_id)
    if owner is None:
        try:
            owner = await bot.fetch_user(house_owner_id)
        except discord.HTTPException as error:
            logger.error(
                "Não foi possível localizar o dono do bot para encaminhar feedback.",
                exc_info=(type(error), error, error.__traceback__),
            )
            await interaction.followup.send(
                "Não foi possível localizar o dono do bot para entregar seu feedback.",
                ephemeral=True,
            )
            return

    embed = discord.Embed(
        title="Feedback do cassino",
        description=cleaned_message,
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(
        name="Apostador",
        value=(
            f"**{interaction.user.display_name}** "
            f"({interaction.user.mention}) (`{interaction.user.id}`)"
        ),
        inline=False,
    )
    if interaction.guild is not None:
        embed.add_field(
            name="Servidor",
            value=f"{interaction.guild.name} (`{interaction.guild.id}`)",
            inline=False,
        )

    try:
        await owner.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "Não consegui entregar o feedback por mensagem direta. "
            "Peça ao dono do bot para permitir DMs do bot e tente novamente.",
            ephemeral=True,
        )
        return
    except discord.HTTPException as error:
        logger.error(
            "Falha ao enviar feedback por DM do apostador %s.",
            interaction.user.id,
            exc_info=(type(error), error, error.__traceback__),
        )
        await interaction.followup.send(
            "Ocorreu um erro ao enviar seu feedback por DM. "
            "Tente novamente mais tarde.",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        "Seu feedback foi enviado por DM ao dono do bot.",
        ephemeral=True,
    )


@bot.tree.command(
    name="daily_cassino",
    description="Resgata a recompensa diária na moeda do cassino do servidor.",
)
@app_commands.guild_only()
async def daily_cassino(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Este comando só pode ser usado em um servidor.",
            ephemeral=True,
        )
        return
    result, balance, amount = claim_guild_casino_reward(
        guild.id,
        interaction.user.id,
        "daily",
    )
    if result == "missing":
        await interaction.response.send_message(
            "Este servidor ainda não tem um cassino. Use `/criar_cassino`.",
            ephemeral=True,
        )
        return
    if result == "cooldown":
        await interaction.response.send_message(
            "Você já resgatou a recompensa diária do cassino. "
            f"Tente novamente em {format_remaining(amount)}.",
            ephemeral=True,
        )
        return
    if result == "insufficient_treasury":
        await interaction.response.send_message(
            "O caixa do cassino está sem fundos para pagar a recompensa diária.",
            ephemeral=True,
        )
        return

    casino = get_guild_casino(guild.id)
    currency_name = casino[2] if casino is not None else "moedas"
    await interaction.response.send_message(
        f"Você recebeu **{format_coins(amount)} {currency_name}**. "
        f"Saldo do cassino: **{format_coins(balance)} {currency_name}**."
    )


@bot.tree.command(
    name="weekly_cassino",
    description="Resgata a recompensa semanal na moeda do cassino do servidor.",
)
@app_commands.guild_only()
async def weekly_cassino(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Este comando só pode ser usado em um servidor.",
            ephemeral=True,
        )
        return
    result, balance, amount = claim_guild_casino_reward(
        guild.id,
        interaction.user.id,
        "weekly",
    )
    if result == "missing":
        await interaction.response.send_message(
            "Este servidor ainda não tem um cassino. Use `/criar_cassino`.",
            ephemeral=True,
        )
        return
    if result == "cooldown":
        await interaction.response.send_message(
            "Você já resgatou a recompensa semanal do cassino. "
            f"Tente novamente em {format_remaining(amount)}.",
            ephemeral=True,
        )
        return
    if result == "insufficient_treasury":
        await interaction.response.send_message(
            "O caixa do cassino está sem fundos para pagar a recompensa semanal.",
            ephemeral=True,
        )
        return

    casino = get_guild_casino(guild.id)
    currency_name = casino[2] if casino is not None else "moedas"
    await interaction.response.send_message(
        f"Você recebeu **{format_coins(amount)} {currency_name}**. "
        f"Saldo do cassino: **{format_coins(balance)} {currency_name}**."
    )


@bot.tree.command(
    name="saldo_cassino",
    description="Mostra seu saldo na moeda do cassino deste servidor.",
)
@app_commands.guild_only()
async def saldo_cassino(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    casino = get_guild_casino(guild.id) if guild is not None else None
    if casino is None:
        await interaction.response.send_message(
            "Este servidor ainda não tem um cassino. Use `/criar_cassino`.",
            ephemeral=True,
        )
        return
    balance = get_guild_casino_balance(guild.id, interaction.user.id)
    await interaction.response.send_message(
        f"{interaction.user.mention}, seu saldo em **{casino[2]}** é "
        f"**{format_coins(balance)} {casino[2]}**.",
        ephemeral=True,
    )


@bot.tree.command(
    name="status_cassino",
    description="Mostra estatísticas privadas do seu cassino neste servidor.",
)
@app_commands.guild_only()
async def status_cassino(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    status = get_guild_casino_status(guild.id) if guild is not None else None
    if status is None or guild is None:
        await interaction.response.send_message(
            "Este servidor ainda não tem um cassino. Use `/criar_cassino`.",
            ephemeral=True,
        )
        return

    (
        owner_id,
        name,
        currency_name,
        treasury,
        level,
        npc_count,
        games_played,
        npc_games,
        house_earned,
        house_lost,
        tax_paid,
        upgrade_costs_paid,
        npc_hiring_costs,
        rewards_paid,
        player_bet_volume,
        player_bet_count,
        player_bet_earned,
        player_bet_lost,
    ) = status
    if interaction.user.id != owner_id:
        await interaction.response.send_message(
            "Somente o proprietário do cassino pode ver estas estatísticas.",
            ephemeral=True,
        )
        return

    net_operating_profit = house_earned - house_lost - tax_paid
    net_sign = "+" if net_operating_profit > 0 else ""
    player_bet_net = player_bet_earned - player_bet_lost
    player_bet_net_sign = "+" if player_bet_net > 0 else ""
    embed = discord.Embed(
        title=f"Status do cassino — {name}",
        description=f"Estatísticas privadas de **{guild.name}**.",
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Caixa e operação",
        value=(
            f"Caixa: **{format_coins(treasury)} {currency_name}**\n"
            f"Nível: **{level}/{len(CASINO_UPGRADE_COSTS)}**\n"
            f"NPCs ativos: **{npc_count}** (limite {CASINO_MAX_NPCS})"
        ),
        inline=False,
    )
    embed.add_field(
        name="Operação de NPCs",
        value=(
            f"Apostas de NPCs: **{format_coins(npc_games)}**\n"
            f"Ganhos brutos: **{format_coins(house_earned)} {currency_name}**\n"
            f"Perdas: **{format_coins(house_lost)} {currency_name}**\n"
            f"Taxas enviadas à casa principal: "
            f"**{format_coins(tax_paid)} {currency_name}**\n"
            f"Resultado operacional líquido: **{net_sign}"
            f"{format_coins(net_operating_profit)} {currency_name}**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Apostas de jogadores",
        value=(
            f"Jogos liquidados: **{format_coins(games_played)}**\n"
            f"Volume apostado: **{format_coins(player_bet_volume)} "
            f"{currency_name}**\n"
            f"Apostas: **{format_coins(player_bet_count)}**\n"
            f"Ganhos brutos do cassino: **{format_coins(player_bet_earned)} "
            f"{currency_name}**\n"
            f"Prêmios pagos aos jogadores: **{format_coins(player_bet_lost)} "
            f"{currency_name}**\n"
            f"Resultado líquido: **{player_bet_net_sign}"
            f"{format_coins(player_bet_net)} {currency_name}**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Investimentos e recompensas",
        value=(
            f"Upgrades pagos à casa principal: "
            f"**{format_coins(upgrade_costs_paid)} {currency_name}**\n"
            f"Contratação de NPCs: **{format_coins(npc_hiring_costs)} {currency_name}**\n"
            f"Recompensas pagas aos jogadores: "
            f"**{format_coins(rewards_paid)} {currency_name}**"
        ),
        inline=False,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(
    name="leaderboard_cassino",
    description="Mostra o ranking da moeda do cassino deste servidor.",
)
@app_commands.guild_only()
async def leaderboard_cassino(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    ranking_data = (
        get_guild_casino_leaderboard(guild.id)
        if guild is not None
        else None
    )
    if ranking_data is None:
        await interaction.response.send_message(
            "Este servidor ainda não tem um cassino. Use `/criar_cassino`.",
            ephemeral=True,
        )
        return
    name, currency_name, ranking = ranking_data
    if not ranking:
        await interaction.response.send_message(
            "Ainda não há jogadores no ranking deste cassino.",
            ephemeral=True,
        )
        return
    lines = [
        f"**{position}.** <@{user_id}> — **{format_coins(balance)} "
        f"{currency_name}** | Ganho: {format_coins(earned)}"
        f" | Perdido: {format_coins(lost)}"
        for position, (user_id, balance, earned, lost) in enumerate(
            ranking,
            start=1,
        )
    ]
    embed = discord.Embed(
        title=f"Leaderboard — {name}",
        description="\n".join(lines),
        color=discord.Color.gold(),
    )
    await interaction.response.send_message(embed=embed)


def create_guild_casino_upgrade_embed(
    treasury: int,
    level: int,
    currency_name: str,
) -> discord.Embed:
    cost = CASINO_UPGRADE_COSTS[level]
    next_level = level + 1
    unlocked_game = next(
        game
        for game, required_level in CASINO_GAME_UNLOCKS.items()
        if required_level == next_level
    )
    embed = discord.Embed(
        title=f"Confirmar upgrade do cassino — nível {next_level}",
        description=(
            f"O jogo **{unlocked_game}** será liberado e a taxa da casa "
            f"principal reduzirá em {CASINO_TAX_REDUCTION_PER_LEVEL} ponto "
            f"percentual por nível, até o mínimo de "
            f"{CASINO_MINIMUM_TAX_PERCENT}%."
        ),
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Custo",
        value=f"**{format_coins(cost)} {currency_name}**",
        inline=True,
    )
    embed.add_field(
        name="Caixa após a compra",
        value=f"**{format_coins(treasury - cost)} {currency_name}**",
        inline=True,
    )
    return embed


class GuildCasinoUpgradeView(discord.ui.View):
    def __init__(self, guild_id: int, owner_id: int, expected_level: int) -> None:
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.expected_level = expected_level

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "Somente o proprietário do cassino pode confirmar este upgrade.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(
        label="Confirmar upgrade",
        emoji="✅",
        style=discord.ButtonStyle.success,
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        status, treasury, level, cost = upgrade_guild_casino(
            self.guild_id,
            self.owner_id,
            self.expected_level,
        )
        if status == "upgraded":
            casino = get_guild_casino(self.guild_id)
            currency_name = casino[2] if casino is not None else "moedas"
            unlocked_game = next(
                game
                for game, required_level in CASINO_GAME_UNLOCKS.items()
                if required_level == level
            )
            message = (
                f"✅ Cassino promovido ao nível **{level}**! "
                f"Jogo liberado: **{unlocked_game}**. Os **"
                f"{format_coins(cost)} {currency_name}** foram pagos à "
                "casa principal."
            )
            if level < len(CASINO_UPGRADE_COSTS):
                next_cost = CASINO_UPGRADE_COSTS[level]
                if treasury >= next_cost:
                    message += (
                        f"\n\nO próximo upgrade custa **"
                        f"{format_coins(next_cost)} {currency_name}**. "
                        "Deseja continuar?"
                    )
                    next_view = GuildCasinoUpgradeView(
                        self.guild_id,
                        self.owner_id,
                        level,
                    )
                    next_embed = create_guild_casino_upgrade_embed(
                        treasury,
                        level,
                        currency_name,
                    )
                    self.stop()
                    await interaction.response.edit_message(
                        content=message,
                        embed=next_embed,
                        view=next_view,
                    )
                    return
                message += (
                    f"\nO próximo nível custa **"
                    f"{format_coins(next_cost)} {currency_name}**; "
                    "o caixa atual não permite continuar."
                )
        elif status == "missing":
            message = "Este servidor ainda não tem um cassino. Use `/criar_cassino`."
        elif status == "not_owner":
            message = "Somente o proprietário atual do cassino pode melhorá-lo."
        elif status == "changed":
            message = (
                "O nível do cassino mudou desde a prévia. Nenhum valor foi "
                "debitado; execute `/upgrade_cassino` novamente."
            )
        elif status == "max_level":
            message = "O cassino já está no nível máximo."
        else:
            message = (
                f"Caixa insuficiente: o upgrade custa "
                f"**{format_coins(cost)} moedas**, mas o caixa disponível é "
                f"**{format_coins(treasury)} moedas**."
            )
        button.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content=message,
            embed=None,
            view=None,
        )

    @discord.ui.button(
        label="Cancelar",
        emoji="✖️",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        button.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content="Upgrade cancelado; nenhum valor foi debitado.",
            embed=None,
            view=None,
        )


@bot.tree.command(
    name="upgrade_cassino",
    description="Pré-visualiza e confirma um upgrade do cassino.",
)
@app_commands.guild_only()
async def upgrade_cassino(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Este comando só pode ser usado em um servidor.",
            ephemeral=True,
        )
        return
    casino = get_guild_casino(guild.id)
    if casino is None:
        message = "Este servidor ainda não tem um cassino. Use `/criar_cassino`."
        await interaction.response.send_message(message, ephemeral=True)
        return
    owner_id, _, currency_name, treasury, level = casino
    if interaction.user.id != owner_id:
        message = "Somente o proprietário do cassino pode comprar upgrades."
        await interaction.response.send_message(message, ephemeral=True)
        return
    if level >= len(CASINO_UPGRADE_COSTS):
        await interaction.response.send_message(
            "O cassino já está no nível máximo.",
            ephemeral=True,
        )
        return
    cost = CASINO_UPGRADE_COSTS[level]
    if treasury < cost:
        await interaction.response.send_message(
            f"O upgrade custa **{format_coins(cost)} {currency_name}**, "
            f"mas o caixa tem **{format_coins(treasury)} {currency_name}**.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        embed=create_guild_casino_upgrade_embed(treasury, level, currency_name),
        view=GuildCasinoUpgradeView(guild.id, owner_id, level),
        ephemeral=True,
    )


@bot.tree.command(
    name="jogar_cassino",
    description="Joga por moedas no cassino próprio deste servidor.",
)
@app_commands.guild_only()
@app_commands.describe(
    aposta="Quantidade de moedas locais para apostar.",
    jogo="Escolha um jogo já liberado pelo cassino.",
    escolha="Cara/coroa, par/ímpar, número 1-6 ou vermelho/preto/verde.",
)
@app_commands.choices(
    jogo=[
        app_commands.Choice(name="Cara ou coroa", value="moeda"),
        app_commands.Choice(name="Dados", value="dados"),
        app_commands.Choice(name="Roleta", value="roleta"),
        app_commands.Choice(name="Caça-níquel", value="cacaniquel"),
    ]
)
async def jogar_cassino(
    interaction: discord.Interaction,
    aposta: app_commands.Range[int, 1, PLAYER_BET_PARAMETER_MAX],
    jogo: app_commands.Choice[str],
    escolha: str | None = None,
) -> None:
    if not await ensure_betting_channel(interaction):
        return
    if not await ensure_bet_limit(interaction, aposta):
        return
    guild = interaction.guild
    casino = get_guild_casino(guild.id) if guild is not None else None
    if casino is None or guild is None:
        await interaction.response.send_message(
            "Este servidor ainda não tem um cassino. Use `/criar_cassino`.",
            ephemeral=True,
        )
        return
    _, name, currency_name, _, upgrade_level = casino
    required_level = CASINO_GAME_UNLOCKS[jogo.value]
    if upgrade_level < required_level:
        await interaction.response.send_message(
            f"**{jogo.name}** ainda está bloqueado. O cassino precisa "
            f"chegar ao nível **{required_level}**.",
            ephemeral=True,
        )
        return

    drawn = ""
    if jogo.value == "moeda":
        normalized_choice = (escolha or "").strip().lower()
        if normalized_choice not in ("cara", "coroa"):
            await interaction.response.send_message(
                "Para cara ou coroa, escolha `cara` ou `coroa`.",
                ephemeral=True,
            )
            return
        drawn = random.choice(("cara", "coroa"))
        payout = aposta * 19 // 10 if normalized_choice == drawn else 0
        choice_text = f"Escolha: **{normalized_choice}**."
        result = f"A moeda caiu em **{drawn}**."
    elif jogo.value == "dados":
        normalized_choice = (escolha or "").strip().lower()
        if normalized_choice == "impar":
            normalized_choice = "ímpar"
        if normalized_choice not in ("par", "ímpar", "1", "2", "3", "4", "5", "6"):
            await interaction.response.send_message(
                "Para dados, escolha `par`, `ímpar` ou um número de `1` a `6`.",
                ephemeral=True,
            )
            return
        roll = random.randint(1, 6)
        if normalized_choice in ("par", "ímpar"):
            drawn = "par" if roll % 2 == 0 else "ímpar"
            won = drawn == normalized_choice
            multiplier = 19 / 10
        else:
            drawn = str(roll)
            won = roll == int(normalized_choice)
            multiplier = 57 / 10
        payout = aposta * int(multiplier * 10) // 10 if won else 0
        choice_text = f"Escolha: **{normalized_choice}**."
        result = f"O dado caiu em **{roll}** ({'par' if roll % 2 == 0 else 'ímpar'})."
    elif jogo.value == "roleta":
        normalized_choice = (escolha or "").strip().lower()
        if normalized_choice not in ("vermelho", "preto", "verde"):
            await interaction.response.send_message(
                "Para a roleta, escolha `vermelho`, `preto` ou `verde`.",
                ephemeral=True,
            )
            return
        number = random.randint(0, 36)
        drawn = (
            "verde"
            if number == 0
            else "vermelho"
            if number in ROULETTE_RED_NUMBERS
            else "preto"
        )
        multiplier = 342 if normalized_choice == "verde" else 19
        payout = aposta * multiplier // 10 if normalized_choice == drawn else 0
        choice_text = f"Escolha: **{normalized_choice}**."
        result = f"A roleta parou no **{number} {drawn}**."
    else:
        reels = random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=3)
        payout, combination, multiplier = slot_payout(reels, aposta)
        drawn = " | ".join(reels)
        choice_text = f"Combinação: **{drawn}**."
        result = (
            f"{combination}! Multiplicador x{multiplier}. "
            f"Combinação: **{drawn}**."
        )

    payout = adjust_player_bet_payout(interaction.user.id, aposta, payout)
    settlement = settle_guild_casino_bet(
        guild.id,
        interaction.user.id,
        get_house_owner_id(),
        aposta,
        payout,
    )
    status, balance, treasury, tax_percent, tax = settlement
    if status == "insufficient_player":
        await interaction.response.send_message(
            f"Saldo insuficiente em **{currency_name}**. "
            f"Você tem {format_coins(balance)}.",
            ephemeral=True,
        )
        return
    if status == "insufficient_treasury":
        await interaction.response.send_message(
            f"O caixa do cassino não consegue cobrir esse prêmio; "
            "a aposta foi cancelada e seu saldo não mudou.",
            ephemeral=True,
        )
        return
    if status != "settled":
        await interaction.response.send_message(
            "Não foi possível concluir a aposta porque o cassino não está disponível.",
            ephemeral=True,
        )
        return

    net_change = payout - aposta
    net_sign = "+" if net_change > 0 else ""
    embed = discord.Embed(
        title=(
            f"{'🎉 VOCÊ GANHOU!' if net_change > 0 else '❌ VOCÊ PERDEU' if net_change < 0 else '🤝 SEM LUCRO OU PREJUÍZO'} — {name}"
        ),
        description=f"{result}\n{choice_text}",
        color=(
            discord.Color.green()
            if net_change > 0
            else discord.Color.red()
            if net_change < 0
            else discord.Color.gold()
        ),
    )
    embed.add_field(
        name="Aposta",
        value=f"{format_coins(aposta)} {currency_name}",
        inline=True,
    )
    embed.add_field(
        name="Retorno total",
        value=f"{format_coins(payout)} {currency_name}",
        inline=True,
    )
    embed.add_field(
        name="Lucro / prejuízo",
        value=f"{net_sign}{format_coins(net_change)} {currency_name}",
        inline=True,
    )
    embed.add_field(
        name="Taxa paga à casa principal",
        value=f"{format_coins(tax)} {currency_name} ({tax_percent}%)",
        inline=True,
    )
    embed.set_footer(
        text=(
            f"Seu saldo: {format_coins(balance)} {currency_name} | "
            f"Caixa do cassino: {format_coins(treasury)} {currency_name}"
        )
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="cacaniquel", description="Gire a máquina caça-níquel usando suas moedas.")
@app_commands.guild_only()
@app_commands.describe(aposta="Quantidade de moedas para apostar (de 1 a 1.000.000).")
async def cacaniquel(
    interaction: discord.Interaction,
    aposta: app_commands.Range[int, 1, PLAYER_BET_PARAMETER_MAX],
) -> None:
    if not await ensure_betting_channel(interaction):
        return
    if not await ensure_not_house_owner(interaction):
        return
    if not await ensure_bet_limit(interaction, aposta):
        return

    await interaction.response.defer()
    reels = random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=3)
    payout, combination, multiplier = slot_payout(reels, aposta)
    payout = adjust_player_bet_payout(interaction.user.id, aposta, payout)
    animation = await asyncio.to_thread(render_slot_gif, reels, payout, multiplier)

    settled, balance, _ = settle_house_bet(
        interaction.user.id,
        get_house_owner_id(),
        aposta,
        payout,
    )
    if not settled:
        await interaction.followup.send(
            "A aposta foi cancelada: saldo insuficiente ou banca principal "
            "sem fundos para cobrir este resultado. "
            f"Seu saldo continua em {format_coins(balance)} moedas.",
            ephemeral=True,
        )
        return

    if payout:
        outcome = f"**{combination}! Multiplicador x{multiplier}.**"
        result_title = "🎉 VOCÊ GANHOU!"
        net_change = payout - aposta
        color = discord.Color.green()
    else:
        outcome = f"**{combination}.**"
        result_title = "😿 SEM PRÊMIO"
        net_change = -aposta
        color = discord.Color.red()

    embed = discord.Embed(
        title=f"🎰 CAÇA-NÍQUEL — {result_title}",
        description=outcome,
        color=color,
    )
    embed.add_field(
        name="🎲 Resultado",
        value=f"` {'  |  '.join(reels)} `",
        inline=False,
    )
    embed.set_image(url="attachment://cacaniquel.gif")
    embed.add_field(
        name="🪙 Aposta",
        value=f"{format_coins(aposta)} moedas",
        inline=True,
    )
    embed.add_field(
        name="💰 Retorno total (inclui aposta)",
        value=f"{format_coins(payout)} moedas",
        inline=True,
    )
    net_sign = "+" if net_change > 0 else ""
    embed.add_field(
        name="📊 Lucro / prejuízo",
        value=f"{net_sign}{format_coins(net_change)} moedas",
        inline=True,
    )
    embed.add_field(
        name="Combinações premiadas",
        value=(
            "Pares: 🍒 x1 • 🍋 x1 • 🔔 x2 • 💎 x3 • ⭐ x4 • 7️⃣ x6\n"
            "Trincas: 🍒 x2 • 🍋 x3 • 🔔 x5 • 💎 x8 • ⭐ x12 • 7️⃣ x25\n"
            "O multiplicador indica o total de moedas recebido."
        ),
        inline=False,
    )
    embed.set_footer(text=f"Saldo atual: {format_coins(balance)} moedas")
    await interaction.followup.send(
        embed=embed,
        file=discord.File(animation, filename="cacaniquel.gif"),
    )


@bot.tree.command(name="corrida", description="Aposte em até três animais e tente acertar o sorteado.")
@app_commands.guild_only()
@app_commands.describe(
    aposta="Moedas para apostar.",
    animal="Primeiro animal escolhido.",
    animal_2="Segundo animal opcional; reduz o multiplicador.",
    animal_3="Terceiro animal opcional; reduz ainda mais o multiplicador.",
)
@app_commands.choices(
    animal=[app_commands.Choice(name=animal, value=animal) for animal in BETTING_ANIMALS],
    animal_2=[app_commands.Choice(name=animal, value=animal) for animal in BETTING_ANIMALS],
    animal_3=[app_commands.Choice(name=animal, value=animal) for animal in BETTING_ANIMALS],
)
async def corrida(
    interaction: discord.Interaction,
    aposta: app_commands.Range[int, 1, PLAYER_BET_PARAMETER_MAX],
    animal: str,
    animal_2: str | None = None,
    animal_3: str | None = None,
) -> None:
    if not await ensure_betting_channel(interaction):
        return
    if not await ensure_not_house_owner(interaction):
        return
    if not await ensure_bet_limit(interaction, aposta):
        return

    selected_animals = [animal]
    if animal_2 is not None:
        selected_animals.append(animal_2)
    if animal_3 is not None:
        selected_animals.append(animal_3)
    if len(set(selected_animals)) != len(selected_animals):
        await interaction.response.send_message(
            "Escolha animais diferentes em cada opção.",
            ephemeral=True,
        )
        return

    if any(selected not in BETTING_ANIMALS for selected in selected_animals):
        await interaction.response.send_message(
            "Um ou mais animais escolhidos são inválidos.",
            ephemeral=True,
        )
        return

    drawn_animal = random.choice(BETTING_ANIMALS)
    payout, multiplier = animal_bet_payout(
        selected_animals,
        drawn_animal,
        aposta,
    )
    payout = adjust_player_bet_payout(interaction.user.id, aposta, payout)
    bet_status, balance, remaining = settle_animal_house_bet(
        interaction.user.id,
        get_house_owner_id(),
        aposta,
        payout,
    )
    if bet_status == "cooldown":
        await interaction.response.send_message(
            "Você já apostou no sorteio de animais hoje. "
            f"Tente novamente em {format_remaining(remaining)}.",
            ephemeral=True,
        )
        return
    if bet_status != "accepted":
        error = (
            f"Saldo insuficiente. Você tem {format_coins(balance)} moedas."
            if bet_status == "insufficient"
            else "A aposta foi cancelada porque a banca principal não consegue "
            "cobrir esse prêmio."
        )
        await interaction.response.send_message(error, ephemeral=True)
        return

    if payout:
        result = f"🎉 O animal sorteado foi **{drawn_animal}**!"
        color = discord.Color.green()
        result_title = "VOCÊ GANHOU!"
        net_change = payout - aposta
    else:
        result = f"🐾 O animal sorteado foi **{drawn_animal}**."
        color = discord.Color.red()
        result_title = "NÃO FOI DESSA VEZ"
        net_change = -aposta

    embed = discord.Embed(
        title=f"🐾 SORTEIO DOS ANIMAIS — {result_title}",
        description=result,
        color=color,
    )
    embed.add_field(
        name="Suas escolhas",
        value="  |  ".join(selected_animals),
        inline=False,
    )
    embed.add_field(
        name="Resultado da aposta",
        value=(
            "✅ O animal sorteado está entre suas escolhas."
            if payout
            else "❌ O animal sorteado não está entre suas escolhas."
        ),
        inline=False,
    )
    embed.add_field(
        name="🪙 Aposta",
        value=f"{format_coins(aposta)} moedas",
        inline=True,
    )
    embed.add_field(
        name="✖️ Multiplicador",
        value=f"{multiplier:g}x",
        inline=True,
    )
    embed.add_field(
        name="💰 Retorno total (inclui aposta)",
        value=f"{format_coins(payout)} moedas",
        inline=True,
    )
    net_sign = "+" if net_change > 0 else ""
    embed.add_field(
        name="📊 Resultado líquido",
        value=f"{net_sign}{format_coins(net_change)} moedas",
        inline=True,
    )
    embed.set_footer(text=f"Saldo atual: {format_coins(balance)} moedas")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="moeda", description="Aposte em cara ou coroa e ganhe o dobro do retorno.")
@app_commands.guild_only()
@app_commands.describe(aposta="Quantidade de moedas para apostar.")
@app_commands.choices(
    escolha=[
        app_commands.Choice(name="Cara", value="cara"),
        app_commands.Choice(name="Coroa", value="coroa"),
    ]
)
async def moeda(
    interaction: discord.Interaction,
    aposta: app_commands.Range[int, 1, PLAYER_BET_PARAMETER_MAX],
    escolha: app_commands.Choice[str],
) -> None:
    if not await ensure_betting_channel(interaction):
        return
    if not await ensure_not_house_owner(interaction):
        return
    if not await ensure_bet_limit(interaction, aposta):
        return

    result = random.choice(("cara", "coroa"))
    payout = aposta * 2 if escolha.value == result else 0
    payout = adjust_player_bet_payout(interaction.user.id, aposta, payout)
    settled, balance, _ = settle_house_bet(
        interaction.user.id,
        get_house_owner_id(),
        aposta,
        payout,
    )
    if not settled:
        await interaction.response.send_message(
            "A aposta foi cancelada: saldo insuficiente ou banca principal "
            "sem fundos para cobrir este resultado. "
            f"Seu saldo continua em {format_coins(balance)} moedas.",
            ephemeral=True,
        )
        return

    await send_bet_result(
        interaction,
        game="CARA OU COROA",
        bet=aposta,
        choice=f"Você escolheu **{escolha.name}**.",
        result=f"A moeda caiu em **{result.capitalize()}**.",
        payout=payout,
        balance=balance,
    )


@bot.tree.command(name="dados", description="Aposte em par, ímpar ou no valor exato de um dado.")
@app_commands.guild_only()
@app_commands.describe(aposta="Quantidade de moedas para apostar.")
@app_commands.choices(
    escolha=[
        app_commands.Choice(name="Par (retorno x2)", value="par"),
        app_commands.Choice(name="Ímpar (retorno x2)", value="ímpar"),
        *[
            app_commands.Choice(name=f"Número {number} (retorno x5)", value=str(number))
            for number in range(1, 7)
        ],
    ]
)
async def dados(
    interaction: discord.Interaction,
    aposta: app_commands.Range[int, 1, PLAYER_BET_PARAMETER_MAX],
    escolha: app_commands.Choice[str],
) -> None:
    if not await ensure_betting_channel(interaction):
        return
    if not await ensure_not_house_owner(interaction):
        return
    if not await ensure_bet_limit(interaction, aposta):
        return

    roll = random.randint(1, 6)
    if escolha.value in ("par", "ímpar"):
        won = ("par" if roll % 2 == 0 else "ímpar") == escolha.value
        multiplier = 2
    else:
        won = roll == int(escolha.value)
        multiplier = 5

    payout = aposta * multiplier if won else 0
    payout = adjust_player_bet_payout(interaction.user.id, aposta, payout)
    settled, balance, _ = settle_house_bet(
        interaction.user.id,
        get_house_owner_id(),
        aposta,
        payout,
    )
    if not settled:
        await interaction.response.send_message(
            "A aposta foi cancelada: saldo insuficiente ou banca principal "
            "sem fundos para cobrir este resultado. "
            f"Seu saldo continua em {format_coins(balance)} moedas.",
            ephemeral=True,
        )
        return

    await send_bet_result(
        interaction,
        game="DADOS",
        bet=aposta,
        choice=f"Você escolheu **{escolha.name}**.",
        result=f"O dado caiu em **{roll}** ({'par' if roll % 2 == 0 else 'ímpar'}).",
        payout=payout,
        balance=balance,
    )


@bot.tree.command(name="roleta", description="Aposte em uma cor da roleta europeia.")
@app_commands.guild_only()
@app_commands.describe(aposta="Quantidade de moedas para apostar.")
@app_commands.choices(
    cor=[
        app_commands.Choice(name="Vermelho (retorno x2)", value="vermelho"),
        app_commands.Choice(name="Preto (retorno x2)", value="preto"),
        app_commands.Choice(name="Verde / zero (retorno x36)", value="verde"),
    ]
)
async def roleta(
    interaction: discord.Interaction,
    aposta: app_commands.Range[int, 1, PLAYER_BET_PARAMETER_MAX],
    cor: app_commands.Choice[str],
) -> None:
    if not await ensure_betting_channel(interaction):
        return
    if not await ensure_not_house_owner(interaction):
        return
    if not await ensure_bet_limit(interaction, aposta):
        return

    number = random.randint(0, 36)
    result_color = (
        "verde"
        if number == 0
        else "vermelho"
        if number in ROULETTE_RED_NUMBERS
        else "preto"
    )
    multiplier = 36 if cor.value == "verde" else 2
    payout = aposta * multiplier if cor.value == result_color else 0
    payout = adjust_player_bet_payout(interaction.user.id, aposta, payout)
    settled, balance, _ = settle_house_bet(
        interaction.user.id,
        get_house_owner_id(),
        aposta,
        payout,
    )
    if not settled:
        await interaction.response.send_message(
            "A aposta foi cancelada: saldo insuficiente ou banca principal "
            "sem fundos para cobrir este resultado. "
            f"Seu saldo continua em {format_coins(balance)} moedas.",
            ephemeral=True,
        )
        return

    await send_bet_result(
        interaction,
        game="ROLETA EUROPEIA",
        bet=aposta,
        choice=f"Você apostou em **{cor.name}**.",
        result=f"A roleta parou no **{number} {result_color}**.",
        payout=payout,
        balance=balance,
    )


@bot.tree.command(
    name="duelo",
    description="Desafie alguém para dados ou jokenpô apostando moedas.",
)
@app_commands.guild_only()
@app_commands.describe(
    oponente="Pessoa que você quer desafiar.",
    aposta="Valor que cada jogador aposta.",
    jogo="Escolha o jogo do desafio.",
)
@app_commands.choices(
    jogo=[
        app_commands.Choice(name="Dados (maior resultado vence)", value="dados"),
        app_commands.Choice(name="Jokenpô", value="jokenpo"),
    ]
)
async def duelo(
    interaction: discord.Interaction,
    oponente: discord.Member,
    aposta: app_commands.Range[int, 1, PLAYER_BET_PARAMETER_MAX],
    jogo: app_commands.Choice[str],
) -> None:
    if not await ensure_betting_channel(interaction):
        return
    if not await ensure_bet_limit(interaction, aposta):
        return
    opponent_limit = get_player_bet_limit(oponente.id)
    if aposta > opponent_limit:
        await interaction.response.send_message(
            f"O limite atual de aposta de {oponente.mention} é "
            f"{format_coins(opponent_limit)} moedas.",
            ephemeral=True,
        )
        return
    if oponente.id == interaction.user.id:
        await interaction.response.send_message(
            "Você não pode desafiar a si mesmo.",
            ephemeral=True,
        )
        return
    if oponente.bot:
        await interaction.response.send_message(
            "Desafios de aposta só podem ser feitos contra outra pessoa.",
            ephemeral=True,
        )
        return

    view = DuelView(interaction.user, oponente, aposta, jogo.value)
    await interaction.response.send_message(embed=view.create_embed(), view=view)
    view.message = await interaction.original_response()


@bot.tree.command(name="blackjack", description="Joga uma partida de blackjack com o bot.")
@app_commands.guild_only()
@app_commands.describe(aposta="Quantidade de moedas que deseja apostar.")
async def blackjack(
    interaction: discord.Interaction,
    aposta: app_commands.Range[int, 1, PLAYER_BET_PARAMETER_MAX],
) -> None:
    if not await ensure_betting_channel(interaction):
        return
    if not await ensure_not_house_owner(interaction):
        return

    if not await ensure_bet_limit(interaction, aposta):
        return

    house_owner_id = get_house_owner_id()
    reserved, balance, reservation_or_reason = reserve_blackjack_bet(
        interaction.user.id,
        house_owner_id,
        aposta,
    )
    if not reserved:
        message = (
            f"Saldo insuficiente. Você tem {format_coins(balance)} moedas."
            if reservation_or_reason == "player"
            else "A banca principal não tem saldo livre suficiente para cobrir "
            "a aposta máxima desta partida."
        )
        await interaction.response.send_message(
            message,
            ephemeral=True,
        )
        return

    buycards = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
    player_cards = [random.choice(buycards), random.choice(buycards)]
    dealer_cards = [random.choice(buycards), random.choice(buycards)]
    game = BlackjackView(
        interaction.user,
        aposta,
        player_cards,
        dealer_cards,
        balance,
        house_owner_id,
        reservation_or_reason,
    )
    if hand_total(player_cards) == 21:
        game.result = "Blackjack! Sua mão inicial chegou a 21."
        game._resolve()

    await interaction.response.send_message(
        embed=game.create_embed(),
        view=None if game.finished else game,
    )
    if not game.finished:
        game.message = await interaction.original_response()

@bot.tree.command(name="clear", description="Apaga de 1 a 100 mensagens recentes do canal.")
@app_commands.guild_only()
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.checks.bot_has_permissions(manage_messages=True)
@app_commands.describe(amount="Quantidade de mensagens a apagar (de 1 a 100).")
async def clear(
    interaction: discord.Interaction,
    amount: app_commands.Range[int, 1, 100],
) -> None:
    channel = interaction.channel
    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        await interaction.response.send_message(
            "Este comando só pode ser usado em canais de texto.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    deleted = await channel.purge(limit=amount)
    await interaction.followup.send(
        f"{len(deleted)} mensagens foram apagadas.",
        ephemeral=True,
    )


@bot.tree.command(name="kick", description="Expulsa um membro do servidor.")
@app_commands.guild_only()
@app_commands.checks.has_permissions(kick_members=True)
@app_commands.checks.bot_has_permissions(kick_members=True)
@app_commands.describe(member="Membro a expulsar.", reason="Motivo opcional.")
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str | None = None,
) -> None:
    guild = interaction.guild
    bot_member = guild.me if guild else None
    if guild is None or bot_member is None:
        await interaction.response.send_message(
            "Não foi possível confirmar o membro do bot neste servidor.",
            ephemeral=True,
        )
        return

    if violates_moderation_hierarchy(interaction, member):
        await interaction.response.send_message(
            "Não posso expulsar esse membro por causa da hierarquia de cargos.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    await member.kick(reason=reason)
    await interaction.followup.send(f"{member} foi expulso do servidor.", ephemeral=True)


@bot.tree.command(name="ban", description="Bane um membro do servidor.")
@app_commands.guild_only()
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.checks.bot_has_permissions(ban_members=True)
@app_commands.describe(member="Membro a banir.", reason="Motivo opcional.")
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str | None = None,
) -> None:
    guild = interaction.guild
    bot_member = guild.me if guild else None
    if guild is None or bot_member is None:
        await interaction.response.send_message(
            "Não foi possível confirmar o membro do bot neste servidor.",
            ephemeral=True,
        )
        return

    if violates_moderation_hierarchy(interaction, member):
        await interaction.response.send_message(
            "Não posso banir esse membro por causa da hierarquia de cargos.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    await member.ban(reason=reason)
    await interaction.followup.send(f"{member} foi banido do servidor.", ephemeral=True)


@bot.tree.command(name="unban", description="Desbane um usuário pelo ID.")
@app_commands.guild_only()
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.checks.bot_has_permissions(ban_members=True)
@app_commands.describe(user_id="ID numérico do usuário a desbanir.", reason="Motivo opcional.")
async def unban(
    interaction: discord.Interaction,
    user_id: str,
    reason: str | None = None,
) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Este comando só pode ser usado em um servidor.",
            ephemeral=True,
        )
        return

    try:
        parsed_user_id = int(user_id)
    except ValueError:
        await interaction.response.send_message(
            "O ID precisa ser numérico.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    try:
        user = await bot.fetch_user(parsed_user_id)
    except discord.NotFound:
        await interaction.followup.send(
            "Usuário não encontrado.",
            ephemeral=True,
        )
        return

    try:
        await guild.unban(user, reason=reason)
    except discord.NotFound:
        await interaction.followup.send(
            "Esse usuário não está banido neste servidor.",
            ephemeral=True,
        )
        return

    await interaction.followup.send(f"{user} foi desbanido do servidor.", ephemeral=True)


async def get_or_create_muted_role(guild: discord.Guild) -> discord.Role:
    muted_role = discord.utils.get(guild.roles, name="Muted")
    if muted_role is not None:
        return muted_role

    muted_role = await guild.create_role(
        name="Muted",
        reason="Role usada pelo comando slash /mute",
    )
    for channel in guild.channels:
        if isinstance(
            channel,
            (
                discord.TextChannel,
                discord.VoiceChannel,
                discord.StageChannel,
                discord.ForumChannel,
                discord.CategoryChannel,
            ),
        ):
            await channel.set_permissions(
                muted_role,
                send_messages=False,
                send_messages_in_threads=False,
                add_reactions=False,
                speak=False,
                connect=False,
            )

    return muted_role


@bot.tree.command(name="mute", description="Silencia um membro usando o cargo Muted.")
@app_commands.guild_only()
@app_commands.checks.has_permissions(manage_roles=True)
@app_commands.checks.bot_has_permissions(manage_roles=True)
@app_commands.describe(member="Membro a silenciar.", reason="Motivo opcional.")
async def mute(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str | None = None,
) -> None:
    guild = interaction.guild
    bot_member = guild.me if guild else None
    if guild is None or bot_member is None:
        await interaction.response.send_message(
            "Não foi possível confirmar o membro do bot neste servidor.",
            ephemeral=True,
        )
        return

    if violates_moderation_hierarchy(interaction, member):
        await interaction.response.send_message(
            "Não posso silenciar esse membro por causa da hierarquia de cargos.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    muted_role = await get_or_create_muted_role(guild)
    if muted_role in member.roles:
        await interaction.followup.send(f"{member} já está silenciado.", ephemeral=True)
        return

    await member.add_roles(
        muted_role,
        reason=reason or f"Silenciado por {interaction.user}",
    )
    await interaction.followup.send(f"{member} foi silenciado.", ephemeral=True)


@bot.tree.command(name="unmute", description="Remove o cargo Muted de um membro.")
@app_commands.guild_only()
@app_commands.checks.has_permissions(manage_roles=True)
@app_commands.checks.bot_has_permissions(manage_roles=True)
@app_commands.describe(member="Membro a dessilenciar.", reason="Motivo opcional.")
async def unmute(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str | None = None,
) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Este comando só pode ser usado em um servidor.",
            ephemeral=True,
        )
        return

    muted_role = discord.utils.get(guild.roles, name="Muted")
    if muted_role is None or muted_role not in member.roles:
        await interaction.response.send_message(
            f"{member} não está silenciado.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    await member.remove_roles(
        muted_role,
        reason=reason or f"Dessilenciado por {interaction.user}",
    )
    await interaction.followup.send(f"{member} foi dessilenciado.", ephemeral=True)


@bot.tree.command(name="serverinfo", description="Mostra informações do servidor.")
@app_commands.guild_only()
async def serverinfo(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Este comando só pode ser usado em um servidor.",
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title=f"Informações do servidor: {guild.name}",
        color=discord.Color.blue(),
    )
    embed.add_field(name="ID do servidor", value=str(guild.id), inline=False)
    embed.add_field(
        name="Dono do servidor",
        value=guild.owner.mention if guild.owner else "Desconhecido",
        inline=False,
    )
    embed.add_field(name="Membros", value=str(guild.member_count or "Desconhecido"), inline=False)
    if guild.icon is not None:
        embed.set_thumbnail(url=guild.icon.url)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="userinfo", description="Mostra informações de um usuário.")
@app_commands.describe(member="Usuário opcional; por padrão, mostra suas informações.")
async def userinfo(
    interaction: discord.Interaction,
    member: discord.Member | None = None,
) -> None:
    target = member or interaction.user
    embed = discord.Embed(
        title=f"Informações do usuário: {target}",
        color=discord.Color.blue(),
    )
    embed.add_field(name="ID", value=str(target.id), inline=False)
    embed.add_field(name="Nome", value=target.name, inline=False)
    embed.add_field(
        name="Conta criada em",
        value=discord.utils.format_dt(target.created_at, style="F"),
        inline=False,
    )
    embed.set_thumbnail(url=target.display_avatar.url)

    embed.add_field(
        name="Entrou no servidor",
        value=(
            discord.utils.format_dt(target.joined_at, style="F")
            if target.joined_at
            else "Desconhecido"
        ),
        inline=False,
    )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ajuda", description="Lista os comandos slash disponíveis.")
async def ajuda(interaction: discord.Interaction) -> None:
    command_lines = [
        f"`/{command.name}` — {command.description}"
        for command in bot.tree.get_commands()
        if isinstance(command, app_commands.Command)
    ]
    embed = discord.Embed(
        title="Comandos do bot",
        description="\n".join(command_lines),
        color=discord.Color.blue(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(
    name="anunciar_update",
    description="Publica as atualizações do bot e menciona o cargo configurado.",
)
@app_commands.check(is_bot_owner)
async def anunciar_update(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)

    try:
        previous_commit = get_last_announced_commit()
    except sqlite3.Error:
        logger.exception(
            "Não foi possível carregar o estado dos anúncios de atualização."
        )
        await interaction.followup.send(
            "Não foi possível consultar o histórico de anúncios. Confira os logs.",
            ephemeral=True,
        )
        return

    update_info = get_git_update_info(previous_commit)
    if update_info is None:
        await interaction.followup.send(
            "Não consegui ler os commits do repositório. Confira os logs do bot.",
            ephemeral=True,
        )
        return
    if not update_info[1]:
        update_info = get_git_update_info(None)
    if update_info is None or not update_info[1]:
        await interaction.followup.send(
            "Não há commits disponíveis para publicar como atualização.",
            ephemeral=True,
        )
        return

    published = await bot.publish_git_updates(
        *update_info,
        mention_role=True,
    )
    if not published:
        await interaction.followup.send(
            "Não foi possível confirmar a publicação. Confira o canal e os logs; "
            "se a mensagem chegou, o estado do anúncio pode não ter sido salvo.",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        "Atualização publicada no canal configurado com a menção ao cargo.",
        ephemeral=True,
    )


@bot.tree.command(name="shutdown", description="Desliga o bot.")
@app_commands.check(is_bot_owner)
async def shutdown(interaction: discord.Interaction) -> None:
    await interaction.response.send_message("Desligando o bot...", ephemeral=True)
    await bot.close()


@bot.tree.command(name="restart", description="Explica como reiniciar o processo do bot.")
@app_commands.check(is_bot_owner)
async def restart(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(
        "O bot não pode reiniciar o próprio processo com segurança. Reinicie o serviço "
        "ou processo que o executa.",
        ephemeral=True,
    )


@bot.tree.command(name="status", description="Define a atividade de jogo do bot.")
@app_commands.check(is_bot_owner)
@app_commands.describe(message="Texto da atividade.")
async def status(interaction: discord.Interaction, message: str) -> None:
    await bot.change_presence(activity=discord.Game(name=message))
    await interaction.response.send_message(
        f"Atividade do bot alterada para: {message}",
        ephemeral=True,
    )


@bot.tree.command(name="clear_status", description="Remove a atividade do bot.")
@app_commands.check(is_bot_owner)
async def clear_status(interaction: discord.Interaction) -> None:
    await bot.change_presence(activity=None)
    await interaction.response.send_message(
        "Atividade do bot removida.",
        ephemeral=True,
    )


@bot.tree.command(name="set_activity", description="Define uma atividade do bot.")
@app_commands.check(is_bot_owner)
@app_commands.describe(
    activity_type="playing, streaming, listening ou watching.",
    message="Texto da atividade.",
    url="URL obrigatória para streaming.",
)
async def set_activity(
    interaction: discord.Interaction,
    activity_type: Literal["playing", "streaming", "listening", "watching"],
    message: str,
    url: str | None = None,
) -> None:
    activity_type = activity_type.lower()
    if activity_type == "playing":
        activity: discord.BaseActivity = discord.Game(name=message)
    elif activity_type == "streaming":
        if url is None:
            await interaction.response.send_message(
                "Informe uma URL válida para a atividade de streaming.",
                ephemeral=True,
            )
            return
        activity = discord.Streaming(name=message, url=url)
    elif activity_type == "listening":
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=message,
        )
    elif activity_type == "watching":
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=message,
        )
    else:
        await interaction.response.send_message(
            "Tipo inválido. Use: playing, streaming, listening ou watching.",
            ephemeral=True,
        )
        return

    await bot.change_presence(activity=activity)
    await interaction.response.send_message(
        f"Atividade alterada para: {activity_type} {message}",
        ephemeral=True,
    )


@bot.tree.command(name="clear_activity", description="Remove a atividade do bot.")
@app_commands.check(is_bot_owner)
async def clear_activity(interaction: discord.Interaction) -> None:
    await bot.change_presence(activity=None)
    await interaction.response.send_message(
        "Atividade do bot removida.",
        ephemeral=True,
    )


@bot.tree.command(name="set_status_type", description="Define o status online, idle, dnd ou invisible.")
@app_commands.check(is_bot_owner)
@app_commands.describe(status_type="online, idle, dnd ou invisible.")
async def set_status_type(
    interaction: discord.Interaction,
    status_type: Literal["online", "idle", "dnd", "invisible"],
) -> None:
    status_map = {
        "online": discord.Status.online,
        "idle": discord.Status.idle,
        "dnd": discord.Status.dnd,
        "invisible": discord.Status.invisible,
    }
    selected_status = status_map.get(status_type.lower())
    if selected_status is None:
        await interaction.response.send_message(
            "Status inválido. Use: online, idle, dnd ou invisible.",
            ephemeral=True,
        )
        return

    await bot.change_presence(status=selected_status)
    await interaction.response.send_message(
        f"Status alterado para: {status_type.lower()}",
        ephemeral=True,
    )


@bot.tree.command(name="clear_status_type", description="Redefine o status do bot para online.")
@app_commands.check(is_bot_owner)
async def clear_status_type(interaction: discord.Interaction) -> None:
    await bot.change_presence(status=discord.Status.online)
    await interaction.response.send_message(
        "Status do bot alterado para online.",
        ephemeral=True,
    )


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        message = "Você não tem as permissões necessárias para este comando."
    elif isinstance(error, app_commands.BotMissingPermissions):
        message = "O bot não tem as permissões necessárias para executar este comando."
    elif isinstance(error, app_commands.CheckFailure):
        message = "Você não tem autorização para usar este comando."
    elif isinstance(error, app_commands.CommandOnCooldown):
        message = f"Tente novamente em {error.retry_after:.1f} segundos."
    else:
        original = getattr(error, "original", error)
        logger.error(
            "Erro ao executar /%s",
            interaction.command.name if interaction.command else "desconhecido",
            exc_info=(type(original), original, original.__traceback__),
        )
        message = "Ocorreu um erro ao executar o comando. O erro foi registrado."

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


bot.run(os.getenv("DISCORD_BOT_TOKEN"))
