// Copyright 2017 The LUCI Authors.
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

package storage

import (
	"testing"

	"golang.org/x/net/context"

	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"

	. "github.com/smartystreets/goconvey/convey"
)

func TestBuilderMasterFilter(t *testing.T) {
	t.Parallel()

	Convey("BuilderMasterFilter", t, func() {
		c := context.Background()
		c = memory.Use(c)

		err := datastore.Put(
			c,
			&Builder{
				ID: BuilderID{
					Master:  "tryserver.chromium.linux",
					Builder: "linux_chromium_rel_ng",
				},
				Migration: BuilderMigration{Status: StatusMigrated},
			},
			&Builder{
				ID: BuilderID{
					Master:  "tryserver.chromium.linux",
					Builder: "linux_chromium_asan_rel_ng",
				},
				Migration: BuilderMigration{Status: StatusLUCINotWAI},
			},

			&Builder{
				ID: BuilderID{
					Master:  "tryserver.chromium.mac",
					Builder: "mac_chromium_rel_ng",
				},
				Migration: BuilderMigration{Status: StatusMigrated},
			},
		)
		So(err, ShouldBeNil)
		datastore.GetTestable(c).CatchupIndexes()

		q := BuilderMasterFilter(c, nil, "tryserver.chromium.linux")
		var builders []*Builder
		err = datastore.GetAll(c, q, &builders)
		So(err, ShouldBeNil)
		So(builders, ShouldHaveLength, 2)
		So(builders[0].ID.Master, ShouldEqual, "tryserver.chromium.linux")
		So(builders[1].ID.Master, ShouldEqual, "tryserver.chromium.linux")
	})
}
