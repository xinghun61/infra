// Copyright 2018 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"os/exec"

	"go.chromium.org/luci/common/logging"
	"golang.org/x/net/context"
)

type runner struct {
	ctx  context.Context
	name string
	arg0 string
	args []string

	cwd          string
	suppressFail bool
}

func newRunner(ctx context.Context, name, arg0 string, args []string) *runner {
	return &runner{
		ctx:  ctx,
		name: name,
		arg0: arg0,
		args: args,
	}
}

func (r *runner) do() error {
	logging.Debugf(r.ctx, "%s: %q", r.name, r.args)
	cmd := exec.CommandContext(r.ctx, r.arg0, r.args...)
	cmd.Dir = r.cwd
	if r.suppressFail {
		return cmd.Run()
	}

	output, err := cmd.CombinedOutput()
	if err != nil {
		logging.WithError(err).Errorf(r.ctx, "failed: %s", string(output))
	}
	return err
}
