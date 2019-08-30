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

package clients

import (
	"sort"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/appengine/gaetesting"
)

func TestSuccessfulPushDuts(t *testing.T) {
	Convey("success", t, func() {
		ctx := gaetesting.TestingContext()
		tqt := taskqueue.GetTestable(ctx)
		qn := "repair-bots"
		tqt.CreateQueue(qn)
		hosts := []string{"host1", "host2"}
		err := PushRepairDUTs(ctx, hosts)
		So(err, ShouldBeNil)
		tasks := tqt.GetScheduledTasks()
		t, ok := tasks[qn]
		So(ok, ShouldBeTrue)
		var taskPaths []string
		for _, v := range t {
			taskPaths = append(taskPaths, v.Path)
		}
		sort.Strings(taskPaths)
		expectedPaths := []string{"/internal/task/cros_repair/host1", "/internal/task/cros_repair/host2"}
		sort.Strings(expectedPaths)
		So(taskPaths, ShouldResemble, expectedPaths)
	})
}

func TestSuccessfulPushLabstations(t *testing.T) {
	Convey("success", t, func() {
		ctx := gaetesting.TestingContext()
		tqt := taskqueue.GetTestable(ctx)
		qn := "repair-labstations"
		tqt.CreateQueue(qn)
		hosts := []string{"host1", "host2"}
		err := PushRepairLabstations(ctx, hosts)
		So(err, ShouldBeNil)
		tasks := tqt.GetScheduledTasks()
		t, ok := tasks[qn]
		So(ok, ShouldBeTrue)
		var taskPaths []string
		for _, v := range t {
			taskPaths = append(taskPaths, v.Path)
		}
		sort.Strings(taskPaths)
		expectedPaths := []string{"/internal/task/labstation_repair/host1", "/internal/task/labstation_repair/host2"}
		sort.Strings(expectedPaths)
		So(taskPaths, ShouldResemble, expectedPaths)
	})
}

func TestUnknownQueuePush(t *testing.T) {
	Convey("no taskqueue", t, func() {
		ctx := gaetesting.TestingContext()
		tqt := taskqueue.GetTestable(ctx)
		tqt.CreateQueue("no-repair-bots")
		err := PushRepairDUTs(ctx, []string{"host1", "host2"})
		So(err, ShouldNotBeNil)
	})
}
