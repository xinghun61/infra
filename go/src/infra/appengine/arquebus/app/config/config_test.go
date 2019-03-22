// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"context"
	"io/ioutil"
	"testing"

	"github.com/golang/protobuf/ptypes/duration"
	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
	"go.chromium.org/luci/config/validation"
)

func createConfig(id string) *Config {
	// returns an assigner with a given ID and all required fields.
	a := &Assigner{
		Id:        id,
		Rotations: []string{"rotation1", "rotation2"},
		Interval:  &duration.Duration{Seconds: 60},
		IssueQuery: &IssueQuery{
			Q:            "test search query",
			ProjectNames: []string{"project1", "project2"},
		},
	}

	return &Config{
		AccessGroup:      "trooper",
		MonorailHostname: "example.com",
		Assigners:        []*Assigner{a},
	}
}

func createValidator() func([]byte) error {
	cs := "services/arquebus"
	p := "config.cfg"
	ctx := context.Background()
	r := validation.RuleSet{}
	r.Add(cs, p, validateConfig)

	return func(content []byte) error {
		c := validation.Context{Context: ctx}
		c.SetFile(p)

		// validate
		err := r.ValidateConfig(&c, cs, p, content)
		So(err, ShouldBeNil)
		return c.Finalize()
	}
}

func TestConfigValidator(t *testing.T) {
	t.Parallel()

	Convey("devcfg template is valid", t, func() {
		content, err := ioutil.ReadFile(
			"../devcfg/services/dev/config-template.cfg",
		)
		So(err, ShouldBeNil)

		validate := createValidator()
		ve := validate(content)
		So(ve, ShouldBeNil)
	})

	Convey("empty config is valid", t, func() {
		validate := createValidator()
		ve := validate([]byte(""))
		So(ve, ShouldBeNil)
	})

	Convey("validateConfig catches errors", t, func() {
		validate := createValidator()

		Convey("with duplicate IDs", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners = append(cfg.Assigners, cfg.Assigners[0])
			ve := validate([]byte(cfg.String()))
			So(ve, ShouldErrLike, "duplicate id")
		})

		Convey("With invalid IDs", func() {
			bad := []string{
				"a-", "-a", "-", "a--b", "a@!3", "123=56",
			}

			for _, id := range bad {
				cfg := createConfig(id)
				ve := validate([]byte(cfg.String()))
				So(ve, ShouldErrLike, "invalid id")
			}
		})

		Convey("With invalid owners", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Owners = []string{"example.com"}
			ve := validate([]byte(cfg.String()))
			So(ve, ShouldErrLike, "invalid email address")
		})

		Convey("With missing interval", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Interval = nil
			ve := validate([]byte(cfg.String()))
			So(ve, ShouldErrLike, "missing interval")
		})

		Convey("With an interval shoter than 1 minute", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Interval = &duration.Duration{
				Seconds: 59,
			}
			ve := validate([]byte(cfg.String()))
			So(
				ve, ShouldErrLike,
				"interval should be at least one minute",
			)
		})

		Convey("With missing rotations", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Rotations = []string{}
			ve := validate([]byte(cfg.String()))
			So(ve, ShouldErrLike, "missing rotations")
		})

		Convey("With missing issue_query", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].IssueQuery = nil
			ve := validate([]byte(cfg.String()))
			So(ve, ShouldErrLike, "missing issue_query")

			cfg.Assigners[0].IssueQuery = &IssueQuery{
				ProjectNames: []string{},
			}
			ve = validate([]byte(cfg.String()))
			So(ve, ShouldErrLike, "missing q")

			cfg.Assigners[0].IssueQuery = &IssueQuery{
				Q: "text search",
			}
			ve = validate([]byte(cfg.String()))
			So(ve, ShouldErrLike, "missing project_names")
		})
	})
}
