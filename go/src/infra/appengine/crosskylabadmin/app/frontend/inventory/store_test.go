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
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestStoreValidity(t *testing.T) {
	Convey("With 1 known DUT", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_suites_0", "link", "DUT_POOL_SUITES"},
		})
		So(err, ShouldBeNil)

		Convey("store initially contains no data", func() {
			store := NewGitStore(tf.FakeGerrit, tf.FakeGitiles)
			So(store.Lab, ShouldBeNil)

			Convey("and initial Commit() fails", func() {
				_, err := store.Commit(tf.C)
				So(err, ShouldNotBeNil)
			})

			Convey("on Refresh(), store obtains data", func() {
				err := store.Refresh(tf.C)
				So(err, ShouldBeNil)
				So(store.Lab, ShouldNotBeNil)

				Convey("on Commit(), store is flushed", func() {
					_, err := store.Commit(tf.C)
					So(err, ShouldBeNil)
					So(store.Lab, ShouldBeNil)

					Convey("and invalidated", func() {
						_, err := store.Commit(tf.C)
						So(err, ShouldNotBeNil)
					})
				})
			})
		})
	})
}
