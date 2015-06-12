# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sqlite3
import subprocess

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TABLE_NAME = 'commits'


def connect(sql_file):
    connection = sqlite3.connect(sql_file)
    cc = connection.cursor()
    return connection, cc


def close(sql_conn):
    sql_conn.commit()
    sql_conn.close()


def check_name(var):
    if not var.isalnum():
        raise ValueError('Table name can only contain letters and numbers. ' +
                         'Got %s' % var)


# TODO(keelerh): fix security vulnerability in sqlite3 table name
# cannot use the safe (?) format for table names, so if the table name is
# user-inputted it is vulnerable to an attack
def create_table(sql_c, tn):
    check_name(tn)
    sql_c.execute('CREATE TABLE IF NOT EXISTS {} (git_hash text, bug_number\
        text, tbr text, review_url text)'.format(tn))


def write_to_table(sql_c, data, tn):
    check_name(tn)
    sql_c.executemany('INSERT INTO {} VALUES (?,?,?,?)'.format(tn), data)


def read_commit_info(git_commit_fields=('id', 'body'),
                     git_log_format=('%H', '%b')):
    git_log_format = '%x1f'.join(git_log_format) + '%x1e'
    log = subprocess.check_output('git log --format="%s" --after="2011"' %
                                  git_log_format, shell=True)
    log = log.strip('\n\x1e').split("\x1e")
    log = [row.strip().split("\x1f") for row in log]
    log = [dict(zip(git_commit_fields, row)) for row in log]
    return log


def is_commit_suspicious(git_commit):
    if 'Review' and 'URL:' not in git_commit['body']:
        return True
    for line in git_commit['body'].split('\n'):
        if line.startswith('TBR=') and len(line) > 4:
            return True
    return False


def get_features_from_commit(git_commit):
    git_hash = git_commit['id']
    bug_num, TBR, review_URL = None, None, None
    for line in git_commit['body'].split('\n'):
        if line.startswith('BUG=') and len(line) > 4:
            if line[4:56] == 'https://code.google.com/p/chromium/issues/' \
                             'detail?id=':
                bug_num = line[56:]
            elif line[4:55] == 'http://code.google.com/p/chromium/issues/' \
                               'detail?id=':
                bug_num = line[55:]
            elif line[4:21] == 'http://crbug.com/':
                bug_num = line[21:]
            elif line[4:13] == 'chromium:':
                bug_num = line[13:]
            else:
                bug_num = line[4:]
        if line.startswith('TBR=') and len(line) > 4:
            TBR = line[4:]
        if line.startswith('Review URL:') and len(line) > 11:
            review_URL = line[12:]
    return (git_hash, bug_num, TBR, review_URL)


def parse_commit_message(git_log):
    commits = []
    for commit in git_log:
        if is_commit_suspicious(commit):
            commits.append(get_features_from_commit(commit))
    return commits


if __name__ == '__main__':
   
    repository = os.path.join(THIS_DIR, os.pardir, os.pardir, os.pardir)
    sqlite_file = os.path.join(THIS_DIR, 'infra_db.sqlite')
  
    conn, c = connect(sqlite_file)
 
    create_table(c, DEFAULT_TABLE_NAME)
    log_dict = read_commit_info()
    output = parse_commit_message(log_dict)
    write_to_table(c, output, DEFAULT_TABLE_NAME)

    close(conn)