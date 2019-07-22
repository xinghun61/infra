// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package manifest defines structure of YAML files with target definitions.
package manifest

import (
	"io"
	"io/ioutil"
	"path/filepath"

	"gopkg.in/yaml.v2"

	"go.chromium.org/luci/common/errors"
)

// Manifest is a definition of what to build, how and where.
type Manifest struct {
	// ContextDir is a unix-style path to the docker context directory to ingest
	// (usually a directory with Dockerfile), relative to this YAML file.
	//
	// All symlinks there are resolved to their targets. Only +w and +x file mode
	// bits are preserved. All other file metadata (owners, setuid bits,
	// modification times) are ignored.
	//
	// If not set, the context directory is assumed empty.
	ContextDir string `yaml:"contextdir"`
}

// Read reads the manifest and rebases all relative paths in it on top of 'cwd'.
func Read(r io.Reader, cwd string) (*Manifest, error) {
	body, err := ioutil.ReadAll(r)
	if err != nil {
		return nil, errors.Annotate(err, "failed to read the manifest body").Err()
	}

	out := Manifest{}
	if err = yaml.Unmarshal(body, &out); err != nil {
		return nil, errors.Annotate(err, "failed to parse the manifest").Err()
	}

	if out.ContextDir != "" {
		out.ContextDir = filepath.Join(cwd, filepath.FromSlash(out.ContextDir))
	}

	return &out, nil
}
