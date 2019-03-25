// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"context"
	"io/ioutil"
	"testing"

	"github.com/golang/protobuf/proto"
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

func TestConfigValidator(t *testing.T) {
	t.Parallel()
	rules := &validation.RuleSet{}
	rules.RegisterVar("appid", func(context.Context) (string, error) {
		return "my_app", nil
	})
	SetupValidation(rules)
	validate := func(cfg *Config) error {
		c := validation.Context{Context: context.Background()}
		err := rules.ValidateConfig(
			&c, "services/my_app", configFile, []byte(cfg.String()),
		)
		So(err, ShouldBeNil)
		return c.Finalize()
	}

	Convey("devcfg template is valid", t, func() {
		content, err := ioutil.ReadFile(
			"../devcfg/services/dev/config-template.cfg",
		)
		So(err, ShouldBeNil)
		cfg := &Config{}
		So(proto.UnmarshalText(string(content), cfg), ShouldBeNil)
		So(validate(cfg), ShouldBeNil)
	})

	Convey("empty config is valid", t, func() {
		So(validate(&Config{}), ShouldBeNil)
	})

	Convey("validateConfig catches errors", t, func() {
		Convey("with duplicate IDs", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners = append(cfg.Assigners, cfg.Assigners[0])
			So(validate(cfg), ShouldErrLike, "duplicate id")
		})

		Convey("With invalid IDs", func() {
			msg := "invalid id"
			So(validate(createConfig("a-")), ShouldErrLike, msg)
			So(validate(createConfig("a-")), ShouldErrLike, msg)
			So(validate(createConfig("-a")), ShouldErrLike, msg)
			So(validate(createConfig("-")), ShouldErrLike, msg)
			So(validate(createConfig("a--b")), ShouldErrLike, msg)
			So(validate(createConfig("a@!3")), ShouldErrLike, msg)
			So(validate(createConfig("12=56")), ShouldErrLike, msg)
			So(validate(createConfig("A-cfg")), ShouldErrLike, msg)
		})

		Convey("With invalid owners", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Owners = []string{"example.com"}
			So(validate(cfg), ShouldErrLike, "invalid email address")
		})

		Convey("With missing interval", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Interval = nil
			So(validate(cfg), ShouldErrLike, "missing interval")
		})

		Convey("With an interval shoter than 1 minute", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Interval = &duration.Duration{Seconds: 59}
			So(validate(cfg), ShouldErrLike, "interval should be at least one minute")
		})

		Convey("With missing rotations", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Rotations = []string{}
			So(validate(cfg), ShouldErrLike, "missing rotations")
		})

		Convey("With missing issue_query", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].IssueQuery = nil
			So(validate(cfg), ShouldErrLike, "missing issue_query")
			cfg.Assigners[0].IssueQuery = &IssueQuery{ProjectNames: []string{}}
			So(validate(cfg), ShouldErrLike, "missing q")
			cfg.Assigners[0].IssueQuery = &IssueQuery{Q: "text"}
			So(validate(cfg), ShouldErrLike, "missing project_names")
		})
	})
}
