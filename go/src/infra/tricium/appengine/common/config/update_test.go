// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"testing"

	"go.chromium.org/luci/config"
	"go.chromium.org/luci/config/impl/memory"

	. "github.com/smartystreets/goconvey/convey"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/triciumtest"
)

var exampleConfig = map[config.Set]memory.Files{
	"services/app": {
		"service.cfg": `
			platforms {
			  name: UBUNTU
			  dimensions: "pool:tricium"
			  dimensions: "os:Ubuntu"
			  has_runtime: true
			}

			data_details {
			  type: GIT_FILE_DETAILS
			  is_platform_specific: false
			}
			functions {
			  type: ISOLATOR
			  name: "GitFileIsolator"
			  needs: GIT_FILE_DETAILS
			  provides: FILES
			  impls {
			    runtime_platform: UBUNTU
			    provides_for_platform: UBUNTU
			    cmd {
			      exec: "isolator"
			      args: "--output=${ISOLATED_OUTDIR}"
			    }
			    deadline: 900
			    cipd_packages {
			      package_name: "infra/tricium/function/git-file-isolator"
			      path: "."
			      version: "live"
			    }
			  }
			}

			swarming_server: "https://chromium-swarm.appspot.com"
			isolate_server: "https://isolateserver.appspot.com"
		`,
	},
	"projects/infra": {
		"app.cfg": `
			acls {
			  role: REQUESTER
			  group: "tricium-infra-requesters"
			}

			service_account: "tricium-dev@appspot.gserviceaccount.com"
			swarming_service_account: "swarming@tricium-dev.iam.gserviceaccount.com"
		`,
	},
	"projects/playground": {
		"app.cfg": `
			acls {
			  role: REQUESTER
			  group: "tricium-playground-requesters"
			}

			selections {
			  function: "GitFileIsolator"
			  platform: UBUNTU
			}

			service_account: "tricium-dev@appspot.gserviceaccount.com"
			swarming_service_account: "swarming@tricium-dev.iam.gserviceaccount.com"
		`,
	},
}

func TestUpdateConfigs(t *testing.T) {
	Convey("Test Environment", t, func() {

		ctx := triciumtest.Context()
		ctx = WithConfigService(ctx, memory.New(exampleConfig))

		So(serviceName(ctx), ShouldEqual, "app")

		Convey("Configs are not present before updating", func() {
			configs, err := getAllProjectConfigs(ctx)
			So(err, ShouldBeNil)
			So(len(configs), ShouldEqual, 0)

			revs, err := getStoredProjectConfigRevisions(ctx)
			So(err, ShouldBeNil)
			So(revs, ShouldBeEmpty)

			rev, err := getStoredServiceConfigRevision(ctx)
			So(err, ShouldBeNil)
			So(rev, ShouldEqual, "")

			sc, err := getServiceConfig(ctx)
			So(err, ShouldNotBeNil)
			So(sc, ShouldBeNil)
		})

		Convey("Configs are updated, first time", func() {
			So(UpdateAllConfigs(ctx), ShouldBeNil)
			configs, err := getAllProjectConfigs(ctx)
			So(err, ShouldBeNil)

			So(len(configs), ShouldResemble, 2)
			So(configs["infra"], ShouldNotBeNil)
			So(configs["playground"], ShouldNotBeNil)

			revs, err := getStoredProjectConfigRevisions(ctx)
			So(err, ShouldBeNil)
			So(revs, ShouldResemble, map[string]string{
				"infra":      "d2b8011d0651413774033b48fbab212d9acf3e8c",
				"playground": "1b40db8eff9122552687206f19c8b68ebb2480be",
			})

			rev, err := getStoredServiceConfigRevision(ctx)
			So(err, ShouldBeNil)
			So(rev, ShouldEqual, "8dad5f169bcb18e5d6ac020ebd032a284e9d1734")

			sc, err := getServiceConfig(ctx)
			So(err, ShouldBeNil)
			So(sc, ShouldNotBeNil)
		})

		Convey("Configs are updated when some configs already set", func() {
			So(setProjectConfig(ctx, "old-project", "abcd", &tricium.ProjectConfig{
				ServiceAccount: "foo@appspot.gserviceaccount.com",
			}), ShouldBeNil)
			So(setProjectConfig(ctx, "infra", "old-version", &tricium.ProjectConfig{
				ServiceAccount: "foo@appspot.gserviceaccount.com",
			}), ShouldBeNil)
			So(setServiceConfig(ctx, "old-version-service-config", &tricium.ServiceConfig{
				SwarmingServer: "https://foo.appspot.com",
			}), ShouldBeNil)

			revs, err := getStoredProjectConfigRevisions(ctx)
			So(err, ShouldBeNil)
			So(revs, ShouldResemble, map[string]string{
				"infra":       "old-version",
				"old-project": "abcd",
			})
			rev, err := getStoredServiceConfigRevision(ctx)
			So(err, ShouldBeNil)
			So(rev, ShouldEqual, "old-version-service-config")

			So(UpdateAllConfigs(ctx), ShouldBeNil)

			revs, err = getStoredProjectConfigRevisions(ctx)
			So(err, ShouldBeNil)
			So(revs, ShouldResemble, map[string]string{
				"infra":      "d2b8011d0651413774033b48fbab212d9acf3e8c",
				"playground": "1b40db8eff9122552687206f19c8b68ebb2480be",
			})
			rev, err = getStoredServiceConfigRevision(ctx)
			So(err, ShouldBeNil)
			So(rev, ShouldEqual, "8dad5f169bcb18e5d6ac020ebd032a284e9d1734")
		})
	})
}
