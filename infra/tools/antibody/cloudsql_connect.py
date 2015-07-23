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
DEFAULT_DATABASE = 'ANTIBODY_2'
USERNAME = 'antibody-team'


def connect(password):  # pragma: no cover
  """Connect to Cloud SQL instance google.com:antibody-978:antibody-sql"""
  connection = MySQLdb.connect(host=DB_INSTANCE_IP,
                               user=USERNAME, passwd=password,
                               db=DEFAULT_DATABASE)
  cc = connection.cursor()
  return connection, cc


def execute_sql_script_from_file(cursor, filename):  # pragma: no cover
  with open(filename, 'r') as f:
    sql_file = f.read()

  sql_commands = sql_file.split(';')[:-1]

  for command in sql_commands:
    cursor.execute(command)


def write_to_commit_people(cursor, rows):  # pragma: no cover
  """people_email_address|git_commit_hash|request_timestamp|type
     
     VARCHAR(200)|VARCHAR(40)|TIMESTAMP|VARCHAR(10)

  type: author or tbr
  """
  cursor.executemany("""REPLACE INTO commit_people VALUES (%s,%s,%s,%s)""",
                     rows)


def write_to_git_commit(cursor, rows):  # pragma: no cover
  """hash|bug_url|timestamp|review_url|project_prj_id|subject
     
     VARCHAR(40)|VARCHAR(200)|TIMESTAMP|VARCHAR(200)|INT|VARCHAR(500)
  """
  cursor.executemany("""REPLACE INTO git_commit VALUES (%s,%s,%s,%s,%s,%s)""",
                     rows)


def write_to_people(cursor, rows):  # pragma: no cover
  """email_address|committer_since
     
     VARCHAR(200)|TIMESTAMP
  """
  cursor.execute("""REPLACE INTO people VALUES (%s,%s)""", rows)


def write_to_project(cursor, rows):  # pragma: no cover
  """prj_id|prj_name|prj_repository
     
     INT|VARCHAR(45)|VARCHAR(250)
  """
  cursor.execute("""REPLACE INTO project VALUES (%s,%s,%s)""", rows)


def write_to_review_people(cursor, rows):  # pragma: no cover
  """people_email_address|review_url|timestamp|request_timestamp|type
     
     VARCHAR(200)|VARCHAR(200)|TIMESTAMP|TIMESTAMP|VARCHAR(10)

  type: author, reviewer, cc, lgtm, or not lgtm
  """
  cursor.executemany("""REPLACE INTO review_people VALUES (%s,%s,%s,%s,%s)""",
                     rows)


def write_to_review(cursor, rows):  # pragma: no cover
  """review_url|request_timestamp|patchset_committed|patchset_still_exists|
     reverted|project_prj_id
     
     VARCHAR(200)|TIMESTAMP|TIMESTAMP|TINYINT|TINYINT|INT
  """
  cursor.execute("""REPLACE INTO review VALUES (%s,%s,%s,%s,%s,%s)""", rows)


def commit(conn):  # pragma: no cover
  conn.commit()


def close(conn, cursor):  # pragma: no cover
  cursor.close()
  conn.commit()
  conn.close()