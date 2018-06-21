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

package app

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"
	"golang.org/x/net/context"
)

func TestTasker(t *testing.T) {
	t.Parallel()
	Convey("In testing context", t, FailureHalts, func() {
		c := gaetesting.TestingContextWithAppID("dev~infra-crosskylabadmin")
		datastore.GetTestable(c).Consistent(true)
		fsc := &fakeSwarmingClient{
			pool: swarmingBotPool,
		}
		server := taskerServerImpl{
			swarmingClientFactory{
				swarmingClientHook: func(context.Context, string) (SwarmingClient, error) {
					return fsc, nil
				},
			},
		}

		Convey("TriggerRepairOnIdle returns internal error", func() {
			_, err := server.TriggerRepairOnIdle(c, nil)
			So(err, ShouldNotBeNil)
		})

		Convey("TriggerRepairOnRepairFailed returns internal error", func() {
			_, err := server.TriggerRepairOnRepairFailed(c, nil)
			So(err, ShouldNotBeNil)
		})

		Convey("EnsureBackgroundTasks returns internal error", func() {
			_, err := server.EnsureBackgroundTasks(c, nil)
			So(err, ShouldNotBeNil)
		})
	})
}
