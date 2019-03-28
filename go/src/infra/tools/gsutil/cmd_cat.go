// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"io"
	"os"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
)

const (
	// Corresponds to Python's io.DEFAULT_BUFFER_SIZE.
	defaultBufferSize = 1024 * 8
)

func catCmd(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "cat urls...",
		ShortDesc: "outputs the contents of URLs to stdout",
		LongDesc:  "Reads in files at provided GCS URLs and redirects them to stdout",

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdCat{}
			ret.logCfg.Level = logging.Info
			ret.authFlags.Register(&ret.Flags, authOpts)
			return ret
		},
	}
}

type cmdCat struct {
	subcommands.CommandRunBase
	logCfg    logging.Config
	authFlags authcli.Flags
}

func (c *cmdCat) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))
	authOpts, err := c.authFlags.Options()
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}
	client, err := storageClient(ctx, authOpts)
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}

	buf := make([]byte, defaultBufferSize)
	for _, url := range args {
		obj, err := object(client, url)
		if err != nil {
			errors.Log(ctx, err)
			return 1
		}
		reader, err := obj.NewReader(ctx)
		if err != nil {
			errors.Log(ctx, err)
			return 1
		}
		defer reader.Close()

		n, err := io.CopyBuffer(os.Stdout, reader, buf)
		if err != nil {
			errors.Log(ctx, err)
			return 1
		}
		attrs, err := obj.Attrs(ctx)
		if err != nil {
			errors.Log(ctx, err)
			return 1
		}
		if n != attrs.Size {
			logging.Errorf(
				ctx, "Read wrong size! expected(%d) != actual(%d)",
				attrs.Size, n)
			return 1
		}
	}
	return 0
}
