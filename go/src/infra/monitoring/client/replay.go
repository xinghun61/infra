// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package client

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/logging"

	"infra/monitoring/messages"
)

// NewReplay returns a client which will replay responses recorded in baseDir.
func NewReplay(baseDir string) readerType {
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
func (c *replay) Build(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64) (*messages.Build, error) {
	b := &messages.Build{}
	err := read(ctx, filepath.Join(c.baseDir, "build", master.Name(), builder, fmt.Sprintf("%d", buildNum)), b)
	return b, err
}

func (c *replay) LatestBuilds(ctx context.Context, master *messages.MasterLocation, builder string) ([]*messages.Build, error) {
	bs := []*messages.Build{}
	err := read(ctx, filepath.Join(c.baseDir, "latestbuilds", master.Name(), builder), bs)
	return bs, err
}

// BuildExtracts fetches build information for masters from CBE in parallel.
// Returns a map of url to error for any requests that had errors.
func (c *replay) BuildExtract(ctx context.Context, master *messages.MasterLocation) (*messages.BuildExtract, error) {
	be := &messages.BuildExtract{}
	err := read(ctx, filepath.Join(c.baseDir, "buildextracts", master.Name()), be)
	return be, err
}

// StdioForStep fetches the standard output for a given build step, and an error if any
// occurred.
func (c *replay) StdioForStep(ctx context.Context, master *messages.MasterLocation, builder, step string, buildNum int64) ([]string, error) {
	s := []string{}
	err := read(ctx, filepath.Join(c.baseDir, "stdioforstep", master.Name(), builder, step, fmt.Sprintf("%d", buildNum)), &s)
	return s, err
}

func (c *replay) CrbugItems(ctx context.Context, label string) ([]messages.CrbugItem, error) {
	res := []messages.CrbugItem{}
	err := read(ctx, filepath.Join(c.baseDir, "crbugitems", label), res)
	return res, err
}

// Findit fetches results from findito for a build.
func (c *replay) Findit(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64, failedSteps []string) ([]*messages.FinditResult, error) {
	s := []*messages.FinditResult{}
	err := read(ctx, filepath.Join(c.baseDir, "findit", master.Name(), builder, fmt.Sprintf("%d", buildNum)), &s)
	return s, err
}

// TODO(seanmccullough): Evaluate GOB encoding as a faster alternative.
func read(ctx context.Context, path string, v interface{}) error {
	f, err := os.Open(path)
	logging.Debugf(ctx, "Reading file: %s", path)
	if err != nil {
		return err
	}
	defer f.Close()

	dec := json.NewDecoder(f)
	err = dec.Decode(v)
	return err
}
