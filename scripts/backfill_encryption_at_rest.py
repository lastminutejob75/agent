#!/usr/bin/env python3
"""
Backfill : chiffre les notes patients et transcripts d'appels existants en clair.

Usage (Railway prod) :
    railway run --service agent python scripts/backfill_encryption_at_rest.py [--dry-run]

Prérequis :
- `DATA_ENCRYPTION_KEY` défini (génération : `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`)
- Accès lecture/écriture à `DATABASE_URL` (et/ou `PG_EVENTS_URL` si distinct)

Ce script est idempotent : il ignore les lignes déjà chiffrées (préfixe `enc:v1:`).
Il avance par lots pour ne pas saturer la base. Sécurisé contre les coupures
(chaque batch est commité indépendamment).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import Iterable, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_enc")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _get_pg_url() -> str:
    return (
        os.environ.get("PG_EVENTS_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()


def _iter_unencrypted(cur, table: str, key_col: str, val_col: str, batch_size: int) -> Iterable[List[Tuple]]:
    """
    Renvoie des lots [(id, value), ...] de lignes encore en clair.
    On re-requête à chaque itération (curseur stable), avec WHERE val NOT LIKE 'enc:%'.
    """
    while True:
        cur.execute(
            f"SELECT {key_col}, {val_col} FROM {table} "
            f"WHERE {val_col} IS NOT NULL AND {val_col} <> '' AND {val_col} NOT LIKE 'enc:%' "
            f"ORDER BY {key_col} ASC LIMIT %s",
            (batch_size,),
        )
        rows = cur.fetchall()
        if not rows:
            return
        yield rows


def _encrypt_batch(rows: List[Tuple]) -> List[Tuple]:
    from backend.crypto_at_rest import encrypt_str, is_encryption_enabled

    if not is_encryption_enabled():
        raise RuntimeError(
            "DATA_ENCRYPTION_KEY absente : impossible de chiffrer. "
            "Générer une clé avec: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    return [(pk, encrypt_str(val)) for (pk, val) in rows]


def backfill_table(
    pg_url: str,
    table: str,
    key_col: str,
    val_col: str,
    *,
    batch_size: int = 500,
    dry_run: bool = False,
) -> int:
    import psycopg

    total = 0
    started = time.time()
    with psycopg.connect(pg_url) as conn:
        with conn.cursor() as cur:
            for batch in _iter_unencrypted(cur, table, key_col, val_col, batch_size):
                encrypted = _encrypt_batch(batch)
                if dry_run:
                    total += len(encrypted)
                    logger.info("dry-run %s: %s lignes prêtes (total: %s)", table, len(encrypted), total)
                    continue
                with conn.cursor() as wcur:
                    wcur.executemany(
                        f"UPDATE {table} SET {val_col} = %s WHERE {key_col} = %s",
                        [(enc_val, pk) for (pk, enc_val) in encrypted],
                    )
                conn.commit()
                total += len(encrypted)
                logger.info("%s: batch %s → total %s", table, len(encrypted), total)
            if dry_run:
                logger.info("(dry-run : aucun UPDATE exécuté)")
    elapsed = time.time() - started
    logger.info("Backfill %s.%s : %s lignes en %.1fs", table, val_col, total, elapsed)
    return total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Ne rien modifier, juste compter.")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--only",
        choices=("notes", "transcripts", "all"),
        default="all",
        help="Limiter au type ciblé",
    )
    args = parser.parse_args()

    pg_url = _get_pg_url()
    if not pg_url:
        logger.error("PG_EVENTS_URL / DATABASE_URL absent. Aborting.")
        sys.exit(2)

    from backend.crypto_at_rest import is_encryption_enabled

    if not is_encryption_enabled():
        logger.error("DATA_ENCRYPTION_KEY absente : impossible de chiffrer.")
        sys.exit(3)

    tasks = []
    if args.only in ("notes", "all"):
        tasks.append(("patient_notes", "id", "note_text"))
    if args.only in ("transcripts", "all"):
        tasks.append(("call_transcripts", "id", "transcript"))

    grand_total = 0
    for table, key_col, val_col in tasks:
        try:
            n = backfill_table(
                pg_url,
                table,
                key_col,
                val_col,
                batch_size=args.batch_size,
                dry_run=args.dry_run,
            )
            grand_total += n
        except Exception as e:
            logger.error("Backfill %s échoué : %s", table, e)
    logger.info("DONE — %s lignes chiffrées au total (dry_run=%s)", grand_total, args.dry_run)


if __name__ == "__main__":
    main()
