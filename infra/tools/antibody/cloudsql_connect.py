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
USERNAME = 'antibody-team'


def connect(password, database_name):  # pragma: no cover
  """Connect to Cloud SQL instance google.com:antibody-978:antibody-sql"""
  connection = MySQLdb.connect(host=DB_INSTANCE_IP,
                               user=USERNAME, passwd=password,
                               db=database_name, local_infile=1)
  cc = connection.cursor()
  return connection, cc


def execute_sql_script_from_file(cursor, filename,
                                 database_name):  # pragma: no cover
  with open(filename, 'r') as f:
    sql_file = f.read()

  sql_commands = sql_file.split(';')[:-1]

  for command in sql_commands:
    cursor.execute(command.replace('_DB_NAME', database_name))


# TODO(keelerh): populate people table, data available at
# https://chrome-internal.googlesource.com/infra/infra_internal/+log/master/
# commit_queue/internal/chromium_committers.txt
def write_to_sql_table(cursor, filename, tablename):  # pragma: no cover
  cursor.execute("""LOAD DATA LOCAL INFILE '%s' INTO TABLE %s
    FIELDS TERMINATED BY ','
    LINES TERMINATED BY '\r\n'""" % (filename, tablename))


def commit(conn):  # pragma: no cover
  conn.commit()


def close(conn, cursor):  # pragma: no cover
  cursor.close()
  conn.commit()
  conn.close()