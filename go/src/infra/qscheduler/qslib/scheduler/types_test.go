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

// TODO(akeshet): The tests in this file make use of a lot of unexported
// methods and fields. It would be better if they were rewritten to use
// only the exported API of the scheduler. That would also entail building
// an exported API for getting job prioritization.

package scheduler

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestClone(t *testing.T) {
	Convey("Given a state with some balances, accounts, and requests", t, func() {
		s := &state{
			balances: map[string]balance{
				"account1": {1, 2, 3},
				"account2": {3, 4, 5},
			},
			workers: map[string]*worker{
				"worker1": {runningTask: &taskRun{cost: balance{11, 12, 13}, requestID: "r1", request: &request{}}},
				"worker2": {runningTask: &taskRun{cost: balance{13, 14, 15}, requestID: "r2", request: &request{}}},
			},
		}
		Convey("when state is Cloned", func() {
			sClone := s.Clone()
			Convey("then account balance values should match.", func() {
				So(sClone.balances["account1"], ShouldResemble, balance{1, 2, 3})
				So(sClone.balances["account2"], ShouldResemble, balance{3, 4, 5})
			})
			Convey("then running task costs should match.", func() {
				So(sClone.workers["worker1"].runningTask.cost, ShouldResemble, balance{11, 12, 13})
				So(sClone.workers["worker2"].runningTask.cost, ShouldResemble, balance{13, 14, 15})
			})
		})
	})
}
