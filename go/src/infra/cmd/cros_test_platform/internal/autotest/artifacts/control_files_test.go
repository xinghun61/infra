// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package artifacts_test

import (
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"infra/cmd/cros_test_platform/internal/autotest/artifacts"
	"infra/cmd/cros_test_platform/internal/testutils"

	"go.chromium.org/luci/common/errors"
)

func TestExtractControlFiles(t *testing.T) {
	outdir, cleanup := testutils.CreateTempDirOrDie(t)
	defer cleanup()
	err := artifacts.ExtractControlFiles(
		artifacts.LocalPaths{ControlFilesArchive: testDataPath("control_files.tar")},
		outdir,
	)
	if err != nil {
		t.Fatalf("failed to extract control files: %s", err)
	}
	want := filepath.Join(outdir, "autotest", "client", "site_tests", "dummy_Pass", "control")
	if !isRegularFile(want) {
		t.Errorf("File %s not created. Output: %s", want, formatDirectoryTreeOrDie(outdir))
	}
}

func testDataPath(file string) string {
	return filepath.Join("testdata", file)
}

func isRegularFile(path string) bool {
	fi, err := os.Stat(path)
	return err == nil && fi.Mode().IsRegular()
}

func formatDirectoryTreeOrDie(root string) string {
	paths := []string{}
	err := filepath.Walk(root, func(p string, fi os.FileInfo, err error) error {
		if err != nil {
			return errors.Annotate(err, "format %s", p).Err()
		}
		paths = append(paths, p)
		return nil
	})
	if err != nil {
		panic(fmt.Sprintf("formatDirectoryTreeOrDie: %s", err))
	}
	return fmt.Sprintf("%v", paths)
}

func TestExtractTestSuites(t *testing.T) {
	outdir, cleanup := testutils.CreateTempDirOrDie(t)
	defer cleanup()
	err := artifacts.ExtractControlFiles(
		artifacts.LocalPaths{TestSuitesArchive: testDataPath("test_suites.tar.bz2")},
		outdir,
	)
	if err != nil {
		t.Fatalf("failed to extract test suites: %s", err)
	}
	want := filepath.Join(outdir, "autotest", "test_suites", "control.dummy")
	if !isRegularFile(want) {
		t.Errorf("File %s not created. Output: %s", want, formatDirectoryTreeOrDie(outdir))
	}
}
