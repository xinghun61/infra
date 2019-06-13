// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testspec

import (
	"path/filepath"
	"testing"

	"infra/cmd/cros_test_platform/internal/testutils"
)

func TestCreation(t *testing.T) {
	d := &controlFilesLoaderImpl{}
	root, cleanup := testutils.CreateTempDirOrDie(t)
	defer cleanup()

	if err := d.Discover(root); err != nil {
		t.Errorf("Load() failed: %s", err)
	}

	if err := d.Discover(filepath.Join(root, "nonExistentDir")); err == nil {
		t.Errorf("Load() did not return error for non-existent path")
	}
}

func TestEnumeration(t *testing.T) {
	d := &controlFilesLoaderImpl{}
	root, cleanup := testutils.CreateTempDirOrDie(t)
	defer cleanup()

	cases := []struct {
		Path    string
		IsTest  bool
		IsSuite bool
	}{
		{createDummyFileOrDie(t, root, "server", "site_tests", "control"), true, false},
		{createDummyFileOrDie(t, root, "server", "site_tests", "control.gobi3k"), true, false},
		{createDummyFileOrDie(t, root, "server", "test_suites", "control"), false, true},
		{createDummyFileOrDie(t, root, "server", "autoserv"), false, false},
		{createDummyFileOrDie(t, root, "server", "site_tests", "control.py"), false, false},
		// Must ignore name matching pattern in directories.
		{createDummyFileOrDie(t, root, "server", "site_tests", "control_flow", "file"), false, false},
		{createDummyFileOrDie(t, root, "server", "test_suites", "uber_control", "problem"), false, false},
		{testutils.CreateDirOrDie(t, root, "server", "control"), false, false},
	}

	if err := d.Discover(root); err != nil {
		t.Fatalf("%s", err)
	}
	for _, c := range cases {
		_, isTest := d.Tests()[c.Path]
		if isTest != c.IsTest {
			t.Errorf("%s is in Tests(): %t, want %t", c.Path, isTest, c.IsTest)
		}
		_, isSuite := d.Suites()[c.Path]
		if isSuite != c.IsSuite {
			t.Errorf("%s is in Tests(): %t, want %t", c.Path, isSuite, c.IsSuite)
		}
	}
}

func createDummyFileOrDie(t *testing.T, path ...string) string {
	return testutils.CreateFileOrDie(t, path, "fake control")
}
