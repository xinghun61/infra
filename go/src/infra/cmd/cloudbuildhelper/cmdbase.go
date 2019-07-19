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

	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
)

// execCb a signature of a function that executes a subcommand.
type execCb func(ctx context.Context) error

// commandBase defines flags common to all subcommands.
type commandBase struct {
	subcommands.CommandRunBase

	exec execCb // called to actually execute the command

	logConfig logging.Config // -log-* flags
	authFlags authcli.Flags  // -auth-* flags
}

// init register base flags. Must be called.
func (c *commandBase) init(exec execCb, needAuth bool) {
	c.exec = exec

	c.logConfig.Level = logging.Info // default logging level
	c.logConfig.AddFlags(&c.Flags)

	if needAuth {
		c.authFlags.Register(&c.Flags, authOptions()) // see main.go
	}
}

// ModifyContext implements cli.ContextModificator.
//
// Used by cli.Application.
func (c *commandBase) ModifyContext(ctx context.Context) context.Context {
	return c.logConfig.Set(ctx)
}

// Run implements the subcommands.CommandRun interface.
func (c *commandBase) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := cli.GetContext(a, c, env)
	if len(args) != 0 {
		return handleErr(ctx, errors.Reason("unexpected positional arguments %q", args).Tag(isCLIError).Err())
	}
	if err := c.exec(ctx); err != nil {
		return handleErr(ctx, err)
	}
	return 0
}

// isCLIError is tagged into errors caused by bad CLI flags.
var isCLIError = errors.BoolTag{Key: errors.NewTagKey("bad CLI invocation")}

// errBadFlag produces an error related to malformed or absent CLI flag
func errBadFlag(flag, msg string) error {
	return errors.Reason("bad %q: %s", flag, msg).Tag(isCLIError).Err()
}

// handleErr prints the error and returns the process exit code.
func handleErr(ctx context.Context, err error) int {
	switch {
	case err == nil:
		return 0
	case isCLIError.In(err):
		executable, eErr := os.Executable()
		if eErr != nil {
			executable = "<unknown executable>"
		} else {
			executable = filepath.Base(executable)
		}
		fmt.Fprintf(os.Stderr, "%s: %s\n", executable, err)
		return 2
	default:
		errors.Log(ctx, err)
		return 1
	}
}
