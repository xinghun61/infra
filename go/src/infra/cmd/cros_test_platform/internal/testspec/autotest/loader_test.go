// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package autotest

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"
)

func TestCreation(t *testing.T) {
	d := &controlFilesLoaderImpl{}
	root, cleanup := createTempDirOrDie(t)
	defer cleanup()

	if err := d.Discover(root); err != nil {
		t.Errorf("Load() failed: %s", err)
	}

	if err := d.Discover(filepath.Join(root, "nonExistentDir")); err == nil {
		t.Errorf("Load() did not return error for non-existent path")
	}
}

func createTempDirOrDie(t *testing.T) (string, func()) {
	t.Helper()
	dir, err := ioutil.TempDir("", "discoverTest")
	if err != nil {
		panic(err)
	}
	return dir, func() {
		os.RemoveAll(dir)
	}
}

func TestEnumeration(t *testing.T) {
	d := &controlFilesLoaderImpl{}
	root, cleanup := createTempDirOrDie(t)
	defer cleanup()

	cases := []struct {
		Path    string
		IsTest  bool
		IsSuite bool
	}{
		{createDummyFileOrDie(t, root, "server", "autoserv"), false, false},
		{createDummyFileOrDie(t, root, "server", "site_tests", "control"), true, false},
		{createDummyFileOrDie(t, root, "server", "site_tests", "control.gobi3k"), true, false},
		{createDummyFileOrDie(t, root, "server", "test_suites", "control"), false, true},
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
	return createFileOrDie(t, path, "fake control")
}

func createFileOrDie(t *testing.T, path []string, text string) string {
	file := path[len(path)-1]
	dir := filepath.Join(path[:len(path)-1]...)
	if err := os.MkdirAll(dir, 0755); err != nil {
		panic(err)
	}
	if err := ioutil.WriteFile(filepath.Join(dir, file), []byte(text), 0644); err != nil {
		panic(err)
	}
	return filepath.Join(dir, file)
}
