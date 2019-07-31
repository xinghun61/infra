// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"context"
	"io/ioutil"
	"os"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"

	"infra/cmd/cloudbuildhelper/dockerfile"
	"infra/cmd/cloudbuildhelper/registry"
)

var cmdPinsAdd = &subcommands.Command{
	UsageLine: "pins-add <pins-yaml-path> <image>[:<tag>]",
	ShortDesc: "adds a pinned docker image to the image pins YAML file",
	LongDesc: `Adds a pinned docker image to the image pins YAML file.

Resolves <image>[:<tag>] to a docker image digest and adds an entry to the
image pins YAML file. If there's such entry already, overwrites it.

Rewrites the YAML file destroying any custom formatting or comments there.
If you want to comment an entry, manually add "comment" field.

The file must exist already. If you are starting completely from scratch, create
an empty file first (e.g. using 'touch').
`,

	CommandRun: func() subcommands.CommandRun {
		c := &cmdPinsAddRun{}
		c.init()
		return c
	},
}

type cmdPinsAddRun struct {
	commandBase

	pins  string
	image string
}

func (c *cmdPinsAddRun) init() {
	c.commandBase.init(c.exec, true, []*string{
		&c.pins,
		&c.image,
	})
}

func (c *cmdPinsAddRun) exec(ctx context.Context) error {
	pinToAdd, err := dockerfile.PinFromString(c.image)
	if err != nil {
		return isCLIError.Apply(err)
	}

	pins, err := readPins(c.pins)
	if err != nil {
		return err
	}

	ts, err := c.tokenSource(ctx)
	if err != nil {
		return errors.Annotate(err, "failed to setup auth").Err()
	}
	registry := &registry.Client{TokenSource: ts}

	resolved, err := registry.GetImage(ctx, pinToAdd.ImageRef())
	if err != nil {
		return errors.Annotate(err, "resolving %q", pinToAdd.ImageRef()).Err()
	}
	pinToAdd.Digest = resolved.Digest

	logging.Infof(ctx, "%s => %s", pinToAdd.ImageRef(), resolved.Digest)
	if err := pins.Add(pinToAdd); err != nil {
		return errors.Annotate(err, "adding resolved tag").Err()
	}

	return errors.Annotate(writePins(c.pins, pins), "writing pins file").Err()
}

// readPins reads pins.yaml.
func readPins(path string) (*dockerfile.Pins, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, errors.Annotate(err, "can't read pins file").Tag(isCLIError).Err()
	}
	defer f.Close()
	pins, err := dockerfile.ReadPins(f)
	return pins, errors.Annotate(err, "malformed %q", path).Tag(isCLIError).Err()
}

// writePins writes pins.yaml.
func writePins(path string, pins *dockerfile.Pins) error {
	out := bytes.Buffer{}
	if err := dockerfile.WritePins(&out, pins); err != nil {
		return err
	}
	return ioutil.WriteFile(path, out.Bytes(), 0666)
}
