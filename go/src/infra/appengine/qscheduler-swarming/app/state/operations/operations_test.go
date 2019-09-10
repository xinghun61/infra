// Copyright 2019 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package operations

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"infra/swarming"
)

func taskWithSliceDimensions(sliceDimensions ...[]string) *swarming.TaskSpec {
	t := &swarming.TaskSpec{}
	for _, dims := range sliceDimensions {
		newSlice := &swarming.SliceSpec{}
		newSlice.Dimensions = dims
		t.Slices = append(t.Slices, newSlice)
	}
	return t
}

func TestGetProvisionableLabels(t *testing.T) {
	Convey("When computing labels, 0-slice tasks return error.", t, func() {
		item := &swarming.NotifyTasksItem{Task: taskWithSliceDimensions()}
		_, err := computeLabels(item)
		So(err, ShouldNotBeNil)

	})
	Convey("When computing labels, 1-slice tasks return only base labels.", t, func() {
		item := &swarming.NotifyTasksItem{
			Task: taskWithSliceDimensions([]string{"base1", "base2"}),
		}
		labels, err := computeLabels(item)
		So(err, ShouldBeNil)
		So(labels.provisionable, ShouldBeEmpty)
		So(labels.base, ShouldContain, "base1")
		So(labels.base, ShouldContain, "base2")
		So(labels.base, ShouldHaveLength, 2)
	})
	Convey("When computing labels, 2-slice tasks return base and provisionable labels.", t, func() {
		item := &swarming.NotifyTasksItem{
			Task: taskWithSliceDimensions(
				[]string{"base1", "base2", "provisionable1", "provisionable2"},
				[]string{"base1", "base2"},
			),
		}
		labels, err := computeLabels(item)
		So(err, ShouldBeNil)
		So(labels.base, ShouldContain, "base1")
		So(labels.base, ShouldContain, "base2")
		So(labels.base, ShouldHaveLength, 2)
		So(labels.provisionable, ShouldContain, "provisionable1")
		So(labels.provisionable, ShouldContain, "provisionable2")
		So(labels.provisionable, ShouldHaveLength, 2)
	})
	Convey("When computing labels, 2-slice tasks with invalid dimensions return error.", t, func() {
		item := &swarming.NotifyTasksItem{
			Task: taskWithSliceDimensions(
				[]string{},
				[]string{"unexepected"},
			),
		}
		_, err := computeLabels(item)
		So(err, ShouldNotBeNil)
	})
	Convey("When computing labels, 3-slice tasks return error.", t, func() {
		item := &swarming.NotifyTasksItem{Task: taskWithSliceDimensions(nil, nil, nil)}
		_, err := computeLabels(item)
		So(err, ShouldNotBeNil)
	})
}

func TestGetAccountId(t *testing.T) {
	cases := []struct {
		name            string
		tags            []string
		expectedAccount string
		errorExpected   bool
	}{
		{
			"nil tags",
			nil,
			"",
			false,
		},
		{
			"no relevant tags",
			[]string{"foo:1", "foo:2"},
			"",
			false,
		},
		{
			"one account tag",
			[]string{"qs_account:foo", "foo:2"},
			"foo",
			false,
		},
		{
			"two account tags",
			[]string{"qs_account:foo", "qs_account:bar"},
			"",
			true,
		},
	}
	for _, c := range cases {
		Convey("When a task has "+c.name, t, func() {
			Convey("then getAccountID returns the correct value / error.", func() {
				i := &swarming.NotifyTasksItem{Task: &swarming.TaskSpec{Tags: c.tags}}
				a, err := GetAccountID(i)
				So(a, ShouldEqual, c.expectedAccount)
				if c.errorExpected {
					So(err, ShouldNotBeNil)
				} else {
					So(err, ShouldBeNil)
				}
			})
		})
	}
}
