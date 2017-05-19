// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package cookflags

import (
	"github.com/luci/luci-go/common/flag/flagenum"
	"github.com/luci/luci-go/common/system/environ"
	"github.com/luci/luci-go/swarming/tasktemplate"
)

// CookMode indicates the value of the -mode flag for kitchen.
type CookMode int

// Set implements flag.Value.
func (m *CookMode) Set(v string) error {
	return cookModeFlagEnum.FlagSet(m, v)
}

// These are the valid options for CookMode (with the obvious exception of the
// zero-value InvalidCookMode :)).
const (
	InvalidCookMode CookMode = iota
	CookSwarming
	CookBuildBot
)

var cookModeFlagEnum = flagenum.Enum{
	"swarming": CookSwarming,
	"buildbot": CookBuildBot,
}

// ReadSwarmingEnv reads relevent data out of the environment.
func ReadSwarmingEnv(env environ.Env) (botID, runID string, err error) {
	var ok bool
	botID, ok = env.Get("SWARMING_BOT_ID")
	if !ok {
		err = inputError("no Swarming bot ID in $SWARMING_BOT_ID")
		return
	}

	if runID, ok = env.Get("SWARMING_TASK_ID"); !ok {
		err = inputError("no Swarming run ID in $SWARMING_TASK_ID")
		return
	}
	return
}

func (m CookMode) FillTemplateParams(env environ.Env, params *tasktemplate.Params) error {
	switch m {
	case CookSwarming:
		_, runID, err := ReadSwarmingEnv(env)
		if err != nil {
			return err
		}
		params.SwarmingRunID = runID
	}
	return nil
}

func (m CookMode) onlyLogDog() bool {
	return m == CookSwarming
}
