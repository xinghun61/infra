// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"net/url"

	"github.com/luci/luci-go/common/flag/flagenum"
	"github.com/luci/luci-go/common/system/environ"
	"github.com/luci/luci-go/swarming/tasktemplate"
)

type cookModeFlag struct {
	cookMode
}

var (
	cookSwarming = cookModeFlag{swarmingCookMode{}}
	cookBuildBot = cookModeFlag{buildBotCookMode{}}

	cookModeFlagEnum = flagenum.Enum{
		"swarming": cookSwarming,
		"buildbot": cookBuildBot,
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
	shouldEmitTimestamps() bool
	alwaysForwardAnnotations() bool
	botID(env environ.Env) (string, error)

	shouldEmitLogDogLinks() bool
	addLogDogGlobalTags(tags map[string]string, props map[string]interface{}, env environ.Env) error
	onlyLogDog() bool
}

type swarmingCookMode struct{}

func (m swarmingCookMode) fillTemplateParams(env environ.Env, params *tasktemplate.Params) error {
	var ok bool
	if params.SwarmingRunID, ok = env.Get("SWARMING_TASK_ID"); !ok {
		return userError("no Swarming run ID in $SWARMING_TASK_ID environment variable")
	}
	return nil
}

func (m swarmingCookMode) needsIOKeepAlive() bool         { return false }
func (m swarmingCookMode) shouldEmitTimestamps() bool     { return true }
func (m swarmingCookMode) alwaysForwardAnnotations() bool { return false }

func (m swarmingCookMode) botID(env environ.Env) (string, error) {
	botID, ok := env.Get("SWARMING_BOT_ID")
	if !ok {
		return "", userError("a valid bot id was expected in $SWARMING_BOT_ID")
	}
	return botID, nil
}
func (m swarmingCookMode) shouldEmitLogDogLinks() bool { return false }
func (m swarmingCookMode) onlyLogDog() bool            { return true }
func (m swarmingCookMode) addLogDogGlobalTags(tags map[string]string, props map[string]interface{},
	env environ.Env) error {

	// SWARMING_SERVER is the full URL: https://example.com
	// We want just the hostname.
	if v, ok := env.Get("SWARMING_SERVER"); ok {
		if u, err := url.Parse(v); err == nil && u.Host != "" {
			tags["swarming.host"] = u.Host
		}
	}
	if v, ok := env.Get("SWARMING_TASK_ID"); ok {
		tags["swarming.run_id"] = v
	}
	if v, ok := env.Get("SWARMING_BOT_ID"); ok {
		tags["bot_id"] = v
	}

	return nil
}

type buildBotCookMode struct{}

func (m buildBotCookMode) fillTemplateParams(env environ.Env, params *tasktemplate.Params) error {
	return nil
}

func (m buildBotCookMode) needsIOKeepAlive() bool         { return true }
func (m buildBotCookMode) shouldEmitTimestamps() bool     { return false }
func (m buildBotCookMode) alwaysForwardAnnotations() bool { return true }

func (m buildBotCookMode) botID(env environ.Env) (string, error) {
	botID, ok := env.Get("BUILDBOT_SLAVENAME")
	if !ok {
		return "", userError("a valid bot id was expected in $BUILDBOT_SLAVENAME")
	}
	return botID, nil
}

func (m buildBotCookMode) onlyLogDog() bool            { return false }
func (m buildBotCookMode) shouldEmitLogDogLinks() bool { return true }
func (m buildBotCookMode) addLogDogGlobalTags(tags map[string]string, props map[string]interface{},
	env environ.Env) error {

	if v, ok := props["mastername"].(string); ok && v != "" {
		tags["buildbot.master"] = v
	}
	if v, ok := props["buildername"].(string); ok && v != "" {
		tags["buildbot.builder"] = v
	}
	if v, ok := props["buildnumber"].(json.Number); ok && v != "" {
		tags["buildbot.buildnumber"] = string(v)
	}

	if v, ok := props["slavename"].(string); ok && v != "" {
		tags["bot_id"] = v
	}

	return nil
}
