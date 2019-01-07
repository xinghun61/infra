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

package fakes

import (
	"infra/appengine/crosskylabadmin/app/config"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/common/proto/gitiles"
)

func TestFakeGitilesArchive(t *testing.T) {
	Convey("FakeGitilesClient.Archive errors on missing testdata", t, func() {
		ctx := gaetesting.TestingContextWithAppID("dev~infra-crosskylabadmin")
		gitilesC := NewGitilesClient()

		_, err := gitilesC.Archive(ctx, &gitiles.ArchiveRequest{
			Project: "fakeproject",
			Ref:     "master",
		})
		So(err, ShouldNotBeNil)
	})

	Convey("FakeGitilesClient.Archive does not return error with correct testdata", t, func() {
		ctx := gaetesting.TestingContextWithAppID("dev~infra-crosskylabadmin")
		gitilesC := NewGitilesClient()

		ic := &config.Inventory{
			Project:     "fakeproject",
			Branch:      "master",
			LabDataPath: "some/dir",
		}
		So(gitilesC.AddArchive(ic, []byte("some test data"), nil), ShouldBeNil)
		_, err := gitilesC.Archive(ctx, &gitiles.ArchiveRequest{
			Project: "fakeproject",
			Ref:     "master",
		})
		So(err, ShouldBeNil)
	})
}
