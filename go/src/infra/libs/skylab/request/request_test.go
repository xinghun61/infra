// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package request_test

import (
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"infra/libs/skylab/inventory"
	"infra/libs/skylab/request"
)

func TestProvisionableDimensions(t *testing.T) {
	Convey("Given request arguments that specify provisionable and regular dimenisons and inventory labels", t, func() {
		model := "foo-model"
		args := request.Args{
			Dimensions:              []string{"k1:v1"},
			ProvisionableDimensions: []string{"k2:v2", "k3:v3"},
			SchedulableLabels:       inventory.SchedulableLabels{Model: &model},
		}
		Convey("when a request is formed", func() {
			req, err := request.New(args)
			So(err, ShouldBeNil)
			So(req, ShouldNotBeNil)
			Convey("then request should have correct slice structure.", func() {
				So(req.TaskSlices, ShouldHaveLength, 2)

				// First slice requires all dimensions.
				// Second slice (fallback) requires only non-provisionable dimensions.
				s0 := req.TaskSlices[0]
				s1 := req.TaskSlices[1]
				So(s0.Properties.Dimensions, ShouldHaveLength, 4)
				So(s1.Properties.Dimensions, ShouldHaveLength, 2)

				d00 := s0.Properties.Dimensions[0]
				d01 := s0.Properties.Dimensions[1]
				d02 := s0.Properties.Dimensions[2]
				d03 := s0.Properties.Dimensions[3]
				So(d00.Key, ShouldEqual, "label-model")
				So(d00.Value, ShouldEqual, "foo-model")
				So(d01.Key, ShouldEqual, "k1")
				So(d01.Value, ShouldEqual, "v1")
				So(d02.Key, ShouldEqual, "k2")
				So(d02.Value, ShouldEqual, "v2")
				So(d03.Key, ShouldEqual, "k3")
				So(d03.Value, ShouldEqual, "v3")

				d10 := s1.Properties.Dimensions[0]
				d11 := s1.Properties.Dimensions[1]
				So(d10.Key, ShouldEqual, "label-model")
				So(d10.Value, ShouldEqual, "foo-model")
				So(d11.Key, ShouldEqual, "k1")
				So(d11.Value, ShouldEqual, "v1")

				// First slice command doesn't include provisioning.
				// Second slice (fallback) does.
				s0FlatCmd := strings.Join(s0.Properties.Command, " ")
				s1FlatCmd := strings.Join(s1.Properties.Command, " ")
				provString := "-provision-labels k2:v2,k3:v3"
				So(s0FlatCmd, ShouldNotContainSubstring, provString)
				So(s1FlatCmd, ShouldContainSubstring, provString)
			})
		})
	})
}

func TestSliceExpiration(t *testing.T) {
	timeOutMins := 11
	Convey("Given a request arguments with no provisionable dimensions", t, func() {
		args := request.Args{
			TimeoutMins: timeOutMins,
		}
		req, err := request.New(args)
		So(req, ShouldNotBeNil)
		So(err, ShouldBeNil)
		Convey("request should have a single slice with provided timeout.", func() {
			So(req.TaskSlices, ShouldHaveLength, 1)
			So(req.TaskSlices[0].ExpirationSecs, ShouldEqual, 60*timeOutMins)
		})
	})
	Convey("Given a request arguments with provisionable dimensions", t, func() {
		args := request.Args{
			TimeoutMins:             timeOutMins,
			ProvisionableDimensions: []string{"k1:v1"},
		}
		req, err := request.New(args)
		So(req, ShouldNotBeNil)
		So(err, ShouldBeNil)
		Convey("request should have 2 slices, with provided timeout on only the second.", func() {
			So(req.TaskSlices, ShouldHaveLength, 2)
			So(req.TaskSlices[0].ExpirationSecs, ShouldBeLessThan, 60*5)
			So(req.TaskSlices[1].ExpirationSecs, ShouldEqual, 60*timeOutMins)
		})
	})
}
