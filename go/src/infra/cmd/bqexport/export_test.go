// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"flag"
	"io"
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	bq "infra/cmd/bqexport/testing"

	"golang.org/x/net/context"
)

var genFlag = flag.Bool("test.generate", false, "Instead of testing, regenerate the golden file.")

// TestBQExport tests the correctness of "bqexport"-generated Go code. It does
// this by loading a testing schema protobuf from the "testing" sub-package,
// generating Go code, comparing it to a golden template
// (test_data/golden.gen.go), and finally compiling a test program using it and
// ensuring that the BigQuery-inferred schema from the struct round-trips back
// to the source TableDef protobuf.
//
// If generation is updated, the golden image can automatically be regenerated
// by passing the "-test.generate" flag to the test. This will NOT run the test,
// but will instead have it regenerate the schema.
//
// Finally, the "test_data" directory is a viable "main" package that can be run
// using "go run" to test the round-trip testing logic against the generated
// golden image.
func TestBQExport(t *testing.T) {
	t.Parallel()

	c := context.Background()

	const (
		packageName = "main"
		structName  = "TestSchema"

		testOutDir = "test_data"
	)

	testOutPath := filepath.Join(testOutDir, "golden.gen.go")
	if *genFlag {
		if err := Export(c, &bq.TestSchemaTable, packageName, structName, testOutPath); err != nil {
			t.Fatalf("failed to regenerate golden path: %s", err)
		}
		return
	}

	var gen []byte
	err := withTempDir(func(tdir string) error {
		outPath := filepath.Join(tdir, "test_output.gen.go")
		if err := Export(c, &bq.TestSchemaTable, packageName, structName, outPath); err != nil {
			return err
		}

		// Compare against the golden file.
		var err error
		gen, err = ioutil.ReadFile(outPath)
		if err != nil {
			t.Fatalf("Could not read output path: %s", err)
		}

		if err := copyFile(filepath.Join(testOutDir, "main.go"), filepath.Join(tdir, "main.go")); err != nil {
			t.Fatalf("Could not copy 'main.go': %s", err)
		}

		cmd := exec.CommandContext(c, "go", "run", "main.go", "test_output.gen.go")
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		cmd.Dir = tdir
		if err := cmd.Run(); err != nil {
			t.Fatalf("Could not verify output: %s", err)
		}
		return nil
	})
	if err != nil {
		t.Fatalf("failed to generate/validate schema file: %s", err)
	}

	golden, err := ioutil.ReadFile(testOutPath)
	if err != nil {
		t.Fatalf("failed to read golden file: %s", err)
	}

	if bytes.Compare(golden, gen) != 0 {
		t.Fatalf("generated file does not match golden file")
	}
}

func withTempDir(fn func(string) error) error {
	tdir, err := ioutil.TempDir("", "bqexport_test")
	if err != nil {
		return err
	}
	defer func() {
		os.RemoveAll(tdir)
	}()
	return fn(tdir)
}

func copyFile(src, dst string) error {
	srcF, err := os.Open(src)
	if err != nil {
		return err
	}
	defer srcF.Close()

	dstF, err := os.Create(dst)
	if err != nil {
		return err
	}

	if _, err := io.Copy(dstF, srcF); err != nil {
		dstF.Close()
		return err
	}

	return dstF.Close()
}
