// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package request_test

import (
	"fmt"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/kylelemons/godebug/pretty"
	. "github.com/smartystreets/goconvey/convey"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"

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
			req, err := args.SwarmingNewTaskRequest()
			So(err, ShouldBeNil)
			So(req, ShouldNotBeNil)
			Convey("then request should have correct slice structure.", func() {
				So(req.TaskSlices, ShouldHaveLength, 2)

				// First slice requires all dimensions.
				// Second slice (fallback) requires only non-provisionable dimensions.
				s0 := req.TaskSlices[0]
				s1 := req.TaskSlices[1]
				So(s0.Properties.Dimensions, ShouldHaveLength, 6)
				So(s1.Properties.Dimensions, ShouldHaveLength, 4)

				type KV struct {
					K string
					V string
				}

				s0Expect := []KV{
					{"pool", "ChromeOSSkylab"},
					{"dut_state", "ready"},
					{"label-model", model},
					{"k1", "v1"},
					{"k2", "v2"},
					{"k3", "v3"},
				}
				s1Expect := s0Expect[:4]

				// TODO(akeshet): Use pretty.Compare instead of looped assertion.
				compare := func([]*swarming.SwarmingRpcsStringPair, []KV) {
					for i, d := range s0.Properties.Dimensions {
						So(d.Key, ShouldEqual, s0Expect[i].K)
						So(d.Value, ShouldEqual, s0Expect[i].V)
					}
				}

				compare(s0.Properties.Dimensions, s0Expect)
				compare(s1.Properties.Dimensions, s1Expect)

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
	timeout := 11 * time.Minute
	Convey("Given a request arguments with no provisionable dimensions", t, func() {
		args := request.Args{
			Timeout: timeout,
		}
		req, err := args.SwarmingNewTaskRequest()
		So(req, ShouldNotBeNil)
		So(err, ShouldBeNil)
		Convey("request should have a single slice with provided timeout.", func() {
			So(req.TaskSlices, ShouldHaveLength, 1)
			So(req.TaskSlices[0].ExpirationSecs, ShouldEqual, 60*11)
		})
	})
	Convey("Given a request arguments with provisionable dimensions", t, func() {
		args := request.Args{
			Timeout:                 timeout,
			ProvisionableDimensions: []string{"k1:v1"},
		}
		req, err := args.SwarmingNewTaskRequest()
		So(req, ShouldNotBeNil)
		So(err, ShouldBeNil)
		Convey("request should have 2 slices, with provided timeout on only the second.", func() {
			So(req.TaskSlices, ShouldHaveLength, 2)
			So(req.TaskSlices[0].ExpirationSecs, ShouldBeLessThan, 60*5)
			So(req.TaskSlices[1].ExpirationSecs, ShouldEqual, 60*11)
		})
	})
}

func TestStaticDimensions(t *testing.T) {
	cases := []struct {
		Tag  string
		Args request.Args
		Want []*swarming.SwarmingRpcsStringPair
	}{
		{
			Tag:  "empty args",
			Args: request.Args{},
			Want: toStringPairs([]string{"pool:ChromeOSSkylab"}),
		},
		{
			Tag: "one schedulable label",
			Args: request.Args{
				SchedulableLabels: inventory.SchedulableLabels{
					Model: stringPtr("some_model"),
				},
			},
			Want: toStringPairs([]string{"pool:ChromeOSSkylab", "label-model:some_model"}),
		},
		{
			Tag: "one dimension",
			Args: request.Args{
				Dimensions: []string{"some:value"},
			},
			Want: toStringPairs([]string{"pool:ChromeOSSkylab", "some:value"}),
		},
		{
			Tag: "one provisionable dimension",
			Args: request.Args{
				ProvisionableDimensions: []string{"cros-version:value"},
			},
			Want: toStringPairs([]string{"pool:ChromeOSSkylab"}),
		},
		{
			Tag: "one of each",
			Args: request.Args{
				SchedulableLabels: inventory.SchedulableLabels{
					Model: stringPtr("some_model"),
				},
				Dimensions:              []string{"some:value"},
				ProvisionableDimensions: []string{"cros-version:value"},
			},
			Want: toStringPairs([]string{"pool:ChromeOSSkylab", "label-model:some_model", "some:value"}),
		},
	}

	for _, c := range cases {
		t.Run(c.Tag, func(t *testing.T) {
			got, err := c.Args.StaticDimensions()
			if err != nil {
				t.Fatalf("error in StaticDimensions(): %s", err)
			}
			want := sortDimensions(c.Want)
			got = sortDimensions(got)
			if diff := pretty.Compare(want, got); diff != "" {
				t.Errorf("Incorrect static dimensions, -want +got: %s", diff)
			}
		})
	}
}

func stringPtr(s string) *string {
	return &s
}

func toStringPairs(ss []string) []*swarming.SwarmingRpcsStringPair {
	ret := make([]*swarming.SwarmingRpcsStringPair, len(ss))
	for i, s := range ss {
		p := strings.Split(s, ":")
		if len(p) != 2 {
			panic(fmt.Sprintf("Invalid dimension %s", s))
		}
		ret[i] = &swarming.SwarmingRpcsStringPair{
			Key:   p[0],
			Value: p[1],
		}
	}
	return ret
}

func sortDimensions(dims []*swarming.SwarmingRpcsStringPair) []*swarming.SwarmingRpcsStringPair {
	sort.SliceStable(dims, func(i, j int) bool {
		return dims[i].Key < dims[j].Key || (dims[i].Key == dims[j].Key && dims[i].Value < dims[j].Value)
	})
	return dims
}
