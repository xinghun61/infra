// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/flag/flagenum"
	"github.com/luci/luci-go/common/system/environ"
	"github.com/luci/luci-go/swarming/tasktemplate"
)

type cookModeFlag struct {
	cookMode
}

var (
	cookSwarming = cookModeFlag{swarmingCookMode{}}

	cookModeFlagEnum = flagenum.Enum{
		"swarming": cookSwarming,
	}
)

// String implements flag.Value.
func (m *cookModeFlag) String() string {
	return cookModeFlagEnum.FlagString(*m)
}

// Set implements flag.Value.
func (m *cookModeFlag) Set(v string) error {
	return cookModeFlagEnum.FlagSet(m, v)
}

// cookMode integrates environment-specific behaviors into Kitchen's "cook"
// command.
type cookMode interface {
	fillTemplateParams(env environ.Env, params *tasktemplate.Params) error
	needsIOKeepAlive() bool
	botID(env environ.Env) (string, error)
}

type swarmingCookMode struct{}

func (m swarmingCookMode) fillTemplateParams(env environ.Env, params *tasktemplate.Params) error {
	var ok bool
	if params.SwarmingRunID, ok = env.Get("SWARMING_TASK_ID"); !ok {
		return errors.New("no Swarming run ID in enviornment")
	}
	return nil
}

func (m swarmingCookMode) needsIOKeepAlive() bool { return false }

func (m swarmingCookMode) botID(env environ.Env) (string, error) {
	botID, ok := env.Get("SWARMING_BOT_ID")
	if !ok {
		return "", errors.Reason("a valid bot id was expected in $SWARMING_BOT_ID").Err()
	}
	return botID, nil
}
