// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"database/sql"
	"fmt"
	"io/ioutil"
	"os/user"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v2"
)

// Config defines a list of databases we can connect to.
//
// It is stored as dbs.yaml configuration file.
type Config struct {
	Databases []*DBConfig `yaml:"databases"`
}

// DBConfig describes how to connect to a MySql database.
type DBConfig struct {
	// ID is logical name of the DB, used only locally to identify the config.
	//
	// For example: 'staging', 'dev', 'prod'.
	ID string `yaml:"id"`

	// User is a mysql user to connect as (e.g. 'root').
	//
	// Can be literal '${user}', to connect as current OS user.
	User string `yaml:"user"`

	// DB is name of the database to connect to.
	//
	// Can contains literal '${user}', will be substituted by current OS user.
	DB string `yaml:"db"`

	// CloudSQLInstance is <cloud-project>:<region>:<cloud-sql-instance> string.
	//
	// If specified, server socket will be proxied through 'cloud_sql_proxy' to
	// the specified Cloud SQL instance (using gcloud's Application Default
	// Credentials for authentication).
	CloudSQLInstance string `yaml:"cloud_sql_instance"`

	// LocalSocket is a path to UNIX domain socket of a local MySql server.
	//
	// If empty and CloudSQLInstance is used, will be auto-generated.
	//
	// If not empty and CloudSQLInstance is used, it MUST end with
	// CloudSQLInstance value. This is limitation of weired cloud_sql_proxy CLI
	// interface.
	//
	// For example, if CloudSQLInstance is 'proj:us-central-1:db', then
	// LocalSocket may be '/var/tmp/sql_dev/proj:us-central-1:db'.
	//
	// If CloudSQLInstance is not used, must be set to a path to local listening
	// socket.
	LocalSocket string `yaml:"local_socket"`

	// RequirePassword, if true, indicates that the tool should ask for MySql user
	// password before proceeding.
	//
	// We use passwords only as a second authentication layer (the primary one
	// being Cloud's IAM, implemented by 'cloud_sql_proxy').
	//
	// It's a good idea to require a password for production database, as a
	// reminder for users that touching it is a big deal.
	RequirePassword bool `yaml:"require_password"`

	// openDBMock is used in unit tests to substitute real DB with a mock.
	//
	// See 'OpenDB' function.
	openDBMock func() (*sql.DB, error)
}

// DefaultConfigPath is a absolute path to ${cwd}/dbs.yaml.
func DefaultConfigPath() string {
	p, err := filepath.Abs("dbs.yaml")
	if err != nil {
		panic(err)
	}
	return p
}

// ConfigVars returns variables to interpolate inside a config.
//
// Each '${key}' will be replaced by corresponding value from the map.
func ConfigVars() (map[string]string, error) {
	u, err := user.Current()
	if err != nil {
		return nil, fmt.Errorf("failed to lookup current OS user - %s", err)
	}
	return map[string]string{
		"user": u.Username,
	}, nil
}

// ReadConfig reads and validates the YAML configuration file with databases.
func ReadConfig(path string, vars map[string]string) (*Config, error) {
	path, err := filepath.Abs(path)
	if err != nil {
		return nil, err
	}
	data, err := ioutil.ReadFile(path)
	if err != nil {
		return nil, err
	}

	out := &Config{}
	if err = yaml.Unmarshal(data, out); err != nil {
		return nil, err
	}

	// Collect a list of pointers to strings to interpolate using 'vars'.
	toInterpolate := []*string{}
	for _, db := range out.Databases {
		toInterpolate = append(toInterpolate, []*string{
			&db.ID, &db.User, &db.DB, &db.CloudSQLInstance, &db.LocalSocket,
		}...)
	}

	// Interpolate them.
	interpol := func(s string) string {
		for k, v := range vars {
			s = strings.Replace(s, "${"+k+"}", v, -1)
		}
		return s
	}
	for _, str := range toInterpolate {
		*str = interpol(*str)
	}

	// Some minimal validation.
	for _, db := range out.Databases {
		if db.User == "" {
			return nil, fmt.Errorf("bad config - in %q, 'user' is required", db.ID)
		}
		if db.DB == "" {
			return nil, fmt.Errorf("bad config - in %q, 'db' is required", db.ID)
		}
		if db.CloudSQLInstance == "" {
			if db.LocalSocket == "" {
				return nil, fmt.Errorf("bad config - in %q, 'local_socket' is required if 'cloud_sql_instance' is not set", db.ID)
			}
		} else {
			chunks := strings.Split(db.CloudSQLInstance, ":")
			if len(chunks) != 3 {
				return nil, fmt.Errorf(
					"bad config - in %q, 'cloud_sql_instance' (%q) should have form <project>:<zone>:<instance>",
					db.ID, db.CloudSQLInstance)
			}
			if db.LocalSocket != "" && !strings.HasSuffix(db.LocalSocket, db.CloudSQLInstance) {
				return nil, fmt.Errorf(
					"bad config - in %q, 'local_socket' path %q must end in %q",
					db.ID, db.LocalSocket, db.CloudSQLInstance)
			}
		}
	}

	return out, nil
}
