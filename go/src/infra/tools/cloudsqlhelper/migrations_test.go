// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"io/ioutil"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestCreateEmptyMigration(t *testing.T) {
	tmp, err := ioutil.TempDir("", "cloudsqlhelper")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmp)

	inputStream = bytes.NewBufferString(" name 1 ABC-def \n")
	if err = CreateEmptyMigration(tmp); err != nil {
		t.Fatal(err)
	}

	inputStream = bytes.NewBufferString(" name 2 \n")
	if err = CreateEmptyMigration(tmp); err != nil {
		t.Fatal(err)
	}

	files, err := ioutil.ReadDir(tmp)
	if err != nil {
		t.Fatal(err)
	}

	all := map[string]string{}
	for _, f := range files {
		body, err := ioutil.ReadFile(filepath.Join(tmp, f.Name()))
		if err != nil {
			t.Error(err)
		} else {
			all[f.Name()] = string(body)
		}
	}

	expected := map[string]string{
		"001_name_1_abc_def.down.sql": "",
		"001_name_1_abc_def.up.sql":   "",
		"002_name_2.down.sql":         "",
		"002_name_2.up.sql":           "",
		"last_version":                "2 name_2\n",
	}
	if !reflect.DeepEqual(all, expected) {
		t.Fatalf("%s != %s", all, expected)
	}
}
