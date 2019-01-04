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

package inventory

import (
	"infra/appengine/crosskylabadmin/app/config"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/common/proto/gitiles"
)

func TestFakeGitilesArchive(t *testing.T) {
	Convey("FakeGitilesClient.Archive errors on missing testdata", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		_, err := tf.FakeGitiles.Archive(tf.C, &gitiles.ArchiveRequest{
			Project: "fakeproject",
			Ref:     "master",
		})
		So(err, ShouldNotBeNil)
	})

	Convey("FakeGitilesClient.Archive does not return error with correct testdata", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		ic := &config.Inventory{
			Project:     "fakeproject",
			Branch:      "master",
			LabDataPath: "some/dir",
		}
		So(tf.FakeGitiles.addArchive(ic, []byte("some test data"), nil), ShouldBeNil)
		_, err := tf.FakeGitiles.Archive(tf.C, &gitiles.ArchiveRequest{
			Project: "fakeproject",
			Ref:     "master",
		})
		So(err, ShouldBeNil)
	})
}
