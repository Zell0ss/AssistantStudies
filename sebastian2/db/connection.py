# db/connection.py
"""
Database connection management with connection pooling.
"""
from utils.logging_config import setup_logging

# Initialize logging
setup_logging()

import pymysql
from dbutils.pooled_db import PooledDB
from loguru import logger
import yaml

_pool = None
_connection = None

def load_config():
    """Load database config from config.yaml"""
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    return config['mariadb']

def init_pool():
    """Initialize connection pool (singleton pattern)"""
    global _pool
    if _pool is None:
        config = load_config()
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=6,
            mincached=2,
            maxcached=5,
            host=config['host'],
            port=config['port'],
            user=config['user'],
            password=config['password'],
            database=config['database'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        logger.info("Database connection pool initialized")
    return _pool

def get_connection():
    """Get a connection from the pool"""
    global _connection
    if _connection is None:
        pool = init_pool()
        _connection = pool.connection()
        logger.debug("Database connection acquired from pool")
    return _connection

def close_connection():
    """Close the current connection"""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
        logger.debug("Database connection closed")
