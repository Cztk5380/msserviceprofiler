# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import subprocess
import os
import re
import logging
import sqlite3

COMMAND_SUCCESS = 0


def execute_cmd(cmd):
    logging.info('Execute command:%s' % " ".join(cmd))
    completed_process = subprocess.run(cmd, shell=False, stderr=subprocess.PIPE)
    if completed_process.returncode != COMMAND_SUCCESS:
        logging.error(completed_process.stderr.decode())
    return completed_process.returncode


def execute_script(cmd):
    logging.info('Execute command:%s' % " ".join(cmd))
    process = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while process.poll() is None:
        line = process.stdout.readline().strip()
        if line:
            logging.debug(line)
    return process.returncode


def check_result_file(out_path):
    pass



def select_count(db_path: str, query: str):
    """
    Execute a SQL query to count the number of records in the database.
    """
    conn, cursor = create_connect_db(db_path)
    cursor.execute(query)
    count = cursor.fetchone()
    destroy_db_connect(conn, cursor)
    return count[0]


def select_by_query(db_path: str, query: str, db_class):
    """
    Execute a SQL query and return the first record as an instance of db_class.
    """
    conn, cursor = create_connect_db(db_path)
    cursor.execute(query)
    rows = cursor.fetchall()
    dbs = [db_class(*row) for row in rows]
    destroy_db_connect(conn, cursor)
    return dbs[0]


def create_connect_db(db_file: str) -> tuple:
    """
    Create a connection to the SQLite database.
    """
    try:
        conn = sqlite3.connect(db_file)
        curs = conn.cursor()
        return conn, curs
    except sqlite3.Error as e:
        logging.error("Unable to connect to database: %s", e)
        return None, None


def destroy_db_connect(conn: any, curs: any) -> None:
    """
    Close the database connection and cursor.
    """
    try:
        if isinstance(curs, sqlite3.Cursor):
            curs.close()
    except sqlite3.Error as err:
        logging.error("%s", err)
    try:
        if isinstance(conn, sqlite3.Connection):
            conn.close()
    except sqlite3.Error as err:
        logging.error("%s", err)
