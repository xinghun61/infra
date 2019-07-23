// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"

	"infra/cmd/cloudbuildhelper/builder"
	"infra/cmd/cloudbuildhelper/dockerfile"
	"infra/cmd/cloudbuildhelper/fileset"
	"infra/cmd/cloudbuildhelper/manifest"
)

var cmdStage = &subcommands.Command{
	UsageLine: "stage -target-manifest <path> -output-location <path> [...]",
	ShortDesc: "prepares the context directory or tarball",
	LongDesc: `Prepares the context directory or tarball.

Evaluates input YAML manifest specified via "-target-manifest" and executes all
local build steps there. Materializes the resulting context dir in a location
specified by "-output-location". If it ends in "*.tar.gz", then the result is
a tarball, otherwise it is a new directory (attempting to output to an existing
directory is an error).

The contents of this directory/tarball is exactly what will be sent to the
docker daemon or to a Cloud Build worker.
`,

	CommandRun: func() subcommands.CommandRun {
		c := &cmdStageRun{}
		c.init()
		return c
	},
}

type cmdStageRun struct {
	commandBase

	targetManifest string
	outputLocation string
}

func (c *cmdStageRun) init() {
	c.commandBase.init(c.exec, false) // no auth

	c.Flags.StringVar(&c.targetManifest, "target-manifest", "", "Where to read YAML with input from.")
	c.Flags.StringVar(&c.outputLocation, "output-location", "", "Where to put the prepared context dir.")
}

func (c *cmdStageRun) exec(ctx context.Context) error {
	switch {
	case c.targetManifest == "":
		return errBadFlag("-target-manifest", "this flag is required")
	case c.outputLocation == "":
		return errBadFlag("-output-location", "this flag is required")
	}

	// Read the input manifest, make sure it parses correctly.
	r, err := os.Open(c.targetManifest)
	if err != nil {
		return errBadFlag("-target-manifest", err.Error())
	}
	defer r.Close()
	m, err := manifest.Read(r, filepath.Dir(c.targetManifest))
	if err != nil {
		return errBadFlag("-target-manifest", fmt.Sprintf("bad manifest file %q", c.targetManifest))
	}

	// Verify -output-location, prepare the corresponding writer (tar.gz or dir).
	var outWriter filesetWriter
	if strings.HasSuffix(c.outputLocation, ".tar.gz") {
		outWriter, err = tarballWriter(c.outputLocation)
	} else {
		outWriter, err = directoryWriter(c.outputLocation)
	}
	if err != nil {
		return errBadFlag("-output-location", err.Error())
	}

	// Load Dockerfile and resolve image tags there into digests using pins.yaml.
	var dockerFileBody []byte
	if m.Dockerfile != "" {
		dockerFileBody, err = dockerfile.LoadAndResolve(m.Dockerfile, m.ImagePins)
		if err != nil {
			return errors.Annotate(err, "when resolving Dockerfile").Err()
		}
	}

	// Execute all build steps to get the resulting fileset.Set.
	b, err := builder.New()
	if err != nil {
		return errors.Annotate(err, "failed to initialize Builder").Err()
	}
	defer b.Close()
	out, err := b.Build(ctx, m)
	if err != nil {
		return errors.Annotate(err, "local build failed").Err()
	}

	// Append resolved Dockerfile to outputs (perhaps overwriting an existing
	// unresolved one). In tarballs produced by cloudbuildhelper the Dockerfile
	// *always* lives in the root of the context directory.
	if m.Dockerfile != "" {
		if err := out.AddFromMemory("Dockerfile", dockerFileBody, nil); err != nil {
			return errors.Annotate(err, "failed to add Dockerfile to output").Err()
		}
	}

	// Save the build result.
	if err := outWriter(ctx, out); err != nil {
		return errors.Annotate(err, "failed to save the output").Err()
	}
	return b.Close()
}

type filesetWriter func(context.Context, *fileset.Set) error

func tarballWriter(location string) (filesetWriter, error) {
	return func(c context.Context, fs *fileset.Set) error {
		logging.Infof(c, "Writing %d files to %s...", fs.Len(), location)
		hash, err := fs.ToTarGzFile(location)
		if err != nil {
			return err
		}
		logging.Infof(c, "Resulting tarball SHA256 is %q", hash)
		return nil
	}, nil
}

func directoryWriter(location string) (filesetWriter, error) {
	if _, err := os.Stat(location); !os.IsNotExist(err) {
		if err == nil {
			return nil, errors.Reason("directory %q already exists, overwrites aren't allowed", location).Err()
		}
		return nil, err
	}
	return func(c context.Context, fs *fileset.Set) error {
		logging.Infof(c, "Copying %d files into %s...", fs.Len(), location)
		if err := os.Mkdir(location, 0777); err != nil {
			return err
		}
		return fs.Materialize(location)
	}, nil
}
