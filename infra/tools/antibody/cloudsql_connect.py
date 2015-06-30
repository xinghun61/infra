# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

try:
  sys.path.append('/usr/lib/python2.7/dist-packages/')
  import MySQLdb
except ImportError:  # pragma: no cover
  pass
finally:
  sys.path.remove('/usr/lib/python2.7/dist-packages/')

DB_INSTANCE_IP = '173.194.225.193'
DEFAULT_DATABASE = 'ANTIBODY_DB'
USERNAME = 'antibody-team'

DEFAULT_GIT_TABLE = 'git'
DEFAULT_RIETVELD_TABLE = 'rietveld'


def connect(password):  # pragma: no cover
  """Connect to Cloud SQL instance google.com:antibody-978:antibody-sql"""
  connection = MySQLdb.connect(host=DB_INSTANCE_IP,
                               user=USERNAME, passwd=password,
                               db=DEFAULT_DATABASE)
  cc = connection.cursor()
  return connection, cc


def create_tables(cursor):  # pragma: no cover
  cursor.execute('CREATE TABLE IF NOT EXISTS %s (git_hash varchar(255) '
                 'PRIMARY KEY, bug_number text, tbr text, review_url text)'
                 % DEFAULT_GIT_TABLE)
  cursor.execute('CREATE TABLE IF NOT EXISTS %s (git_hash varchar(255) '
                 'PRIMARY KEY, lgtm text, tbr text, review_url text, '
                 'request_timestamp int, num_cced int)' 
                 % DEFAULT_RIETVELD_TABLE)


def write_to_git_table(cursor, rows):  # pragma: no cover
  cursor.executemany("""REPLACE INTO git VALUES (%s,%s,%s,%s)""", rows)


def write_to_rietveld_table(cursor, rows):  # pragma: no cover
  cursor.execute("""REPLACE INTO rietveld VALUES (%s,%s,%s,%s,%s,%s)""", rows)


def close(conn, cursor):  # pragma: no cover
  cursor.close()
  conn.commit()
  conn.close()