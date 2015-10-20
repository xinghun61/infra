// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package client

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"infra/monitoring/messages"
)

// NewReplay returns a client which will replay responses recorded in baseDir.
func NewReplay(baseDir string) Reader {
	rc := &replay{
		baseDir: baseDir,
	}
	return rc
}

type replay struct {
	baseDir string
}

// Build fetches the build summary for master master, builder builder and build id buildNum
// from build.chromium.org.
func (c *replay) Build(master, builder string, buildNum int64) (*messages.Build, error) {
	b := &messages.Build{}
	err := read(filepath.Join(c.baseDir, "build", master, builder, fmt.Sprintf("%d", buildNum)), b)
	return b, err
}

func (c *replay) LatestBuilds(master, builder string) ([]*messages.Build, error) {
	bs := []*messages.Build{}
	err := read(filepath.Join(c.baseDir, "latestbuilds", master, builder), bs)
	return bs, err
}

// TestResults fetches the results of a step failure's test run.
func (c *replay) TestResults(masterName, builderName, stepName string, buildNumber int64) (*messages.TestResults, error) {
	r := &messages.TestResults{}
	err := read(filepath.Join(c.baseDir, "testresults", masterName, builderName, stepName, fmt.Sprintf("%d", buildNumber)), r)
	return r, err
}

// BuildExtracts fetches build information for masters from CBE in parallel.
// Returns a map of url to error for any requests that had errors.
func (c *replay) BuildExtract(master string) (*messages.BuildExtract, error) {
	be := &messages.BuildExtract{}
	err := read(filepath.Join(c.baseDir, "buildextracts", master), be)
	return be, err
}

// StdioForStep fetches the standard output for a given build step, and an error if any
// occurred.
func (c *replay) StdioForStep(master, builder, step string, buildNum int64) ([]string, error) {
	s := []string{}
	err := read(filepath.Join(c.baseDir, "stdioforstep", master, builder, step, fmt.Sprintf("%d", buildNum)), &s)
	return s, err
}

// TODO(seanmccullough): Evaluate GOB encoding as a faster alternative.
func read(path string, v interface{}) error {
	f, err := os.Open(path)
	log.Infof("Reading file: %s", path)
	if err != nil {
		return err
	}
	defer f.Close()

	dec := json.NewDecoder(f)
	err = dec.Decode(v)
	return err
}
