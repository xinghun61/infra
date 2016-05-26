// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// These structs are used for parsing gatekeeper.json files.

package messages

import (
	"encoding/json"
	"net/url"
	"strings"
)

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

type GatekeeperConfig struct {
	Categories map[string]BuilderConfig  `json:"categories"`
	Masters    map[string][]MasterConfig `json:"masters"`
}

// TreeMasterConfig is a named group of masters. e.g. chromium, or blink.
type TreeMasterConfig struct {
	BuildDB string                      `json:"build-db"`
	Masters map[MasterLocation][]string `json:"masters"`
}

// Intermediate struct without parsed URLs
type treeMasterConfig struct {
	BuildDB string              `json:"build-db"`
	Masters map[string][]string `json:"masters"`
}

func (t *TreeMasterConfig) UnmarshalJSON(b []byte) error {
	tmpT := treeMasterConfig{}
	if err := json.Unmarshal(b, &tmpT); err != nil {
		return err
	}

	t.BuildDB = tmpT.BuildDB

	for master, allowed := range tmpT.Masters {
		parsed, err := url.Parse(master)
		if err != nil {
			return err
		}

		t.Masters[MasterLocation{*parsed}] = allowed
	}

	return nil
}

type MasterLocation struct {
	url.URL
}

func (m *MasterLocation) Name() string {
	parts := strings.Split(m.Path, "/")
	return parts[len(parts)-1]
}

func (m *MasterLocation) MarshalJSON() ([]byte, error) {
	return []byte(m.String()), nil

}
