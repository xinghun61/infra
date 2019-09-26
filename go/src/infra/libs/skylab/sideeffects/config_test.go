// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package sideeffects

import (
	"io/ioutil"
	"testing"

	"github.com/google/uuid"
	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform/side_effects"
)

func basicConfig() *side_effects.Config {
	return &side_effects.Config{
		Tko: &side_effects.TKOConfig{
			ProxySocket:       tempFile(),
			MysqlUser:         "foo-user",
			MysqlPasswordFile: tempFile(),
		},
		GoogleStorage: &side_effects.GoogleStorageConfig{
			Bucket:          "foo-bucket",
			CredentialsFile: tempFile(),
		},
	}
}

func tempFile() string {
	f, _ := ioutil.TempFile("", "")
	return f.Name()
}

func TestSuccess(t *testing.T) {
	Convey("Given a complete config pointing to existing files", t, func() {
		cfg := basicConfig()
		err := ValidateConfig(cfg)
		Convey("no error is returned.", func() {
			So(err, ShouldBeNil)
		})
	})
}

func TestMissingArgs(t *testing.T) {
	Convey("Given a side_effects.Config with a missing", t, func() {
		cases := []struct {
			name         string
			fieldDropper func(*side_effects.Config)
		}{
			{
				name: "proxy socket",
				fieldDropper: func(c *side_effects.Config) {
					c.Tko.ProxySocket = ""
				},
			},
			{
				name: "MySQL user",
				fieldDropper: func(c *side_effects.Config) {
					c.Tko.MysqlUser = ""
				},
			},
			{
				name: "MySQL password file",
				fieldDropper: func(c *side_effects.Config) {
					c.Tko.MysqlPasswordFile = ""
				},
			},
			{
				name: "Google Storage bucket",
				fieldDropper: func(c *side_effects.Config) {
					c.GoogleStorage.Bucket = ""
				},
			},
			{
				name: "Google Storage credentials file",
				fieldDropper: func(c *side_effects.Config) {
					c.GoogleStorage.CredentialsFile = ""
				},
			},
		}
		for _, c := range cases {
			Convey(c.name, func() {
				cfg := basicConfig()
				c.fieldDropper(cfg)
				err := ValidateConfig(cfg)
				Convey("then the correct error is returned.", func() {
					So(err, ShouldNotBeNil)
					So(err.Error(), ShouldContainSubstring, c.name)
				})
			})
		}
	})
}

func TestMissingFiles(t *testing.T) {
	Convey("Given a missing", t, func() {
		cases := []struct {
			name        string
			fileDropper func(c *side_effects.Config)
		}{
			{
				name: "proxy socket",
				fileDropper: func(c *side_effects.Config) {
					c.Tko.ProxySocket = uuid.New().String()
				},
			},
			{
				name: "MySQL password file",
				fileDropper: func(c *side_effects.Config) {
					c.Tko.MysqlPasswordFile = uuid.New().String()
				},
			},
			{
				name: "Google Storage credentials file",
				fileDropper: func(c *side_effects.Config) {
					c.GoogleStorage.CredentialsFile = uuid.New().String()
				},
			},
		}
		for _, c := range cases {
			Convey(c.name, func() {
				cfg := basicConfig()
				c.fileDropper(cfg)
				err := ValidateConfig(cfg)
				Convey("then the correct error is returned.", func() {
					So(err, ShouldNotBeNil)
					So(err.Error(), ShouldContainSubstring, c.name)
				})
			})
		}
	})
}
