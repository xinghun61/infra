// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

const goodConfig = `
databases:

# Comment, blah.
- id: dev
  user: ${user}
  db: dev-${user}
  cloud_sql_instance: cloud-project-dev:us-central1:sql-db-dev
  local_socket: /var/tmp/cloud-sql/cloud-project-dev:us-central1:sql-db-dev

- id: staging
  user: root
  db: staging
  local_socket: /var/tmp/cloud-sql/cloud-project-dev:us-central1:sql-db-dev

- id: prod
  user: root
  db: prod
  cloud_sql_instance: cloud-project-prod:us-central1:sql-db-prod
  require_password: true
`

func dropFile(body string) (string, func(), error) {
	f, err := ioutil.TempFile("", "cloudsqlhelper")
	if err != nil {
		return "", nil, err
	}
	cleanup := func() {
		f.Close()
		os.Remove(f.Name())
	}
	if _, err := f.WriteString(body); err != nil {
		cleanup()
		return "", nil, err
	}
	f.Close()
	return f.Name(), cleanup, nil
}

func TestReadConfigHappyPath(t *testing.T) {
	path, cleanup, err := dropFile(goodConfig)
	if err != nil {
		t.Fatal(err)
	}
	defer cleanup()

	cfg, err := ReadConfig(path, map[string]string{"user": "os_user"})
	if err != nil {
		t.Fatal(err)
	}

	expected := &Config{
		Databases: []*DBConfig{
			{
				ID:               "dev",
				User:             "os_user",
				DB:               "dev-os_user",
				CloudSQLInstance: "cloud-project-dev:us-central1:sql-db-dev",
				LocalSocket:      "/var/tmp/cloud-sql/cloud-project-dev:us-central1:sql-db-dev",
			},
			{
				ID:          "staging",
				User:        "root",
				DB:          "staging",
				LocalSocket: "/var/tmp/cloud-sql/cloud-project-dev:us-central1:sql-db-dev",
			},
			{
				ID:               "prod",
				User:             "root",
				DB:               "prod",
				CloudSQLInstance: "cloud-project-prod:us-central1:sql-db-prod",
				RequirePassword:  true,
			},
		},
	}

	if !reflect.DeepEqual(cfg, expected) {
		t.Errorf("%s != %s", cfg, expected)
	}
}

func TestReadConfigMissing(t *testing.T) {
	if _, err := ReadConfig(filepath.Join(os.TempDir(), "some-random-missing-path"), nil); err == nil {
		t.Fatal("should have failed, but it didn't")
	}
}

func TestReadConfigBroken(t *testing.T) {
	path, cleanup, err := dropFile("not a yaml")
	if err != nil {
		t.Fatal(err)
	}
	defer cleanup()

	if _, err := ReadConfig(path, nil); err == nil {
		t.Fatal("should have failed, but it didn't")
	}
}

func TestReadConfigValidation(t *testing.T) {
	cases := []struct {
		cfg string
		err string
	}{
		{
			`{"databases":[{"id": "dev"}]}`,
			`bad config - in "dev", 'user' is required`,
		},
		{
			`{"databases":[{"id": "dev", "user": "blah"}]}`,
			`bad config - in "dev", 'db' is required`,
		},
		{
			`{"databases":[{"id": "dev", "user": "blah", "db": "blah"}]}`,
			`bad config - in "dev", 'local_socket' is required if 'cloud_sql_instance' is not set`,
		},
		{
			`{"databases":[{"id": "dev", "user": "blah", "db": "blah"}]}`,
			`bad config - in "dev", 'local_socket' is required if 'cloud_sql_instance' is not set`,
		},
		{
			`{"databases":[{"id": "dev", "user": "blah", "db": "blah", "cloud_sql_instance": "zzzz"}]}`,
			`bad config - in "dev", 'cloud_sql_instance' ("zzzz") should have form <project>:<zone>:<instance>`,
		},
		{
			`{"databases":[{"id": "dev", "user": "blah", "db": "blah", "cloud_sql_instance": "a:b:c", "local_socket": "/zzz"}]}`,
			`bad config - in "dev", 'local_socket' path "/zzz" must end in "a:b:c"`,
		},
	}
	for idx, c := range cases {
		path, cleanup, err := dropFile(c.cfg)
		if err != nil {
			t.Error(err)
		} else {
			defer cleanup()
			errMsg := ""
			if _, err := ReadConfig(path, nil); err != nil {
				errMsg = err.Error()
			}
			if errMsg != c.err {
				t.Errorf("for case %d, %q != %q", idx, errMsg, c.err)
			}
		}
	}
}
