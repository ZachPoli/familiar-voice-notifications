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


class VoiceMappingNotFoundError(ValueError):
    """Base error for missing voice-mapping records."""


class VoiceProfileNotFoundError(VoiceMappingNotFoundError):
    """Raised when a requested voice profile does not exist."""


class SenderAliasNotFoundError(VoiceMappingNotFoundError):
    """Raised when a requested sender alias does not exist."""


class VoiceMappingConflictError(ValueError):
    """Base error for voice-mapping uniqueness conflicts."""


class ProfileKeyConflictError(VoiceMappingConflictError):
    """Raised when a profile key is already in use."""


class SenderAliasConflictError(VoiceMappingConflictError):
    """Raised when a normalized sender alias is already in use."""


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


def _profile_key_exists(
    connection: sqlite3.Connection,
    profile_key: str,
    excluded_profile_id: int | None = None,
) -> bool:
    query = "SELECT 1 FROM voice_profiles WHERE profile_key = ?"
    parameters: tuple[str] | tuple[str, int] = (profile_key,)

    if excluded_profile_id is not None:
        query += " AND id != ?"
        parameters = (profile_key, excluded_profile_id)

    return connection.execute(query, parameters).fetchone() is not None


def _alias_exists(
    connection: sqlite3.Connection,
    normalized_alias: str,
    excluded_alias_id: int | None = None,
) -> bool:
    query = (
        "SELECT 1 FROM sender_aliases WHERE normalized_alias = ?"
    )
    parameters: tuple[str] | tuple[str, int] = (normalized_alias,)

    if excluded_alias_id is not None:
        query += " AND id != ?"
        parameters = (normalized_alias, excluded_alias_id)

    return connection.execute(query, parameters).fetchone() is not None


def _fetch_aliases(
    connection: sqlite3.Connection,
    profile_id: int,
) -> list[dict[str, int | str]]:
    rows = connection.execute(
        """
        SELECT id, normalized_alias
        FROM sender_aliases
        WHERE voice_profile_id = ?
        ORDER BY id
        """,
        (profile_id,),
    ).fetchall()

    return [
        {
            "id": row["id"],
            "normalized_alias": row["normalized_alias"],
        }
        for row in rows
    ]


def _profile_result(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
) -> dict[str, object]:
    return {
        "id": row["id"],
        "profile_key": row["profile_key"],
        "display_name": row["display_name"],
        "voice_id_configured": bool(row["voice_id"]),
        "aliases": _fetch_aliases(connection, row["id"]),
    }


def _fetch_profile_row(
    connection: sqlite3.Connection,
    profile_id: int,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT id, profile_key, display_name, voice_id
        FROM voice_profiles
        WHERE id = ?
        """,
        (profile_id,),
    ).fetchone()

    if row is None:
        raise VoiceProfileNotFoundError("Voice profile not found.")

    return row


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
            if _profile_key_exists(connection, profile_key.strip()):
                raise ProfileKeyConflictError(
                    "A voice profile with that profile key already exists."
                )

            if any(
                _alias_exists(connection, alias)
                for alias in normalized_aliases
            ):
                raise SenderAliasConflictError(
                    "A normalized sender alias already exists."
                )

            try:
                return _insert_voice_profile(
                    connection,
                    profile_key.strip(),
                    display_name.strip(),
                    voice_id.strip(),
                    normalized_aliases,
                )
            except sqlite3.IntegrityError as error:
                if "voice_profiles.profile_key" in str(error):
                    raise ProfileKeyConflictError(
                        "A voice profile with that profile key already exists."
                    ) from error

                raise SenderAliasConflictError(
                    "A normalized sender alias already exists."
                ) from error


def list_voice_profiles(
    database_path: str | Path | None = None,
) -> list[dict[str, object]]:
    """Return all voice profiles and aliases ordered by database ID."""

    with closing(connect_database(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT id, profile_key, display_name, voice_id
            FROM voice_profiles
            ORDER BY id
            """
        ).fetchall()

        return [_profile_result(connection, row) for row in rows]


def get_voice_profile(
    profile_id: int,
    database_path: str | Path | None = None,
) -> dict[str, object]:
    """Return one voice profile and its aliases."""

    with closing(connect_database(database_path)) as connection:
        row = _fetch_profile_row(connection, profile_id)
        return _profile_result(connection, row)


def update_voice_profile(
    profile_id: int,
    *,
    profile_key: str | None = None,
    display_name: str | None = None,
    voice_id: str | None = None,
    database_path: str | Path | None = None,
) -> dict[str, object]:
    """Update supplied fields on one voice profile transactionally."""

    updates: dict[str, str] = {}

    if profile_key is not None:
        cleaned_profile_key = profile_key.strip()
        if not cleaned_profile_key:
            raise ValueError("profile_key cannot be blank.")
        updates["profile_key"] = cleaned_profile_key

    if display_name is not None:
        cleaned_display_name = display_name.strip()
        if not cleaned_display_name:
            raise ValueError("display_name cannot be blank.")
        updates["display_name"] = cleaned_display_name

    if voice_id is not None:
        cleaned_voice_id = voice_id.strip()
        if not cleaned_voice_id:
            raise ValueError("voice_id cannot be blank.")
        updates["voice_id"] = cleaned_voice_id

    if not updates:
        raise ValueError("At least one profile field is required.")

    with closing(connect_database(database_path)) as connection:
        with connection:
            _fetch_profile_row(connection, profile_id)

            if "profile_key" in updates and _profile_key_exists(
                connection,
                updates["profile_key"],
                profile_id,
            ):
                raise ProfileKeyConflictError(
                    "A voice profile with that profile key already exists."
                )

            assignments = [f"{column} = ?" for column in updates]
            assignments.append("updated_at = CURRENT_TIMESTAMP")
            parameters = [*updates.values(), profile_id]

            try:
                connection.execute(
                    f"""
                    UPDATE voice_profiles
                    SET {", ".join(assignments)}
                    WHERE id = ?
                    """,
                    parameters,
                )
            except sqlite3.IntegrityError as error:
                raise ProfileKeyConflictError(
                    "A voice profile with that profile key already exists."
                ) from error

            row = _fetch_profile_row(connection, profile_id)
            return _profile_result(connection, row)


def delete_voice_profile(
    profile_id: int,
    database_path: str | Path | None = None,
) -> None:
    """Delete a voice profile and its aliases through foreign-key cascade."""

    with closing(connect_database(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                "DELETE FROM voice_profiles WHERE id = ?",
                (profile_id,),
            )

            if cursor.rowcount == 0:
                raise VoiceProfileNotFoundError(
                    "Voice profile not found."
                )


def add_sender_alias(
    profile_id: int,
    alias: str,
    database_path: str | Path | None = None,
) -> dict[str, int | str]:
    """Add one normalized alias to an existing voice profile."""

    normalized_alias = normalize_alias(alias)
    if not normalized_alias:
        raise ValueError("Sender alias cannot be blank.")

    with closing(connect_database(database_path)) as connection:
        with connection:
            _fetch_profile_row(connection, profile_id)

            if _alias_exists(connection, normalized_alias):
                raise SenderAliasConflictError(
                    "A normalized sender alias already exists."
                )

            try:
                cursor = connection.execute(
                    """
                    INSERT INTO sender_aliases (
                        voice_profile_id,
                        normalized_alias
                    ) VALUES (?, ?)
                    """,
                    (profile_id, normalized_alias),
                )
            except sqlite3.IntegrityError as error:
                raise SenderAliasConflictError(
                    "A normalized sender alias already exists."
                ) from error

            return {
                "id": cursor.lastrowid,
                "normalized_alias": normalized_alias,
            }


def update_sender_alias(
    alias_id: int,
    alias: str,
    database_path: str | Path | None = None,
) -> dict[str, int | str]:
    """Replace one sender alias with its normalized new value."""

    normalized_alias = normalize_alias(alias)
    if not normalized_alias:
        raise ValueError("Sender alias cannot be blank.")

    with closing(connect_database(database_path)) as connection:
        with connection:
            row = connection.execute(
                """
                SELECT id, normalized_alias
                FROM sender_aliases
                WHERE id = ?
                """,
                (alias_id,),
            ).fetchone()

            if row is None:
                raise SenderAliasNotFoundError(
                    "Sender alias not found."
                )

            if row["normalized_alias"] == normalized_alias:
                return {
                    "id": row["id"],
                    "normalized_alias": row["normalized_alias"],
                }

            if _alias_exists(connection, normalized_alias, alias_id):
                raise SenderAliasConflictError(
                    "A normalized sender alias already exists."
                )

            try:
                connection.execute(
                    """
                    UPDATE sender_aliases
                    SET normalized_alias = ?
                    WHERE id = ?
                    """,
                    (normalized_alias, alias_id),
                )
            except sqlite3.IntegrityError as error:
                raise SenderAliasConflictError(
                    "A normalized sender alias already exists."
                ) from error

            return {
                "id": alias_id,
                "normalized_alias": normalized_alias,
            }


def delete_sender_alias(
    alias_id: int,
    database_path: str | Path | None = None,
) -> None:
    """Delete one sender alias, including a profile's final alias."""

    with closing(connect_database(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                "DELETE FROM sender_aliases WHERE id = ?",
                (alias_id,),
            )

            if cursor.rowcount == 0:
                raise SenderAliasNotFoundError(
                    "Sender alias not found."
                )


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
