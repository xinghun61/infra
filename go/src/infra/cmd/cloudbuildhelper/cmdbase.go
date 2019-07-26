// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"fmt"
	"os"

	"github.com/maruel/subcommands"
	"golang.org/x/oauth2"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/system/signals"
)

// execCb a signature of a function that executes a subcommand.
type execCb func(ctx context.Context) error

// commandBase defines flags common to all subcommands.
type commandBase struct {
	subcommands.CommandRunBase

	exec     execCb    // called to actually execute the command
	needAuth bool      // set in init, true if we have auth flags registered
	posArgs  []*string // will be filled in by positional arguments

	logConfig logging.Config // -log-* flags
	authFlags authcli.Flags  // -auth-* flags
}

// init register base flags. Must be called.
func (c *commandBase) init(exec execCb, needAuth bool, posArgs []*string) {
	c.exec = exec
	c.needAuth = needAuth
	c.posArgs = posArgs

	c.logConfig.Level = logging.Info // default logging level
	c.logConfig.AddFlags(&c.Flags)

	if c.needAuth {
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

	if len(args) != len(c.posArgs) {
		if len(c.posArgs) == 0 {
			return handleErr(ctx, errors.Reason("unexpected positional arguments %q", args).Tag(isCLIError).Err())
		}
		return handleErr(ctx, errors.Reason(
			"expected %d positional argument(s), got %d",
			len(c.posArgs), len(args)).Tag(isCLIError).Err())
	}

	for i, arg := range args {
		*c.posArgs[i] = arg
	}

	ctx, cancel := context.WithCancel(ctx)
	signals.HandleInterrupt(cancel)

	if err := c.exec(ctx); err != nil {
		return handleErr(ctx, err)
	}
	return 0
}

// tokenSource returns a source of OAuth2 tokens (based on CLI flags) or
// auth.ErrLoginRequired if the user needs to login first.
//
// This error is sniffed by Run(...) and converted into a comprehensible error
// message, so no need to handle it specially.
//
// Panics if the command was not configured to use auth in c.init(...).
func (c *commandBase) tokenSource(ctx context.Context) (oauth2.TokenSource, error) {
	if !c.needAuth {
		panic("needAuth is false")
	}
	opts, err := c.authFlags.Options()
	if err != nil {
		return nil, errors.Annotate(err, "bad auth options").Tag(isCLIError).Err()
	}
	authn := auth.NewAuthenticator(ctx, auth.SilentLogin, opts)
	if email, err := authn.GetEmail(); err == nil {
		logging.Infof(ctx, "Running as %s", email)
	}
	return authn.TokenSource()
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
	case errors.Contains(err, context.Canceled): // happens on Ctrl+C
		fmt.Fprintf(os.Stderr, "%s\n", err)
		return 4
	case errors.Contains(err, auth.ErrLoginRequired):
		fmt.Fprintf(os.Stderr, "Need to login first by running:\n  $ %s login\n", os.Args[0])
		return 3
	case isCLIError.In(err):
		fmt.Fprintf(os.Stderr, "%s: %s\n", os.Args[0], err)
		return 2
	default:
		logging.Errorf(ctx, "%s", err)
		logging.Errorf(ctx, "Full context:")
		errors.Log(ctx, err)
		return 1
	}
}
