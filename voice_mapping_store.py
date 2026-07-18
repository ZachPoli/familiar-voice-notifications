import os
import sqlite3
from contextlib import closing
from pathlib import Path


BACKEND_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = Path("data/voice_mappings.sqlite3")
BOOTSTRAP_METADATA_KEY = "environment_bootstrap_v1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS voice_profiles (
    id INTEGER PRIMARY KEY,
    profile_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    voice_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sender_aliases (
    id INTEGER PRIMARY KEY,
    voice_profile_id INTEGER NOT NULL,
    normalized_alias TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (voice_profile_id)
        REFERENCES voice_profiles(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS storage_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

ENVIRONMENT_PROFILES = (
    (
        "zach",
        "Zach",
        "ZACH_VOICE_ID",
        "ZACH_SENDER_ALIASES",
    ),
    (
        "emily",
        "Emily",
        "EMILY_VOICE_ID",
        "EMILY_SENDER_ALIASES",
    ),
)


def normalize_alias(value: str) -> str:
    """Normalize an alias for exact storage and matching."""

    return " ".join(value.strip().casefold().split())


def resolve_database_path(
    database_path: str | Path | None = None,
) -> Path:
    """Resolve the configured database path from the backend directory."""

    configured_path = database_path

    if configured_path is None:
        configured_path = os.getenv(
            "VOICE_MAPPINGS_DB_PATH",
            str(DEFAULT_DATABASE_PATH),
        )

    path = Path(configured_path).expanduser()

    if not path.is_absolute():
        path = BACKEND_DIRECTORY / path

    return path.resolve()


def connect_database(
    database_path: str | Path | None = None,
) -> sqlite3.Connection:
    """Open a SQLite connection with foreign-key enforcement enabled."""

    connection = sqlite3.connect(
        resolve_database_path(database_path),
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _parse_aliases(value: str) -> list[str]:
    aliases = {
        normalized
        for alias in value.split(",")
        if (normalized := normalize_alias(alias))
    }
    return sorted(aliases)


def _insert_voice_profile(
    connection: sqlite3.Connection,
    profile_key: str,
    display_name: str,
    voice_id: str,
    aliases: list[str],
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO voice_profiles (
            profile_key,
            display_name,
            voice_id
        ) VALUES (?, ?, ?)
        """,
        (profile_key, display_name, voice_id),
    )
    profile_id = cursor.lastrowid

    connection.executemany(
        """
        INSERT INTO sender_aliases (
            voice_profile_id,
            normalized_alias
        ) VALUES (?, ?)
        """,
        ((profile_id, alias) for alias in aliases),
    )

    return profile_id


def add_voice_profile(
    profile_key: str,
    display_name: str,
    voice_id: str,
    aliases: list[str],
    database_path: str | Path | None = None,
) -> int:
    """Add one voice profile and its aliases in a transaction."""

    normalized_aliases = sorted(
        {
            normalized
            for alias in aliases
            if (normalized := normalize_alias(alias))
        }
    )

    if not profile_key.strip():
        raise ValueError("profile_key cannot be blank.")
    if not display_name.strip():
        raise ValueError("display_name cannot be blank.")
    if not voice_id.strip():
        raise ValueError("voice_id cannot be blank.")
    if not normalized_aliases:
        raise ValueError("At least one sender alias is required.")

    with closing(connect_database(database_path)) as connection:
        with connection:
            try:
                return _insert_voice_profile(
                    connection,
                    profile_key.strip(),
                    display_name.strip(),
                    voice_id.strip(),
                    normalized_aliases,
                )
            except sqlite3.IntegrityError as error:
                raise ValueError(
                    "The profile key or a normalized sender alias already exists."
                ) from error


def _bootstrap_environment_mappings(
    connection: sqlite3.Connection,
) -> None:
    marker = connection.execute(
        "SELECT value FROM storage_metadata WHERE key = ?",
        (BOOTSTRAP_METADATA_KEY,),
    ).fetchone()

    if marker is not None:
        return

    has_user_data = connection.execute(
        """
        SELECT
            EXISTS(SELECT 1 FROM voice_profiles)
            OR EXISTS(SELECT 1 FROM sender_aliases)
        """
    ).fetchone()[0]

    if not has_user_data:
        try:
            for (
                profile_key,
                display_name,
                voice_id_variable,
                aliases_variable,
            ) in ENVIRONMENT_PROFILES:
                voice_id = os.getenv(voice_id_variable, "").strip()
                aliases = _parse_aliases(
                    os.getenv(aliases_variable, ""),
                )

                if not voice_id or not aliases:
                    continue

                _insert_voice_profile(
                    connection,
                    profile_key,
                    display_name,
                    voice_id,
                    aliases,
                )
        except sqlite3.IntegrityError as error:
            raise ValueError(
                "Environment bootstrap contains conflicting sender aliases."
            ) from error

    connection.execute(
        """
        INSERT INTO storage_metadata (key, value)
        VALUES (?, ?)
        """,
        (BOOTSTRAP_METADATA_KEY, "complete"),
    )


def initialize_database(
    database_path: str | Path | None = None,
) -> Path:
    """Create the database schema and handle one-time environment seeding."""

    path = resolve_database_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = connect_database(path)
    try:
        connection.executescript(SCHEMA)
        connection.commit()

        with connection:
            _bootstrap_environment_mappings(connection)
    finally:
        connection.close()

    return path


def find_voice_id_for_sender(
    sender: str,
    database_path: str | Path | None = None,
) -> str | None:
    """Return the mapped voice ID for a sender, if one exists."""

    normalized_sender = normalize_alias(sender)

    if not normalized_sender:
        return None

    with closing(connect_database(database_path)) as connection:
        row = connection.execute(
            """
            SELECT voice_profiles.voice_id
            FROM sender_aliases
            JOIN voice_profiles
                ON voice_profiles.id = sender_aliases.voice_profile_id
            WHERE sender_aliases.normalized_alias = ?
            """,
            (normalized_sender,),
        ).fetchone()

    if row is None:
        return None

    return row["voice_id"]
