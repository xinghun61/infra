// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// These structs are used for parsing gatekeeper.json files.

package messages

// MasterConfig represents filtering configurtaion for alerts
// generated about a buildbot master.
type MasterConfig struct {
	Categories       []string                 `json:"categories"`
	TreeNotify       []string                 `json:"tree_notify"`
	SheriffClasses   []string                 `json:"sheriff_classes"`
	Builders         map[string]BuilderConfig `json:"builders"`
	ExcludedBuilders []string                 `json:"excluded_builders"`
	ExcludedSteps    []string                 `json:"excluded_steps"`
}

// BuilderConfig represents filtering configuration for alerts
// generated about a buildbot builder.
type BuilderConfig struct {
	ExcludedSteps     []string `json:"excluded_steps"`
	ForgivingSteps    []string `json:"forgiving_steps"`
	ForgivingOptional []string `json:"forgiving_optional"`
	SheriffClasses    []string `json:"sheriff_classes"`
	ClosingSteps      []string `json:"closing_steps"`
	ClosingOptional   []string `json:"closing_optional"`
}

// TreeMasterConfig is a named group of masters. e.g. chromium, or blink.
type TreeMasterConfig struct {
	BuildDB string   `json:"build-db"`
	Masters []string `json:"masters"`
}
