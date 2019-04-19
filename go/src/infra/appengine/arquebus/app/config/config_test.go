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

	"infra/appengine/arquebus/app/util"
)

func createConfig(id string) *Config {
	// returns an assigner with a given ID and all required fields.
	var cfg Assigner
	So(proto.UnmarshalText(util.SampleValidAssignerCfg, &cfg), ShouldBeNil)
	cfg.Id = id

	return &Config{
		AccessGroup:      "trooper",
		MonorailHostname: "example.com",
		Assigners:        []*Assigner{&cfg},
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
		Convey("For duplicate IDs", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners = append(cfg.Assigners, cfg.Assigners[0])
			So(validate(cfg), ShouldErrLike, "duplicate id")
		})

		Convey("for invalid IDs", func() {
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

		Convey("for invalid owners", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Owners = []string{"example.com"}
			So(validate(cfg), ShouldErrLike, "invalid email address")
		})

		Convey("for missing interval", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Interval = nil
			So(validate(cfg), ShouldErrLike, "missing interval")
		})

		Convey("for an interval shoter than 1 minute", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Interval = &duration.Duration{Seconds: 59}
			So(validate(cfg), ShouldErrLike, "interval should be at least one minute")
		})

		Convey("for missing assignees", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Assignees = []*UserSource{}
			So(validate(cfg), ShouldErrLike, "missing assignees")
		})

		Convey("for missing issue_query", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].IssueQuery = nil
			So(validate(cfg), ShouldErrLike, "missing issue_query")
			cfg.Assigners[0].IssueQuery = &IssueQuery{ProjectNames: []string{}}
			So(validate(cfg), ShouldErrLike, "missing q")
			cfg.Assigners[0].IssueQuery = &IssueQuery{Q: "text"}
			So(validate(cfg), ShouldErrLike, "missing project_names")
		})

		Convey("for invalid UserResource", func() {
			cfg := createConfig("my-assigner")
			assigner := cfg.Assigners[0]
			source := &UserSource{}
			assigner.Assignees[0] = source

			Convey("with missing value", func() {
				source.Reset()
				So(validate(cfg), ShouldErrLike, "missing value")
			})

			Convey("with missing position in rotation", func() {
				source.From = &UserSource_Rotation{Rotation: "rotation"}
				So(validate(cfg), ShouldErrLike, "missing position")
				source.From = &UserSource_Rotation{Rotation: "rotation?position"}
				So(validate(cfg), ShouldErrLike, "missing position")
			})

			Convey("with invalid position in rotation", func() {
				source.From = &UserSource_Rotation{Rotation: "rotation?position=left"}
				So(validate(cfg), ShouldErrLike, "invalid position value")
			})

			Convey("with invalid user", func() {
				source.From = &UserSource_Email{Email: "example"}
				So(validate(cfg), ShouldErrLike, "invalid email")
				source.From = &UserSource_Email{Email: "example.org"}
				So(validate(cfg), ShouldErrLike, "invalid email")
				source.From = &UserSource_Email{Email: "http://foo@example.org"}
				So(validate(cfg), ShouldErrLike, "invalid email")
			})
		})
	})
}
