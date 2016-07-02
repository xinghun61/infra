// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package sqlmock

import (
	"fmt"
	"io"
	"strings"
	"sync"

	"database/sql"
	"database/sql/driver"
)

var mockDriver MockDriver

type FullQuery struct {
	Query string
	Args  []driver.Value
}

type MockResult struct{}

var _ driver.Result = MockResult{}

func (res MockResult) LastInsertId() (int64, error) { return 0, nil }
func (res MockResult) RowsAffected() (int64, error) { return 0, nil }

type MockRows struct {
	current int
	rows    [][]driver.Value
}

var _ driver.Rows = &MockRows{}

func (rows *MockRows) Columns() []string {
	if len(rows.rows) == 0 {
		return []string{}
	}
	ret := []string{}
	for i := 0; i < len(rows.rows[0]); i += 1 {
		ret = append(ret, fmt.Sprintf("col%d", i))
	}
	return ret
}

func (rows *MockRows) Close() error { return nil }

func (rows *MockRows) Next(dest []driver.Value) error {
	if rows.current >= len(rows.rows) {
		return io.EOF
	}
	for i := 0; i < len(dest); i += 1 {
		dest[i] = rows.rows[rows.current][i]
	}
	rows.current += 1
	return nil
}

type MockStmt struct {
	conn  *MockConn
	query string
}

var _ driver.Stmt = MockStmt{}

func (st MockStmt) Close() error { return nil }

func (st MockStmt) NumInput() int {
	// Very crude way to determine the number of placeholders. Will obviously
	// break if an extra '?' exists somewhere in the query string. It's hard to
	// do better without parsing the SQL string.
	return strings.Count(st.query, "?")
}

func (st MockStmt) Exec(args []driver.Value) (driver.Result, error) {
	st.conn.extend(FullQuery{st.query, args})
	return MockResult{}, nil
}
func (st MockStmt) Query(args []driver.Value) (driver.Rows, error) {
	st.conn.extend(FullQuery{st.query, args})
	r := st.conn.popRows()
	return r, nil
}

type MockTx struct{}

var _ driver.Tx = MockTx{}

func (tx MockTx) Commit() error { return nil }

func (tx MockTx) Rollback() error { return nil }

type MockConn struct {
	Queries []FullQuery
	Rows    []MockRows
	lock    sync.Mutex
}

var _ driver.Conn = &MockConn{}

func (conn *MockConn) Prepare(query string) (driver.Stmt, error) {
	return MockStmt{conn, query}, nil
}

func (conn *MockConn) Close() error {
	return nil
}

func (conn *MockConn) Begin() (driver.Tx, error) {
	return MockTx{}, nil
}

func (conn *MockConn) extend(args ...FullQuery) {
	conn.lock.Lock()
	defer conn.lock.Unlock()
	conn.Queries = append(conn.Queries, args...)
}

func (conn *MockConn) popRows() *MockRows {
	conn.lock.Lock()
	defer conn.lock.Unlock()
	rows := MockRows{}
	if len(conn.Rows) > 0 {
		rows = conn.Rows[0]
		conn.Rows = conn.Rows[1:]
	}
	return &rows
}

func (conn *MockConn) PushRows(rows [][]driver.Value) error {
	mockRows := MockRows{}
	conn.lock.Lock()
	defer conn.lock.Unlock()
	colNumRow0 := 0
	for i, row := range rows {
		newRow := []driver.Value{}
		colNum := 0
		for _, value := range row {
			colNum += 1
			if s, ok := value.(string); ok {
				newRow = append(newRow, []byte(s))
			} else {
				newRow = append(newRow, value)
			}
		}
		if i == 0 {
			colNumRow0 = colNum
		} else if colNum != colNumRow0 {
			return fmt.Errorf("Inconsistent number of columns. Got %d "+
				"when previous rows got", colNum, colNumRow0)
		}

		mockRows.rows = append(mockRows.rows, newRow)
	}
	conn.Rows = append(conn.Rows, mockRows)
	return nil
}

type MockDriver struct {
	count int
	conn  map[string]*MockConn
	lock  sync.Mutex
}

var _ driver.Driver = &MockDriver{}

func (dr *MockDriver) Open(dsn string) (driver.Conn, error) {
	// Always return the same connection for a given dsn.
	dr.lock.Lock()
	defer dr.lock.Unlock()
	if conn, ok := dr.conn[dsn]; ok {
		return conn, nil
	}
	// Panicking because it's an internal error.
	panic(fmt.Sprintf("Internal error: unknown dsn %s", dsn))
}

// PopOldestQuery returns the oldest query received.
// An non-nil error is returned if there are no queries in the list.
func (conn *MockConn) PopOldestQuery() (*FullQuery, error) {
	conn.lock.Lock()
	defer conn.lock.Unlock()
	if len(conn.Queries) == 0 {
		return nil, fmt.Errorf("No queries have been received")
	}
	query := conn.Queries[0]
	conn.Queries = conn.Queries[1:]
	return &query, nil
}

func NewMockDB() (*sql.DB, *MockConn) {
	mockDriver.lock.Lock()
	mockDriver.count++
	dsn := fmt.Sprintf("MockDSN_%d", mockDriver.count)
	// We have to create the mock connection here because sql.Open is asynchronous
	// and we want to return the connection from the present function.
	conn := &MockConn{}
	mockDriver.conn[dsn] = conn
	mockDriver.lock.Unlock()

	db, _ := sql.Open("sqlmock", dsn)
	return db, conn
}

func init() {
	mockDriver = MockDriver{
		conn: map[string]*MockConn{},
	}
	sql.Register("sqlmock", &mockDriver)
}
