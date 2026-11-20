#!/usr/bin/env python3
"""One-time administrator setup for a new database (not needed after player data migration)."""
import getpass
import hashlib
import os
import uuid

import psycopg


def main():
    if not os.environ.get('DATABASE_URL'):
        raise RuntimeError('DATABASE_URL must be set')
    username = input('Administrator login (4-24 lowercase letters/digits/_): ').strip().lower()
    if not (4 <= len(username) <= 24 and all(c.isascii() and (c.islower() or c.isdigit() or c == '_') for c in username)):
        raise ValueError('Invalid username')
    password = getpass.getpass('Password (at least 8 characters): ')
    if len(password) < 8:
        raise ValueError('Password too short')
    salt, user_id = str(uuid.uuid4()), str(uuid.uuid4())
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100_000).hex()
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users WHERE role='super'")
            if cur.fetchone()[0] != 0:
                raise RuntimeError('A super administrator already exists; refusing to add another one')
            cur.execute('SELECT id FROM users WHERE username=%s', (username,))
            if cur.fetchone():
                raise RuntimeError('Username already exists; refuse to change existing credentials')
            cur.execute("INSERT INTO users(id,username,password_hash,salt,nickname,role,created_at) VALUES(%s,%s,%s,%s,%s,'super',%s)",
                        (user_id, username, digest, salt, '超级管理员', int(__import__('time').time() * 1000)))
            cur.execute("INSERT INTO settings(key,value) VALUES('super_user',%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", (user_id,))
    print('Administrator created. Keep this account and password safe.')


if __name__ == '__main__':
    main()
