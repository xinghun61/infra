// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bufio"
	"fmt"
	"io"
	"io/ioutil"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"unicode"

	"golang.org/x/net/context"

	"github.com/mattes/migrate"
	"github.com/mattes/migrate/database/mysql"
	_ "github.com/mattes/migrate/source/file"

	"go.chromium.org/luci/common/logging"
)

// inputStream is mocked in tests.
var inputStream io.Reader = os.Stdin

// migrateLogger adapts our logger to the one used by 'migrate' package.
type migrateLogger struct {
	ctx context.Context
}

func (m migrateLogger) Printf(f string, v ...interface{}) { logging.Infof(m.ctx, "migrate: "+f, v...) }
func (m migrateLogger) Verbose() bool                     { return false }

// DefaultMigrationsPath returns a path to a directory with migration files.
func DefaultMigrationsPath() string {
	p, err := filepath.Abs("migrations")
	if err != nil {
		panic(err)
	}
	return p
}

// CreateEmptyMigration asks user for a migration title and creates two empty
// appropriately named *.sql files (for 'up' and 'down' migrations).
func CreateEmptyMigration(migrationsPath string) error {
	if err := os.MkdirAll(migrationsPath, 0777); err != nil {
		return err
	}

	// Read a line and convert to snake case.
	fmt.Printf("Enter a name for the new migration:\n> ")
	reader := bufio.NewReader(inputStream)
	name, _ := reader.ReadString('\n')
	name = strings.Map(func(r rune) rune {
		if unicode.IsSpace(r) || r == '-' {
			return '_'
		}
		return unicode.ToLower(r)
	}, strings.TrimSpace(name))

	// Grab new migration number and put last migration name into the file, so
	// that if multiple CLs with same sequence number are committed, there'll be
	// a merge conflict in 'last_version' file.
	seq, err := bumpSequenceFile(filepath.Join(migrationsPath, "last_version"), name)
	if err != nil {
		return err
	}

	base := filepath.Join(migrationsPath, fmt.Sprintf("%03d_%s", seq, name))
	files := []string{base + ".up.sql", base + ".down.sql"}
	for _, f := range files {
		fd, err := os.Create(f)
		if err != nil {
			return err
		}
		fd.Close()
		fmt.Printf("Created %s\n", f)
	}

	fmt.Println(
		"Populate these files with SQL statements to migrate schema up (for roll-forwards)\n" +
			"and down (for roll-backs). Test locally that migrations apply in both directions!")

	return nil
}

// bumpSequenceFile non-atomically increments the integer in given file and
// returns its new value.
//
// If the file doesn't exist, it is created and the integer is set to 1.
func bumpSequenceFile(path, migration string) (seq uint64, err error) {
	switch buf, err := ioutil.ReadFile(path); {
	case os.IsNotExist(err):
		seq = 0
	case err != nil:
		return 0, err
	default:
		fields := strings.Fields(string(buf))
		if len(fields) == 0 {
			return 0, fmt.Errorf("malformed last_version file %q", path)
		}
		seq, err = strconv.ParseUint(fields[0], 10, 32)
		if err != nil {
			return 0, err
		}
	}

	seq++

	str := fmt.Sprintf("%d %s\n", seq, migration)
	if err := ioutil.WriteFile(path, []byte(str), 0644); err != nil {
		return 0, err
	}

	return seq, nil
}

// WithMigrate sets up instance of migrate.Migrate and calls 'body'.
func WithMigrate(ctx context.Context, migrationsPath string, conf *DBConfig, socket string, body func(m *migrate.Migrate) error) error {
	db, err := OpenDB(ctx, socket, conf, false)
	if err != nil {
		return err
	}
	defer db.Close()

	driver, err := mysql.WithInstance(db, &mysql.Config{})
	if err != nil {
		return err
	}
	defer driver.Close()

	m, err := migrate.NewWithDatabaseInstance("file://"+filepath.ToSlash(migrationsPath), "mysql", driver)
	if err != nil {
		return err
	}
	defer m.Close()

	m.Log = migrateLogger{ctx}
	return body(m)
}

// ReportVersion logs current schema version (as fetched from the DB itself).
func ReportVersion(ctx context.Context, m *migrate.Migrate) {
	switch ver, dirty, err := m.Version(); {
	case err == migrate.ErrNilVersion:
		logging.Infof(ctx, "Current version: none")
	case err == nil && !dirty:
		logging.Infof(ctx, "Current version: %d", ver)
	case err == nil && dirty:
		logging.Warningf(ctx, "Current version: %d (dirty!)", ver)
	default:
		fmt.Println(err)
		logging.Errorf(ctx, "Current version: unknown (%s)", err)
	}
}
