// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"flag"

	flagx "go.chromium.org/luci/common/flag"
)

// createRunCommon encapsulates parameters that are common to
// all of the create-* subcommands.
type createRunCommon struct {
	board       string
	model       string
	pool        string
	image       string
	priority    int
	timeoutMins int
	tags        []string
	keyvals     []string
	qsAccount   string
	buildBucket bool
}

func (c *createRunCommon) Register(fl *flag.FlagSet) {
	fl.StringVar(&c.image, "image", "",
		`Fully specified image name to run test against,
e.g., reef-canary/R73-11580.0.0.`)
	fl.StringVar(&c.board, "board", "", "Board to run test on.")
	fl.StringVar(&c.model, "model", "", "Model to run test on.")
	fl.StringVar(&c.pool, "pool", "", "Device pool to run test on.")
	fl.IntVar(&c.priority, "priority", defaultTaskPriority,
		`Specify the priority of the test.  A high value means this test
will be executed in a low priority. If the tasks runs in a quotascheduler controlled pool, this value will be ignored.`)
	fl.IntVar(&c.timeoutMins, "timeout-mins", 30, "Task runtime timeout.")
	fl.Var(flagx.StringSlice(&c.keyvals), "keyval",
		`Autotest keyval for test. Key may not contain : character. May be
specified multiple times.`)
	fl.StringVar(&c.qsAccount, "qs-account", "", "Quota Scheduler account to use for this task.  Optional.")
	fl.Var(flagx.StringSlice(&c.tags), "tag", "Swarming tag for test; may be specified multiple times.")
	fl.BoolVar(&c.buildBucket, "bb", false, "Use buildbucket recipe backend.")
}

func (c *createRunCommon) ValidateArgs(fl flag.FlagSet) error {
	if c.board == "" {
		return NewUsageError(fl, "missing -board")
	}
	if c.pool == "" {
		return NewUsageError(fl, "missing -pool")
	}
	if c.image == "" {
		return NewUsageError(fl, "missing -image")
	}
	if c.priority < 50 || c.priority > 255 {
		return NewUsageError(fl, "priority should in [50,255]")
	}
	return nil
}
