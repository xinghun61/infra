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

package bugs

import (
	"strings"
	"testing"

	"golang.org/x/net/context"

	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/luci/common/clock/testclock"

	"infra/appengine/luci-migration/storage"
	"infra/monorail"
	"infra/monorail/monorailtest"

	. "github.com/smartystreets/goconvey/convey"
)

func TestPostComment(t *testing.T) {
	t.Parallel()

	Convey("PostComment", t, func() {
		c := context.Background()
		c = memory.UseWithAppID(c, "luci-migration")

		var actualMonorailReq *monorail.InsertCommentRequest
		monorailServer := &monorailtest.ServerMock{
			InsertCommentImpl: func(c context.Context, in *monorail.InsertCommentRequest) (*monorail.InsertCommentResponse, error) {
				actualMonorailReq = in
				return &monorail.InsertCommentResponse{}, nil
			},
		}

		builder := &storage.Builder{
			ID: storage.BuilderID{
				Master:  "tryserver.chromium.linux",
				Builder: "linux_chromium_rel_ng",
			},
			IssueID: storage.IssueID{
				Hostname: "monorail.example.com",
				Project:  "chromium",
				ID:       54,
			},
			Migration: storage.BuilderMigration{
				AnalysisTime: testclock.TestRecentTimeUTC,
				Status:       storage.StatusLUCIWAI,
				Correctness:  1.0,
				Speed:        0.9,
			},
		}

		Convey("WAI", func() {
			err := PostComment(c, ForwardingFactory(monorailServer), builder)
			So(err, ShouldBeNil)

			So(actualMonorailReq, ShouldResemble, &monorail.InsertCommentRequest{
				Issue: &monorail.IssueRef{
					ProjectId: "chromium",
					IssueId:   54,
				},
				SendEmail: true,
				Comment: &monorail.InsertCommentRequest_Comment{
					Content: strings.TrimSpace(
						`Status changed to "LUCI WAI" (correctness 100%, speed 90%)
For the latest status, see https://luci-migration.example.com/masters/tryserver.chromium.linux/builders/linux_chromium_rel_ng`),
					Updates: &monorail.Update{
						Labels: []string{"MigrationStatus-WAI"},
					},
				},
			})
		})
		Convey("Not WAI", func() {
			builder.Migration.Status = storage.StatusLUCINotWAI
			err := PostComment(c, ForwardingFactory(monorailServer), builder)
			So(err, ShouldBeNil)
			So(actualMonorailReq.Comment.Updates.Labels, ShouldResemble, []string{"-MigrationStatus-WAI"})
		})

		Convey("Migrated", func() {
			builder.Migration.Status = storage.StatusMigrated
			err := PostComment(c, ForwardingFactory(monorailServer), builder)
			So(err, ShouldBeNil)
			So(actualMonorailReq.Comment.Updates.Labels, ShouldResemble, []string{"MigrationStatus-WAI"})
			So(actualMonorailReq.Comment.Updates.Status, ShouldEqual, monorail.StatusFixed)
			So(actualMonorailReq.Comment.Content, ShouldEqual, `Status changed to "Migrated"`)
		})

		Convey("Do not post twice", func() {
			reqs := 0

			monorailServer.InsertCommentImpl = func(c context.Context, in *monorail.InsertCommentRequest) (*monorail.InsertCommentResponse, error) {
				reqs++
				return &monorail.InsertCommentResponse{}, nil
			}

			err := PostComment(c, ForwardingFactory(monorailServer), builder)
			So(err, ShouldBeNil)
			err = PostComment(c, ForwardingFactory(monorailServer), builder)
			So(err, ShouldBeNil)
			So(reqs, ShouldEqual, 1)
		})
	})
}
