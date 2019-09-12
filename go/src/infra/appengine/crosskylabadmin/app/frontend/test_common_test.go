// Copyright 2018 The LUCI Authors.
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

package frontend

import (
	"testing"

	"infra/appengine/crosskylabadmin/app/clients"

	. "github.com/smartystreets/goconvey/convey"
)

func TestCreateTaskArgsMatcher(t *testing.T) {
	Convey("matching with nil args fails", t, func() {
		So((&createTaskArgsMatcher{
			DutID:        "dut_id",
			DutState:     "dut_state",
			Priority:     10,
			CmdSubString: "-b c",
		}).Matches(nil), ShouldBeFalse)
	})

	Convey("with non-nil args", t, func() {
		arg := &clients.SwarmingCreateTaskArgs{
			Cmd:                  []string{"a", "-b", "c"},
			DutID:                "dut_id",
			DutState:             "dut_state",
			ExecutionTimeoutSecs: 20,
			Priority:             10,
		}
		Convey("all fields matching pass", func() {
			So((&createTaskArgsMatcher{
				DutID:        "dut_id",
				DutState:     "dut_state",
				Priority:     10,
				CmdSubString: "-b c",
			}).Matches(arg), ShouldBeTrue)
		})
		Convey("missing fields matching pass", func() {
			So((&createTaskArgsMatcher{}).Matches(arg), ShouldBeTrue)
		})

		Convey("mistaching DutID fails", func() {
			So((&createTaskArgsMatcher{
				DutID:        "wrong",
				DutState:     "dut_state",
				Priority:     10,
				CmdSubString: "-b c",
			}).Matches(arg), ShouldBeFalse)
		})
		Convey("mistaching DutState fails", func() {
			So((&createTaskArgsMatcher{
				DutID:        "dut_id",
				DutState:     "wrong",
				Priority:     10,
				CmdSubString: "-b c",
			}).Matches(arg), ShouldBeFalse)
		})
		Convey("mistaching Priority fails", func() {
			So((&createTaskArgsMatcher{
				DutID:        "dut_id",
				DutState:     "dut_state",
				Priority:     999,
				CmdSubString: "-b c",
			}).Matches(arg), ShouldBeFalse)
		})
		Convey("mistaching CmdSubstring fails", func() {
			So((&createTaskArgsMatcher{
				DutID:        "dut_id",
				DutState:     "dut_state",
				Priority:     10,
				CmdSubString: "-x z",
			}).Matches(arg), ShouldBeFalse)
		})
	})
}
