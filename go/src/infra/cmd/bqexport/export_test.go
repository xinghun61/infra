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

var goldenPath = filepath.Join("testing", "golden.json")

func TestBQExport(t *testing.T) {
	t.Parallel()

	c := context.Background()
	exp := Exporter{
		Package: "infra/cmd/bqexport/testing",
		Name:    "TestSchema",
	}
	if *genFlag {
		if err := exp.Export(c, goldenPath); err != nil {
			t.Fatalf("failed to regenerate golden path: %s", err)
		}
		return
	}

	var gen []byte
	err := withTempDir(func(tdir string) error {
		outPath := filepath.Join(tdir, "output.json")
		if err := exp.Export(c, outPath); err != nil {
			return err
		}

		// Compare against the golden file.
		var err error
		gen, err = ioutil.ReadFile(outPath)
		return err
	})
	if err != nil {
		t.Fatalf("failed to generate schema file: %s", err)
	}

	golden, err := ioutil.ReadFile(goldenPath)
	if err != nil {
		t.Fatalf("failed to read golden file: %s", err)
	}

	if bytes.Compare(golden, gen) != 0 {
		t.Fatalf("generated file does not match golden file")
	}
}
