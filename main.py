import asyncio
import io
import json
import logging
import math
import os
import random
import sqlite3
import tempfile
import time
import unicodedata
from contextlib import closing
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands
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
UPDATE_ANNOUNCEMENT_MESSAGE = (
    "*MINI UPDATE*\n\n"
    "**NOVOS JOGOS**\n\n"
    "Agora voc\u00ea pode jogar `/raspadinha`, combinando tr\u00eas s\u00edmbolos, e "
    "`/campo_minado`, escolhendo abrir de 1 a 5 casas e controlar o risco.\n\n"
    "Os dois jogos t\u00eam GIFs animados pr\u00f3prios, bot\u00e3o para repetir a aposta "
    "e retorno esperado pr\u00f3ximo de 95%, antes dos b\u00f4nus de prest\u00edgio.\n\n"
    "Os jogos tamb\u00e9m est\u00e3o dispon\u00edveis em `/jogar_cassino`: Campo Minado "
    "a partir do n\u00edvel 2 e Raspadinha no n\u00edvel 3. Eles foram inclu\u00eddos no "
    "guia `/ajuda`.\n\n"
    "ultima update da semana, mas ainda tem mais novidades chegando em breve!"
)
MAIN_HOUSE_STARTING_BALANCE = 1_000_000_000
MAIN_HOUSE_UPGRADE_MAX_LEVEL = 20
MAIN_HOUSE_UPGRADE_COST_PERCENT_PER_LEVEL = 1
MAIN_HOUSE_UPGRADE_NPC_BONUS = 20
PROJECT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
BLACKLIST_FILE = os.path.join(PROJECT_DIRECTORY, "blacklist.json")
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
SLOT_PROFIT_FACTOR_NUMERATOR = 11_400
SLOT_PROFIT_FACTOR_DENOMINATOR = 10_000
BET_RETURN_PERCENT = 100
BETTING_ANIMALS = (
    "Leão 🦁",
    "Tigre 🐯",
    "Elefante 🐘",
    "Macaco 🐒",
    "Raposa 🦊",
    "Lobo 🐺",
    "Coelho 🐰",
    "Panda 🐼",
    "Urso 🐻",
    "Javali 🐗",
    "Crocodilo 🐊",
    "Girafa 🦒",
    "Zebra 🦓",
    "Hipopótamo 🦛",
    "Canguru 🦘",
    "Tartaruga 🐢",
)
ANIMAL_BET_MULTIPLIERS = {
    count: BET_RETURN_PERCENT * len(BETTING_ANIMALS) / 100 / count
    for count in range(1, 4)
}
ANIMAL_BET_COOLDOWN = 24 * 60 * 60
ROULETTE_RED_NUMBERS = frozenset(
    {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
)
BLACKJACK_CARDS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
BLACKJACK_CARD_WEIGHTS = (2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1)
BLACKJACK_STREAK_BONUS_PER_WIN_PERCENT = 10
BLACKJACK_STREAK_BONUS_MAX_PERCENT = 200
DEFAULT_CASINO_CREATION_FEE = 750_000
DEFAULT_CASINO_TAX_PERCENT = 15
DEFAULT_MAIN_HOUSE_NPCS = 50
MAIN_HOUSE_NPC_BET_MIN = 5_000
MAIN_HOUSE_NPC_BET_MAX = 20_000
CASINO_STARTING_NPCS = 10
CASINO_MAX_NPCS = 100
CASINO_NPC_HIRE_COST = 2_000
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
    "dados": 3,
    "roleta": 1,
    "maior_menor": 2,
    "campo_minado": 2,
    "cacaniquel": 3,
    "jokenpo": 3,
    "raspadinha": 3,
}
CASINO_GAME_DISPLAY_NAMES = {
    "campo_minado": "Campo Minado",
    "raspadinha": "Raspadinha",
}
PVP_HOUSE_TAX_PERCENT = 5
CASINO_PARTICIPANT_COMMANDS = frozenset(
    {
        "jogar_cassino",
        "cacaniquel",
        "jogo_do_bixo",
        "moeda",
        "dados",
        "roleta",
        "duelo",
        "blackjack",
        "maior_menor",
        "jokenpo",
        "campo_minado",
        "raspadinha",
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
        "mudar_trabalho",
        "workshift",
        "roubar",
        "prestigio",
        "upgrade_prestigio",
    }
)
PRESTIGE_STARTING_REQUIREMENT = 1_000_000
PRESTIGE_MAX_LEVEL = 28
PRESTIGE_MAX_UPGRADE_LEVEL = 10
PLAYER_BASE_BET_LIMIT = 100_000_000
PLAYER_BET_LIMIT_PER_UPGRADE = 150_000
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
WORK_RECOVERY_SECONDS = 8 * 60 * 60
WORK_LIMIT_SECONDS = 8 * 60 * 60
WORK_INTERVAL_SECONDS = 30 * 60
ROBBERY_MAX_ATTEMPTS = 5
ROBBERY_RECOVERY_SECONDS = 8 * 60 * 60
ROBBERY_SUCCESS_CHANCE = 0.65
JOBS = {
    "desempregado": ("Bico", 0, 3_000),
    "entregador": ("Entregador", 5_000, 7_500),
    "seguranca": ("Segurança", 20_000, 12_000),
    "programador": ("Programador", 75_000, 17_500),
    "influenciador": ("Influenciador", 200_000, 30_000),
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
                animal_bet_at INTEGER,
                job TEXT NOT NULL DEFAULT 'desempregado',
                work_used_seconds INTEGER NOT NULL DEFAULT 0,
                work_started_at INTEGER,
                robbery_attempts INTEGER NOT NULL DEFAULT 5,
                robbery_recover_at INTEGER
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
                BOT_OWNER_ID INTEGER NOT NULL,
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
                house_BOT_OWNER_ID INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                exposure INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS blackjack_win_streaks (
                user_id INTEGER PRIMARY KEY,
                win_streak INTEGER NOT NULL DEFAULT 0
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
        account_column_migrations = {
            "job": "TEXT NOT NULL DEFAULT 'desempregado'",
            "work_used_seconds": "INTEGER NOT NULL DEFAULT 0",
            "work_started_at": "INTEGER",
            "robbery_attempts": f"INTEGER NOT NULL DEFAULT {ROBBERY_MAX_ATTEMPTS}",
            "robbery_recover_at": "INTEGER",
        }
        for column, declaration in account_column_migrations.items():
            if column not in columns:
                connection.execute(
                    "ALTER TABLE economy_accounts "
                    f"ADD COLUMN {column} {declaration}"
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
                
class BlacklistError(Exception):
  """Indica que a blacklist não pôde ser lida ou gravada com segurança."""


def carregar_blacklist() -> list[int]:
  try:
    with open(BLACKLIST_FILE, "r", encoding="utf-8") as arquivo:
      dados = json.load(arquivo)
  except FileNotFoundError:
    return []
  except (OSError, json.JSONDecodeError) as erro:
    logger.exception("Não foi possível carregar a blacklist.")
    raise BlacklistError("Não foi possível ler a lista de bloqueio.") from erro

  if not isinstance(dados, list):
    logger.error("Formato inválido em %s: esperado uma lista.", BLACKLIST_FILE)
    raise BlacklistError("A lista de bloqueio está em formato inválido.")

  ids = []
  for item in dados:
    # Aceita arquivos antigos com IDs salvos como texto, mas rejeita outros dados.
    if isinstance(item, bool):
      logger.error("ID inválido encontrado na blacklist: %r", item)
      raise BlacklistError("A lista de bloqueio contém um ID inválido.")
    if isinstance(item, int):
      user_id = item
    elif isinstance(item, str) and item.isdecimal():
      user_id = int(item)
    else:
      logger.error("ID inválido encontrado na blacklist: %r", item)
      raise BlacklistError("A lista de bloqueio contém um ID inválido.")
    if user_id > 0 and user_id not in ids:
      ids.append(user_id)
  return ids


def salvar_blacklist(lista: list[int]) -> None:
  caminho_temporario = f"{BLACKLIST_FILE}.tmp"
  try:
    with open(caminho_temporario, "w", encoding="utf-8") as arquivo:
      json.dump(sorted(set(lista)), arquivo, indent=4)
      arquivo.flush()
      os.fsync(arquivo.fileno())
    os.replace(caminho_temporario, BLACKLIST_FILE)
  except OSError as erro:
    logger.exception("Não foi possível salvar a blacklist.")
    try:
      if os.path.exists(caminho_temporario):
        os.remove(caminho_temporario)
    except OSError:
      logger.exception("Não foi possível limpar o arquivo temporário da blacklist.")
    raise BlacklistError("Não foi possível salvar a lista de bloqueio.") from erro


async def verificar_usuario_bloqueado(interaction: discord.Interaction) -> bool:
  if interaction.user.id == BOT_OWNER_ID:
    return False
  try:
    blacklist = carregar_blacklist()
  except BlacklistError:
    if not interaction.response.is_done():
      await interaction.response.send_message(
          "⚠️ A lista de bloqueio está temporariamente indisponível. Tente novamente mais tarde.",
          ephemeral=True,
      )
    return True

  if interaction.user.id in blacklist:
    if not interaction.response.is_done():
      await interaction.response.send_message(
          "❌ Você está **bloqueado** de usar os comandos deste bot.",
          ephemeral=True,
      )
    return True
  return False


class BlacklistView(discord.ui.View):
  async def interaction_check(self, interaction: discord.Interaction) -> bool:
    return not await verificar_usuario_bloqueado(interaction)


class BlacklistCommandTree(app_commands.CommandTree):
  async def interaction_check(self, interaction: discord.Interaction) -> bool:
    return not await verificar_usuario_bloqueado(interaction)


class MeuBot(commands.Bot):

  def __init__(self):
    intents = discord.Intents.default()
    super().__init__(command_prefix="!", intents=intents)

  async def setup_hook(self):
    await self.tree.sync()
    print("Comandos slash sincronizados!")


bot = MeuBot()


# ---------------------------------------------------------
# COMANDOS PARA O OWNER (Bloquear / Desbloquear / Listar)
# ---------------------------------------------------------


@bot.tree.command(
    name="bloquear", description="Bloqueia um usuário de usar os comandos (Owner)"
)
@app_commands.describe(usuario="O usuário que deseja bloquear")
async def bloquear(interaction: discord.Interaction, usuario: discord.User):
  # Verifica se quem está executando é o Owner
  if interaction.user.id != BOT_OWNER_ID:
    return await interaction.response.send_message(
        "❌ Apenas o dono do bot pode usar este comando.", ephemeral=True
    )

  try:
    blacklist = carregar_blacklist()
  except BlacklistError:
    return await interaction.response.send_message(
        "⚠️ Não foi possível ler a lista de bloqueio. Nenhuma alteração foi feita.",
        ephemeral=True,
    )

  if usuario.id == BOT_OWNER_ID:
    return await interaction.response.send_message(
        "⚠️ Você não pode bloquear o dono do bot.", ephemeral=True
    )

  if usuario.id in blacklist:
    return await interaction.response.send_message(
        f"⚠️ O usuário {usuario.mention} já está bloqueado.", ephemeral=True
    )

  blacklist.append(usuario.id)
  try:
    salvar_blacklist(blacklist)
  except BlacklistError:
    return await interaction.response.send_message(
        "⚠️ Não foi possível salvar a lista de bloqueio.", ephemeral=True
    )

  await interaction.response.send_message(
      f"🚫 O usuário {usuario.mention} foi **bloqueado** dos comandos do bot.",
      ephemeral=True,
  )


@bot.tree.command(
    name="desbloquear",
    description="Desbloqueia um usuário dos comandos (Owner)",
)
@app_commands.describe(usuario="O usuário que deseja desbloquear")
async def desbloquear(
    interaction: discord.Interaction, usuario: discord.User
):
  if interaction.user.id != BOT_OWNER_ID:
    return await interaction.response.send_message(
        "❌ Apenas o dono do bot pode usar este comando.", ephemeral=True
    )

  try:
    blacklist = carregar_blacklist()
  except BlacklistError:
    return await interaction.response.send_message(
        "⚠️ Não foi possível ler a lista de bloqueio. Nenhuma alteração foi feita.",
        ephemeral=True,
    )

  if usuario.id not in blacklist:
    return await interaction.response.send_message(
        f"⚠️ O usuário {usuario.mention} não está na lista de bloqueados.",
        ephemeral=True,
    )

  blacklist.remove(usuario.id)
  try:
    salvar_blacklist(blacklist)
  except BlacklistError:
    return await interaction.response.send_message(
        "⚠️ Não foi possível salvar a lista de bloqueio.", ephemeral=True
    )

  await interaction.response.send_message(
      f"✅ O usuário {usuario.mention} foi **desbloqueado** dos comandos do bot.",
      ephemeral=True,
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
        with closing(sqlite3.connect(legacy_database_path)) as source, closing(
            sqlite3.connect(temporary_path)
        ) as destination:
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
        main_house_BOT_OWNER_ID = get_house_BOT_OWNER_ID()
        global_ranked = sorted(
            (
                row
                for row in global_accounts
                if row[0] != main_house_BOT_OWNER_ID
            ),
            key=lambda row: (-row[1], -row[2], row[3], row[0]),
        )
        global_ranks = {
            row[0]: rank for rank, row in enumerate(global_ranked, start=1)
        }

        casino = connection.execute(
            "SELECT BOT_OWNER_ID FROM guild_casinos WHERE guild_id = ?",
            (guild.id,),
        ).fetchone()
        casino_BOT_OWNER_ID = casino[0] if casino else None
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
                if row[0] not in (main_house_BOT_OWNER_ID, casino_BOT_OWNER_ID)
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
    if interaction.user.id != get_house_BOT_OWNER_ID():
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


def blackjack_streak_bonus_percent(win_streak: int) -> int:
    return min(
        win_streak * BLACKJACK_STREAK_BONUS_PER_WIN_PERCENT,
        BLACKJACK_STREAK_BONUS_MAX_PERCENT,
    )


def apply_blackjack_streak_bonus(
    bet: int,
    payout: int,
    previous_win_streak: int,
) -> int:
    if payout <= bet:
        return payout
    bonus_percent = blackjack_streak_bonus_percent(previous_win_streak + 1)
    profit = payout - bet
    return payout + (profit * bonus_percent + 99) // 100


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


def set_house_BOT_OWNER_ID(owner_id: int) -> None:
    if owner_id != BOT_OWNER_ID:
        raise ValueError("O proprietário da casa principal é definido pelo BOT_OWNER_ID.")
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute(
            """
            INSERT INTO casino_settings (setting, value) VALUES ('house_BOT_OWNER_ID', ?)
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


def get_house_BOT_OWNER_ID() -> int:
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
            WHERE house_BOT_OWNER_ID = ?
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


def payout_for_target_rtp(
    bet: int,
    winning_outcomes: int,
    total_outcomes: int,
    *,
    push_outcomes: int = 0,
) -> int:
    if (
        bet <= 0
        or total_outcomes <= 0
        or winning_outcomes <= 0
        or push_outcomes < 0
        or winning_outcomes + push_outcomes > total_outcomes
    ):
        raise ValueError("Probabilidades ou valor de aposta inválidos.")
    payout_numerator = (
        BET_RETURN_PERCENT * total_outcomes - 100 * push_outcomes
    )
    if payout_numerator <= 0:
        raise ValueError("O retorno esperado precisa ser positivo.")
    return bet * payout_numerator // (100 * winning_outcomes)


SCRATCH_SYMBOLS = ("CEREJA", "LIMAO", "SINO", "ESTRELA", "DIAMANTE")


def play_scratchcard(bet: int) -> tuple[list[str], int, str]:
    symbols = random.choices(SCRATCH_SYMBOLS, k=3)
    if len(set(symbols)) == 1:
        return symbols, bet * 10, "trinca"
    if len(set(symbols)) == 2:
        return symbols, bet * 23 // 20, "par"
    return symbols, 0, "sem combinação"


def play_mines(bet: int, safe_picks: int) -> tuple[list[int], set[int], int]:
    if not 1 <= safe_picks <= 5:
        raise ValueError("A quantidade de casas seguras deve estar entre 1 e 5.")
    mines = set(random.sample(range(9), 2))
    opened: list[int] = []
    for tile in random.sample(range(9), 9):
        opened.append(tile)
        if tile in mines:
            break
        if len(opened) == safe_picks:
            break

    if opened[-1] in mines:
        return opened, mines, 0

    winning_outcomes = math.comb(7, safe_picks)
    total_outcomes = math.comb(9, safe_picks)
    fair_payout = payout_for_target_rtp(
        bet,
        winning_outcomes,
        total_outcomes,
    )
    return opened, mines, max(bet, fair_payout * 95 // 100)


def render_bet_result_image(
    game: str,
    result: str,
    payout: int,
    bet: int,
) -> io.BytesIO:
    profit = payout - bet
    background = (18, 24, 45)
    accent = (71, 205, 145) if profit > 0 else (
        (241, 190, 76) if profit == 0 else (235, 92, 105)
    )
    image = Image.new("RGB", (960, 360), background)
    draw = ImageDraw.Draw(image)
    font_path = r"C:\Windows\Fonts\arial.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 31)
        result_font = ImageFont.truetype(font_path, 25)
        detail_font = ImageFont.truetype(font_path, 20)
        emblem_font = ImageFont.truetype(font_path, 32)
    except OSError:
        title_font = ImageFont.load_default()
        result_font = ImageFont.load_default()
        detail_font = ImageFont.load_default()
        emblem_font = ImageFont.load_default()

    draw.rounded_rectangle(
        (18, 18, 942, 342),
        radius=30,
        fill=(31, 39, 68),
        outline=accent,
        width=5,
    )
    draw.ellipse((58, 93, 258, 293), fill=(17, 23, 43), outline=accent, width=5)
    game_label = unicodedata.normalize("NFKD", game.upper())
    game_label = game_label.encode("ascii", "ignore").decode("ascii") or "JOGO"
    emblem = "".join(word[0] for word in game_label.split()[:3])
    draw.text(
        (158, 193),
        emblem,
        font=emblem_font,
        fill=accent,
        anchor="mm",
    )
    draw.text((300, 76), game_label[:42], font=title_font, fill=(255, 225, 150))

    art_result = result.replace("**", "").replace("`", "")
    art_result = unicodedata.normalize("NFKD", art_result)
    art_result = art_result.encode("ascii", "ignore").decode("ascii")
    lines: list[str] = []
    current_line = ""
    for word in art_result.split():
        candidate = f"{current_line} {word}".strip()
        if current_line and draw.textbbox((0, 0), candidate, font=result_font)[2] > 590:
            lines.append(current_line)
            current_line = word
        else:
            current_line = candidate
    if current_line:
        lines.append(current_line)
    for line_number, line in enumerate(lines[:3]):
        draw.text(
            (300, 137 + line_number * 36),
            line,
            font=result_font,
            fill=(245, 247, 255),
        )
    draw.line((300, 260, 890, 260), fill=(73, 83, 117), width=2)
    draw.text(
        (300, 287),
        f"APOSTA  {format_coins(bet)}    |    RETORNO  {format_coins(payout)}",
        font=detail_font,
        fill=(208, 216, 238),
    )

    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output


async def send_bet_result(
    interaction: discord.Interaction,
    *,
    game: str,
    bet: int,
    choice: str,
    result: str,
    payout: int,
    balance: int,
    view: discord.ui.View | None = None,
    edit_message: bool = False,
    file: discord.File | None = None,
    image_url: str | None = None,
    currency_name: str = "moedas",
    casino_name: str | None = None,
    tax_percent: int | None = None,
    tax_amount: int = 0,
    treasury: int | None = None,
) -> None:
    net_change = payout - bet if payout else -bet
    if file is None and image_url is None:
        artwork = await asyncio.to_thread(
            render_bet_result_image,
            game,
            result,
            payout,
            bet,
        )
        file = discord.File(artwork, filename="resultado-aposta.png")
        image_url = "attachment://resultado-aposta.png"
    net_sign = "+" if net_change > 0 else ""
    result_title = (
        "🎉 VOCÊ GANHOU!"
        if net_change > 0
        else "🤝 EMPATE"
        if net_change == 0
        else "❌ VOCÊ PERDEU"
    )
    embed = discord.Embed(
        title=f"{result_title} — {game}",
        description=result,
        color=(
            discord.Color.green()
            if net_change > 0
            else discord.Color.gold()
            if net_change == 0
            else discord.Color.red()
        ),
    )
    embed.add_field(name="Sua aposta", value=choice, inline=False)
    embed.add_field(
        name="🪙 Valor apostado",
        value=f"{format_coins(bet)} {currency_name}",
        inline=True,
    )
    embed.add_field(
        name="💰 Retorno total (inclui aposta)",
        value=f"{format_coins(payout)} {currency_name}",
        inline=True,
    )
    embed.add_field(
        name="📊 Lucro / prejuízo",
        value=f"{net_sign}{format_coins(net_change)} {currency_name}",
        inline=True,
    )
    if tax_percent is not None:
        embed.add_field(
            name="Taxa paga à casa principal",
            value=f"{format_coins(tax_amount)} {currency_name} ({tax_percent}%)",
            inline=True,
        )
    footer = f"Saldo atual: {format_coins(balance)} {currency_name}"
    if casino_name is not None and treasury is not None:
        footer = (
            f"{casino_name} | {footer} | Caixa: "
            f"{format_coins(treasury)} {currency_name}"
        )
    embed.set_footer(text=footer)
    if image_url is not None:
        embed.set_image(url=image_url)

    if edit_message:
        await interaction.response.edit_message(
            embed=embed,
            view=view,
            attachments=[file] if file is not None else [],
        )
    else:
        if file is None:
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(
                embed=embed,
                view=view,
                file=file,
            )


class BetAgainView(BlacklistView):
    def __init__(
        self,
        user_id: int,
        game: str,
        bet: int,
        choice: str | tuple[str, ...],
        guild_id: int | None = None,
    ) -> None:
        super().__init__(timeout=300)
        self.user_id = user_id
        self.game = game
        self.bet = bet
        self.choice = choice
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if await verificar_usuario_bloqueado(interaction):
            return False
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            "Somente quem fez a aposta pode apostar novamente.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(
        label="Apostar novamente",
        emoji="🔁",
        style=discord.ButtonStyle.primary,
    )
    async def repeat(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        await repeat_bet(
            interaction,
            self.game,
            self.bet,
            self.choice,
            guild_id=self.guild_id,
        )


async def repeat_bet(
    interaction: discord.Interaction,
    game: str,
    bet: int,
    choice: str | tuple[str, ...],
    *,
    guild_id: int | None = None,
) -> None:
    if not await ensure_betting_channel(interaction):
        return
    if guild_id is None and not await ensure_not_house_owner(interaction):
        return
    if not await ensure_bet_limit(interaction, bet):
        return
    casino = get_guild_casino(guild_id) if guild_id is not None else None
    if guild_id is not None and (
        interaction.guild is None
        or interaction.guild.id != guild_id
        or casino is None
    ):
        await interaction.response.send_message(
            "Este cassino não está mais disponível neste servidor.",
            ephemeral=True,
        )
        return

    payout = 0
    result = ""
    file = None
    image_url = None
    choice_text = ""
    if game == "moeda":
        result_value = random.choice(("cara", "coroa"))
        assert isinstance(choice, str)
        payout = payout_for_target_rtp(bet, 1, 2) if choice == result_value else 0
        choice_text = f"Você escolheu **{choice.capitalize()}**."
        result = f"A moeda caiu em **{result_value.capitalize()}**."
    elif game == "dados":
        roll = random.randint(1, 6)
        assert isinstance(choice, str)
        if choice in ("par", "ímpar"):
            won = ("par" if roll % 2 == 0 else "ímpar") == choice
            payout = payout_for_target_rtp(bet, 3, 6) if won else 0
        else:
            won = roll == int(choice)
            payout = payout_for_target_rtp(bet, 1, 6) if won else 0
        choice_text = f"Você escolheu **{choice.capitalize()}**."
        result = f"O dado caiu em **{roll}**."
    elif game == "roleta":
        number = random.randint(0, 36)
        result_color = (
            "verde"
            if number == 0
            else "vermelho"
            if number in ROULETTE_RED_NUMBERS
            else "preto"
        )
        assert isinstance(choice, str)
        winning_outcomes = 1 if choice == "verde" else 18
        payout = (
            payout_for_target_rtp(bet, winning_outcomes, 37)
            if choice == result_color
            else 0
        )
        choice_text = f"Você apostou em **{choice.capitalize()}**."
        result = f"A roleta parou no **{number} {result_color}**."
    elif game == "maior_menor":
        card = random.randint(1, 13)
        assert isinstance(choice, str)
        if card == 7:
            payout = bet
            result = f"Saiu **{card}**. Empate: sua aposta foi devolvida."
        else:
            won = (card > 7 and choice == "maior") or (
                card < 7 and choice == "menor"
            )
            payout = (
                payout_for_target_rtp(bet, 6, 13, push_outcomes=1)
                if won
                else 0
            )
            result = (
                f"Saiu **{card}**; o resultado foi "
                f"**{'maior' if card > 7 else 'menor'} que 7**."
            )
        choice_text = f"Você escolheu **{choice} que 7**."
    elif game == "jokenpo":
        assert isinstance(choice, str)
        house_choice = random.choice(("pedra", "papel", "tesoura"))
        beats = {
            "pedra": "tesoura",
            "papel": "pedra",
            "tesoura": "papel",
        }
        if choice == house_choice:
            payout = bet
            result = (
                f"Empate: ambos escolheram **{choice}**. "
                "Sua aposta foi devolvida."
            )
        elif beats[choice] == house_choice:
            payout = payout_for_target_rtp(bet, 1, 3, push_outcomes=1)
            result = f"Você venceu: **{choice}** vence **{house_choice}**."
        else:
            result = f"A casa venceu: **{house_choice}** vence **{choice}**."
        choice_text = f"Você escolheu **{choice}**."
    elif game == "jogo_do_bixo":
        assert isinstance(choice, tuple)
        drawn_animal = random.choice(BETTING_ANIMALS)
        payout, multiplier = animal_bet_payout(choice, drawn_animal, bet)
        choice_text = "Você escolheu **" + " | ".join(choice) + "**."
        result = (
            f"O animal sorteado foi **{drawn_animal}** "
            f"(multiplicador x{multiplier:g})."
        )
    elif game == "cacaniquel":
        reels = random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=3)
        payout, combination, _ = slot_payout(reels, bet)
        choice_text = "Giro da máquina caça-níquel."
        result = f"Resultado: **{' | '.join(reels)}** — {combination}."
    elif game == "raspadinha":
        symbols, payout, combination = play_scratchcard(bet)
        choice_text = "Raspadinha de tr\u00eas cart\u00f5es."
        result = f"S\u00edmbolos revelados: **{' | '.join(symbols)}** \u2014 {combination}."
    elif game == "campo_minado":
        assert isinstance(choice, str)
        safe_picks = int(choice)
        opened_tiles, mine_positions, payout = play_mines(bet, safe_picks)
        choice_text = f"Tentativas de abertura: **{safe_picks} casas**."
        if payout:
            result = f"Voc\u00ea abriu {safe_picks} casas sem encontrar uma mina."
        else:
            result = f"Uma mina apareceu na tentativa **{len(opened_tiles)}**. A aposta foi perdida."
    else:
        raise ValueError(f"Jogo de repetição desconhecido: {game}")

    payout = adjust_player_bet_payout(interaction.user.id, bet, payout)
    if game == "dados":
        animation = await asyncio.to_thread(render_dice_gif, roll)
        file = discord.File(animation, filename="dados.gif")
        image_url = "attachment://dados.gif"
    elif game == "roleta":
        animation = await asyncio.to_thread(
            render_roulette_gif,
            number,
            result_color,
        )
        file = discord.File(animation, filename="roleta.gif")
        image_url = "attachment://roleta.gif"
    elif game == "cacaniquel":
        multiplier = payout / bet
        result = (
            f"Resultado: **{' | '.join(reels)}** — {combination} "
            f"(multiplicador x{multiplier:g})."
        )
        animation = await asyncio.to_thread(render_slot_gif, reels, multiplier)
        file = discord.File(animation, filename="cacaniquel.gif")
        image_url = "attachment://cacaniquel.gif"
    elif game == "raspadinha":
        animation = await asyncio.to_thread(
            render_scratchcard_gif,
            symbols,
            payout / bet,
        )
        file = discord.File(animation, filename="raspadinha.gif")
        image_url = "attachment://raspadinha.gif"
    elif game == "campo_minado":
        animation = await asyncio.to_thread(
            render_mines_gif,
            opened_tiles,
            mine_positions,
            payout / bet,
        )
        file = discord.File(animation, filename="campo-minado.gif")
        image_url = "attachment://campo-minado.gif"
    if game == "jogo_do_bixo":
        bet_status, balance, remaining = settle_animal_house_bet(
            interaction.user.id,
            get_house_BOT_OWNER_ID(),
            bet,
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
            await interaction.response.send_message(
                "A aposta foi cancelada: saldo insuficiente ou banca "
                "principal sem fundos para cobrir esse resultado.",
                ephemeral=True,
            )
            return
    elif guild_id is not None:
        status, balance, treasury, tax_percent, tax = settle_guild_casino_bet(
            guild_id,
            interaction.user.id,
            get_house_BOT_OWNER_ID(),
            bet,
            payout,
        )
        if status != "settled":
            message = (
                f"Saldo insuficiente no cassino. Seu saldo é "
                f"{format_coins(balance)}."
                if status == "insufficient_player"
                else "O caixa do cassino não cobre esse prêmio; "
                "a aposta foi cancelada."
                if status == "insufficient_treasury"
                else "Não foi possível concluir a aposta porque o cassino "
                "não está mais disponível."
            )
            await interaction.response.send_message(message, ephemeral=True)
            return
        assert casino is not None
        _, casino_name, currency_name, _, _ = casino
        await send_bet_result(
            interaction,
            game=casino_name,
            bet=bet,
            choice=choice_text,
            result=result,
            payout=payout,
            balance=balance,
            view=BetAgainView(
                interaction.user.id,
                game,
                bet,
                choice,
                guild_id,
            ),
            edit_message=True,
            file=file,
            image_url=image_url,
            currency_name=currency_name,
            casino_name=casino_name,
            tax_percent=tax_percent,
            tax_amount=tax,
            treasury=treasury,
        )
        return
    else:
        settled, balance, _ = settle_house_bet(
            interaction.user.id,
            get_house_BOT_OWNER_ID(),
            bet,
            payout,
        )
        if not settled:
            await interaction.response.send_message(
                "A aposta foi cancelada: saldo insuficiente ou banca "
                "principal sem fundos para cobrir esse resultado. "
                f"Seu saldo continua em {format_coins(balance)} moedas.",
                ephemeral=True,
            )
            return

    await send_bet_result(
        interaction,
        game=game.upper(),
        bet=bet,
        choice=choice_text,
        result=result,
        payout=payout,
        balance=balance,
        view=BetAgainView(interaction.user.id, game, bet, choice),
        edit_message=True,
        file=file,
        image_url=image_url,
    )


def get_leaderboard(user_ids: list[int]) -> list[tuple[int, int, int, int]]:
    accounts: list[tuple[int, int, int, int]] = []
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        owner_setting = connection.execute(
            "SELECT value FROM casino_settings WHERE setting = 'house_BOT_OWNER_ID'"
        ).fetchone()
        house_BOT_OWNER_ID = owner_setting[0] if owner_setting else None
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

    if house_BOT_OWNER_ID is not None:
        accounts = [
            account for account in accounts if account[0] != house_BOT_OWNER_ID
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


def change_player_job(user_id: int, job_key: str) -> tuple[str, int]:
    if job_key not in JOBS:
        raise ValueError("Trabalho desconhecido.")

    application_cost = JOBS[job_key][1]
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            (user_id,),
        )
        if connection.execute(
            "SELECT 1 FROM guild_casinos WHERE BOT_OWNER_ID = ? LIMIT 1",
            (user_id,),
        ).fetchone() is not None:
            balance = connection.execute(
                "SELECT balance FROM economy_accounts WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
            return "casino_owner", balance

        balance, current_job = connection.execute(
            "SELECT balance, job FROM economy_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if current_job == job_key:
            return "same_job", balance
        if balance < application_cost:
            return "insufficient", balance

        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = balance - ?, total_lost = total_lost + ?, job = ?
            WHERE user_id = ?
            """,
            (application_cost, application_cost, job_key, user_id),
        )
        return "changed", balance - application_cost


def work_player_shift(
    user_id: int,
) -> tuple[str, str, int, int, int, int, int]:
    now = int(time.time())
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            (user_id,),
        )
        balance, job_key, work_used, work_started_at = connection.execute(
            """
            SELECT balance, job, work_used_seconds, work_started_at
            FROM economy_accounts WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        if job_key not in JOBS:
            raise ValueError(f"Trabalho inválido salvo para o usuário {user_id}.")

        if work_started_at is None or now - work_started_at >= WORK_RECOVERY_SECONDS:
            work_used = 0
            work_started_at = now

        remaining = max(0, WORK_LIMIT_SECONDS - work_used)
        if remaining == 0:
            return (
                "limit",
                job_key,
                0,
                0,
                balance,
                remaining,
                work_started_at + WORK_RECOVERY_SECONDS,
            )

        intervals = max(1, remaining // WORK_INTERVAL_SECONDS)
        duration = random.randint(1, intervals) * WORK_INTERVAL_SECONDS
        payout = JOBS[job_key][2] * duration // (60 * 60)
        remaining -= duration
        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = balance + ?, total_earned = total_earned + ?,
                work_used_seconds = ?, work_started_at = ?
            WHERE user_id = ?
            """,
            (
                payout,
                payout,
                WORK_LIMIT_SECONDS - remaining,
                work_started_at,
                user_id,
            ),
        )
        return (
            "worked",
            job_key,
            duration,
            payout,
            balance + payout,
            remaining,
            work_started_at + WORK_RECOVERY_SECONDS,
        )


def attempt_robbery(
    user_id: int,
) -> tuple[str, int, int, int, int | None]:
    now = int(time.time())
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            (user_id,),
        )
        balance, attempts, recover_at = connection.execute(
            """
            SELECT balance, robbery_attempts, robbery_recover_at
            FROM economy_accounts WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if attempts == 0 and recover_at is not None and now < recover_at:
            return "cooldown", balance, attempts, 0, recover_at
        if attempts == 0:
            attempts = ROBBERY_MAX_ATTEMPTS
            recover_at = None
            connection.execute(
                """
                UPDATE economy_accounts
                SET robbery_attempts = ?, robbery_recover_at = NULL
                WHERE user_id = ?
                """,
                (attempts, user_id),
            )

        if random.random() < ROBBERY_SUCCESS_CHANCE:
            won_amount = random.randint(2_500, 15_000)
            attempts -= 1
            recover_at = now + ROBBERY_RECOVERY_SECONDS if attempts == 0 else None
            connection.execute(
                """
                UPDATE economy_accounts
                SET balance = balance + ?, total_earned = total_earned + ?,
                    robbery_attempts = ?, robbery_recover_at = ?
                WHERE user_id = ?
                """,
                (won_amount, won_amount, attempts, recover_at, user_id),
            )
            return "success", balance + won_amount, attempts, won_amount, recover_at

        lost_amount = min(balance, random.randint(500, 5_000))
        attempts = 0
        recover_at = now + ROBBERY_RECOVERY_SECONDS
        connection.execute(
            """
            UPDATE economy_accounts
            SET balance = balance - ?, total_lost = total_lost + ?,
                robbery_attempts = 0, robbery_recover_at = ?
            WHERE user_id = ?
            """,
            (lost_amount, lost_amount, recover_at, user_id),
        )
        return "failed", balance - lost_amount, attempts, lost_amount, recover_at


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
    house_BOT_OWNER_ID: int,
    bet: int,
    payout: int,
) -> tuple[bool, int, int]:
    if user_id == house_BOT_OWNER_ID:
        return False, get_balance(user_id), get_balance(house_BOT_OWNER_ID)
    if bet <= 0 or payout < 0:
        raise ValueError("A aposta precisa ser positiva e o retorno não pode ser negativo.")

    player_change = payout - bet
    house_change = -player_change
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            ((user_id,), (house_BOT_OWNER_ID,)),
        )
        balances = {
            account_id: balance
            for account_id, balance in connection.execute(
                """
                SELECT user_id, balance FROM economy_accounts
                WHERE user_id IN (?, ?)
                """,
                (user_id, house_BOT_OWNER_ID),
            )
        }
        player_balance = balances[user_id]
        house_balance = balances[house_BOT_OWNER_ID]
        if player_balance < bet:
            return False, player_balance, house_balance

        reservations = connection.execute(
            """
            SELECT COALESCE(SUM(exposure), 0) FROM house_bet_reservations
            WHERE house_BOT_OWNER_ID = ?
            """,
            (house_BOT_OWNER_ID,),
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
                house_BOT_OWNER_ID,
            ),
        )
        increment_house_stat(connection, "main_house_games")
        player_balance += player_change
        house_balance += house_change
        return True, player_balance, house_balance


def reserve_blackjack_bet(
    user_id: int,
    house_BOT_OWNER_ID: int,
    bet: int,
) -> tuple[bool, int, str, int]:
    if user_id == house_BOT_OWNER_ID:
        return False, get_balance(user_id), "owner", 0
    if bet <= 0:
        raise ValueError("A aposta precisa ser positiva.")

    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            ((user_id,), (house_BOT_OWNER_ID,)),
        )
        player_balance = connection.execute(
            "SELECT balance FROM economy_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        house_balance = connection.execute(
            "SELECT balance FROM economy_accounts WHERE user_id = ?",
            (house_BOT_OWNER_ID,),
        ).fetchone()[0]
        bonus_levels = connection.execute(
            """
            SELECT prestige_level + prestige_upgrade_gains
            FROM economy_accounts WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()[0]
        streak_row = connection.execute(
            "SELECT win_streak FROM blackjack_win_streaks WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        win_streak = streak_row[0] if streak_row is not None else 0
        base_payout = bet + apply_positive_profit_bonus(bet, bonus_levels)
        max_payout = apply_blackjack_streak_bonus(
            bet,
            base_payout,
            win_streak,
        )
        exposure = max_payout - bet
        reserved = connection.execute(
            """
            SELECT COALESCE(SUM(exposure), 0) FROM house_bet_reservations
            WHERE house_BOT_OWNER_ID = ?
            """,
            (house_BOT_OWNER_ID,),
        ).fetchone()[0]
        if player_balance < bet:
            return False, player_balance, "player", 0
        if house_balance - reserved < exposure:
            return False, player_balance, "house", 0

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
                (user_id, house_BOT_OWNER_ID, amount, exposure, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, house_BOT_OWNER_ID, bet, exposure, int(time.time())),
        )
        record_bet_activity(connection, user_id, bet)
        return True, player_balance - bet, str(reservation.lastrowid), win_streak


def settle_blackjack_bet(
    reservation_id: str,
    user_id: int,
    house_BOT_OWNER_ID: int,
    bet: int,
    payout: int,
) -> int:
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        reservation = connection.execute(
            """
            SELECT amount, exposure FROM house_bet_reservations
            WHERE reservation_id = ? AND user_id = ? AND house_BOT_OWNER_ID = ?
            """,
            (int(reservation_id), user_id, house_BOT_OWNER_ID),
        ).fetchone()
        if reservation is None or reservation[0] != bet:
            raise RuntimeError("A reserva desta partida de blackjack não foi encontrada.")

        house_balance = connection.execute(
            "SELECT balance FROM economy_accounts WHERE user_id = ?",
            (house_BOT_OWNER_ID,),
        ).fetchone()[0]
        other_reservations = connection.execute(
            """
            SELECT COALESCE(SUM(exposure), 0) FROM house_bet_reservations
            WHERE house_BOT_OWNER_ID = ? AND reservation_id != ?
            """,
            (house_BOT_OWNER_ID, int(reservation_id)),
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
                house_BOT_OWNER_ID,
            ),
        )
        connection.execute(
            "DELETE FROM house_bet_reservations WHERE reservation_id = ?",
            (int(reservation_id),),
        )
        if payout > bet:
            connection.execute(
                """
                INSERT INTO blackjack_win_streaks (user_id, win_streak)
                VALUES (?, 1)
                ON CONFLICT(user_id)
                DO UPDATE SET win_streak = win_streak + 1
                """,
                (user_id,),
            )
        elif payout < bet:
            connection.execute(
                """
                INSERT INTO blackjack_win_streaks (user_id, win_streak)
                VALUES (?, 0)
                ON CONFLICT(user_id)
                DO UPDATE SET win_streak = 0
                """,
                (user_id,),
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
        house_BOT_OWNER_ID = get_house_BOT_OWNER_ID()
        connection.execute(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            (house_BOT_OWNER_ID,),
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
                (house_BOT_OWNER_ID,),
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
                    house_BOT_OWNER_ID,
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
    house_BOT_OWNER_ID: int,
    amount: int,
    payout: int,
) -> tuple[str, int, int]:
    now = int(time.time())
    if user_id == house_BOT_OWNER_ID:
        return "owner", get_balance(user_id), get_balance(house_BOT_OWNER_ID)
    if amount <= 0 or payout < 0:
        raise ValueError("A aposta precisa ser positiva e o retorno não pode ser negativo.")

    player_change = payout - amount
    house_change = -player_change
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            ((user_id,), (house_BOT_OWNER_ID,)),
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
            (house_BOT_OWNER_ID,),
        ).fetchone()[0]
        reservations = connection.execute(
            """
            SELECT COALESCE(SUM(exposure), 0) FROM house_bet_reservations
            WHERE house_BOT_OWNER_ID = ?
            """,
            (house_BOT_OWNER_ID,),
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
                house_BOT_OWNER_ID,
            ),
        )
        increment_house_stat(connection, "main_house_games")
        return "accepted", player_balance + player_change, house_balance + house_change


def get_guild_casino(guild_id: int) -> tuple[int, str, str, int, int] | None:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        casino = connection.execute(
            """
            SELECT BOT_OWNER_ID, name, currency_name, treasury, upgrade_level
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
            SELECT BOT_OWNER_ID, name, currency_name, treasury, upgrade_level,
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
            SELECT BOT_OWNER_ID, treasury, npc_count
            FROM guild_casinos WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()
        if casino is None:
            return "missing", 0, 0

        BOT_OWNER_ID, treasury, current_npcs = casino
        if BOT_OWNER_ID != user_id:
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
    online_BOT_OWNER_IDs_by_guild: dict[int, set[int]] | None = None,
) -> tuple[int, int]:
    current_time = int(time.time()) if now is None else now
    online_BOT_OWNER_IDs_by_guild = online_BOT_OWNER_IDs_by_guild or {}
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        settings = dict(
            connection.execute(
                """
                SELECT setting, value FROM casino_settings
                WHERE setting IN (
                    'house_BOT_OWNER_ID', 'main_house_npcs',
                    'main_house_npc_bet_upgrade_level',
                    'main_house_npc_next_bet_at',
                    'main_house_npc_owner_online', 'tax_percent'
                )
                """
            ).fetchall()
        )
        if "house_BOT_OWNER_ID" not in settings:
            return 0, 0

        house_BOT_OWNER_ID = settings["house_BOT_OWNER_ID"]
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
            (house_BOT_OWNER_ID,),
        )
        house_balance = connection.execute(
            "SELECT balance FROM economy_accounts WHERE user_id = ?",
            (house_BOT_OWNER_ID,),
        ).fetchone()[0]
        main_house_prestige_bonus = connection.execute(
            """
            SELECT COALESCE(SUM(prestige_level), 0)
            FROM economy_accounts WHERE user_id != ?
            """,
            (house_BOT_OWNER_ID,),
        ).fetchone()[0]
        reservations = connection.execute(
            """
            SELECT COALESCE(SUM(exposure), 0) FROM house_bet_reservations
            WHERE house_BOT_OWNER_ID = ?
            """,
            (house_BOT_OWNER_ID,),
        ).fetchone()[0]
        casinos = connection.execute(
            """
            SELECT c.guild_id, c.BOT_OWNER_ID, c.treasury, c.upgrade_level,
                   c.npc_count, c.npc_next_bet_at, c.npc_owner_online,
                   COALESCE(a.prestige_level, 0)
            FROM guild_casinos AS c
            LEFT JOIN economy_accounts AS a ON a.user_id = c.BOT_OWNER_ID
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

        for guild_id, BOT_OWNER_ID, *_ in casinos:
            progress = casino_progress[guild_id]
            owner_online = BOT_OWNER_ID in online_BOT_OWNER_IDs_by_guild.get(
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
            (house_balance, main_house_earned, main_house_lost, house_BOT_OWNER_ID),
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
    house_BOT_OWNER_ID: int,
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
            return "exists", get_balance(creator_id), get_balance(house_BOT_OWNER_ID)

        connection.executemany(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            ((creator_id,), (house_BOT_OWNER_ID,)),
        )
        balances = {
            account_id: balance
            for account_id, balance in connection.execute(
                """
                SELECT user_id, balance FROM economy_accounts
                WHERE user_id IN (?, ?)
                """,
                (creator_id, house_BOT_OWNER_ID),
            )
        }
        creator_balance = balances[creator_id]
        house_balance = balances[house_BOT_OWNER_ID]
        if creator_id != house_BOT_OWNER_ID and creator_balance < creation_fee:
            return "insufficient", creator_balance, house_balance

        if creator_id != house_BOT_OWNER_ID:
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
                (creation_fee, creation_fee, house_BOT_OWNER_ID),
            )
            creator_balance -= creation_fee
        connection.execute(
            """
            INSERT INTO guild_casinos
                (
                    guild_id, BOT_OWNER_ID, name, currency_name, treasury,
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
            creation_fee if creator_id != house_BOT_OWNER_ID else 0
        )


def delete_guild_casino(
    guild_id: int,
    user_id: int,
) -> tuple[str, int, int]:
    with closing(sqlite3.connect(ECONOMY_DB_PATH, timeout=10)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        casino = connection.execute(
            """
            SELECT BOT_OWNER_ID, treasury
            FROM guild_casinos WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()
        if casino is None:
            return "missing", 0, 0

        BOT_OWNER_ID, treasury = casino
        if BOT_OWNER_ID != user_id:
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
            "SELECT BOT_OWNER_ID, name, currency_name FROM guild_casinos WHERE guild_id = ?",
            (guild_id,),
        ).fetchone()
        if casino is None:
            return None
        BOT_OWNER_ID, name, currency_name = casino
        main_house_owner = connection.execute(
            "SELECT value FROM casino_settings WHERE setting = 'house_BOT_OWNER_ID'"
        ).fetchone()
        main_house_BOT_OWNER_ID = (
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
            (guild_id, BOT_OWNER_ID, main_house_BOT_OWNER_ID),
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
            SELECT BOT_OWNER_ID, treasury, upgrade_level
            FROM guild_casinos WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()
        if casino is None:
            return "missing", 0, 0, 0
        BOT_OWNER_ID, treasury, level = casino
        if user_id != BOT_OWNER_ID:
            return "not_owner", treasury, level, 0
        if expected_level is not None and level != expected_level:
            return "changed", treasury, level, 0
        if level >= len(CASINO_UPGRADE_COSTS):
            return "max_level", treasury, level, 0
        cost = CASINO_UPGRADE_COSTS[level]
        if treasury < cost:
            return "insufficient", treasury, level, cost
        house_owner = connection.execute(
            "SELECT value FROM casino_settings WHERE setting = 'house_BOT_OWNER_ID'"
        ).fetchone()
        if house_owner is None:
            raise RuntimeError("O owner do bot ainda não foi carregado para a banca.")
        house_BOT_OWNER_ID = house_owner[0]
        connection.execute(
            "INSERT OR IGNORE INTO economy_accounts (user_id) VALUES (?)",
            (house_BOT_OWNER_ID,),
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
            (cost, cost, house_BOT_OWNER_ID),
        )
        return "upgraded", new_treasury, new_level, cost


def settle_guild_casino_bet(
    guild_id: int,
    user_id: int,
    house_BOT_OWNER_ID: int,
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
                (house_BOT_OWNER_ID,),
            )
            connection.execute(
                """
                UPDATE economy_accounts
                SET balance = balance + ?, total_earned = total_earned + ?
                WHERE user_id = ?
                """,
                (tax, tax, house_BOT_OWNER_ID),
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


def draw_blackjack_card() -> str:
    return random.choices(
        BLACKJACK_CARDS,
        weights=BLACKJACK_CARD_WEIGHTS,
        k=1,
    )[0]


class BlackjackView(BlacklistView):
    def __init__(
        self,
        user: discord.User | discord.Member,
        bet: int,
        player_cards: list[str],
        dealer_cards: list[str],
        balance: int,
        house_BOT_OWNER_ID: int,
        reservation_id: str,
        win_streak: int,
    ) -> None:
        super().__init__(timeout=90)
        self.user = user
        self.bet = bet
        self.player_cards = player_cards
        self.dealer_cards = dealer_cards
        self.balance = balance
        self.house_BOT_OWNER_ID = house_BOT_OWNER_ID
        self.reservation_id = reservation_id
        self.win_streak = win_streak
        self.streak_bonus_percent = 0
        self.message: discord.InteractionMessage | None = None
        self.finished = False
        self.timed_out = False
        self.result = "Escolha uma ação nos botões abaixo."
        self.payout = 0
        self.net_change = 0
        self.turn_lock = asyncio.Lock()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if await verificar_usuario_bloqueado(interaction):
            return False
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
            if self.net_change > 0:
                embed.add_field(
                    name="🔥 Bônus da sequência",
                    value=(
                        f"+{self.streak_bonus_percent}% sobre o lucro "
                        f"({self.win_streak} vitória(s) seguida(s))"
                    ),
                    inline=False,
                )
            elif self.net_change == 0:
                embed.add_field(
                    name="🔥 Sequência",
                    value=(
                        f"{self.win_streak} vitória(s); sequência mantida "
                        "após inatividade."
                        if self.timed_out
                        else f"{self.win_streak} vitória(s); empate mantém a sequência."
                    ),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="🔥 Sequência",
                    value="Zerada após a derrota.",
                    inline=False,
                )
        else:
            embed.description = (
                f"{self.result}\n\n"
                "Use **Comprar carta** para pedir outra ou **Parar** "
                "para encerrar sua mão. O dealer compra até chegar a 17."
            )
            next_bonus = blackjack_streak_bonus_percent(self.win_streak + 1)
            embed.add_field(
                name="🔥 Próximo bônus",
                value=(
                    f"+{next_bonus}% sobre o lucro se vencer "
                    f"(sequência atual: {self.win_streak})"
                ),
                inline=False,
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
                self.dealer_cards.append(draw_blackjack_card())

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
        if self.payout > self.bet:
            self.streak_bonus_percent = blackjack_streak_bonus_percent(
                self.win_streak + 1
            )
            self.payout = apply_blackjack_streak_bonus(
                self.bet,
                self.payout,
                self.win_streak,
            )
            self.result += (
                f"\n🔥 Bônus da sequência: "
                f"+{self.streak_bonus_percent}% sobre o lucro."
            )
        self.balance = settle_blackjack_bet(
            self.reservation_id,
            self.user.id,
            self.house_BOT_OWNER_ID,
            self.bet,
            self.payout,
        )
        if self.payout > self.bet:
            self.win_streak += 1
        elif self.payout < self.bet:
            self.win_streak = 0
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
                self.player_cards.append(draw_blackjack_card())
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
                view=(
                    BlackjackAgainView(self.user.id, self.bet)
                    if self.finished
                    else self
                ),
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
            self.timed_out = True
            self.balance = settle_blackjack_bet(
                self.reservation_id,
                self.user.id,
                self.house_BOT_OWNER_ID,
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
                await self.message.edit(
                    embed=self.create_embed(),
                    view=BlackjackAgainView(self.user.id, self.bet),
                )


class BlackjackAgainView(BlacklistView):
    def __init__(self, user_id: int, bet: int) -> None:
        super().__init__(timeout=300)
        self.user_id = user_id
        self.bet = bet

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if await verificar_usuario_bloqueado(interaction):
            return False
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            "Somente quem fez a aposta pode iniciar outra partida.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(
        label="Jogar blackjack novamente",
        emoji="🔁",
        style=discord.ButtonStyle.primary,
    )
    async def repeat(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        await repeat_blackjack(interaction, self.bet)


class PrestigeConfirmView(BlacklistView):
    def __init__(self, user_id: int) -> None:
        super().__init__(timeout=60)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if await verificar_usuario_bloqueado(interaction):
            return False
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


class PrestigeUpgradeView(BlacklistView):
    def __init__(self, user_id: int, upgrade_key: str) -> None:
        super().__init__(timeout=60)
        self.user_id = user_id
        self.upgrade_key = upgrade_key

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if await verificar_usuario_bloqueado(interaction):
            return False
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


class DeleteGuildCasinoView(BlacklistView):
    def __init__(
        self,
        guild_id: int,
        BOT_OWNER_ID: int,
        casino_name: str,
    ) -> None:
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.BOT_OWNER_ID = BOT_OWNER_ID
        self.casino_name = casino_name

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if await verificar_usuario_bloqueado(interaction):
            return False
        if interaction.user.id == self.BOT_OWNER_ID:
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


def slot_payout(reels: list[str], bet: int) -> tuple[int, str, float]:
    if len(reels) != 3 or bet <= 0:
        raise ValueError("A máquina exige três símbolos e uma aposta positiva.")

    if reels[0] == reels[1] == reels[2]:
        base_multiplier = SLOT_TRIPLE_MULTIPLIERS[reels[0]]
        base_payout = bet * base_multiplier
        payout = bet + (
            (base_payout - bet) * SLOT_PROFIT_FACTOR_NUMERATOR
            // SLOT_PROFIT_FACTOR_DENOMINATOR
        )
        return payout, f"Trinca de {reels[0]}", payout / bet

    for symbol in SLOT_SYMBOLS:
        if reels.count(symbol) == 2:
            base_multiplier = SLOT_PAIR_MULTIPLIERS[symbol]
            base_payout = bet * base_multiplier
            payout = (
                bet + (
                    (base_payout - bet) * SLOT_PROFIT_FACTOR_NUMERATOR
                    // SLOT_PROFIT_FACTOR_DENOMINATOR
                )
                if base_payout > bet
                else base_payout
            )
            return payout, f"Par de {symbol}", payout / bet

    return 0, "Sem combinação premiada", 0.0


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

    count = len(selected_animals)
    multiplier = ANIMAL_BET_MULTIPLIERS[count]
    payout = (
        payout_for_target_rtp(bet, count, len(BETTING_ANIMALS))
        if drawn_animal in selected_animals
        else 0
    )
    return payout, multiplier


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


def render_scratchcard_gif(
    symbols: list[str],
    multiplier: float,
) -> io.BytesIO:
    width, height = 600, 330
    frames: list[Image.Image] = []
    colors = {
        "CEREJA": (231, 82, 103),
        "LIMAO": (129, 205, 91),
        "SINO": (246, 191, 76),
        "ESTRELA": (100, 173, 245),
        "DIAMANTE": (102, 221, 211),
    }
    font_path = r"C:\Windows\Fonts\arial.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 27)
        symbol_font = ImageFont.truetype(font_path, 19)
        caption_font = ImageFont.truetype(font_path, 17)
    except OSError:
        title_font = ImageFont.load_default()
        symbol_font = ImageFont.load_default()
        caption_font = ImageFont.load_default()

    for frame_index in range(18):
        image = Image.new("RGB", (width, height), (18, 23, 48))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (24, 18, width - 24, height - 18),
            radius=27,
            fill=(35, 43, 74),
            outline=(247, 201, 87),
            width=4,
        )
        draw.text(
            (width // 2, 53),
            "RASP - RASPADINHA",
            font=title_font,
            fill=(255, 225, 150),
            anchor="mm",
        )
        revealed_count = min(3, max(0, (frame_index - 2) // 4))
        for index, center_x in enumerate((155, 300, 445)):
            card = (center_x - 61, 91, center_x + 61, 231)
            draw.rounded_rectangle(
                card,
                radius=18,
                fill=(242, 239, 221),
                outline=(255, 255, 255),
                width=3,
            )
            if index < revealed_count:
                color = colors[symbols[index]]
                draw.ellipse(
                    (center_x - 37, 113, center_x + 37, 187),
                    fill=color,
                    outline=(255, 255, 255),
                    width=3,
                )
                draw.text(
                    (center_x, 208),
                    symbols[index],
                    font=symbol_font,
                    fill=(36, 43, 63),
                    anchor="mm",
                )
            else:
                draw.rounded_rectangle(
                    (center_x - 52, 100, center_x + 52, 222),
                    radius=13,
                    fill=(143, 151, 169),
                    outline=(220, 226, 238),
                    width=2,
                )
                for hatch_y in range(107, 218, 15):
                    draw.line(
                        (center_x - 47, hatch_y, center_x + 47, hatch_y + 22),
                        fill=(176, 183, 198),
                        width=2,
                    )
                scratch_x = center_x - 39 + (frame_index * 17 % 78)
                draw.line(
                    (scratch_x, 110, scratch_x + 26, 208),
                    fill=(255, 236, 177),
                    width=5,
                )

        if revealed_count == 3:
            label = f"PREMIO  x{multiplier:g}" if multiplier > 1 else (
                "APOSTA DEVOLVIDA" if multiplier == 1 else "SEM PREMIO"
            )
            accent = (83, 216, 154) if multiplier > 1 else (
                (247, 201, 87) if multiplier == 1 else (205, 211, 228)
            )
            draw.rounded_rectangle(
                (170, 252, 430, 296),
                radius=18,
                fill=(20, 26, 47),
                outline=accent,
                width=2,
            )
            draw.text(
                (width // 2, 274),
                label,
                font=caption_font,
                fill=accent,
                anchor="mm",
            )
        else:
            draw.text(
                (width // 2, 274),
                "RASPE OS CARTOES...",
                font=caption_font,
                fill=(213, 221, 241),
                anchor="mm",
            )
        frames.append(image)

    output = io.BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=[75] * (len(frames) - 1) + [1200],
        optimize=False,
        disposal=2,
    )
    output.seek(0)
    return output


def render_mines_gif(
    opened_tiles: list[int],
    mine_positions: set[int],
    multiplier: float,
) -> io.BytesIO:
    width, height = 560, 360
    frames: list[Image.Image] = []
    font_path = r"C:\Windows\Fonts\arial.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 27)
        tile_font = ImageFont.truetype(font_path, 24)
        caption_font = ImageFont.truetype(font_path, 17)
    except OSError:
        title_font = ImageFont.load_default()
        tile_font = ImageFont.load_default()
        caption_font = ImageFont.load_default()

    steps = [opened_tiles[:index] for index in range(1, len(opened_tiles) + 1)]
    steps.append(opened_tiles)
    for frame_index, visible_tiles in enumerate(steps):
        final_frame = frame_index == len(steps) - 1
        visible = set(visible_tiles)
        hit_mine = bool(visible & mine_positions)
        image = Image.new("RGB", (width, height), (18, 23, 48))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (22, 16, width - 22, height - 16),
            radius=26,
            fill=(35, 43, 74),
            outline=(247, 201, 87),
            width=4,
        )
        draw.text(
            (width // 2, 48),
            "CAMPO MINADO",
            font=title_font,
            fill=(255, 225, 150),
            anchor="mm",
        )
        for tile in range(9):
            column, row = tile % 3, tile // 3
            left = 145 + column * 91
            top = 80 + row * 75
            bounds = (left, top, left + 68, top + 58)
            is_mine = tile in mine_positions
            is_revealed = tile in visible
            show_mine = is_mine and (is_revealed or final_frame)
            fill = (
                (185, 61, 77)
                if show_mine
                else (54, 168, 119)
                if is_revealed
                else (68, 83, 119)
            )
            draw.rounded_rectangle(
                bounds,
                radius=12,
                fill=fill,
                outline=(226, 232, 245),
                width=2,
            )
            if show_mine:
                label = "X"
            elif is_revealed:
                label = "O"
            else:
                label = "O"
            draw.text(
                (left + 34, top + 29),
                label,
                font=tile_font,
                fill=(255, 255, 255),
                anchor="mm",
            )
        if final_frame:
            label = f"PREMIO  x{multiplier:g}" if multiplier > 1 else (
                "VOCE ACHOU UMA MINA" if hit_mine else "APOSTA DEVOLVIDA"
            )
            accent = (83, 216, 154) if multiplier > 1 else (
                (235, 92, 105) if hit_mine else (247, 201, 87)
            )
        else:
            label = "PROCURANDO CASAS SEGURAS..."
            accent = (213, 221, 241)
        draw.text(
            (width // 2, 323),
            label,
            font=caption_font,
            fill=accent,
            anchor="mm",
        )
        frames.append(image)

    output = io.BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=[230] * (len(frames) - 1) + [1200],
        optimize=False,
        disposal=2,
    )
    output.seek(0)
    return output


def render_slot_gif(reels: list[str], multiplier: float) -> io.BytesIO:
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
            banner_color = (
                "#53d89a"
                if multiplier > 1
                else "#f7c957"
                if multiplier == 1
                else "#c6c9d8"
            )
            banner_text = (
                f"PREMIO  x{multiplier:g}"
                if multiplier > 1
                else "APOSTA DEVOLVIDA"
                if multiplier == 1
                else "TENTE DE NOVO"
            )
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


def render_dice_gif(result: int) -> io.BytesIO:
    width, height = 560, 300
    frame_count = 16
    frames: list[Image.Image] = []
    font_path = r"C:\Windows\Fonts\arial.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 28)
        result_font = ImageFont.truetype(font_path, 20)
    except OSError:
        title_font = ImageFont.load_default()
        result_font = ImageFont.load_default()

    pip_positions = {
        1: ((0, 0),),
        2: ((-1, -1), (1, 1)),
        3: ((-1, -1), (0, 0), (1, 1)),
        4: ((-1, -1), (-1, 1), (1, -1), (1, 1)),
        5: ((-1, -1), (-1, 1), (0, 0), (1, -1), (1, 1)),
        6: ((-1, -1), (-1, 0), (-1, 1), (1, -1), (1, 0), (1, 1)),
    }
    for frame_index in range(frame_count):
        image = Image.new("RGB", (width, height), (18, 28, 49))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (20, 18, width - 20, height - 18),
            radius=28,
            fill=(31, 44, 70),
            outline=(82, 196, 164),
            width=4,
        )
        draw.text(
            (width // 2, 48),
            "DADOS",
            font=title_font,
            fill=(255, 225, 150),
            anchor="mm",
        )
        rolled = result if frame_index == frame_count - 1 else random.randint(1, 6)
        die_box = (width // 2 - 76, 76, width // 2 + 76, 228)
        draw.rounded_rectangle(
            die_box,
            radius=24,
            fill=(248, 246, 235),
            outline=(255, 255, 255),
            width=4,
        )
        for column, row in pip_positions[rolled]:
            x = width // 2 + column * 42
            y = 152 + row * 42
            draw.ellipse(
                (x - 9, y - 9, x + 9, y + 9),
                fill=(37, 49, 73),
            )
        draw.text(
            (width // 2, 260),
            f"RESULTADO: {rolled}" if frame_index == frame_count - 1 else "ROLANDO...",
            font=result_font,
            fill=(230, 237, 249),
            anchor="mm",
        )
        frames.append(image)

    output = io.BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=[65] * (frame_count - 1) + [1100],
        optimize=False,
        disposal=2,
    )
    output.seek(0)
    return output


def render_roulette_gif(number: int, result_color: str) -> io.BytesIO:
    width, height = 560, 320
    frame_count = 20
    frames: list[Image.Image] = []
    font_path = r"C:\Windows\Fonts\arial.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 26)
        result_font = ImageFont.truetype(font_path, 21)
        center_font = ImageFont.truetype(font_path, 27)
    except OSError:
        title_font = ImageFont.load_default()
        result_font = ImageFont.load_default()
        center_font = ImageFont.load_default()

    segment_angle = 360 / 37
    target_rotation = -90 - number * segment_angle
    for frame_index in range(frame_count):
        image = Image.new("RGB", (width, height), (18, 28, 49))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (20, 16, width - 20, height - 16),
            radius=28,
            fill=(31, 44, 70),
            outline=(219, 173, 86),
            width=4,
        )
        draw.text(
            (width // 2, 42),
            "ROLETA EUROPEIA",
            font=title_font,
            fill=(255, 225, 150),
            anchor="mm",
        )
        center_x, center_y = width // 2, 178
        radius = 108
        remaining_turns = 5 * (1 - frame_index / (frame_count - 1)) ** 2
        rotation = target_rotation - remaining_turns * 360
        for index in range(37):
            center_angle = rotation + index * segment_angle
            start_angle = center_angle - segment_angle / 2
            draw.pieslice(
                (
                    center_x - radius,
                    center_y - radius,
                    center_x + radius,
                    center_y + radius,
                ),
                start=start_angle,
                end=start_angle + segment_angle,
                fill=(
                    (43, 165, 107)
                    if index == 0
                    else (194, 57, 67)
                    if index in ROULETTE_RED_NUMBERS
                    else (30, 34, 42)
                ),
                outline=(235, 217, 173),
                width=1,
            )
        draw.ellipse(
            (
                center_x - 47,
                center_y - 47,
                center_x + 47,
                center_y + 47,
            ),
            fill=(24, 35, 54),
            outline=(235, 217, 173),
            width=3,
        )
        is_final_frame = frame_index == frame_count - 1
        center_text = str(number) if is_final_frame else "..."
        draw.text(
            (center_x, center_y),
            center_text,
            font=center_font,
            fill=(255, 255, 255),
            anchor="mm",
        )
        ball_angle = math.radians(-90)
        ball_x = center_x + int((radius + 13) * math.cos(ball_angle))
        ball_y = center_y + int((radius + 13) * math.sin(ball_angle))
        draw.ellipse(
            (ball_x - 8, ball_y - 8, ball_x + 8, ball_y + 8),
            fill=(255, 244, 205),
            outline=(255, 255, 255),
            width=2,
        )
        draw.text(
            (width // 2, 294),
            f"{number} {result_color.upper()}"
            if is_final_frame
            else "GIRANDO...",
            font=result_font,
            fill=(230, 237, 249),
            anchor="mm",
        )
        frames.append(image)

    output = io.BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=[65] * (frame_count - 1) + [1200],
        optimize=False,
        disposal=2,
    )
    output.seek(0)
    return output


initialize_economy()


def get_last_announced_update() -> str | None:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection, connection:
        state = connection.execute(
            """
            SELECT value FROM bot_update_state
            WHERE setting = 'last_announced_update'
            """
        ).fetchone()
    return state[0] if state is not None else None


def set_last_announced_update(message: str) -> None:
    with closing(
        sqlite3.connect(ECONOMY_DB_PATH, timeout=10)
    ) as connection, connection:
        connection.execute(
            """
            INSERT INTO bot_update_state (setting, value)
            VALUES ('last_announced_update', ?)
            ON CONFLICT(setting) DO UPDATE SET value = excluded.value
            """,
            (message,),
        )


# Os comandos de blacklist foram registrados antes de a classe final do bot
# estar definida. Guarde a árvore temporária para transferi-los ao bot ativo.
legacy_bot = bot


class BotDiscord(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True
        super().__init__(intents=intents)
        self.tree = BlacklistCommandTree(self)
        self.house_BOT_OWNER_ID: int | None = None
        self.npc_betting_task: asyncio.Task[None] | None = None

    async def setup_hook(self) -> None:
        self.house_BOT_OWNER_ID = BOT_OWNER_ID
        set_house_BOT_OWNER_ID(self.house_BOT_OWNER_ID)


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
        if self.npc_betting_task is None or self.npc_betting_task.done():
            self.npc_betting_task = asyncio.create_task(
                self.npc_betting_loop(),
                name="npc-betting-loop",
            )

    async def announce_update(self, message: str) -> bool:
        return await self.publish_update_message(
            message,
            mention_role=True,
        )

    async def publish_update_message(
        self,
        message: str,
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
            title="🎰 Novidades do Cassino",
            description=message,
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text="Atualização manual do bot")
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
            set_last_announced_update(message)
        except sqlite3.Error:
            logger.exception(
                "A atualização foi publicada, mas seu estado não pôde ser salvo."
            )
            return False
        return True

    async def npc_betting_loop(self) -> None:
        while not self.is_closed():
            try:
                online_BOT_OWNER_IDs_by_guild = {
                    guild.id: {
                        member.id
                        for member in guild.members
                        if member.status is not discord.Status.offline
                    }
                    for guild in self.guilds
                }
                main_house_online = any(
                    BOT_OWNER_ID in BOT_OWNER_IDs
                    for BOT_OWNER_IDs in online_BOT_OWNER_IDs_by_guild.values()
                )
                main_bets, local_bets = run_npc_betting_cycle(
                    main_house_online=main_house_online,
                    online_BOT_OWNER_IDs_by_guild=online_BOT_OWNER_IDs_by_guild,
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
for command in legacy_bot.tree.get_commands():
    bot.tree.add_command(command)


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


class DuelView(BlacklistView):
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

    def finished_view(self) -> discord.ui.View | None:
        if not self.finished:
            return self
        if not self.accepted:
            return None
        return DuelAgainView(
            self.challenger,
            self.opponent,
            self.bet,
            self.game,
        )

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
        if await verificar_usuario_bloqueado(interaction):
            return False
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
                view=self.finished_view(),
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
                view=self.finished_view(),
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
                await self.message.edit(
                    embed=self.create_embed(),
                    view=self.finished_view(),
                )


class DuelAgainView(BlacklistView):
    def __init__(
        self,
        challenger: discord.User | discord.Member,
        opponent: discord.User | discord.Member,
        bet: int,
        game: str,
    ) -> None:
        super().__init__(timeout=300)
        self.challenger = challenger
        self.opponent = opponent
        self.bet = bet
        self.game = game

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if await verificar_usuario_bloqueado(interaction):
            return False
        if interaction.user.id in (self.challenger.id, self.opponent.id):
            return True
        await interaction.response.send_message(
            "Somente os participantes podem repetir este desafio.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(
        label="Desafiar novamente",
        emoji="🔁",
        style=discord.ButtonStyle.primary,
    )
    async def repeat(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if not await ensure_betting_channel(interaction):
            return
        challenger_limit = get_player_bet_limit(self.challenger.id)
        opponent_limit = get_player_bet_limit(self.opponent.id)
        if self.bet > min(challenger_limit, opponent_limit):
            await interaction.response.send_message(
                "O limite de aposta de um dos participantes mudou; "
                "inicie outro desafio com um valor menor.",
                ephemeral=True,
            )
            return
        view = DuelView(self.challenger, self.opponent, self.bet, self.game)
        await interaction.response.edit_message(
            embed=view.create_embed(),
            view=view,
        )
        view.message = interaction.message


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
        f"{interaction.user.mention} recebeu {format_coins(amount)} moedas "
        f"de recompensa diária. Saldo: {format_coins(balance)} moedas!"
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
        f"{interaction.user.mention} recebeu {format_coins(amount)} moedas "
        f"de recompensa semanal. Saldo: {format_coins(balance)} moedas!"
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
        f"{interaction.user.mention} recebeu {format_coins(amount)} moedas "
        f"de recompensa mensal. Saldo: {format_coins(balance)} moedas!"
    )


@bot.tree.command(name="saldo", description="Mostra seu saldo de moedas.")
async def saldo(interaction: discord.Interaction) -> None:
    balance = get_balance(interaction.user.id)
    await interaction.response.send_message(
        f"{interaction.user.mention}, seu saldo é de "
        f"{format_coins(balance)} moedas.",
        ephemeral=True,
    )


class JobSelectView(BlacklistView):
    def __init__(self, user_id: int) -> None:
        super().__init__(timeout=120)
        self.user_id = user_id
        options = [
            discord.SelectOption(
                label=name,
                value=job_key,
                description=(
                    f"Inscrição: {format_coins(cost)} moedas | "
                    f"Salário: {format_coins(hourly_rate)} moedas/h"
                ),
                emoji="💼",
            )
            for job_key, (name, cost, hourly_rate) in JOBS.items()
        ]
        self.add_item(JobSelect(options))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if await verificar_usuario_bloqueado(interaction):
            return False
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            "Este seletor de trabalho pertence a outra pessoa.",
            ephemeral=True,
        )
        return False


class JobSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder="Escolha seu próximo trabalho",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        status, balance = change_player_job(
            interaction.user.id,
            self.values[0],
        )
        if status == "casino_owner":
            await interaction.response.edit_message(
                content="Donos de cassino não podem trocar de trabalho.",
                embed=None,
                view=None,
            )
            return
        if status == "same_job":
            await interaction.response.send_message(
                "Você já trabalha nessa profissão.",
                ephemeral=True,
            )
            return
        if status == "insufficient":
            cost = JOBS[self.values[0]][1]
            await interaction.response.send_message(
                f"A inscrição custa {format_coins(cost)} moedas; "
                f"seu saldo é {format_coins(balance)} moedas.",
                ephemeral=True,
            )
            return

        job_name, application_cost, hourly_rate = JOBS[self.values[0]]
        embed = discord.Embed(
            title="💼 Novo trabalho confirmado",
            description=f"Agora você trabalha como **{job_name}**.",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Taxa de inscrição",
            value=f"{format_coins(application_cost)} moedas",
            inline=True,
        )
        embed.add_field(
            name="Salário por hora",
            value=f"{format_coins(hourly_rate)} moedas",
            inline=True,
        )
        embed.add_field(
            name="Saldo restante",
            value=f"{format_coins(balance)} moedas",
            inline=True,
        )
        self.view.stop()
        await interaction.response.edit_message(embed=embed, view=None)


@bot.tree.command(
    name="mudar_trabalho",
    description="Escolha um trabalho e pague a taxa de inscrição.",
)
async def mudar_trabalho(interaction: discord.Interaction) -> None:
    with closing(sqlite3.connect(ECONOMY_DB_PATH)) as connection:
        owns_casino = connection.execute(
            "SELECT 1 FROM guild_casinos WHERE BOT_OWNER_ID = ? LIMIT 1",
            (interaction.user.id,),
        ).fetchone()
    if owns_casino is not None:
        await interaction.response.send_message(
            "Este upgrade de trabalho só está disponível para quem não possui cassino.",
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title="📋 Mudar de trabalho",
        description=(
            "Selecione uma profissão. A taxa de inscrição é cobrada "
            "imediatamente e cada trabalho paga por hora trabalhada."
        ),
        color=discord.Color.blurple(),
    )
    for name, cost, hourly_rate in JOBS.values():
        embed.add_field(
            name=name,
            value=(
                f"Inscrição: **{format_coins(cost)} moedas**\n"
                f"Salário: **{format_coins(hourly_rate)} moedas/h**"
            ),
            inline=True,
        )
    await interaction.response.send_message(
        embed=embed,
        view=JobSelectView(interaction.user.id),
        ephemeral=True,
    )


@bot.tree.command(
    name="workshift",
    description="Trabalhe até 8 horas e recupere seu limite a cada 8 horas.",
)
async def workshift(interaction: discord.Interaction) -> None:
    status, job_key, duration, payout, balance, remaining, resets_at = (
        work_player_shift(interaction.user.id)
    )
    if status == "limit":
        await interaction.response.send_message(
            "Você já trabalhou o limite de **8 horas**. "
            f"As horas serão recuperadas em {format_remaining(resets_at - int(time.time()))}.",
            ephemeral=True,
        )
        return

    job_name, _, hourly_rate = JOBS[job_key]
    embed = discord.Embed(
        title="🧰 Turno concluído",
        description=(
            f"{interaction.user.mention}, você trabalhou como "
            f"**{job_name}** por **{format_remaining(duration)}**."
        ),
        color=discord.Color.green(),
    )
    embed.add_field(
        name="Pagamento",
        value=f"+{format_coins(payout)} moedas",
        inline=True,
    )
    embed.add_field(
        name="Salário por hora",
        value=f"{format_coins(hourly_rate)} moedas",
        inline=True,
    )
    embed.add_field(
        name="Saldo atual",
        value=f"{format_coins(balance)} moedas",
        inline=True,
    )
    embed.add_field(
        name="Horas restantes neste ciclo",
        value=f"{format_remaining(remaining)} de 8h",
        inline=False,
    )
    embed.set_footer(text="O limite de 8 horas é renovado a cada 8 horas.")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="roubar",
    description="Tente roubar moedas; você pode ganhar ou perder dinheiro.",
)
async def roubar(interaction: discord.Interaction) -> None:
    status, balance, attempts, amount, recover_at = attempt_robbery(
        interaction.user.id
    )
    if status == "cooldown":
        remaining = max(0, (recover_at or 0) - int(time.time()))
        await interaction.response.send_message(
            f"Você esgotou suas tentativas. As **5 tentativas** voltam em "
            f"{format_remaining(remaining)} (recuperação após 8 horas).",
            ephemeral=True,
        )
        return

    if status == "success":
        title = "🤑 Roubo bem-sucedido!"
        description = f"Você conseguiu **{format_coins(amount)} moedas**."
        color = discord.Color.green()
    else:
        title = "🚨 Você foi pego!"
        description = (
            f"Você perdeu **{format_coins(amount)} moedas** e suas tentativas "
            "foram esgotadas."
        )
        color = discord.Color.red()

    embed = discord.Embed(title=title, description=description, color=color)
    embed.add_field(
        name="Tentativas restantes",
        value=f"{format_coins(attempts)} de {ROBBERY_MAX_ATTEMPTS}",
        inline=True,
    )
    embed.add_field(
        name="Saldo atual",
        value=f"{format_coins(balance)} moedas",
        inline=True,
    )
    if attempts == 0 and recover_at is not None:
        embed.set_footer(
            text=(
                "Todas as tentativas voltam em "
                f"{format_remaining(recover_at - int(time.time()))}."
            )
        )
    await interaction.response.send_message(embed=embed)


class PlayerDataResetView(BlacklistView):
    def __init__(self, BOT_OWNER_ID: int, reset_type: str) -> None:
        super().__init__(timeout=60)
        self.BOT_OWNER_ID = BOT_OWNER_ID
        self.reset_type = reset_type

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if await verificar_usuario_bloqueado(interaction):
            return False
        if interaction.user.id == self.BOT_OWNER_ID == BOT_OWNER_ID:
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
        f"**{format_coins(position)}.** <@{user_id}> — "
        f"**{format_coins(balance)}** moedas"
        f" | Ganho: {format_coins(earned)}"
        f" | Perdido: {format_coins(lost)}"
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


class MainHouseUpgradeView(BlacklistView):
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
        get_house_BOT_OWNER_ID(),
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

    BOT_OWNER_ID, name, currency_name, treasury, _ = casino
    if interaction.user.id != BOT_OWNER_ID:
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
        view=DeleteGuildCasinoView(guild.id, BOT_OWNER_ID, name),
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
    house_BOT_OWNER_ID = get_house_BOT_OWNER_ID()
    owner = bot.get_user(house_BOT_OWNER_ID)
    if owner is None:
        try:
            owner = await bot.fetch_user(house_BOT_OWNER_ID)
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
    house_BOT_OWNER_ID = get_house_BOT_OWNER_ID()
    owner = bot.get_user(house_BOT_OWNER_ID)
    if owner is None:
        try:
            owner = await bot.fetch_user(house_BOT_OWNER_ID)
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
        BOT_OWNER_ID,
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
    if interaction.user.id != BOT_OWNER_ID:
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
    unlocked_games = [
        CASINO_GAME_DISPLAY_NAMES.get(game, game)
        for game, required_level in CASINO_GAME_UNLOCKS.items()
        if required_level == next_level
    ]
    embed = discord.Embed(
        title=f"Confirmar upgrade do cassino — nível {next_level}",
        description=(
            f"Jogos liberados: **{', '.join(unlocked_games)}**. "
            "A taxa da casa "
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


class GuildCasinoUpgradeView(BlacklistView):
    def __init__(self, guild_id: int, BOT_OWNER_ID: int, expected_level: int) -> None:
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.BOT_OWNER_ID = BOT_OWNER_ID
        self.expected_level = expected_level

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if await verificar_usuario_bloqueado(interaction):
            return False
        if interaction.user.id == self.BOT_OWNER_ID:
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
            self.BOT_OWNER_ID,
            self.expected_level,
        )
        if status == "upgraded":
            casino = get_guild_casino(self.guild_id)
            currency_name = casino[2] if casino is not None else "moedas"
            unlocked_games = [
                CASINO_GAME_DISPLAY_NAMES.get(game, game)
                for game, required_level in CASINO_GAME_UNLOCKS.items()
                if required_level == level
            ]
            message = (
                f"✅ Cassino promovido ao nível **{level}**! "
                f"Jogos liberados: **{', '.join(unlocked_games)}**. Os **"
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
                        self.BOT_OWNER_ID,
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
    BOT_OWNER_ID, _, currency_name, treasury, level = casino
    if interaction.user.id != BOT_OWNER_ID:
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
        view=GuildCasinoUpgradeView(guild.id, BOT_OWNER_ID, level),
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
    escolha=(
        "Cara/coroa, par ou impar, numero, cor, maior/menor ou "
        "pedra/papel/tesoura. Campo Minado: 1 a 5 casas seguras; "
        "Raspadinha nao usa escolha."
    ),
)
@app_commands.choices(
    jogo=[
        app_commands.Choice(name="Cara ou coroa", value="moeda"),
        app_commands.Choice(name="Dados", value="dados"),
        app_commands.Choice(name="Roleta", value="roleta"),
        app_commands.Choice(name="Maior ou menor", value="maior_menor"),
        app_commands.Choice(name="Caça-níquel", value="cacaniquel"),
        app_commands.Choice(name="Jokenpô", value="jokenpo"),
        app_commands.Choice(name="Campo Minado", value="campo_minado"),
        app_commands.Choice(name="Raspadinha", value="raspadinha"),
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
    normalized_choice = ""
    if jogo.value == "moeda":
        normalized_choice = (escolha or "").strip().lower()
        if normalized_choice not in ("cara", "coroa"):
            await interaction.response.send_message(
                "Para cara ou coroa, escolha `cara` ou `coroa`.",
                ephemeral=True,
            )
            return
        drawn = random.choice(("cara", "coroa"))
        payout = (
            payout_for_target_rtp(aposta, 1, 2)
            if normalized_choice == drawn
            else 0
        )
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
            payout = payout_for_target_rtp(aposta, 3, 6) if won else 0
        else:
            drawn = str(roll)
            won = roll == int(normalized_choice)
            payout = payout_for_target_rtp(aposta, 1, 6) if won else 0
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
        winning_outcomes = 1 if normalized_choice == "verde" else 18
        payout = (
            payout_for_target_rtp(aposta, winning_outcomes, 37)
            if normalized_choice == drawn
            else 0
        )
        choice_text = f"Escolha: **{normalized_choice}**."
        result = f"A roleta parou no **{number} {drawn}**."
    elif jogo.value == "maior_menor":
        normalized_choice = (escolha or "").strip().lower()
        if normalized_choice not in ("maior", "menor"):
            await interaction.response.send_message(
                "Para maior ou menor, escolha `maior` ou `menor` que 7.",
                ephemeral=True,
            )
            return
        card = random.randint(1, 13)
        if card == 7:
            payout = aposta
            result = f"Saiu **{card}**. Empate: sua aposta foi devolvida."
        else:
            won = (card > 7 and normalized_choice == "maior") or (
                card < 7 and normalized_choice == "menor"
            )
            payout = (
                payout_for_target_rtp(aposta, 6, 13, push_outcomes=1)
                if won
                else 0
            )
            result = (
                f"Saiu **{card}**; o resultado foi "
                f"**{'maior' if card > 7 else 'menor'} que 7**."
            )
        choice_text = f"Escolha: **{normalized_choice} que 7**."
    elif jogo.value == "jokenpo":
        normalized_choice = (escolha or "").strip().lower()
        if normalized_choice not in ("pedra", "papel", "tesoura"):
            await interaction.response.send_message(
                "Para jokenpô, escolha `pedra`, `papel` ou `tesoura`.",
                ephemeral=True,
            )
            return
        drawn = random.choice(("pedra", "papel", "tesoura"))
        beats = {
            "pedra": "tesoura",
            "papel": "pedra",
            "tesoura": "papel",
        }
        if normalized_choice == drawn:
            payout = aposta
            result = (
                f"Empate: ambos escolheram **{drawn}**. "
                "Sua aposta foi devolvida."
            )
        elif beats[normalized_choice] == drawn:
            payout = payout_for_target_rtp(aposta, 1, 3, push_outcomes=1)
            result = f"Você venceu: **{normalized_choice}** vence **{drawn}**."
        else:
            payout = 0
            result = f"A casa venceu: **{drawn}** vence **{normalized_choice}**."
        choice_text = f"Escolha: **{normalized_choice}**."
    elif jogo.value == "campo_minado":
        normalized_choice = (escolha or "").strip()
        if not normalized_choice.isdecimal() or not 1 <= int(normalized_choice) <= 5:
            await interaction.response.send_message(
                "Para Campo Minado, escolha de 1 a 5 casas seguras em `escolha`.",
                ephemeral=True,
            )
            return
        safe_picks = int(normalized_choice)
        opened_tiles, mine_positions, payout = play_mines(aposta, safe_picks)
        choice_text = f"Tentativas: **{safe_picks} casas seguras**."
        if payout:
            result = f"Voce abriu {safe_picks} casas sem encontrar uma mina."
        else:
            result = f"Uma mina apareceu na tentativa **{len(opened_tiles)}**. A aposta foi perdida."
    elif jogo.value == "raspadinha":
        symbols, payout, combination = play_scratchcard(aposta)
        normalized_choice = "raspadinha"
        choice_text = "Raspadinha de tres cartoes."
        result = f"Simbolos revelados: **{' | '.join(symbols)}** - {combination}."
    else:
        reels = random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=3)
        payout, combination, _ = slot_payout(reels, aposta)
        drawn = " | ".join(reels)
        choice_text = f"Combinação: **{drawn}**."
        result = f"{combination}! Combinação: **{drawn}**."

    payout = adjust_player_bet_payout(interaction.user.id, aposta, payout)
    if jogo.value == "cacaniquel":
        result = (
            f"{combination}! Multiplicador x{payout / aposta:g}. "
            f"Combinação: **{drawn}**."
        )
    result_file = None
    result_image_url = None
    if jogo.value == "dados":
        animation = await asyncio.to_thread(render_dice_gif, roll)
        result_file = discord.File(animation, filename="dados.gif")
        result_image_url = "attachment://dados.gif"
    elif jogo.value == "roleta":
        animation = await asyncio.to_thread(
            render_roulette_gif,
            number,
            drawn,
        )
        result_file = discord.File(animation, filename="roleta.gif")
        result_image_url = "attachment://roleta.gif"
    elif jogo.value == "campo_minado":
        animation = await asyncio.to_thread(
            render_mines_gif,
            opened_tiles,
            mine_positions,
            payout / aposta,
        )
        result_file = discord.File(animation, filename="campo-minado.gif")
        result_image_url = "attachment://campo-minado.gif"
    elif jogo.value == "raspadinha":
        animation = await asyncio.to_thread(
            render_scratchcard_gif,
            symbols,
            payout / aposta,
        )
        result_file = discord.File(animation, filename="raspadinha.gif")
        result_image_url = "attachment://raspadinha.gif"
    settlement = settle_guild_casino_bet(
        guild.id,
        interaction.user.id,
        get_house_BOT_OWNER_ID(),
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
            "O caixa do cassino não consegue cobrir esse prêmio; "
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

    await send_bet_result(
        interaction,
        game=name,
        bet=aposta,
        choice=choice_text,
        result=result,
        payout=payout,
        balance=balance,
        file=result_file,
        image_url=result_image_url,
        view=BetAgainView(
            interaction.user.id,
            jogo.value,
            aposta,
            normalized_choice if jogo.value != "cacaniquel" else "giro",
            guild_id=guild.id,
        ),
        currency_name=currency_name,
        casino_name=name,
        tax_percent=tax_percent,
        tax_amount=tax,
        treasury=treasury,
    )


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
    payout, combination, _ = slot_payout(reels, aposta)
    payout = adjust_player_bet_payout(interaction.user.id, aposta, payout)
    multiplier = payout / aposta
    animation = await asyncio.to_thread(render_slot_gif, reels, multiplier)

    settled, balance, _ = settle_house_bet(
        interaction.user.id,
        get_house_BOT_OWNER_ID(),
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

    if payout > aposta:
        outcome = f"**{combination}! Multiplicador x{multiplier}.**"
        result_title = "🎉 VOCÊ GANHOU!"
        net_change = payout - aposta
        color = discord.Color.green()
    elif payout == aposta:
        outcome = f"**{combination}. Sua aposta foi devolvida.**"
        result_title = "🤝 EMPATE"
        net_change = 0
        color = discord.Color.gold()
    else:
        outcome = f"**{combination}.**"
        result_title = "😿 SEM PREMIO"
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
            "Os prêmios foram recalibrados para manter o retorno esperado "
            "próximo de 95% antes dos bônus de prestígio. O multiplicador "
            "considera o retorno final desta aposta."
        ),
        inline=False,
    )
    embed.set_footer(text=f"Saldo atual: {format_coins(balance)} moedas")
    await interaction.followup.send(
        embed=embed,
        file=discord.File(animation, filename="cacaniquel.gif"),
        view=BetAgainView(
            interaction.user.id,
            "cacaniquel",
            aposta,
            "giro",
        ),
    )


@bot.tree.command(
    name="jogo_do_bixo",
    description="Aposte em até três animais e tente acertar o sorteado.",
)
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
async def jogo_do_bixo(
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
        get_house_BOT_OWNER_ID(),
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
    artwork = await asyncio.to_thread(
        render_bet_result_image,
        "JOGO DO BICHO",
        result,
        payout,
        aposta,
    )
    embed.set_image(url="attachment://resultado-jogo-do-bicho.png")
    await interaction.response.send_message(
        embed=embed,
        file=discord.File(artwork, filename="resultado-jogo-do-bicho.png"),
        view=BetAgainView(
            interaction.user.id,
            "jogo_do_bixo",
            aposta,
            tuple(selected_animals),
        ),
    )


@bot.tree.command(name="moeda", description="Aposte em cara ou coroa com retorno de 1,9x.")
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
    payout = (
        payout_for_target_rtp(aposta, 1, 2)
        if escolha.value == result
        else 0
    )
    payout = adjust_player_bet_payout(interaction.user.id, aposta, payout)
    settled, balance, _ = settle_house_bet(
        interaction.user.id,
        get_house_BOT_OWNER_ID(),
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
        view=BetAgainView(
            interaction.user.id,
            "moeda",
            aposta,
            escolha.value,
        ),
    )


@bot.tree.command(name="dados", description="Aposte em par, ímpar ou no valor exato de um dado.")
@app_commands.guild_only()
@app_commands.describe(aposta="Quantidade de moedas para apostar.")
@app_commands.choices(
    escolha=[
        app_commands.Choice(name="Par (retorno x1,9)", value="par"),
        app_commands.Choice(name="Ímpar (retorno x1,9)", value="ímpar"),
        *[
            app_commands.Choice(name=f"Número {number} (retorno x5,7)", value=str(number))
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
        payout = payout_for_target_rtp(aposta, 3, 6) if won else 0
    else:
        won = roll == int(escolha.value)
        payout = payout_for_target_rtp(aposta, 1, 6) if won else 0

    payout = adjust_player_bet_payout(interaction.user.id, aposta, payout)
    animation = await asyncio.to_thread(render_dice_gif, roll)
    settled, balance, _ = settle_house_bet(
        interaction.user.id,
        get_house_BOT_OWNER_ID(),
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
        file=discord.File(animation, filename="dados.gif"),
        image_url="attachment://dados.gif",
        view=BetAgainView(
            interaction.user.id,
            "dados",
            aposta,
            escolha.value,
        ),
    )


@bot.tree.command(name="roleta", description="Aposte em uma cor da roleta europeia.")
@app_commands.guild_only()
@app_commands.describe(aposta="Quantidade de moedas para apostar.")
@app_commands.choices(
    cor=[
        app_commands.Choice(name="Vermelho (retorno x1,95)", value="vermelho"),
        app_commands.Choice(name="Preto (retorno x1,95)", value="preto"),
        app_commands.Choice(name="Verde / zero (retorno x35,15)", value="verde"),
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
    winning_outcomes = 1 if cor.value == "verde" else 18
    payout = (
        payout_for_target_rtp(aposta, winning_outcomes, 37)
        if cor.value == result_color
        else 0
    )
    payout = adjust_player_bet_payout(interaction.user.id, aposta, payout)
    animation = await asyncio.to_thread(
        render_roulette_gif,
        number,
        result_color,
    )
    settled, balance, _ = settle_house_bet(
        interaction.user.id,
        get_house_BOT_OWNER_ID(),
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
        file=discord.File(animation, filename="roleta.gif"),
        image_url="attachment://roleta.gif",
        view=BetAgainView(
            interaction.user.id,
            "roleta",
            aposta,
            cor.value,
        ),
    )


@bot.tree.command(
    name="maior_menor",
    description="Adivinhe se a carta será maior ou menor que 7.",
)
@app_commands.guild_only()
@app_commands.describe(
    aposta="Valor da aposta.",
    escolha="Aposte se a carta será maior ou menor que 7.",
)
@app_commands.choices(
    escolha=[
        app_commands.Choice(name="Maior que 7 (retorno x1,89)", value="maior"),
        app_commands.Choice(name="Menor que 7 (retorno x1,89)", value="menor"),
    ]
)
async def maior_menor(
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

    card = random.randint(1, 13)
    if card == 7:
        payout = aposta
        result = "Saiu **7**. Empate: sua aposta foi devolvida."
    else:
        won = (card > 7 and escolha.value == "maior") or (
            card < 7 and escolha.value == "menor"
        )
        payout = (
            payout_for_target_rtp(aposta, 6, 13, push_outcomes=1)
            if won
            else 0
        )
        result = (
            f"Saiu **{card}**; o resultado foi "
            f"**{'maior' if card > 7 else 'menor'} que 7**."
        )
    payout = adjust_player_bet_payout(interaction.user.id, aposta, payout)
    settled, balance, _ = settle_house_bet(
        interaction.user.id,
        get_house_BOT_OWNER_ID(),
        aposta,
        payout,
    )
    if not settled:
        await interaction.response.send_message(
            "A aposta foi cancelada: saldo insuficiente ou banca principal "
            "sem fundos para cobrir esse resultado. "
            f"Seu saldo continua em {format_coins(balance)} moedas.",
            ephemeral=True,
        )
        return

    await send_bet_result(
        interaction,
        game="MAIOR OU MENOR",
        bet=aposta,
        choice=f"Você escolheu **{escolha.name}**.",
        result=result,
        payout=payout,
        balance=balance,
        view=BetAgainView(
            interaction.user.id,
            "maior_menor",
            aposta,
            escolha.value,
        ),
    )


@bot.tree.command(
    name="jokenpo",
    description="Jogue pedra, papel ou tesoura contra a casa.",
)
@app_commands.guild_only()
@app_commands.describe(
    aposta="Valor da aposta.",
    escolha="Escolha pedra, papel ou tesoura.",
)
@app_commands.choices(
    escolha=[
        app_commands.Choice(name="Pedra (retorno x1,85)", value="pedra"),
        app_commands.Choice(name="Papel (retorno x1,85)", value="papel"),
        app_commands.Choice(name="Tesoura (retorno x1,85)", value="tesoura"),
    ]
)
async def jokenpo(
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

    drawn = random.choice(("pedra", "papel", "tesoura"))
    beats = {
        "pedra": "tesoura",
        "papel": "pedra",
        "tesoura": "papel",
    }
    if escolha.value == drawn:
        payout = aposta
        result = (
            f"Empate: ambos escolheram **{drawn}**. "
            "Sua aposta foi devolvida."
        )
    elif beats[escolha.value] == drawn:
        payout = payout_for_target_rtp(aposta, 1, 3, push_outcomes=1)
        result = f"Você venceu: **{escolha.value}** vence **{drawn}**."
    else:
        payout = 0
        result = f"A casa venceu: **{drawn}** vence **{escolha.value}**."

    payout = adjust_player_bet_payout(interaction.user.id, aposta, payout)
    settled, balance, _ = settle_house_bet(
        interaction.user.id,
        get_house_BOT_OWNER_ID(),
        aposta,
        payout,
    )
    if not settled:
        await interaction.response.send_message(
            "A aposta foi cancelada: saldo insuficiente ou banca principal "
            "sem fundos para cobrir esse resultado. "
            f"Seu saldo continua em {format_coins(balance)} moedas.",
            ephemeral=True,
        )
        return

    await send_bet_result(
        interaction,
        game="JOKENPÔ",
        bet=aposta,
        choice=f"Você escolheu **{escolha.name}**.",
        result=result,
        payout=payout,
        balance=balance,
        view=BetAgainView(
            interaction.user.id,
            "jokenpo",
            aposta,
            escolha.value,
        ),
    )


@bot.tree.command(
    name="raspadinha",
    description="Raspe tres simbolos e tente encontrar uma combinacao premiada.",
)
@app_commands.guild_only()
@app_commands.describe(aposta="Quantidade de moedas para apostar.")
async def raspadinha(
    interaction: discord.Interaction,
    aposta: app_commands.Range[int, 1, PLAYER_BET_PARAMETER_MAX],
) -> None:
    if not await ensure_betting_channel(interaction):
        return
    if not await ensure_not_house_owner(interaction):
        return
    if not await ensure_bet_limit(interaction, aposta):
        return

    symbols, payout, combination = play_scratchcard(aposta)
    payout = adjust_player_bet_payout(interaction.user.id, aposta, payout)
    animation = await asyncio.to_thread(
        render_scratchcard_gif,
        symbols,
        payout / aposta,
    )
    settled, balance, _ = settle_house_bet(
        interaction.user.id,
        get_house_BOT_OWNER_ID(),
        aposta,
        payout,
    )
    if not settled:
        await interaction.response.send_message(
            "A aposta foi cancelada: saldo insuficiente ou banca sem fundos. "
            f"Seu saldo continua em {format_coins(balance)} moedas.",
            ephemeral=True,
        )
        return

    await send_bet_result(
        interaction,
        game="RASPADINHA",
        bet=aposta,
        choice="Raspadinha de tres cartoes.",
        result=f"Simbolos revelados: **{' | '.join(symbols)}** - {combination}.",
        payout=payout,
        balance=balance,
        file=discord.File(animation, filename="raspadinha.gif"),
        image_url="attachment://raspadinha.gif",
        view=BetAgainView(interaction.user.id, "raspadinha", aposta, "girar"),
    )


@bot.tree.command(
    name="campo_minado",
    description="Abra de 1 a 5 casas seguras sem encontrar uma mina.",
)
@app_commands.guild_only()
@app_commands.describe(
    aposta="Quantidade de moedas para apostar.",
    casas_para_abrir="Quantas casas voce quer tentar abrir: de 1 a 5.",
)
async def campo_minado(
    interaction: discord.Interaction,
    aposta: app_commands.Range[int, 1, PLAYER_BET_PARAMETER_MAX],
    casas_para_abrir: app_commands.Range[int, 1, 5],
) -> None:
    if not await ensure_betting_channel(interaction):
        return
    if not await ensure_not_house_owner(interaction):
        return
    if not await ensure_bet_limit(interaction, aposta):
        return

    opened_tiles, mine_positions, payout = play_mines(aposta, casas_para_abrir)
    payout = adjust_player_bet_payout(interaction.user.id, aposta, payout)
    animation = await asyncio.to_thread(
        render_mines_gif,
        opened_tiles,
        mine_positions,
        payout / aposta,
    )
    if payout:
        result = f"Voce abriu {casas_para_abrir} casas sem encontrar uma mina."
    else:
        result = f"Uma mina apareceu na tentativa **{len(opened_tiles)}**. A aposta foi perdida."
    settled, balance, _ = settle_house_bet(
        interaction.user.id,
        get_house_BOT_OWNER_ID(),
        aposta,
        payout,
    )
    if not settled:
        await interaction.response.send_message(
            "A aposta foi cancelada: saldo insuficiente ou banca sem fundos. "
            f"Seu saldo continua em {format_coins(balance)} moedas.",
            ephemeral=True,
        )
        return

    await send_bet_result(
        interaction,
        game="CAMPO MINADO",
        bet=aposta,
        choice=f"Tentativas de abertura: **{casas_para_abrir} casas**.",
        result=result,
        payout=payout,
        balance=balance,
        file=discord.File(animation, filename="campo-minado.gif"),
        image_url="attachment://campo-minado.gif",
        view=BetAgainView(
            interaction.user.id,
            "campo_minado",
            aposta,
            str(casas_para_abrir),
        ),
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

    house_BOT_OWNER_ID = get_house_BOT_OWNER_ID()
    reserved, balance, reservation_or_reason, win_streak = reserve_blackjack_bet(
        interaction.user.id,
        house_BOT_OWNER_ID,
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

    player_cards = [draw_blackjack_card(), draw_blackjack_card()]
    dealer_cards = [draw_blackjack_card(), draw_blackjack_card()]
    game = BlackjackView(
        interaction.user,
        aposta,
        player_cards,
        dealer_cards,
        balance,
        house_BOT_OWNER_ID,
        reservation_or_reason,
        win_streak,
    )
    if hand_total(player_cards) == 21:
        game.result = "Blackjack! Sua mão inicial chegou a 21."
        game._resolve()

    await interaction.response.send_message(
        embed=game.create_embed(),
        view=(
            BlackjackAgainView(interaction.user.id, aposta)
            if game.finished
            else game
        ),
    )
    if not game.finished:
        game.message = await interaction.original_response()


async def repeat_blackjack(
    interaction: discord.Interaction,
    bet: int,
) -> None:
    if not await ensure_betting_channel(interaction):
        return
    if not await ensure_not_house_owner(interaction):
        return
    if not await ensure_bet_limit(interaction, bet):
        return

    house_BOT_OWNER_ID = get_house_BOT_OWNER_ID()
    reserved, balance, reservation_or_reason, win_streak = reserve_blackjack_bet(
        interaction.user.id,
        house_BOT_OWNER_ID,
        bet,
    )
    if not reserved:
        message = (
            f"Saldo insuficiente. Você tem {format_coins(balance)} moedas."
            if reservation_or_reason == "player"
            else "A banca principal não tem saldo livre suficiente para cobrir "
            "a aposta máxima desta partida."
        )
        await interaction.response.send_message(message, ephemeral=True)
        return

    game = BlackjackView(
        interaction.user,
        bet,
        [draw_blackjack_card(), draw_blackjack_card()],
        [draw_blackjack_card(), draw_blackjack_card()],
        balance,
        house_BOT_OWNER_ID,
        reservation_or_reason,
        win_streak,
    )
    if hand_total(game.player_cards) == 21:
        game.result = "Blackjack! Sua mão inicial chegou a 21."
        game._resolve()

    await interaction.response.edit_message(
        embed=game.create_embed(),
        view=(
            BlackjackAgainView(interaction.user.id, bet)
            if game.finished
            else game
        ),
    )
    if not game.finished:
        game.message = interaction.message

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


@bot.tree.command(
    name="ajuda",
    description="Mostra os comandos organizados por funcionalidade.",
)
async def ajuda(interaction: discord.Interaction) -> None:
    categories = (
        (
            "💰 Renda e economia",
            {
                "daily", "weekly", "monthly", "saldo", "workshift",
                "mudar_trabalho", "roubar", "feedback",
            },
        ),
        (
            "🎲 Jogos de aposta",
            {
                "moeda", "dados", "roleta", "jogo_do_bixo", "cacaniquel",
                "maior_menor", "jokenpo", "campo_minado", "raspadinha",
                "duelo", "blackjack",
            },
        ),
        (
            "🎰 Cassino do servidor",
            {
                "criar_cassino", "excluir_cassino", "jogar_cassino",
                "solicitar_jogo_cassino", "daily_cassino", "weekly_cassino",
                "saldo_cassino", "status_cassino", "leaderboard_cassino",
                "contratar_npcs_cassino", "upgrade_cassino",
            },
        ),
        (
            "⭐ Prestígio e upgrades",
            {"prestigio", "upgrade_prestigio", "upgrade_casa_principal"},
        ),
        (
            "📊 Status e rankings",
            {
                "status_apostador", "status_casa_principal", "leaderboard",
                "userinfo", "serverinfo",
            },
        ),
        (
            "⚙️ Configuração e moderação",
            {
                "canal_apostas", "configurar_autorole_cassino",
                "configurar_cassinos", "configurar_npcs_principais",
                "resetar_dados_jogadores", "clear", "kick", "ban", "unban",
                "mute", "unmute",
            },
        ),
        (
            "🤖 Utilidades do bot",
            {
                "ajuda", "anunciar_update", "shutdown", "restart", "status",
                "clear_status", "set_activity", "clear_activity",
                "set_status_type", "clear_status_type",
            },
        ),
    )
    commands = {
        command.name: command
        for command in bot.tree.get_commands()
        if isinstance(command, app_commands.Command)
    }
    assigned_names = set().union(*(names for _, names in categories))
    uncategorized = set(commands) - assigned_names
    grouped_commands = [
        (title, names & commands.keys())
        for title, names in categories
    ]
    if uncategorized:
        grouped_commands.append(("📚 Outros comandos", uncategorized))

    embeds: list[discord.Embed] = []
    current_embed = discord.Embed(
        title="Guia de comandos",
        description=(
            "Comandos organizados por funcionalidade. Use `/` e selecione "
            "um comando para ver os parâmetros disponíveis."
        ),
        color=discord.Color.blue(),
    )
    current_characters = len(current_embed.title) + len(current_embed.description)
    for title, names in grouped_commands:
        entries = [
            f"`/{commands[name].name}` — {commands[name].description}"
            for name in sorted(names)
        ]
        chunks: list[str] = []
        current_chunk = ""
        for entry in entries:
            candidate = f"{current_chunk}\n{entry}".strip()
            if current_chunk and len(candidate) > 950:
                chunks.append(current_chunk)
                current_chunk = entry
            else:
                current_chunk = candidate
        if current_chunk:
            chunks.append(current_chunk)
        for chunk_index, chunk in enumerate(chunks):
            field_title = title if chunk_index == 0 else f"{title} (continuação)"
            field_cost = len(field_title) + len(chunk)
            if current_embed.fields and current_characters + field_cost > 5_500:
                embeds.append(current_embed)
                current_embed = discord.Embed(
                    title="Guia de comandos (continuação)",
                    color=discord.Color.blue(),
                )
                current_characters = len(current_embed.title)
            current_embed.add_field(name=field_title, value=chunk, inline=False)
            current_characters += field_cost
    if current_embed.fields or not embeds:
        embeds.append(current_embed)
    await interaction.response.send_message(embeds=embeds, ephemeral=True)


@bot.tree.command(
    name="anunciar_update",
    description="Publica as atualizações do bot e menciona o cargo configurado.",
)
@app_commands.check(is_bot_owner)
async def anunciar_update(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    published = await bot.announce_update(UPDATE_ANNOUNCEMENT_MESSAGE)
    if not published:
        await interaction.followup.send(
            "Não foi possível publicar a atualização. Confira o canal e os logs.",
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


if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("Defina a variável de ambiente DISCORD_BOT_TOKEN antes de iniciar o bot.")
    bot.run(token)
