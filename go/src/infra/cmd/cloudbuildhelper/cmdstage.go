// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"

	"infra/cmd/cloudbuildhelper/builder"
	"infra/cmd/cloudbuildhelper/dockerfile"
	"infra/cmd/cloudbuildhelper/manifest"
)

var cmdStage = &subcommands.Command{
	UsageLine: "stage -target-manifest <path> -output-tarball <path> [...]",
	ShortDesc: "prepares the tarball with the context directory",
	LongDesc: `Prepares the tarball with the context directory.

Evaluates input YAML manifest specified via "-target-manifest" and executes all
local build steps there. Writes the resulting context dir to a *.tar.gz file
specified via "-output-tarball". The contents of this tarball is exactly what
will be sent to the docker daemon or to a Cloud Build worker.
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
	outputTarball  string
}

func (c *cmdStageRun) init() {
	c.commandBase.init(c.exec, false) // no auth

	c.Flags.StringVar(&c.targetManifest, "target-manifest", "", "Where to read YAML with input from.")
	c.Flags.StringVar(&c.outputTarball, "output-tarball", "", "Where to write the tarball with the context dir.")
}

func (c *cmdStageRun) exec(ctx context.Context) error {
	switch {
	case c.targetManifest == "":
		return errBadFlag("-target-manifest", "this flag is required")
	case c.outputTarball == "":
		return errBadFlag("-output-tarball", "this flag is required")
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
	logging.Infof(ctx, "Writing %d files to %s...", out.Len(), c.outputTarball)
	hash, err := out.ToTarGzFile(c.outputTarball)
	if err != nil {
		return errors.Annotate(err, "failed to save the output").Err()
	}
	logging.Infof(ctx, "Resulting tarball SHA256 is %q", hash)
	return b.Close()
}
