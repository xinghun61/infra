// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/triciumtest"
)

func TestConfigStorage(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()

		Convey("Set and get single project config", func() {
			config := &tricium.ProjectConfig{
				ServiceAccount:         "tricium-dev@appspot.gserviceaccount.com",
				SwarmingServiceAccount: "swarming@tricium-dev.iam.gserviceaccount.com",
			}
			So(setProjectConfig(ctx, "my-project", "version", config), ShouldBeNil)
			result, err := getProjectConfig(ctx, "my-project")
			So(err, ShouldBeNil)
			// ShouldResemble doesn't quite work here because the
			// retrieved config message could have some extra
			// generated fields (e.g. XXX_sizecache) set to
			// something non-zero.
			So(result, ShouldNotBeNil)
		})

		Convey("Set, get, delete multiple project configs", func() {
			configs := map[string]*tricium.ProjectConfig{
				"infra": {
					Repos: []*tricium.RepoDetails{
						{
							Source: &tricium.RepoDetails_GitRepo{
								GitRepo: &tricium.GitRepo{
									Url: "https://repo-host.com/infra",
								},
							},
						},
					},
				},
				"playground": {
					Repos: []*tricium.RepoDetails{
						{
							Source: &tricium.RepoDetails_GitRepo{
								GitRepo: &tricium.GitRepo{
									Url: "https://repo-host.com/playground",
								},
							},
						},
					},
				},
			}
			So(setProjectConfig(ctx, "infra", "v", configs["infra"]), ShouldBeNil)
			So(setProjectConfig(ctx, "playground", "v", configs["playground"]), ShouldBeNil)
			result, err := getAllProjectConfigs(ctx)
			So(err, ShouldBeNil)
			So(len(result), ShouldEqual, 2)
			So(deleteProjectConfigs(ctx, []string{"playground"}), ShouldBeNil)
			result, err = getAllProjectConfigs(ctx)
			So(err, ShouldBeNil)
			So(len(result), ShouldEqual, 1)
			So(result["infra"], ShouldNotBeNil)
		})

		Convey("Set and get service config", func() {
			config := &tricium.ServiceConfig{
				SwarmingServer: "https://chromium-swarm.appspot.com",
				IsolateServer:  "https://isolateserver.appspot.com",
				Platforms: []*tricium.Platform_Details{
					{
						Name:       platform,
						Dimensions: []string{"pool:Chrome", "os:Ubuntu13.04"},
						HasRuntime: true,
					},
				},
				DataDetails: []*tricium.Data_TypeDetails{
					{
						Type:               tricium.Data_GIT_FILE_DETAILS,
						IsPlatformSpecific: false,
					},
				},
			}
			setServiceConfig(ctx, "version", config)
			result, err := getServiceConfig(ctx)
			So(err, ShouldBeNil)
			So(result, ShouldNotBeNil)
		})
	})

	Convey("Test Environment with nothing set", t, func() {
		ctx := triciumtest.Context()

		Convey("Get service config when none is set", func() {
			_, err := getServiceConfig(ctx)
			So(err, ShouldNotBeNil)
		})

		Convey("Get project config when none is set", func() {
			_, err := getProjectConfig(ctx, "project-name")
			So(err, ShouldNotBeNil)
		})

		Convey("Get all project configs when none are set", func() {
			configs, err := getAllProjectConfigs(ctx)
			So(configs, ShouldBeEmpty)
			So(err, ShouldBeNil)
		})

	})
}
