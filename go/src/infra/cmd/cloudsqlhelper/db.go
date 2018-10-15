// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bufio"
	"database/sql"
	"fmt"
	"os"
	"strings"

	_ "github.com/go-sql-driver/mysql"
	"golang.org/x/net/context"

	"go.chromium.org/luci/common/logging"
)

// OpenDB opens a connection to a MySql database listening to given unix socket.
//
// If 'rootDB' is true, will connect to default 'mysql' DB (useful when creating
// or dropping DBs).
func OpenDB(ctx context.Context, socket string, conf *DBConfig, rootDB bool) (*sql.DB, error) {
	if conf.openDBMock != nil {
		return conf.openDBMock()
	}

	logging.Infof(ctx, "Connecting to %s DB (%q at %s) as %q...", conf.ID, conf.DB, conf.CloudSQLInstance, conf.User)

	dbName := conf.DB
	if rootDB {
		dbName = ""
	}

	password := ""
	if conf.RequirePassword {
		var err error
		password, err = ReadPassword(
			fmt.Sprintf("Enter password for user %q on %s (for %s DB):", conf.User, conf.CloudSQLInstance, conf.ID))
		if err != nil {
			return nil, err
		}
	}

	// Note: multiStatements is needed by 'migrate' library.
	return sql.Open("mysql", fmt.Sprintf("%s:%s@unix(%s)/%s?multiStatements=true", conf.User, password, socket, dbName))
}

// ReadPassword reads a DB user password from terminal.
func ReadPassword(prompt string) (string, error) {
	// TODO(vadimsh): Disable terminal echo. This is not trivial...
	fmt.Println(strings.Repeat("-", 80))
	fmt.Println(prompt)
	fmt.Println(strings.Repeat("-", 80))
	fmt.Printf("> ")
	reader := bufio.NewReader(os.Stdin)
	pwd, _ := reader.ReadString('\n')
	return strings.TrimSpace(pwd), nil
}
