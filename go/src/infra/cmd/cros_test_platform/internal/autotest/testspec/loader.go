// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testspec

import (
	"io"
	"os"
	"path/filepath"
	"regexp"

	"go.chromium.org/luci/common/errors"
)

// controlFileLoader needs a docstring
type controlFilesLoaderImpl struct {
	tests  map[string]io.Reader
	suites map[string]io.Reader
}

// Tests returns the paths to test control files discovered.
func (d *controlFilesLoaderImpl) Tests() map[string]io.Reader {
	return d.tests
}

// Suites returns the paths to suite control files discovered.
func (d *controlFilesLoaderImpl) Suites() map[string]io.Reader {
	return d.suites
}

// Discover finds the control files in the directory tree rooted at root.
//
// Discover returns an error if it is unable to read any path in the directory
// tree.
func (d *controlFilesLoaderImpl) Discover(root string) error {
	d.reset()
	if err := filepath.Walk(root, d.walkFunc); err != nil {
		d.reset()
		return errors.Annotate(err, "Load(%s)", root).Err()
	}
	return nil
}

func (d *controlFilesLoaderImpl) reset() {
	d.tests = make(map[string]io.Reader)
	d.suites = make(map[string]io.Reader)
}

func (d *controlFilesLoaderImpl) walkFunc(path string, info os.FileInfo, err error) error {
	if err != nil {
		return err
	}
	if isTestControl(path) {
		d.tests[path] = openROLazy(path)
	}
	if isSuiteControl(path) {
		d.suites[path] = openROLazy(path)
	}
	return nil
}

func isTestControl(path string) bool {
	return isControl(path) && !isSuiteControl(path)
}

func isSuiteControl(path string) bool {
	return isControl(path) && isInDir("test_suites", path)
}

var controlFilePattern = regexp.MustCompile(`control(\..*)?`)

func isControl(path string) bool {
	return controlFilePattern.MatchString(path)
}

func isInDir(dir, path string) bool {
	return filepath.Base(filepath.Dir(path)) == dir
}
