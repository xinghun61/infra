// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"context"
	"encoding/json"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	bbapi "go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"
	"go.chromium.org/luci/common/logging/memlogger"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
)

func TestParametersJSON(t *testing.T) {
	Convey("Creates parameters_json string", t, func() {
		w := &admin.Worker{
			Name:       "FileIsolator",
			Dimensions: []string{"pool:Chrome", "os:Ubuntu13.04"},
			Deadline:   1200,
		}
		recipe := &admin.Worker_Recipe{
			Recipe: &tricium.Recipe{
				Name:        "recipe",
				CipdPackage: "infra/recipe_bundle",
				CipdVersion: "live",
				Properties:  "{\"enable\":\"all\"}",
			},
		}
		ctx := memory.Use(memlogger.Use(context.Background()))
		actualBytes, err := swarmingParametersJSON(ctx, w, recipe)
		So(err, ShouldBeNil)
		actual := make(map[string]interface{})
		err = json.Unmarshal([]byte(actualBytes), &actual)
		So(err, ShouldBeNil)
		expected := map[string]interface{}{
			"builder_name": "tricium",
			"properties": map[string]interface{}{
				"enable": "all",
			},
			"swarming": map[string]interface{}{
				"override_builder_cfg": map[string]interface{}{
					// Note: the "pool" dimension is never included in the
					// dimensions in a buildbucket request; the pool must be
					// specified in the cr-buildbucket.cfg that defines the
					// builder.
					"dimensions": []interface{}{"os:Ubuntu13.04"},
					"recipe": map[string]interface{}{
						"name":         "recipe",
						"cipd_package": "infra/recipe_bundle",
						"cipd_version": "live",
					},
					"execution_timeout_secs": float64(1200),
				},
			},
		}
		So(actual, ShouldResemble, expected)
	})
}

func TestParametersJSONWithBuilder(t *testing.T) {
	Convey("Creates parameters_json string", t, func() {
		w := &admin.Worker{
			Name:       "FileIsolator",
			Dimensions: []string{"pool:Chrome", "os:Ubuntu13.04"},
			Deadline:   1200,
		}
		recipe := &admin.Worker_Recipe{
			Recipe: &tricium.Recipe{
				Name:        "recipe",
				CipdPackage: "infra/recipe_bundle",
				CipdVersion: "live",
				Properties:  "{\"enable\":\"all\"}",
				Project:     "chromium",
				Bucket:      "tricium",
				Builder:     "test",
			},
		}
		ctx := memory.Use(memlogger.Use(context.Background()))
		actualBytes, err := swarmingParametersJSON(ctx, w, recipe)
		So(err, ShouldBeNil)
		actual := make(map[string]interface{})
		err = json.Unmarshal([]byte(actualBytes), &actual)
		So(err, ShouldBeNil)
		expected := map[string]interface{}{
			"builder_name": "test",
			"properties": map[string]interface{}{
				"enable": "all",
			},
			"swarming": map[string]interface{}{
				"override_builder_cfg": map[string]interface{}{
					// Note: the "pool" dimension is never included in the
					// dimensions in a buildbucket request; the pool must be
					// specified in the cr-buildbucket.cfg that defines the
					// builder.
					"dimensions": []interface{}{"os:Ubuntu13.04"},
					"recipe": map[string]interface{}{
						"name":         "recipe",
						"cipd_package": "infra/recipe_bundle",
						"cipd_version": "live",
					},
					"execution_timeout_secs": float64(1200),
				},
			},
		}
		So(actual, ShouldResemble, expected)
	})
}

func TestMakeRequest(t *testing.T) {
	Convey("Creates a valid build request", t, func() {
		ctx := memory.Use(memlogger.Use(context.Background()))
		pubsubUserdata := "userdata"
		parametersJSON := "{}"
		tags := []string{"tag"}
		recipe := &admin.Worker_Recipe{
			Recipe: &tricium.Recipe{
				Name:        "recipe",
				CipdPackage: "infra/recipe_bundle",
				CipdVersion: "live",
			},
		}
		So(
			makeRequest(ctx, pubsubUserdata, parametersJSON, tags, recipe.Recipe),
			ShouldResemble, &bbapi.LegacyApiPutRequestMessage{
				Bucket: "luci.tricium.try",
				PubsubCallback: &bbapi.LegacyApiPubSubCallbackMessage{
					Topic:    topic(ctx),
					UserData: pubsubUserdata,
				},
				Tags:           tags,
				ParametersJson: "{}",
			})
	})
}

func TestMakeRequestWithBuilder(t *testing.T) {
	Convey("Creates a valid build request", t, func() {
		ctx := memory.Use(memlogger.Use(context.Background()))
		pubsubUserdata := "userdata"
		parametersJSON := "{}"
		tags := []string{"tag"}
		recipe := &admin.Worker_Recipe{
			Recipe: &tricium.Recipe{
				Name:        "recipe",
				CipdPackage: "infra/recipe_bundle",
				CipdVersion: "live",
				Project:     "chromium",
				Bucket:      "tricium",
				Builder:     "test",
			},
		}
		So(
			makeRequest(ctx, pubsubUserdata, parametersJSON, tags, recipe.Recipe),
			ShouldResemble, &bbapi.LegacyApiPutRequestMessage{
				Bucket: "luci.chromium.tricium",
				PubsubCallback: &bbapi.LegacyApiPubSubCallbackMessage{
					Topic:    topic(ctx),
					UserData: pubsubUserdata,
				},
				Tags:           tags,
				ParametersJson: "{}",
			})
	})
}
