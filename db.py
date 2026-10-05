"""
Database Management Module for Job Recruitment & ATS.
Uses psycopg2 with RealDictCursor for robust relational querying,
transaction management, and execution of triggers, views, and stored procedures.
"""

import os
import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from config import Config

# Global connection pool instance
_connection_pool = None


def get_pool():
    """Initializes or returns the psycopg2 ThreadedConnectionPool."""
    global _connection_pool
    if _connection_pool is None or _connection_pool.closed:
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            dbname=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            cursor_factory=RealDictCursor
        )
    return _connection_pool


@contextmanager
def get_db_cursor(commit=False):
    """
    Context manager yielding a psycopg2 RealDictCursor from the pool.
    Automatically commits if commit=True and no exception occurs.
    Rolls back on exception and releases connection back to the pool.
    """
    p = get_pool()
    conn = p.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)


def query_all(query_str, params=None):
    """Executes a SELECT query and returns all matching rows as dictionaries."""
    with get_db_cursor(commit=False) as cur:
        cur.execute(query_str, params or ())
        return cur.fetchall()


def query_one(query_str, params=None):
    """Executes a SELECT query and returns a single row as a dictionary or None."""
    with get_db_cursor(commit=False) as cur:
        cur.execute(query_str, params or ())
        return cur.fetchone()


def execute_dml(query_str, params=None, returning_col=None):
    """
    Executes an INSERT, UPDATE, or DELETE query.
    If returning_col is specified, fetches and returns that column value (e.g. 'job_id').
    Otherwise returns rowcount.
    """
    with get_db_cursor(commit=True) as cur:
        cur.execute(query_str, params or ())
        if returning_col:
            result = cur.fetchone()
            return result[returning_col] if result else None
        return cur.rowcount


def call_procedure(proc_name, params):
    """Executes a PostgreSQL Stored Procedure using the CALL statement."""
    placeholders = ", ".join(["%s"] * len(params))
    query_str = f"CALL {proc_name}({placeholders});"
    with get_db_cursor(commit=True) as cur:
        cur.execute(query_str, params)


def ensure_database_exists():
    """
    Checks if the target database (ats_db) exists.
    If not, connects to default 'postgres' database and creates it.
    """
    try:
        # Test connection to target db
        conn = psycopg2.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            dbname=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        conn.close()
        return True
    except psycopg2.OperationalError:
        # Connect to template/default postgres db to create target db
        try:
            admin_conn = psycopg2.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                dbname='postgres',
                user=Config.DB_USER,
                password=Config.DB_PASSWORD
            )
            admin_conn.autocommit = True
            with admin_conn.cursor() as cur:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(Config.DB_NAME)))
            admin_conn.close()
            print(f"Database '{Config.DB_NAME}' created successfully.")
            return True
        except Exception as e:
            print(f"Notice: Could not automatically create database '{Config.DB_NAME}': {e}")
            return False


def execute_sql_file(file_path):
    """Reads and executes a complete SQL script file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"SQL file not found at: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        sql_script = f.read()

    # Use raw connection for multi-statement DDL/DML script execution
    conn = psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql_script)
    finally:
        conn.close()


def init_db():
    """Executes schema.sql to construct tables, triggers, views, and procedures."""
    ensure_database_exists()
    schema_path = os.path.join(Config.BASE_DIR, 'sql', 'schema.sql')
    execute_sql_file(schema_path)
    print("Database schema successfully applied.")


def seed_db():
    """Executes seed.sql to populate initial sample records."""
    seed_path = os.path.join(Config.BASE_DIR, 'sql', 'seed.sql')
    execute_sql_file(seed_path)
    print("Database seed data successfully inserted.")
