# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the sql module."""

import unittest

import settings
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

  def execute(self, stmt_str, args=None):
    self.last_executed = stmt_str % tuple(args or [])

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
    pass

  def close(self):
    pass


sql.MakeConnection = MockSQLCnxn


class MonorailConnectionTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = sql.MonorailConnection()
    self.orig_dev_mode = settings.dev_mode
    self.orig_num_logical_shards = settings.num_logical_shards
    settings.dev_mode = False

  def tearDown(self):
    settings.dev_mode = self.orig_dev_mode
    settings.num_logical_shards = self.orig_num_logical_shards

  def testGetMasterConnection(self):
    sql_cnxn = self.cnxn.GetMasterConnection()
    self.assertEqual(settings.db_instance, sql_cnxn.instance)
    self.assertEqual(settings.db_database_name, sql_cnxn.database)

    sql_cnxn2 = self.cnxn.GetMasterConnection()
    self.assertIs(sql_cnxn2, sql_cnxn)

  def testGetConnectionForShard(self):
    sql_cnxn = self.cnxn.GetConnectionForShard(1)
    self.assertEqual(settings.physical_db_name_format % 1,
                      sql_cnxn.instance)
    self.assertEqual(settings.db_database_name, sql_cnxn.database)

    sql_cnxn2 = self.cnxn.GetConnectionForShard(1)
    self.assertIs(sql_cnxn2, sql_cnxn)


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

  def testMakeUpdate(self):
    stmt = sql.Statement.MakeUpdate('Employee', {'fulltime': True})
    stmt_str, args = stmt.Generate()
    self.assertEqual(
        'UPDATE Employee SET fulltime=%s',
        stmt_str)
    self.assertEqual([1], args)

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
