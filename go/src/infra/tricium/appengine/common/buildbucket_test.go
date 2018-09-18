// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"encoding/json"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	bbapi "go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
)

func TestParametersJSON(t *testing.T) {
	Convey("Creates parameters_json string", t, func() {
		w := &admin.Worker{
			Name:       "FileIsolator",
			Dimensions: []string{"pool:Chrome", "os:Ubuntu13.04"},
		}
		recipe := &admin.Worker_Recipe{&tricium.Recipe{
			Name:        "recipe",
			CipdPackage: "infra/recipe_bundle",
			CipdVersion: "live",
			Properties:  "{\"enable\":\"all\"}",
		}}
		gerrit := map[string]string{
			"gerrit_project":   "infra",
			"gerrit_change":    "ChangeId",
			"gerrit_cl_number": "1234",
			"gerrit_patch_set": "2",
		}
		actual_bytes, err := swarmingParametersJSON(w, recipe, gerrit)
		So(err, ShouldBeNil)
		actual := make(map[string]interface{})
		err = json.Unmarshal([]byte(actual_bytes), &actual)
		So(err, ShouldBeNil)
		expected := map[string]interface{}{
			"builder_name": "tricium",
			"properties": map[string]interface{}{
				"enable": "all",
				"gerrit_props": map[string]interface{}{
					"gerrit_project":   "infra",
					"gerrit_change":    "ChangeId",
					"gerrit_cl_number": "1234",
					"gerrit_patch_set": "2",
				},
			},
			"swarming": map[string]interface{}{
				"override_builder_cfg": map[string]interface{}{
					"dimensions": []interface{}{"pool:Chrome", "os:Ubuntu13.04"},
					"recipe": map[string]interface{}{
						"name":         "recipe",
						"cipd_package": "infra/recipe_bundle",
						"cipd_version": "live",
					},
				},
			},
		}
		So(actual, ShouldResemble, expected)
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
