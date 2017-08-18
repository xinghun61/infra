// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"flag"
	"io/ioutil"
	"path/filepath"
	"testing"

	"golang.org/x/net/context"
)

var genFlag = flag.Bool("test.generate", false, "Instead of testing, regenerate the golden file.")

const (
	testOutDir  = "test_data"
	testOutName = "golden.json"
)

func TestBQExport(t *testing.T) {
	t.Parallel()

	c := context.Background()
	exp := Exporter{
		Package: "infra/cmd/bqexport/testing",
		Name:    "TestSchema",
	}
	if *genFlag {
		exp.OutDir = testOutDir
		if err := exp.Export(c, testOutName); err != nil {
			t.Fatalf("failed to regenerate golden path: %s", err)
		}
		return
	}

	var gen []byte
	err := withTempDir(func(tdir string) error {
		exp.OutDir = tdir
		if err := exp.Export(c, ""); err != nil {
			return err
		}

		// Compare against the golden file.
		outPath := filepath.Join(tdir, "raw_events", "testing_test_schema_table.json")
		var err error
		gen, err = ioutil.ReadFile(outPath)
		return err
	})
	if err != nil {
		t.Fatalf("failed to generate schema file: %s", err)
	}

	goldenPath := filepath.Join(testOutDir, "raw_events", testOutName)
	golden, err := ioutil.ReadFile(goldenPath)
	if err != nil {
		t.Fatalf("failed to read golden file: %s", err)
	}

	if bytes.Compare(golden, gen) != 0 {
		t.Fatalf("generated file does not match golden file")
	}
}
