# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A set of classes for interacting with tables in SQL."""

import logging
import random
import re
import sys
import time

import settings

if not settings.unit_test_mode:
  import MySQLdb

from framework import framework_helpers

from infra_libs import ts_mon

# MonorailConnection maintains a dictionary of connections to SQL databases.
# Each is identified by an int shard ID.
# And there is one connection to the master DB identified by key MASTER_CNXN.
MASTER_CNXN = 'master_cnxn'

CONNECTION_COUNT = ts_mon.CounterMetric(
    'monorail/sql/connection_count',
    'Count of connections made to the SQL database.',
    [ts_mon.BooleanField('success')])


@framework_helpers.retry(2, delay=1, backoff=2)
def MakeConnection(instance, database):
  logging.info('About to connect to SQL instance %r db %r', instance, database)
  if settings.unit_test_mode:
    raise ValueError('unit tests should not need real database connections')
  try:
    if settings.dev_mode:
      cnxn = MySQLdb.connect(
        host='127.0.0.1', port=3306, db=database, user='root', charset='utf8')
    else:
      cnxn = MySQLdb.connect(
        unix_socket='/cloudsql/' + instance, db=database, user='root',
        charset='utf8')
    CONNECTION_COUNT.increment({'success': True})
  except MySQLdb.OperationalError:
    CONNECTION_COUNT.increment({'success': False})
    raise
  return cnxn


class MonorailConnection(object):
  """Create and manage connections to the SQL servers.

  We only store connections in the context of a single user request, not
  across user requests.  The main purpose of this class is to make using
  sharded tables easier.
  """

  def __init__(self):
    self.sql_cnxns = {}   # {MASTER_CNXN: cnxn, shard_id: cnxn, ...}

  def GetMasterConnection(self):
    """Return a connection to the master SQL DB."""
    if MASTER_CNXN not in self.sql_cnxns:
      self.sql_cnxns[MASTER_CNXN] = MakeConnection(
          settings.db_instance, settings.db_database_name)
      logging.info(
          'created a master connection %r', self.sql_cnxns[MASTER_CNXN])

    return self.sql_cnxns[MASTER_CNXN]

  def GetConnectionForShard(self, shard_id):
    """Return a connection to the DB replica that will be used for shard_id."""
    if settings.dev_mode:
      return self.GetMasterConnection()

    if shard_id not in self.sql_cnxns:
      physical_shard_id = shard_id % settings.num_logical_shards
      shard_instance_name = (
          settings.physical_db_name_format % physical_shard_id)
      self.sql_cnxns[shard_id] = MakeConnection(
          shard_instance_name, settings.db_database_name)
      logging.info('created a replica connection for shard %d', shard_id)

    return self.sql_cnxns[shard_id]

  def Execute(self, stmt_str, stmt_args, shard_id=None, commit=True):
    """Execute the given SQL statement on one of the relevant databases."""
    if shard_id is None:
      # No shard was specified, so hit the master.
      sql_cnxn = self.GetMasterConnection()
    else:
      sql_cnxn = self.GetConnectionForShard(shard_id)

    return self._ExecuteWithSQLConnection(
      sql_cnxn, stmt_str, stmt_args, commit=commit)

  def _ExecuteWithSQLConnection(
      self, sql_cnxn, stmt_str, stmt_args, commit=True):
    """Execute a statement on the given database and return a cursor."""
    cursor = sql_cnxn.cursor()
    cursor.execute('SET NAMES utf8mb4')
    start_time = time.time()
    if stmt_str.startswith('INSERT') or stmt_str.startswith('REPLACE'):
      logging.info('SQL stmt_str: \n%s', stmt_str)
      logging.info('SQL stmt_args: %r', stmt_args)
      cursor.executemany(stmt_str, stmt_args)
    else:
      logging.info('SQL stmt: \n%s', (stmt_str % tuple(stmt_args)))
      cursor.execute(stmt_str, args=stmt_args)
    logging.info('%d rows in %d ms', cursor.rowcount,
                 int((time.time() - start_time) * 1000))
    if commit and not stmt_str.startswith('SELECT'):
      start_time = time.time()
      try:
        sql_cnxn.commit()
      except MySQLdb.DatabaseError:
        sql_cnxn.rollback()
      logging.info('commit took %d ms',
                   int((time.time() - start_time) * 1000))

    return cursor

  def Commit(self):
    """Explicitly commit any pending txns.  Normally done automatically."""
    sql_cnxn = self.GetMasterConnection()
    start_time = time.time()
    try:
      sql_cnxn.commit()
    except MySQLdb.DatabaseError:
      logging.exception('Commit failed for cnxn, rolling back')
      sql_cnxn.rollback()
    logging.info('final commit took %d ms',
                 int((time.time() - start_time) * 1000))

  def Close(self):
    """Safely close any connections that are still open."""
    for sql_cnxn in self.sql_cnxns.itervalues():
      try:
        sql_cnxn.close()
      except MySQLdb.DatabaseError:
        # This might happen if the cnxn is somehow already closed.
        logging.exception('ProgrammingError when trying to close cnxn')


class SQLTableManager(object):
  """Helper class to make it easier to deal with an SQL table."""

  def __init__(self, table_name):
    self.table_name = table_name

  def Select(
      self, cnxn, distinct=False, cols=None, left_joins=None,
      joins=None, where=None, or_where_conds=False, group_by=None,
      order_by=None, limit=None, offset=None, shard_id=None, use_clause=None,
      having=None, **kwargs):
    """Compose and execute an SQL SELECT statement on this table.

    Args:
      cnxn: MonorailConnection to the databases.
      distinct: If True, add DISTINCT keyword.
      cols: List of columns to retrieve, defaults to '*'.
      left_joins: List of LEFT JOIN (str, args) pairs.
      joins: List of regular JOIN (str, args) pairs.
      where: List of (str, args) for WHERE clause.
      or_where_conds: Set to True to use OR in the WHERE conds.
      group_by: List of strings for GROUP BY clause.
      order_by: List of (str, args) for ORDER BY clause.
      limit: Optional LIMIT on the number of rows returned.
      offset: Optional OFFSET when using LIMIT.
      shard_id: Int ID of the shard to query.
      use_clause: Optional string USE clause to tell the DB which index to use.
      having: List of (str, args) for Optional HAVING clause
      **kwargs: WHERE-clause equality and set-membership conditions.

    Keyword args are used to build up more WHERE conditions that compare
    column values to constants.  Key word Argument foo='bar' translates to 'foo
    = "bar"', and foo=[3, 4, 5] translates to 'foo IN (3, 4, 5)'.

    Returns:
      A list of rows, each row is a tuple of values for the requested cols.
    """
    cols = cols or ['*']  # If columns not specified, retrieve all columns.
    stmt = Statement.MakeSelect(
        self.table_name, cols, distinct=distinct,
        or_where_conds=or_where_conds)
    if use_clause:
      stmt.AddUseClause(use_clause)
    if having:
      stmt.AddHavingTerms(having)
    stmt.AddJoinClauses(left_joins or [], left=True)
    stmt.AddJoinClauses(joins or [])
    stmt.AddWhereTerms(where or [], **kwargs)
    stmt.AddGroupByTerms(group_by or [])
    stmt.AddOrderByTerms(order_by or [])
    stmt.SetLimitAndOffset(limit, offset)
    stmt_str, stmt_args = stmt.Generate()

    cursor = cnxn.Execute(stmt_str, stmt_args, shard_id=shard_id)
    rows = cursor.fetchall()
    return rows

  def SelectRow(
      self, cnxn, cols=None, default=None, where=None, **kwargs):
    """Run a query that is expected to return just one row."""
    rows = self.Select(cnxn, distinct=True, cols=cols, where=where, **kwargs)
    if len(rows) == 1:
      return rows[0]
    elif not rows:
      logging.info('SelectRow got 0 results, so using default %r', default)
      return default
    else:
      raise ValueError('SelectRow got %d results, expected only 1', len(rows))

  def SelectValue(self, cnxn, col, default=None, where=None, **kwargs):
    """Run a query that is expected to return just one row w/ one value."""
    row = self.SelectRow(
        cnxn, cols=[col], default=[default], where=where, **kwargs)
    return row[0]

  def InsertRows(
      self, cnxn, cols, row_values, replace=False, ignore=False,
      commit=True, return_generated_ids=False):
    """Insert all the given rows.

    Args:
      cnxn: MonorailConnection object.
      cols: List of column names to set.
      row_values: List of lists with values to store.  The length of each
          nested list should be equal to len(cols).
      replace: Set to True if inserted values should replace existing DB rows
          that have the same DB keys.
      ignore: Set to True to ignore rows that would duplicate existing DB keys.
      commit: Set to False if this operation is part of a series of operations
          that should not be committed until the final one is done.
      return_generated_ids: Set to True to return a list of generated
          autoincrement IDs for inserted rows.  This requires us to insert rows
          one at a time.

    Returns:
      If return_generated_ids is set to True, this method returns a list of the
      auto-increment IDs generated by the DB.  Otherwise, [] is returned.
    """
    if not row_values:
      return None  # Nothing to insert

    generated_ids = []
    if return_generated_ids:
      # We must insert the rows one-at-a-time to know the generated IDs.
      for row_value in row_values:
        stmt = Statement.MakeInsert(
            self.table_name, cols, [row_value], replace=replace, ignore=ignore)
        stmt_str, stmt_args = stmt.Generate()
        cursor = cnxn.Execute(stmt_str, stmt_args, commit=commit)
        if cursor.lastrowid:
          generated_ids.append(cursor.lastrowid)
      return generated_ids

    stmt = Statement.MakeInsert(
      self.table_name, cols, row_values, replace=replace, ignore=ignore)
    stmt_str, stmt_args = stmt.Generate()
    cnxn.Execute(stmt_str, stmt_args, commit=commit)
    return []


  def InsertRow(
      self, cnxn, replace=False, ignore=False, commit=True, **kwargs):
    """Insert a single row into the table.

    Args:
      cnxn: MonorailConnection object.
      replace: Set to True if inserted values should replace existing DB rows
          that have the same DB keys.
      ignore: Set to True to ignore rows that would duplicate existing DB keys.
      commit: Set to False if this operation is part of a series of operations
          that should not be committed until the final one is done.
      **kwargs: column=value assignments to specify what to store in the DB.

    Returns:
      The generated autoincrement ID of the key column if one was generated.
      Otherwise, return None.
    """
    cols = sorted(kwargs.keys())
    row = tuple(kwargs[col] for col in cols)
    generated_ids = self.InsertRows(
        cnxn, cols, [row], replace=replace, ignore=ignore,
        commit=commit, return_generated_ids=True)
    if generated_ids:
      return generated_ids[0]
    else:
      return None

  def Update(self, cnxn, delta, where=None, commit=True, **kwargs):
    """Update one or more rows.

    Args:
      cnxn: MonorailConnection object.
      delta: Dictionary of {column: new_value} assignments.
      where: Optional list of WHERE conditions saying which rows to update.
      commit: Set to False if this operation is part of a series of operations
          that should not be committed until the final one is done.
      **kwargs: WHERE-clause equality and set-membership conditions.

    Returns:
      Int number of rows updated.
    """
    if not delta:
      return 0   # Nothing is being changed

    stmt = Statement.MakeUpdate(self.table_name, delta)
    stmt.AddWhereTerms(where, **kwargs)
    stmt_str, stmt_args = stmt.Generate()

    cursor = cnxn.Execute(stmt_str, stmt_args, commit=commit)
    return cursor.rowcount

  def IncrementCounterValue(self, cnxn, col_name, where=None, **kwargs):
    """Atomically increment a counter stored in MySQL, return new value.

    Args:
      cnxn: MonorailConnection object.
      col_name: int column to increment.
      where: Optional list of WHERE conditions saying which rows to update.
      **kwargs: WHERE-clause equality and set-membership conditions.  The
          where and kwargs together should narrow the update down to exactly
          one row.

    Returns:
      The new, post-increment value of the counter.
    """
    stmt = Statement.MakeIncrement(self.table_name, col_name)
    stmt.AddWhereTerms(where, **kwargs)
    stmt_str, stmt_args = stmt.Generate()

    cursor = cnxn.Execute(stmt_str, stmt_args)
    assert cursor.rowcount == 1, (
        'missing or ambiguous counter: %r' % cursor.rowcount)
    return cursor.lastrowid

  def Delete(self, cnxn, where=None, commit=True, **kwargs):
    """Delete the specified table rows.

    Args:
      cnxn: MonorailConnection object.
      where: Optional list of WHERE conditions saying which rows to update.
      commit: Set to False if this operation is part of a series of operations
          that should not be committed until the final one is done.
      **kwargs: WHERE-clause equality and set-membership conditions.

    Returns:
      Int number of rows updated.
    """
    # Deleting the whole table is never intended in Monorail.
    assert where or kwargs

    stmt = Statement.MakeDelete(self.table_name)
    stmt.AddWhereTerms(where, **kwargs)
    stmt_str, stmt_args = stmt.Generate()

    cursor = cnxn.Execute(stmt_str, stmt_args, commit=commit)
    return cursor.rowcount


class Statement(object):
  """A class to help build complex SQL statements w/ full escaping.

  Start with a Make*() method, then fill in additional clauses as needed,
  then call Generate() to return the SQL string and argument list.  We pass
  the string and args to MySQLdb separately so that it can do escaping on
  the arg values as appropriate to prevent SQL-injection attacks.

  The only values that are not escaped by MySQLdb are the table names
  and column names, and bits of SQL syntax, all of which is hard-coded
  in our application.
  """

  @classmethod
  def MakeSelect(cls, table_name, cols, distinct=False, or_where_conds=False):
    """Constuct a SELECT statement."""
    assert _IsValidTableName(table_name)
    assert all(_IsValidColumnName(col) for col in cols)
    main_clause = 'SELECT%s %s FROM %s' % (
        (' DISTINCT' if distinct else ''), ', '.join(cols), table_name)
    return cls(main_clause, or_where_conds=or_where_conds)

  @classmethod
  def MakeInsert(
      cls, table_name, cols, new_values, replace=False, ignore=False):
    """Constuct an INSERT statement."""
    if replace == True:
      return cls.MakeReplace(table_name, cols, new_values, ignore)
    assert _IsValidTableName(table_name)
    assert all(_IsValidColumnName(col) for col in cols)
    ignore_word = ' IGNORE' if ignore else ''
    main_clause = 'INSERT%s INTO %s (%s)' % (
        ignore_word, table_name, ', '.join(cols))
    return cls(main_clause, insert_args=new_values)

  @classmethod
  def MakeReplace(
      cls, table_name, cols, new_values, ignore=False):
    """Construct an INSERT...ON DUPLICATE KEY UPDATE... statement.

    Uses the INSERT/UPDATE syntax because REPLACE is literally a DELETE
    followed by an INSERT, which doesn't play well with foreign keys.
    INSERT/UPDATE is an atomic check of whether the primary key exists,
    followed by an INSERT if it doesn't or an UPDATE if it does.
    """
    assert _IsValidTableName(table_name)
    assert all(_IsValidColumnName(col) for col in cols)
    ignore_word = ' IGNORE' if ignore else ''
    main_clause = 'INSERT%s INTO %s (%s)' % (
        ignore_word, table_name, ', '.join(cols))
    return cls(main_clause, insert_args=new_values, duplicate_update_cols=cols)

  @classmethod
  def MakeUpdate(cls, table_name, delta):
    """Constuct an UPDATE statement."""
    assert _IsValidTableName(table_name)
    assert all(_IsValidColumnName(col) for col in delta.iterkeys())
    update_strs = []
    update_args = []
    for col, val in delta.iteritems():
      update_strs.append(col + '=%s')
      update_args.append(val)

    main_clause = 'UPDATE %s SET %s' % (
        table_name, ', '.join(update_strs))
    return cls(main_clause, update_args=update_args)

  @classmethod
  def MakeIncrement(cls, table_name, col_name, step=1):
    """Constuct an UPDATE statement that increments and returns a counter."""
    assert _IsValidTableName(table_name)
    assert _IsValidColumnName(col_name)

    main_clause = (
        'UPDATE %s SET %s = LAST_INSERT_ID(%s + %%s)' % (
            table_name, col_name, col_name))
    update_args = [step]
    return cls(main_clause, update_args=update_args)

  @classmethod
  def MakeDelete(cls, table_name):
    """Constuct a DELETE statement."""
    assert _IsValidTableName(table_name)
    main_clause = 'DELETE FROM %s' % table_name
    return cls(main_clause)

  def __init__(
      self, main_clause, insert_args=None, update_args=None,
      duplicate_update_cols=None, or_where_conds=False):
    self.main_clause = main_clause  # E.g., SELECT or DELETE
    self.or_where_conds = or_where_conds
    self.insert_args = insert_args or []  # For INSERT statements
    self.update_args = update_args or []  # For UPDATEs
    self.duplicate_update_cols = duplicate_update_cols or []  # For REPLACE-ish

    self.use_clauses = []
    self.join_clauses, self.join_args = [], []
    self.where_conds, self.where_args = [], []
    self.having_conds, self.having_args = [], []
    self.group_by_terms, self.group_by_args = [], []
    self.order_by_terms, self.order_by_args = [], []
    self.limit, self.offset = None, None

  def Generate(self):
    """Return an SQL string having %s placeholders and args to fill them in."""
    clauses = [self.main_clause] + self.use_clauses + self.join_clauses
    if self.where_conds:
      if self.or_where_conds:
        clauses.append('WHERE ' + '\n  OR '.join(self.where_conds))
      else:
        clauses.append('WHERE ' + '\n  AND '.join(self.where_conds))
    if self.group_by_terms:
      clauses.append('GROUP BY ' + ', '.join(self.group_by_terms))
    if self.having_conds:
      assert self.group_by_terms
      clauses.append('HAVING %s' % ','.join(self.having_conds))
    if self.order_by_terms:
      clauses.append('ORDER BY ' + ', '.join(self.order_by_terms))

    if self.limit and self.offset:
      clauses.append('LIMIT %d OFFSET %d' % (self.limit, self.offset))
    elif self.limit:
      clauses.append('LIMIT %d' % self.limit)
    elif self.offset:
      clauses.append('LIMIT %d OFFSET %d' % (sys.maxint, self.offset))

    if self.insert_args:
      clauses.append('VALUES (' + PlaceHolders(self.insert_args[0]) + ')')
      args = self.insert_args
      if self.duplicate_update_cols:
        clauses.append('ON DUPLICATE KEY UPDATE %s' % (
            ', '.join(['%s=VALUES(%s)' % (col, col)
                       for col in self.duplicate_update_cols])))
      assert not (self.join_args + self.update_args + self.where_args +
                  self.group_by_args + self.order_by_args + self.having_args)
    else:
      args = (self.join_args + self.update_args + self.where_args +
              self.group_by_args + self.having_args + self.order_by_args)
      assert not (self.insert_args + self.duplicate_update_cols)

    args = _BoolsToInts(args)
    stmt_str = '\n'.join(clause for clause in clauses if clause)

    assert _IsValidStatement(stmt_str), stmt_str
    return stmt_str, args

  def AddUseClause(self, use_clause):
    """Add a USE clause (giving the DB a hint about which indexes to use)."""
    assert _IsValidUseClause(use_clause), use_clause
    self.use_clauses.append(use_clause)

  def AddJoinClauses(self, join_pairs, left=False):
    """Save JOIN clauses based on the given list of join conditions."""
    for join, args in join_pairs:
      assert _IsValidJoin(join), join
      assert join.count('%s') == len(args), join
      self.join_clauses.append(
          '  %sJOIN %s' % (('LEFT ' if left else ''), join))
      self.join_args.extend(args)

  def AddGroupByTerms(self, group_by_term_list):
    """Save info needed to generate the GROUP BY clause."""
    assert all(_IsValidGroupByTerm(term) for term in group_by_term_list)
    self.group_by_terms.extend(group_by_term_list)

  def AddOrderByTerms(self, order_by_pairs):
    """Save info needed to generate the ORDER BY clause."""
    for term, args in order_by_pairs:
      assert _IsValidOrderByTerm(term), term
      assert term.count('%s') == len(args), term
      self.order_by_terms.append(term)
      self.order_by_args.extend(args)

  def SetLimitAndOffset(self, limit, offset):
    """Save info needed to generate the LIMIT OFFSET clause."""
    self.limit = limit
    self.offset = offset

  def AddWhereTerms(self, where_cond_pairs, **kwargs):
    """Generate a WHERE clause."""
    where_cond_pairs = where_cond_pairs or []

    for cond, args in where_cond_pairs:
      assert _IsValidWhereCond(cond), cond
      assert cond.count('%s') == len(args), cond
      self.where_conds.append(cond)
      self.where_args.extend(args)

    for col, val in sorted(kwargs.items()):
      assert _IsValidColumnName(col), col
      eq = True
      if col.endswith('_not'):
        col = col[:-4]
        eq = False

      if isinstance(val, set):
        val = list(val)  # MySQL inteface cannot handle sets.

      if val is None or val == []:
        op = 'IS' if eq else 'IS NOT'
        self.where_conds.append(col + ' ' + op + ' NULL')
      elif isinstance(val, list):
        op = 'IN' if eq else 'NOT IN'
        # Sadly, MySQLdb cannot escape lists, so we flatten to multiple "%s"s
        self.where_conds.append(
            col + ' ' + op + ' (' + PlaceHolders(val) + ')')
        self.where_args.extend(val)
      else:
        op = '=' if eq else '!='
        self.where_conds.append(col + ' ' + op + ' %s')
        self.where_args.append(val)

  def AddHavingTerms(self, having_cond_pairs):
    """Generate a HAVING clause."""
    for cond, args in having_cond_pairs:
      assert _IsValidHavingCond(cond), cond
      assert cond.count('%s') == len(args), cond
      self.having_conds.append(cond)
      self.having_args.extend(args)


def PlaceHolders(sql_args):
  """Return a comma-separated list of %s placeholders for the given args."""
  return ','.join('%s' for _ in sql_args)


TABLE_PAT = '[A-Z][_a-zA-Z0-9]+'
COLUMN_PAT = '[a-z][_a-z]+'
COMPARE_OP_PAT = '(<|>|=|!=|>=|<=|LIKE|NOT LIKE)'
SHORTHAND = {
    'table': TABLE_PAT,
    'column': COLUMN_PAT,
    'tab_col': r'(%s\.)?%s' % (TABLE_PAT, COLUMN_PAT),
    'placeholder': '%s',  # That's a literal %s that gets passed to MySQLdb
    'multi_placeholder': '%s(, ?%s)*',
    'compare_op': COMPARE_OP_PAT,
    'opt_asc_desc': '( ASC| DESC)?',
    'opt_alias': '( AS %s)?' % TABLE_PAT,
    'email_cond': (r'\(?'
                   r'('
                   r'(LOWER\(User\d+\.email\) IS NULL OR )?'
                   r'LOWER\(User\d+\.email\) '
                   r'(%s %%s|IN \(%%s(, ?%%s)*\))'
                   r'( (AND|OR) )?'
                   r')+'
                   r'\)?' % COMPARE_OP_PAT),
    }


def _MakeRE(regex_str):
  """Return a regular expression object, expanding our shorthand as needed."""
  return re.compile(regex_str.format(**SHORTHAND))


TABLE_RE = _MakeRE('^{table}$')
TAB_COL_RE = _MakeRE('^{tab_col}$')
USE_CLAUSE_RE = _MakeRE(
    r'^USE INDEX \({column}\) USE INDEX FOR ORDER BY \({column}\)$')
HAVING_RE_LIST = [
    _MakeRE(r'^COUNT\(\*\) {compare_op} {placeholder}$')]
COLUMN_RE_LIST = [
    TAB_COL_RE,
    _MakeRE(r'\*'),
    _MakeRE(r'COUNT\(\*\)'),
    _MakeRE(r'COUNT\({tab_col}\)'),
    _MakeRE(r'MAX\({tab_col}\)'),
    _MakeRE(r'MIN\({tab_col}\)'),
    ]
JOIN_RE_LIST = [
    TABLE_RE,
    _MakeRE(
        r'^{table}{opt_alias} ON {tab_col} = {tab_col}'
        r'( AND {tab_col} = {tab_col})?'
        r'( AND {tab_col} IN \({multi_placeholder}\))?$'),
    _MakeRE(
        r'^{table}{opt_alias} ON {tab_col} = {tab_col}'
        r'( AND {tab_col} = {tab_col})?'
        r'( AND {tab_col} = {placeholder})?'
        r'( AND {tab_col} IN \({multi_placeholder}\))?$'),
    _MakeRE(
        r'^{table}{opt_alias} ON {tab_col} = {tab_col}'
        r'( AND {tab_col} = {tab_col})?'
        r'( AND {tab_col} = {placeholder})?'
        r'( AND {tab_col} IN \({multi_placeholder}\))?'
        r'( AND {tab_col} IS NULL)?'
        r'( AND \({tab_col} IS NULL'
        r' OR {tab_col} NOT IN \({multi_placeholder}\)\))?$'),
    _MakeRE(
        r'^{table}{opt_alias} ON {tab_col} = {tab_col}'
        r'( AND {tab_col} = {tab_col})?'
        r'( AND {tab_col} = {placeholder})?'
        r' AND {tab_col} {compare_op} {placeholder}$'),
    _MakeRE(
        r'^{table}{opt_alias} ON {tab_col} = {tab_col}'
        r'( AND {tab_col} = {tab_col})?'
        r'( AND {tab_col} = {placeholder})?'
        r' AND \({tab_col} IS NULL OR'
        r' {tab_col} != {placeholder}\)$'),
    _MakeRE(
        r'^{table}{opt_alias} ON {tab_col} = {tab_col} AND {email_cond}$'),
    _MakeRE(
        r'^{table}{opt_alias} ON '
        r'\({tab_col} = {tab_col} OR {tab_col} = {tab_col}\)$'),
    _MakeRE(
        r'^\({table} AS {table} JOIN User AS {table} '
        r'ON {tab_col} = {tab_col} AND {email_cond}\) '
        r'ON Issue.id = {tab_col}'
        r'( AND {tab_col} IS NULL)?'),
    _MakeRE(
        r'^{table} AS {table} ON {tab_col} = {tab_col} '
        r'LEFT JOIN {table} AS {table} ON {tab_col} = {tab_col}'),
    ]
ORDER_BY_RE_LIST = [
    _MakeRE(r'^{tab_col}{opt_asc_desc}$'),
    _MakeRE(r'^LOWER\({tab_col}\){opt_asc_desc}$'),
    _MakeRE(r'^ISNULL\({tab_col}\){opt_asc_desc}$'),
    _MakeRE(r'^FIELD\({tab_col}, {multi_placeholder}\){opt_asc_desc}$'),
    _MakeRE(r'^FIELD\(IF\(ISNULL\({tab_col}\), {tab_col}, {tab_col}\), '
            r'{multi_placeholder}\){opt_asc_desc}$'),
    ]
GROUP_BY_RE_LIST = [
    TAB_COL_RE,
    ]
WHERE_COND_RE_LIST = [
    _MakeRE(r'^TRUE$'),
    _MakeRE(r'^FALSE$'),
    _MakeRE(r'^{tab_col} IS NULL$'),
    _MakeRE(r'^{tab_col} IS NOT NULL$'),
    _MakeRE(r'^{tab_col} {compare_op} {tab_col}$'),
    _MakeRE(r'^{tab_col} {compare_op} {placeholder}$'),
    _MakeRE(r'^{tab_col} %% {placeholder} = {placeholder}$'),
    _MakeRE(r'^{tab_col} IN \({multi_placeholder}\)$'),
    _MakeRE(r'^{tab_col} NOT IN \({multi_placeholder}\)$'),
    _MakeRE(r'^LOWER\({tab_col}\) IS NULL$'),
    _MakeRE(r'^LOWER\({tab_col}\) IS NOT NULL$'),
    _MakeRE(r'^LOWER\({tab_col}\) {compare_op} {placeholder}$'),
    _MakeRE(r'^LOWER\({tab_col}\) IN \({multi_placeholder}\)$'),
    _MakeRE(r'^LOWER\({tab_col}\) NOT IN \({multi_placeholder}\)$'),
    _MakeRE(r'^LOWER\({tab_col}\) LIKE {placeholder}$'),
    _MakeRE(r'^LOWER\({tab_col}\) NOT LIKE {placeholder}$'),
    _MakeRE(r'^timestep < \(SELECT MAX\(j.timestep\) FROM Invalidate AS j '
            r'WHERE j.kind = %s '
            r'AND j.cache_key = Invalidate.cache_key\)$'),
    _MakeRE(r'^\({tab_col} IS NULL OR {tab_col} {compare_op} {placeholder}\) '
             'AND \({tab_col} IS NULL OR {tab_col} {compare_op} {placeholder}'
             '\)$'),
    _MakeRE(r'^\({tab_col} IS NOT NULL AND {tab_col} {compare_op} '
             '{placeholder}\) OR \({tab_col} IS NOT NULL AND {tab_col} '
             '{compare_op} {placeholder}\)$'),
    ]

# Note: We never use ';' for multiple statements, '@' for SQL variables, or
# any quoted strings in stmt_str (quotes are put in my MySQLdb for args).
STMT_STR_RE = re.compile(
    r'\A(SELECT|UPDATE|DELETE|INSERT|REPLACE) [-+=!<>%*.,()\w\s]+\Z',
    re.MULTILINE)


def _IsValidTableName(table_name):
  return TABLE_RE.match(table_name)


def _IsValidColumnName(column_expr):
  return any(regex.match(column_expr) for regex in COLUMN_RE_LIST)


def _IsValidUseClause(use_clause):
  return USE_CLAUSE_RE.match(use_clause)

def _IsValidHavingCond(cond):
  if cond.startswith('(') and cond.endswith(')'):
    cond = cond[1:-1]

  if ' OR ' in cond:
    return all(_IsValidHavingCond(c) for c in cond.split(' OR '))

  if ' AND ' in cond:
    return all(_IsValidHavingCond(c) for c in cond.split(' AND '))

  return any(regex.match(cond) for regex in HAVING_RE_LIST)


def _IsValidJoin(join):
  return any(regex.match(join) for regex in JOIN_RE_LIST)


def _IsValidOrderByTerm(term):
  return any(regex.match(term) for regex in ORDER_BY_RE_LIST)


def _IsValidGroupByTerm(term):
  return any(regex.match(term) for regex in GROUP_BY_RE_LIST)


def _IsValidWhereCond(cond):
  if cond.startswith('NOT '):
    cond = cond[4:]
  if cond.startswith('(') and cond.endswith(')'):
    cond = cond[1:-1]

  if any(regex.match(cond) for regex in WHERE_COND_RE_LIST):
    return True

  if ' OR ' in cond:
    return all(_IsValidWhereCond(c) for c in cond.split(' OR '))

  if ' AND ' in cond:
    return all(_IsValidWhereCond(c) for c in cond.split(' AND '))

  return False


def _IsValidStatement(stmt_str):
  """Final check to make sure there is no funny junk sneaking in somehow."""
  return (STMT_STR_RE.match(stmt_str) and
          '--' not in stmt_str)


def _BoolsToInts(arg_list):
  """Convert any True values to 1s and Falses to 0s.

  Google's copy of MySQLdb has bool-to-int conversion disabled,
  and yet it seems to be needed otherwise they are converted
  to strings and always interpreted as 0 (which is FALSE).

  Args:
    arg_list: (nested) list of SQL statment argument values, which may
        include some boolean values.

  Returns:
    The same list, but with True replaced by 1 and False replaced by 0.
  """
  result = []
  for arg in arg_list:
    if isinstance(arg, (list, tuple)):
      result.append(_BoolsToInts(arg))
    elif arg is True:
      result.append(1)
    elif arg is False:
      result.append(0)
    else:
      result.append(arg)

  return result
