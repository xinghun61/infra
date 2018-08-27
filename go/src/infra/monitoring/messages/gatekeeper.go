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
	Categories        []string `json:"categories"`
	ExcludedSteps     []string `json:"excluded_steps"`
	ForgivingSteps    []string `json:"forgiving_steps"`
	ForgivingOptional []string `json:"forgiving_optional"`
	SheriffClasses    []string `json:"sheriff_classes"`
	ClosingSteps      []string `json:"closing_steps"`
	ClosingOptional   []string `json:"closing_optional"`
}

// CategoryConfig represents a reusable filtering configuration
// that can be included by masters or builders.
type CategoryConfig struct {
	ExcludedSteps     []string `json:"excluded_steps"`
	ForgivingSteps    []string `json:"forgiving_steps"`
	ForgivingOptional []string `json:"forgiving_optional"`
	SheriffClasses    []string `json:"sheriff_classes"`
	ClosingSteps      []string `json:"closing_steps"`
	ClosingOptional   []string `json:"closing_optional"`
}

// GatekeeperConfig is the main gatekeeper.json config.
type GatekeeperConfig struct {
	Categories map[string]CategoryConfig `json:"categories"`
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

// UnmarshalJSON unmarshals bytes into this struct.
func (t *TreeMasterConfig) UnmarshalJSON(b []byte) error {
	tmpT := treeMasterConfig{}
	if err := json.Unmarshal(b, &tmpT); err != nil {
		return err
	}

	t.BuildDB = tmpT.BuildDB
	t.Masters = make(map[MasterLocation][]string)

	for master, allowed := range tmpT.Masters {
		parsed, err := url.Parse(master)
		if err != nil {
			return err
		}

		t.Masters[MasterLocation{*parsed}] = allowed
	}

	return nil
}

// MasterLocation is the location of a master. Currently it's just a URL.
type MasterLocation struct {
	url.URL
}

// Name is the name of the master; chromium, chromium.linux, etc.
func (m *MasterLocation) Name() string {
	parts := strings.Split(m.Path, "/")
	return parts[len(parts)-1]
}

// Internal returns if this master
func (m *MasterLocation) Internal() bool {
	// TODO(martiniss): Fix this, and make it not even necessary.
	name := m.Name()
	return (strings.Contains(name, "internal") || strings.Contains(
		name, "official") || strings.Contains(name, "infra.cron"))
}

// MarshalJSON returns the JSON serialized version of a master location.
func (m *MasterLocation) MarshalJSON() ([]byte, error) {
	return []byte(m.String()), nil

}
