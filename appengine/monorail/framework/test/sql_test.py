# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the sql module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock
import time
import unittest

import settings
from framework import exceptions
from framework import sql


class MockSQLCnxn(object):
  """This class mocks the connection and cursor classes."""

  def __init__(self, instance, database):
    self.instance = instance
    self.database = database
    self.last_executed = None
    self.last_executed_args = None
    self.result_rows = None
    self.rowcount = 0
    self.lastrowid = None
    self.pool_key = instance + '/' + database
    self.is_bad = False
    self.has_uncommitted = False

  def execute(self, stmt_str, args=None):
    self.last_executed = stmt_str % tuple(args or [])
    if not stmt_str.startswith(('SET', 'SELECT')):
      self.has_uncommitted = True

  def executemany(self, stmt_str, args):
    # We cannot format the string because args has many values for each %s.
    self.last_executed = stmt_str
    self.last_executed_args = tuple(args)

    # sql.py only calls executemany() for INSERT.
    assert stmt_str.startswith('INSERT')
    self.lastrowid = 123

  def fetchall(self):
    return self.result_rows

  def cursor(self):
    return self

  def commit(self):
    self.has_uncommitted = False

  def close(self):
    assert not self.has_uncommitted

  def rollback(self):
    self.has_uncommitted = False

  def ping(self):
    if self.is_bad:
      raise BaseException('connection error!')


sql.cnxn_ctor = MockSQLCnxn


class ConnectionPoolingTest(unittest.TestCase):

  def testGet(self):
    pool_size = 2
    num_dbs = 2
    p = sql.ConnectionPool(pool_size)

    for i in range(num_dbs):
      for _ in range(pool_size):
        c = p.get('test', 'db%d' % i)
        self.assertIsNotNone(c)
        p.release(c)

    cnxn1 = p.get('test', 'db0')
    q = p.queues[cnxn1.pool_key]
    self.assertIs(q.qsize(), 0)

    p.release(cnxn1)
    self.assertIs(q.qsize(), pool_size - 1)
    self.assertIs(q.full(), False)
    self.assertIs(q.empty(), False)

    cnxn2 = p.get('test', 'db0')
    q = p.queues[cnxn2.pool_key]
    self.assertIs(q.qsize(), 0)
    self.assertIs(q.full(), False)
    self.assertIs(q.empty(), True)

  def testGetAndReturnPooledCnxn(self):
    p = sql.ConnectionPool(2)

    cnxn1 = p.get('test', 'db1')
    self.assertIs(len(p.queues), 1)

    cnxn2 = p.get('test', 'db2')
    self.assertIs(len(p.queues), 2)

    # Should use the existing pool.
    cnxn3 = p.get('test', 'db1')
    self.assertIs(len(p.queues), 2)

    p.release(cnxn3)
    p.release(cnxn2)

    cnxn1.is_bad = True
    p.release(cnxn1)
    # cnxn1 should not be returned from the pool if we
    # ask for a connection to its database.

    cnxn4 = p.get('test', 'db1')

    self.assertIsNot(cnxn1, cnxn4)
    self.assertIs(len(p.queues), 2)
    self.assertIs(cnxn4.is_bad, False)

  def testGetAndReturnPooledCnxn_badCnxn(self):
    p = sql.ConnectionPool(2)

    cnxn1 = p.get('test', 'db1')
    cnxn2 = p.get('test', 'db2')
    cnxn3 = p.get('test', 'db1')

    cnxn3.is_bad = True

    p.release(cnxn3)
    q = p.queues[cnxn3.pool_key]
    self.assertIs(q.qsize(), 1)

    with self.assertRaises(BaseException):
      cnxn3 = p.get('test', 'db1')

    q = p.queues[cnxn2.pool_key]
    self.assertIs(q.qsize(), 0)
    p.release(cnxn2)
    self.assertIs(q.qsize(), 1)

    p.release(cnxn1)
    q = p.queues[cnxn1.pool_key]
    self.assertIs(q.qsize(), 1)


class MonorailConnectionTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = sql.MonorailConnection()
    self.orig_local_mode = settings.local_mode
    self.orig_num_logical_shards = settings.num_logical_shards
    settings.local_mode = False

  def tearDown(self):
    settings.local_mode = self.orig_local_mode
    settings.num_logical_shards = self.orig_num_logical_shards

  def testGetMasterConnection(self):
    sql_cnxn = self.cnxn.GetMasterConnection()
    self.assertEqual(settings.db_instance, sql_cnxn.instance)
    self.assertEqual(settings.db_database_name, sql_cnxn.database)

    sql_cnxn2 = self.cnxn.GetMasterConnection()
    self.assertIs(sql_cnxn2, sql_cnxn)

  def testGetConnectionForShard(self):
    sql_cnxn = self.cnxn.GetConnectionForShard(1)
    replica_name = settings.db_replica_names[
      1 % len(settings.db_replica_names)]
    self.assertEqual(settings.physical_db_name_format % replica_name,
                      sql_cnxn.instance)
    self.assertEqual(settings.db_database_name, sql_cnxn.database)

    sql_cnxn2 = self.cnxn.GetConnectionForShard(1)
    self.assertIs(sql_cnxn2, sql_cnxn)

  def testClose(self):
    sql_cnxn = self.cnxn.GetMasterConnection()
    self.cnxn.Close()
    self.assertFalse(sql_cnxn.has_uncommitted)

  def testExecute_Master(self):
    """Execute() with no shard passes the statement to the master sql cnxn."""
    sql_cnxn = self.cnxn.GetMasterConnection()
    with mock.patch.object(self.cnxn, '_ExecuteWithSQLConnection') as ewsc:
      ewsc.return_value = 'db result'
      actual_result = self.cnxn.Execute('statement', [])
      self.assertEqual('db result', actual_result)
      ewsc.assert_called_once_with(sql_cnxn, 'statement', [], commit=True)

  def testExecute_Shard(self):
    """Execute() with a shard passes the statement to the shard sql cnxn."""
    shard_id = 1
    sql_cnxn_1 = self.cnxn.GetConnectionForShard(shard_id)
    with mock.patch.object(self.cnxn, '_ExecuteWithSQLConnection') as ewsc:
      ewsc.return_value = 'db result'
      actual_result = self.cnxn.Execute('statement', [], shard_id=shard_id)
      self.assertEqual('db result', actual_result)
      ewsc.assert_called_once_with(sql_cnxn_1, 'statement', [], commit=True)

  def testExecute_Shard_Unavailable(self):
    """If a shard is unavailable, we try the next one."""
    shard_id = 1
    sql_cnxn_1 = self.cnxn.GetConnectionForShard(shard_id)
    sql_cnxn_2 = self.cnxn.GetConnectionForShard(shard_id + 1)

    # Simulate a recent failure on shard 1.
    self.cnxn.unavailable_shards[1] = int(time.time()) - 300

    with mock.patch.object(self.cnxn, '_ExecuteWithSQLConnection') as ewsc:
      ewsc.return_value = 'db result'
      actual_result = self.cnxn.Execute('statement', [], shard_id=shard_id)
      self.assertEqual('db result', actual_result)
      ewsc.assert_called_once_with(sql_cnxn_2, 'statement', [], commit=True)

    # Even a new MonorailConnection instance shares the same state.
    other_cnxn = sql.MonorailConnection()
    other_sql_cnxn_2 = other_cnxn.GetConnectionForShard(shard_id + 1)

    with mock.patch.object(other_cnxn, '_ExecuteWithSQLConnection') as ewsc:
      ewsc.return_value = 'db result'
      actual_result = other_cnxn.Execute('statement', [], shard_id=shard_id)
      self.assertEqual('db result', actual_result)
      ewsc.assert_called_once_with(
          other_sql_cnxn_2, 'statement', [], commit=True)

    # Simulate an old failure on shard 1, allowing us to try using it again.
    self.cnxn.unavailable_shards[1] = (
        int(time.time()) - sql.BAD_SHARD_AVOIDANCE_MS - 1)

    with mock.patch.object(self.cnxn, '_ExecuteWithSQLConnection') as ewsc:
      ewsc.return_value = 'db result'
      actual_result = self.cnxn.Execute('statement', [], shard_id=shard_id)
      self.assertEqual('db result', actual_result)
      ewsc.assert_called_once_with(sql_cnxn_1, 'statement', [], commit=True)


class TableManagerTest(unittest.TestCase):

  def setUp(self):
    self.emp_tbl = sql.SQLTableManager('Employee')
    self.cnxn = sql.MonorailConnection()
    self.master_cnxn = self.cnxn.GetMasterConnection()

  def testSelect_Trivial(self):
    self.master_cnxn.result_rows = [(111, True), (222, False)]
    rows = self.emp_tbl.Select(self.cnxn)
    self.assertEqual('SELECT * FROM Employee', self.master_cnxn.last_executed)
    self.assertEqual([(111, True), (222, False)], rows)

  def testSelect_Conditions(self):
    self.master_cnxn.result_rows = [(111,)]
    rows = self.emp_tbl.Select(
        self.cnxn, cols=['emp_id'], fulltime=True, dept_id=[10, 20])
    self.assertEqual(
        'SELECT emp_id FROM Employee'
        '\nWHERE dept_id IN (10,20)'
        '\n  AND fulltime = 1',
        self.master_cnxn.last_executed)
    self.assertEqual([(111,)], rows)

  def testSelectRow(self):
    self.master_cnxn.result_rows = [(111,)]
    row = self.emp_tbl.SelectRow(
        self.cnxn, cols=['emp_id'], fulltime=True, dept_id=[10, 20])
    self.assertEqual(
        'SELECT DISTINCT emp_id FROM Employee'
        '\nWHERE dept_id IN (10,20)'
        '\n  AND fulltime = 1',
        self.master_cnxn.last_executed)
    self.assertEqual((111,), row)

  def testSelectRow_NoMatches(self):
    self.master_cnxn.result_rows = []
    row = self.emp_tbl.SelectRow(
        self.cnxn, cols=['emp_id'], fulltime=True, dept_id=[99])
    self.assertEqual(
        'SELECT DISTINCT emp_id FROM Employee'
        '\nWHERE dept_id IN (99)'
        '\n  AND fulltime = 1',
        self.master_cnxn.last_executed)
    self.assertEqual(None, row)

    row = self.emp_tbl.SelectRow(
        self.cnxn, cols=['emp_id'], fulltime=True, dept_id=[99],
        default=(-1,))
    self.assertEqual((-1,), row)

  def testSelectValue(self):
    self.master_cnxn.result_rows = [(111,)]
    val = self.emp_tbl.SelectValue(
        self.cnxn, 'emp_id', fulltime=True, dept_id=[10, 20])
    self.assertEqual(
        'SELECT DISTINCT emp_id FROM Employee'
        '\nWHERE dept_id IN (10,20)'
        '\n  AND fulltime = 1',
        self.master_cnxn.last_executed)
    self.assertEqual(111, val)

  def testSelectValue_NoMatches(self):
    self.master_cnxn.result_rows = []
    val = self.emp_tbl.SelectValue(
        self.cnxn, 'emp_id', fulltime=True, dept_id=[99])
    self.assertEqual(
        'SELECT DISTINCT emp_id FROM Employee'
        '\nWHERE dept_id IN (99)'
        '\n  AND fulltime = 1',
        self.master_cnxn.last_executed)
    self.assertEqual(None, val)

    val = self.emp_tbl.SelectValue(
        self.cnxn, 'emp_id', fulltime=True, dept_id=[99],
        default=-1)
    self.assertEqual(-1, val)

  def testInsertRow(self):
    self.master_cnxn.rowcount = 1
    generated_id = self.emp_tbl.InsertRow(self.cnxn, emp_id=111, fulltime=True)
    self.assertEqual(
        'INSERT INTO Employee (emp_id, fulltime)'
        '\nVALUES (%s,%s)',
        self.master_cnxn.last_executed)
    self.assertEqual(
        ([111, 1],),
        self.master_cnxn.last_executed_args)
    self.assertEqual(123, generated_id)

  def testInsertRows_Empty(self):
    generated_id = self.emp_tbl.InsertRows(
        self.cnxn, ['emp_id', 'fulltime'], [])
    self.assertIsNone(self.master_cnxn.last_executed)
    self.assertIsNone(self.master_cnxn.last_executed_args)
    self.assertEqual(None, generated_id)

  def testInsertRows(self):
    self.master_cnxn.rowcount = 2
    generated_ids = self.emp_tbl.InsertRows(
        self.cnxn, ['emp_id', 'fulltime'], [(111, True), (222, False)])
    self.assertEqual(
        'INSERT INTO Employee (emp_id, fulltime)'
        '\nVALUES (%s,%s)',
        self.master_cnxn.last_executed)
    self.assertEqual(
        ([111, 1], [222, 0]),
        self.master_cnxn.last_executed_args)
    self.assertEqual([], generated_ids)

  def testUpdate(self):
    self.master_cnxn.rowcount = 2
    rowcount = self.emp_tbl.Update(
        self.cnxn, {'fulltime': True}, emp_id=[111, 222])
    self.assertEqual(
        'UPDATE Employee SET fulltime=1'
        '\nWHERE emp_id IN (111,222)',
        self.master_cnxn.last_executed)
    self.assertEqual(2, rowcount)

  def testUpdate_Limit(self):
    self.emp_tbl.Update(
        self.cnxn, {'fulltime': True}, limit=8, emp_id=[111, 222])
    self.assertEqual(
        'UPDATE Employee SET fulltime=1'
        '\nWHERE emp_id IN (111,222)'
        '\nLIMIT 8',
        self.master_cnxn.last_executed)

  def testIncrementCounterValue(self):
    self.master_cnxn.rowcount = 1
    self.master_cnxn.lastrowid = 9
    new_counter_val = self.emp_tbl.IncrementCounterValue(
        self.cnxn, 'years_worked', emp_id=111)
    self.assertEqual(
        'UPDATE Employee SET years_worked = LAST_INSERT_ID(years_worked + 1)'
        '\nWHERE emp_id = 111',
        self.master_cnxn.last_executed)
    self.assertEqual(9, new_counter_val)

  def testDelete(self):
    self.master_cnxn.rowcount = 1
    rowcount = self.emp_tbl.Delete(self.cnxn, fulltime=True)
    self.assertEqual(
        'DELETE FROM Employee'
        '\nWHERE fulltime = 1',
        self.master_cnxn.last_executed)
    self.assertEqual(1, rowcount)

  def testDelete_Limit(self):
    self.emp_tbl.Delete(self.cnxn, fulltime=True, limit=3)
    self.assertEqual(
        'DELETE FROM Employee'
        '\nWHERE fulltime = 1'
        '\nLIMIT 3',
        self.master_cnxn.last_executed)


class StatementTest(unittest.TestCase):

  def testMakeSelect(self):
    stmt = sql.Statement.MakeSelect('Employee', ['emp_id', 'fulltime'])
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'SELECT emp_id, fulltime FROM Employee',
        stmt_str)
    self.assertEqual([], args)

    stmt = sql.Statement.MakeSelect(
        'Employee', ['emp_id', 'fulltime'], distinct=True)
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'SELECT DISTINCT emp_id, fulltime FROM Employee',
        stmt_str)
    self.assertEqual([], args)

  def testMakeInsert(self):
    stmt = sql.Statement.MakeInsert(
        'Employee', ['emp_id', 'fulltime'], [(111, True), (222, False)])
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'INSERT INTO Employee (emp_id, fulltime)'
        '\nVALUES (%s,%s)',
        stmt_str)
    self.assertEqual([[111, 1], [222, 0]], args)

    stmt = sql.Statement.MakeInsert(
        'Employee', ['emp_id', 'fulltime'], [(111, False)], replace=True)
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'INSERT INTO Employee (emp_id, fulltime)'
        '\nVALUES (%s,%s)'
        '\nON DUPLICATE KEY UPDATE '
        'emp_id=VALUES(emp_id), fulltime=VALUES(fulltime)',
        stmt_str)
    self.assertEqual([[111, 0]], args)

    stmt = sql.Statement.MakeInsert(
        'Employee', ['emp_id', 'fulltime'], [(111, False)], ignore=True)
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'INSERT IGNORE INTO Employee (emp_id, fulltime)'
        '\nVALUES (%s,%s)',
        stmt_str)
    self.assertEqual([[111, 0]], args)

  def testMakeInsert_InvalidString(self):
    with self.assertRaises(exceptions.InputException):
      sql.Statement.MakeInsert(
          'Employee', ['emp_id', 'name'], [(111, 'First \x00 Last')])

  def testMakeUpdate(self):
    stmt = sql.Statement.MakeUpdate('Employee', {'fulltime': True})
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'UPDATE Employee SET fulltime=%s',
        stmt_str)
    self.assertEqual([1], args)

  def testMakeUpdate_InvalidString(self):
    with self.assertRaises(exceptions.InputException):
      sql.Statement.MakeUpdate('Employee', {'name': 'First \x00 Last'})

  def testMakeIncrement(self):
    stmt = sql.Statement.MakeIncrement('Employee', 'years_worked')
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'UPDATE Employee SET years_worked = LAST_INSERT_ID(years_worked + %s)',
        stmt_str)
    self.assertEqual([1], args)

    stmt = sql.Statement.MakeIncrement('Employee', 'years_worked', step=5)
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'UPDATE Employee SET years_worked = LAST_INSERT_ID(years_worked + %s)',
        stmt_str)
    self.assertEqual([5], args)

  def testMakeDelete(self):
    stmt = sql.Statement.MakeDelete('Employee')
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'DELETE FROM Employee',
        stmt_str)
    self.assertEqual([], args)

  def testAddUseClause(self):
    stmt = sql.Statement.MakeSelect('Employee', ['emp_id', 'fulltime'])
    stmt.AddUseClause('USE INDEX (emp_id) USE INDEX FOR ORDER BY (emp_id)')
    stmt.AddOrderByTerms([('emp_id', [])])
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'SELECT emp_id, fulltime FROM Employee'
        '\nUSE INDEX (emp_id) USE INDEX FOR ORDER BY (emp_id)'
        '\nORDER BY emp_id',
        stmt_str)
    self.assertEqual([], args)

  def testAddJoinClause_Empty(self):
    stmt = sql.Statement.MakeSelect('Employee', ['emp_id', 'fulltime'])
    stmt.AddJoinClauses([])
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'SELECT emp_id, fulltime FROM Employee',
        stmt_str)
    self.assertEqual([], args)

  def testAddJoinClause(self):
    stmt = sql.Statement.MakeSelect('Employee', ['emp_id', 'fulltime'])
    stmt.AddJoinClauses([('CorporateHoliday', [])])
    stmt.AddJoinClauses(
        [('Product ON Project.inventor_id = emp_id', [])], left=True)
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'SELECT emp_id, fulltime FROM Employee'
        '\n  JOIN CorporateHoliday'
        '\n  LEFT JOIN Product ON Project.inventor_id = emp_id',
        stmt_str)
    self.assertEqual([], args)

  def testAddGroupByTerms_Empty(self):
    stmt = sql.Statement.MakeSelect('Employee', ['emp_id', 'fulltime'])
    stmt.AddGroupByTerms([])
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'SELECT emp_id, fulltime FROM Employee',
        stmt_str)
    self.assertEqual([], args)

  def testAddGroupByTerms(self):
    stmt = sql.Statement.MakeSelect('Employee', ['emp_id', 'fulltime'])
    stmt.AddGroupByTerms(['dept_id', 'location_id'])
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'SELECT emp_id, fulltime FROM Employee'
        '\nGROUP BY dept_id, location_id',
        stmt_str)
    self.assertEqual([], args)

  def testAddOrderByTerms_Empty(self):
    stmt = sql.Statement.MakeSelect('Employee', ['emp_id', 'fulltime'])
    stmt.AddOrderByTerms([])
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'SELECT emp_id, fulltime FROM Employee',
        stmt_str)
    self.assertEqual([], args)

  def testAddOrderByTerms(self):
    stmt = sql.Statement.MakeSelect('Employee', ['emp_id', 'fulltime'])
    stmt.AddOrderByTerms([('dept_id', []), ('emp_id DESC', [])])
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'SELECT emp_id, fulltime FROM Employee'
        '\nORDER BY dept_id, emp_id DESC',
        stmt_str)
    self.assertEqual([], args)

  def testSetLimitAndOffset(self):
    stmt = sql.Statement.MakeSelect('Employee', ['emp_id', 'fulltime'])
    stmt.SetLimitAndOffset(100, 0)
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'SELECT emp_id, fulltime FROM Employee'
        '\nLIMIT 100',
        stmt_str)
    self.assertEqual([], args)

    stmt.SetLimitAndOffset(100, 500)
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'SELECT emp_id, fulltime FROM Employee'
        '\nLIMIT 100 OFFSET 500',
        stmt_str)
    self.assertEqual([], args)

  def testAddWhereTerms_Select(self):
    stmt = sql.Statement.MakeSelect('Employee', ['emp_id', 'fulltime'])
    stmt.AddWhereTerms([], emp_id=[111, 222])
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'SELECT emp_id, fulltime FROM Employee'
        '\nWHERE emp_id IN (%s,%s)',
        stmt_str)
    self.assertEqual([111, 222], args)

  def testAddWhereTerms_Update(self):
    stmt = sql.Statement.MakeUpdate('Employee', {'fulltime': True})
    stmt.AddWhereTerms([], emp_id=[111, 222])
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'UPDATE Employee SET fulltime=%s'
        '\nWHERE emp_id IN (%s,%s)',
        stmt_str)
    self.assertEqual([1, 111, 222], args)

  def testAddWhereTerms_Delete(self):
    stmt = sql.Statement.MakeDelete('Employee')
    stmt.AddWhereTerms([], emp_id=[111, 222])
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'DELETE FROM Employee'
        '\nWHERE emp_id IN (%s,%s)',
        stmt_str)
    self.assertEqual([111, 222], args)

  def testAddWhereTerms_Empty(self):
    """Add empty terms should have no effect."""
    stmt = sql.Statement.MakeSelect('Employee', ['emp_id', 'fulltime'])
    stmt.AddWhereTerms([])
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'SELECT emp_id, fulltime FROM Employee',
        stmt_str)
    self.assertEqual([], args)

  def testAddWhereTerms_MulitpleTerms(self):
    stmt = sql.Statement.MakeSelect('Employee', ['emp_id', 'fulltime'])
    stmt.AddWhereTerms(
        [('emp_id %% %s = %s', [2, 0])], fulltime=True, emp_id_not=222)
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'SELECT emp_id, fulltime FROM Employee'
        '\nWHERE emp_id %% %s = %s'
        '\n  AND emp_id != %s'
        '\n  AND fulltime = %s',
        stmt_str)
    self.assertEqual([2, 0, 222, 1], args)

  def testAddHavingTerms_NoGroupBy(self):
    stmt = sql.Statement.MakeSelect('Employee', ['emp_id', 'fulltime'])
    stmt.AddHavingTerms([('COUNT(*) > %s', [10])])
    self.assertRaises(AssertionError, stmt.Generate)

  def testAddHavingTerms_WithGroupBy(self):
    stmt = sql.Statement.MakeSelect('Employee', ['emp_id', 'fulltime'])
    stmt.AddGroupByTerms(['dept_id', 'location_id'])
    stmt.AddHavingTerms([('COUNT(*) > %s', [10])])
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'SELECT emp_id, fulltime FROM Employee'
        '\nGROUP BY dept_id, location_id'
        '\nHAVING COUNT(*) > %s',
        stmt_str)
    self.assertEqual([10], args)


class FunctionsTest(unittest.TestCase):

  def testIsValidDBValue_NonString(self):
    self.assertTrue(sql._IsValidDBValue(12))
    self.assertTrue(sql._IsValidDBValue(True))
    self.assertTrue(sql._IsValidDBValue(False))
    self.assertTrue(sql._IsValidDBValue(None))

  def testIsValidDBValue_String(self):
    self.assertTrue(sql._IsValidDBValue(''))
    self.assertTrue(sql._IsValidDBValue('hello'))
    self.assertTrue(sql._IsValidDBValue(u'hello'))
    self.assertFalse(sql._IsValidDBValue('null \x00 byte'))

  def testBoolsToInts_NoChanges(self):
    self.assertEqual(['hello'], sql._BoolsToInts(['hello']))
    self.assertEqual([['hello']], sql._BoolsToInts([['hello']]))
    self.assertEqual([['hello']], sql._BoolsToInts([('hello',)]))
    self.assertEqual([12], sql._BoolsToInts([12]))
    self.assertEqual([[12]], sql._BoolsToInts([[12]]))
    self.assertEqual([[12]], sql._BoolsToInts([(12,)]))
    self.assertEqual(
        [12, 13, 'hi', [99, 'yo']],
        sql._BoolsToInts([12, 13, 'hi', [99, 'yo']]))

  def testBoolsToInts_WithChanges(self):
    self.assertEqual([1, 0], sql._BoolsToInts([True, False]))
    self.assertEqual([[1, 0]], sql._BoolsToInts([[True, False]]))
    self.assertEqual([[1, 0]], sql._BoolsToInts([(True, False)]))
    self.assertEqual(
        [12, 1, 'hi', [0, 'yo']],
        sql._BoolsToInts([12, True, 'hi', [False, 'yo']]))

  def testRandomShardID(self):
    """A random shard ID must always be a valid shard ID."""
    shard_id = sql.RandomShardID()
    self.assertTrue(0 <= shard_id < settings.num_logical_shards)
