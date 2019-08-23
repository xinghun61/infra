// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"flag"
	"fmt"
	"time"

	"go.chromium.org/luci/common/data/strpair"
	flagx "go.chromium.org/luci/common/flag"

	"infra/cmd/skylab/internal/cmd/recipe"
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
	fl.BoolVar(&c.buildBucket, "bb", true, "(Default: True) Use buildbucket recipe backend.")
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

func (c *createRunCommon) RecipeArgs() (recipe.Args, error) {
	keyvalMap, err := toKeyvalMap(c.keyvals)
	if err != nil {
		return recipe.Args{}, err
	}

	return recipe.Args{
		Board:        c.board,
		Image:        c.image,
		Model:        c.model,
		Pool:         c.pool,
		QuotaAccount: c.qsAccount,
		Timeout:      time.Duration(c.timeoutMins) * time.Minute,
		Keyvals:      keyvalMap,
		Priority:     int64(c.priority),
		Tags:         c.tags,
	}, nil
}

func (c *createRunCommon) BuildTags() []string {
	ts := c.tags
	ts = append(ts, fmt.Sprintf("priority:%d", c.priority))
	if c.image != "" {
		ts = append(ts, fmt.Sprintf("build:%s", c.image))
	}
	if c.board != "" {
		ts = append(ts, fmt.Sprintf("label-board:%s", c.board))
	}
	if c.model != "" {
		ts = append(ts, fmt.Sprintf("label-model:%s", c.model))
	}
	if c.pool != "" {
		ts = append(ts, fmt.Sprintf("label-pool:%s", c.pool))
	}
	return ts
}

func toKeyvalMap(keyvals []string) (map[string]string, error) {
	m := make(map[string]string, len(keyvals))
	for _, s := range keyvals {
		k, v := strpair.Parse(s)
		if v == "" {
			return nil, fmt.Errorf("malformed keyval with key '%s' has no value", k)
		}
		if _, ok := m[k]; ok {
			return nil, fmt.Errorf("keyval with key %s specified more than once", k)
		}
		m[k] = v
	}
	return m, nil
}
