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

package discovery

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"testing"

	"golang.org/x/net/context"

	"infra/monorail"
	"infra/monorail/monorailtest"

	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/common/testing/prpctest"
	"go.chromium.org/luci/milo/api/proto"

	"infra/appengine/luci-migration/bugs"
	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"

	. "github.com/smartystreets/goconvey/convey"
)

func TestDiscovery(t *testing.T) {
	t.Parallel()

	Convey("Discovery", t, func() {
		c := context.Background()
		c = memory.Use(c)
		c = config.Use(c, &config.Config{
			Masters: []*config.Master{
				{
					Name:       "tryserver.chromium.linux",
					LuciBucket: "luci.chromium.try",
				},
			},
		})
		c, _ = testclock.UseTime(c, testclock.TestRecentTimeUTC)
		datastore.GetTestable(c).Consistent(true)

		// Make tryserver.chromium.linux:linux_chromium_rel_ng known.
		chromiumRelNg := &storage.Builder{
			ID:      bid("tryserver.chromium.linux", "linux_chromium_rel_ng"),
			IssueID: storage.IssueID{Hostname: "monorail-prod.appspot.com", Project: "chromium", ID: 54},
		}
		deletedBuilder := &storage.Builder{
			ID:      bid("tryserver.chromium.linux", "deleted"),
			IssueID: storage.IssueID{Hostname: "monorail-prod.appspot.com", Project: "chromium", ID: 55},
		}
		flippedBuilder := &storage.Builder{
			ID:        bid("tryserver.chromium.linux", "migrated_not_decommed"),
			IssueID:   storage.IssueID{Hostname: "monorail-prod.appspot.com", Project: "chromium", ID: 60},
			Migration: storage.BuilderMigration{Status: storage.StatusMigrated},
		}
		err := datastore.Put(c, chromiumRelNg, deletedBuilder, flippedBuilder)
		So(err, ShouldBeNil)
		datastore.GetTestable(c).CatchupIndexes()

		// Mock Buildbot service.
		buildbotServer := prpctest.Server{}
		milo.RegisterBuildbotServer(&buildbotServer, &buildbotMock{
			builders: []map[string]struct{}{
				{
					"linux_chromium_rel_ng":      {},
					"linux_chromium_asan_rel_ng": {},
					"migrated_not_decommed":      {},
				},
				{
					"deleted":                    {},
					"linux_chromium_rel_ng":      {},
					"linux_chromium_asan_rel_ng": {},
					"migrated_not_decommed":      {},
				},
			},
		})
		buildbotServer.Start(c)
		defer buildbotServer.Close()
		buildbotPrpcClient, err := buildbotServer.NewClient()
		So(err, ShouldBeNil)

		// Mock Monorail.
		var bugReqs []*monorail.InsertIssueRequest
		var commentReqs []*monorail.InsertCommentRequest
		monorailServer := &monorailtest.ServerMock{
			InsertIssueImpl: func(c context.Context, in *monorail.InsertIssueRequest) (*monorail.InsertIssueResponse, error) {
				bugReqs = append(bugReqs, in)
				return &monorail.InsertIssueResponse{Issue: &monorail.Issue{Id: 56}}, nil
			},
			InsertCommentImpl: func(c context.Context, in *monorail.InsertCommentRequest) (*monorail.InsertCommentResponse, error) {
				commentReqs = append(commentReqs, in)
				return &monorail.InsertCommentResponse{}, nil
			},
		}

		// Discover tryserver.chromium.linux builders.
		d := Builders{
			Buildbot:         milo.NewBuildbotPRPCClient(buildbotPrpcClient),
			Monorail:         bugs.ForwardingFactory(monorailServer),
			MonorailHostname: "monorail-prod.appspot.com",
		}
		linuxTryserver := &config.Master{
			Name:           "tryserver.chromium.linux",
			SchedulingType: config.SchedulingType_TRYJOBS,
			Os:             config.OS_LINUX,

			LuciBucket: "luci.chromium.try",
		}
		err = d.Discover(c, linuxTryserver)
		So(err, ShouldBeNil)

		// Verify sent monorail requests.
		So(bugReqs, ShouldHaveLength, 1)
		So(bugReqs[0].Issue.Summary, ShouldEqual, "Migrate \"linux_chromium_asan_rel_ng\" to LUCI")
		So(commentReqs, ShouldHaveLength, 0)

		// Verify linux_chromium_asan_rel_ng was discovered.
		chromiumAsanRelNg := &storage.Builder{
			ID: bid("tryserver.chromium.linux", "linux_chromium_asan_rel_ng"),
		}
		err = datastore.Get(c, chromiumAsanRelNg)
		So(err, ShouldBeNil)
		So(chromiumAsanRelNg, ShouldResemble, &storage.Builder{
			ID:             chromiumAsanRelNg.ID,
			SchedulingType: config.SchedulingType_TRYJOBS,
			OS:             config.OS_LINUX,

			IssueID:                 storage.IssueID{Hostname: "monorail-prod.appspot.com", Project: "chromium", ID: 56},
			IssueDescriptionVersion: bugs.DescriptionVersion,

			NotOnBuildbot: false,
		})

		// Verify linux_chromium_rel_ng was not rediscovered.
		chromiumRelNg.IssueID = storage.IssueID{}
		err = datastore.Get(c, chromiumRelNg)
		So(err, ShouldBeNil)
		So(chromiumRelNg.IssueID.ID, ShouldEqual, 54) // was not overwritten during discovery
		So(chromiumRelNg.NotOnBuildbot, ShouldEqual, false)

		// Verify lost builder got its entity updated.
		err = datastore.Get(c, deletedBuilder)
		So(err, ShouldBeNil)
		So(deletedBuilder.NotOnBuildbot, ShouldEqual, true)

		Convey("rediscovery", func() {
			err = d.Discover(c, linuxTryserver)
			So(err, ShouldBeNil)

			// Verify re-found builder got its entity updated.
			err = datastore.Get(c, deletedBuilder)
			So(err, ShouldBeNil)
			So(deletedBuilder.NotOnBuildbot, ShouldEqual, false)

			// Verify sent monorail requests (should be same as before rediscovery; no new bugs).
			So(bugReqs, ShouldHaveLength, 1)
		})
	})
}

type buildbotMock struct {
	counter  int
	builders []map[string]struct{}
}

func (m *buildbotMock) GetCompressedMasterJSON(c context.Context, req *milo.MasterRequest) (*milo.CompressedMasterJSON, error) {
	if m.counter >= len(m.builders) {
		panic("more calls to Buildbot mock than expected")
	}

	if !req.NoEmulation {
		return nil, fmt.Errorf("did not disable emulation")
	}
	masterJSON := masterJSON{
		Builders: m.builders[m.counter],
	}
	m.counter++
	buf := &bytes.Buffer{}
	gzipped := gzip.NewWriter(buf)
	err := json.NewEncoder(gzipped).Encode(masterJSON)
	if err != nil {
		return nil, err
	}

	if err := gzipped.Flush(); err != nil {
		return nil, err
	}
	return &milo.CompressedMasterJSON{
		Data: buf.Bytes(),
	}, nil
}
func (*buildbotMock) GetBuildbotBuildJSON(context.Context, *milo.BuildbotBuildRequest) (*milo.BuildbotBuildJSON, error) {
	panic("not implemented")
}
func (*buildbotMock) GetBuildbotBuildsJSON(context.Context, *milo.BuildbotBuildsRequest) (*milo.BuildbotBuildsJSON, error) {
	panic("not implemented")
}
