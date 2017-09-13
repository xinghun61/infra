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

	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"
	"infra/monorail"
	"infra/monorail/monorailtest"

	. "github.com/smartystreets/goconvey/convey"
)

func TestDescription(t *testing.T) {
	t.Parallel()

	Convey("Description", t, func() {
		c := context.Background()
		c = memory.Use(c)

		var actualMonorailReq *monorail.InsertIssueRequest
		monorailServer := &monorailtest.ServerMock{
			InsertIssueImpl: func(c context.Context, in *monorail.InsertIssueRequest) (*monorail.InsertIssueResponse, error) {
				actualMonorailReq = in
				return &monorail.InsertIssueResponse{Issue: &monorail.Issue{Id: 55}}, nil
			},
		}

		builder := &storage.Builder{
			ID: storage.BuilderID{
				Master:  "tryserver.chromium.linux",
				Builder: "linux_chromium_rel_ng",
			},
			LUCIBuildbucketBucket: "luci.chromium.try",
			OS: config.OS_LINUX,
			IssueID: storage.IssueID{
				Project: "chromium",
			},
		}

		issueID, err := CreateBuilderBug(c, monorailtest.NewClient(monorailServer), builder)
		So(err, ShouldBeNil)
		So(issueID, ShouldEqual, 55)

		expectedBugDescription := strings.TrimSpace(`
Migrate builder tryserver.chromium.linux:linux_chromium_rel_ng to LUCI.

Buildbot: https://ci.chromium.org/buildbot/tryserver.chromium.linux/linux_chromium_rel_ng
LUCI: https://ci.chromium.org/buildbucket/luci.chromium.try/linux_chromium_rel_ng

Migration app will be posting updates on changes of the migration status.
For the latest status, see
https://app.example.com/masters/tryserver.chromium.linux/builders/linux_chromium_rel_ng

Migration app will close this bug when the builder is entirely migrated from Buildbot to LUCI.
`)
		So(actualMonorailReq, ShouldResemble, &monorail.InsertIssueRequest{
			ProjectId: "chromium",
			SendEmail: true,
			Issue: &monorail.Issue{
				Status:      "Available",
				Summary:     "Migrate \"linux_chromium_rel_ng\" to LUCI",
				Description: expectedBugDescription,
				Components:  []string{"Infra>Platform"},
				Labels: []string{
					"Via-Luci-Migration",
					"Type-Task",
					"Pri-3",
					"Master-tryserver.chromium.linux",
					"Restrict-View-Google",
					"OS-LINUX",
				},
			},
		})
	})
}
