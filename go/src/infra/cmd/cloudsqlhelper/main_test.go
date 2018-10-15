// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"database/sql"
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"

	"github.com/DATA-DOG/go-sqlmock"
	"golang.org/x/net/context"
)

var okResult = sqlmock.NewResult(1, 1)

func makeBunchOfFiles(files map[string]string) (string, error) {
	root, err := ioutil.TempDir("", "cloudsqlhelper")
	if err != nil {
		return "", err
	}
	for name, value := range files {
		if err := ioutil.WriteFile(filepath.Join(root, name), []byte(value), 0600); err != nil {
			os.RemoveAll(root)
			return "", err
		}
	}
	return root, nil
}

func withMockDB(t *testing.T, run func(ctx context.Context, mock sqlmock.Sqlmock, ops Options, conf *DBConfig) error) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("failed to create mock DB - %s", err)
	}

	conf := &DBConfig{
		ID:               "unit-test",
		User:             "unit-test-user",
		DB:               "unit-test-db",
		CloudSQLInstance: "unused",
		openDBMock:       func() (*sql.DB, error) { return db, err },
	}

	migrations, err := makeBunchOfFiles(map[string]string{
		"001_init.up.sql":        "CREATE TABLE stuff();",
		"001_init.down.sql":      "DROP TABLE stuff;",
		"002_moar.up.sql":        "CREATE TABLE moar_stuff();",
		"002_moar.down.sql":      "DROP TABLE moar_stuff;",
		"003_even_moar.up.sql":   "CREATE TABLE even_moar_stuff();",
		"003_even_moar.down.sql": "DROP TABLE even_moar_stuff;",
	})
	if err != nil {
		t.Fatalf("failed to drop migration files - %s", err)
	}
	defer os.RemoveAll(migrations)

	if err = run(context.Background(), mock, Options{MigrationsPath: migrations}, conf); err != nil {
		t.Fatalf("%s", err)
	}

	if err = mock.ExpectationsWereMet(); err != nil {
		t.Fatalf("there were unfulfilled expectations: %s", err)
	}
}

func TestCreateDB(t *testing.T) {
	withMockDB(t, func(ctx context.Context, mock sqlmock.Sqlmock, opts Options, conf *DBConfig) error {
		mock.ExpectExec("CREATE DATABASE IF NOT EXISTS `unit-test-db`").WillReturnResult(sqlmock.NewResult(0, 0))
		return createCmd(ctx, opts, conf, "unused-socket")
	})
}

func TestDropDB(t *testing.T) {
	withMockDB(t, func(ctx context.Context, mock sqlmock.Sqlmock, opts Options, conf *DBConfig) error {
		mock.ExpectExec("DROP DATABASE IF EXISTS `unit-test-db`").WillReturnResult(sqlmock.NewResult(0, 0))
		return dropCmd(ctx, opts, conf, "unused-socket")
	})
}

func TestMigrateUpNewDB(t *testing.T) {
	withMockDB(t, func(ctx context.Context, mock sqlmock.Sqlmock, opts Options, conf *DBConfig) error {
		expectPrelude(mock, false) // no schema_migrations table yet!
		mock.ExpectExec("CREATE TABLE `schema_migrations`").WillReturnResult(okResult)

		expectSelectVersion(mock, -1, false) // prints current version (which is none)

		expectLock(mock)
		expectSelectVersion(mock, -1, false) // no version recorded yet

		// Applies all known migrations.

		expectSetVersion(mock, 1, true)
		mock.ExpectExec("CREATE TABLE stuff\\(\\)").WillReturnResult(okResult)
		expectSetVersion(mock, 1, false)

		expectSetVersion(mock, 2, true)
		mock.ExpectExec("CREATE TABLE moar_stuff\\(\\)").WillReturnResult(okResult)
		expectSetVersion(mock, 2, false)

		expectSetVersion(mock, 3, true)
		mock.ExpectExec("CREATE TABLE even_moar_stuff\\(\\)").WillReturnResult(okResult)
		expectSetVersion(mock, 3, false)

		expectUnlock(mock)
		expectSelectVersion(mock, 3, false) // prints current version

		return migrateUpCmd(ctx, opts, conf, "unused-socket")
	})
}

func TestMigrateUpExistingDB(t *testing.T) {
	withMockDB(t, func(ctx context.Context, mock sqlmock.Sqlmock, opts Options, conf *DBConfig) error {
		expectPrelude(mock, true)           // the migrations table already exists
		expectSelectVersion(mock, 1, false) // prints current version

		expectLock(mock)
		expectSelectVersion(mock, 1, false) // have version 1 already

		// Applies two new migrations.
		expectSetVersion(mock, 2, true)
		mock.ExpectExec("CREATE TABLE moar_stuff\\(\\)").WillReturnResult(okResult)
		expectSetVersion(mock, 2, false)

		expectSetVersion(mock, 3, true)
		mock.ExpectExec("CREATE TABLE even_moar_stuff\\(\\)").WillReturnResult(okResult)
		expectSetVersion(mock, 3, false)

		expectUnlock(mock)
		expectSelectVersion(mock, 3, false) // prints current version

		return migrateUpCmd(ctx, opts, conf, "unused-socket")
	})
}

func TestMigrateUpNoop(t *testing.T) {
	withMockDB(t, func(ctx context.Context, mock sqlmock.Sqlmock, opts Options, conf *DBConfig) error {
		expectPrelude(mock, true)           // the migrations table already exists
		expectSelectVersion(mock, 3, false) // prints current version

		expectLock(mock)
		expectSelectVersion(mock, 3, false) // have most recent version already

		// Nothing to apply!

		expectUnlock(mock)

		return migrateUpCmd(ctx, opts, conf, "unused-socket")
	})
}

func TestMigrateDown(t *testing.T) {
	withMockDB(t, func(ctx context.Context, mock sqlmock.Sqlmock, opts Options, conf *DBConfig) error {
		expectPrelude(mock, true) // the migrations table already exists

		expectSelectVersion(mock, 3, false) // prints current version

		expectLock(mock)
		expectSelectVersion(mock, 3, false) // have most recent version

		// Applies one reverse migration, and only one.
		expectSetVersion(mock, 2, true)
		mock.ExpectExec("DROP TABLE even_moar_stuff;").WillReturnResult(okResult)
		expectSetVersion(mock, 2, false)

		expectUnlock(mock)
		expectSelectVersion(mock, 2, false) // prints current version

		return migrateDownCmd(ctx, opts, conf, "unused-socket")
	})
}

func TestMigrateTo(t *testing.T) {
	withMockDB(t, func(ctx context.Context, mock sqlmock.Sqlmock, opts Options, conf *DBConfig) error {
		// Asked to migrate two version back.
		opts.Args = []string{"1"}

		expectPrelude(mock, true)           // the migrations table already exists
		expectSelectVersion(mock, 3, false) // prints current version

		expectLock(mock)
		expectSelectVersion(mock, 3, false) // have most recent version

		// Applies two reverse migrations.
		expectSetVersion(mock, 2, true)
		mock.ExpectExec("DROP TABLE even_moar_stuff;").WillReturnResult(okResult)
		expectSetVersion(mock, 2, false)

		expectSetVersion(mock, 1, true)
		mock.ExpectExec("DROP TABLE moar_stuff;").WillReturnResult(okResult)
		expectSetVersion(mock, 1, false)

		expectUnlock(mock)
		expectSelectVersion(mock, 1, false) // prints current version

		return migrateToCmd(ctx, opts, conf, "unused-socket")
	})
}

func TestShowVersion(t *testing.T) {
	withMockDB(t, func(ctx context.Context, mock sqlmock.Sqlmock, opts Options, conf *DBConfig) error {
		expectPrelude(mock, true)           // the migrations table already exists
		expectSelectVersion(mock, 3, false) // prints current version
		return showVersionCmd(ctx, opts, conf, "unused-socket")
	})
}

func TestForceVersion(t *testing.T) {
	withMockDB(t, func(ctx context.Context, mock sqlmock.Sqlmock, opts Options, conf *DBConfig) error {
		// Asked to force set version to 1.
		opts.Args = []string{"1"}

		expectPrelude(mock, true)           // the migrations table already exists
		expectSelectVersion(mock, 3, false) // prints current version

		expectLock(mock)

		expectSetVersion(mock, 1, false) // just sets the version without running migrations

		expectUnlock(mock)
		expectSelectVersion(mock, 3, false) // prints current version

		return forceVersionCmd(ctx, opts, conf, "unused-socket")
	})
}

/// Snippets of expectations corresponding to common query patterns.

func expectPrelude(mock sqlmock.Sqlmock, haveMigrationsTable bool) {
	mock.ExpectQuery("SELECT DATABASE()").
		WillReturnRows(sqlmock.NewRows([]string{"..."}).AddRow("unit-test-db"))

	rows := sqlmock.NewRows([]string{"tables"})
	if haveMigrationsTable {
		rows.AddRow("schema_migrations")
	}

	mock.ExpectQuery("SHOW TABLES LIKE \"schema_migrations\"").WillReturnRows(rows)
}

func expectSelectVersion(mock sqlmock.Sqlmock, version int, dirty bool) {
	// Use version == -1 as "the table is empty" signal.
	rows := sqlmock.NewRows([]string{"version", "dirty"})
	if version >= 0 {
		rows.AddRow(version, dirty)
	}
	mock.ExpectQuery("SELECT version, dirty FROM `schema_migrations` LIMIT 1").WillReturnRows(rows)
}

func expectLock(mock sqlmock.Sqlmock) {
	mock.ExpectQuery("SELECT GET_LOCK").
		WithArgs(sqlmock.AnyArg()).
		WillReturnRows(sqlmock.NewRows([]string{"..."}).AddRow(1))
}

func expectUnlock(mock sqlmock.Sqlmock) {
	mock.ExpectExec("SELECT RELEASE_LOCK").
		WithArgs(sqlmock.AnyArg()).
		WillReturnResult(sqlmock.NewResult(1, 1))
}

func expectSetVersion(mock sqlmock.Sqlmock, version int, dirty bool) {
	mock.ExpectBegin()
	mock.ExpectExec("TRUNCATE `schema_migrations`").
		WillReturnResult(sqlmock.NewResult(1, 1))
	mock.ExpectExec("INSERT INTO `schema_migrations` \\(version, dirty\\)").
		WithArgs(version, dirty).WillReturnResult(sqlmock.NewResult(1, 1))
	mock.ExpectCommit()
}
