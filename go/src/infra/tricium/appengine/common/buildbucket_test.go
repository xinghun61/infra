// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	bbapi "go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
)

func TestParametersJSON(t *testing.T) {
	Convey("Creates parameters_json string", t, func() {
		serverURL := "https://chromium-swarm-dev.appspot.com"
		w := &admin.Worker{
			Name:       "FileIsolator",
			Dimensions: []string{"pool:Chrome", "os:Ubuntu13.04"},
		}
		recipe := &admin.Worker_Recipe{&tricium.Recipe{
			Name: "recipe",
		}}
		actual, err := swarmingParametersJSON(serverURL, w, recipe)
		So(err, ShouldBeNil)
		expected := `{"builder_name":"tricium","swarming":{"hostname":"https://chromium-swarm-dev.appspot.com","override_builder_cfg":{"dimensions":["pool:Chrome","os:Ubuntu13.04"],"recipe":{"Recipe":{"name":"recipe"}}}}}`
		So(actual, ShouldEqual, expected)
	})
}

func TestMakeRequest(t *testing.T) {
	Convey("Creates a valid build request", t, func() {
		pubsubTopic := "topic"
		pubsubUserdata := "userdata"
		parameters_json := "{}"
		tags := []string{"tag"}

		So(
			makeRequest(pubsubTopic, pubsubUserdata, parameters_json, tags),
			ShouldResemble, &bbapi.ApiPutRequestMessage{
				Bucket: "luci.infra.tricium",
				PubsubCallback: &bbapi.ApiPubSubCallbackMessage{
					Topic:    pubsubTopic,
					UserData: pubsubUserdata,
				},
				Tags:           tags,
				ParametersJson: parameters_json,
			})
	})
}
