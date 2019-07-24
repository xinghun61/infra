// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"fmt"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/common/errors"
)

var cmdBuild = &subcommands.Command{
	UsageLine: "build <target-manifest-path> [...]",
	ShortDesc: "builds a docker image using Google Cloud Build",
	LongDesc: `Builds a docker image using Google Cloud Build.

TODO(vadimsh): Write mini doc.
`,

	CommandRun: func() subcommands.CommandRun {
		c := &cmdBuildRun{}
		c.init()
		return c
	},
}

type cmdBuildRun struct {
	commandBase

	targetManifest string
	infra          string
}

func (c *cmdBuildRun) init() {
	c.commandBase.init(c.exec, true, []*string{
		&c.targetManifest,
	})
	c.Flags.StringVar(&c.infra, "infra", "dev", "What section to pick from 'infra' field in the YAML.")
}

func (c *cmdBuildRun) exec(ctx context.Context) error {
	m, err := readManifest(c.targetManifest)
	if err != nil {
		return err
	}

	infra, ok := m.Infra[c.infra]
	if !ok {
		return errBadFlag("-infra", fmt.Sprintf("no %q infra specified in the manifest", c.infra))
	}

	// Need a token source to talk to Google Storage and Cloud Build.
	ts, err := c.tokenSource(ctx)
	if err != nil {
		return errors.Annotate(err, "failed to setup auth").Err()
	}

	// TODO(vadimsh): Implement.
	_ = infra
	_ = ts
	return nil
}
