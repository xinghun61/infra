// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package discovery

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"strings"
	"testing"

	"golang.org/x/net/context"

	"infra/monorail"
	"infra/monorail/monorailtest"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/testing/prpctest"
	"github.com/luci/luci-go/milo/api/proto"

	"infra/appengine/luci-migration/storage"

	. "github.com/smartystreets/goconvey/convey"
)

func TestDiscovery(t *testing.T) {
	t.Parallel()

	Convey("Discovery", t, func() {
		c := context.Background()
		c = memory.Use(c)

		// Make tryserver.chromium.linux:linux_chromium_rel_ng known.
		chromiumRelNg := &storage.Builder{
			ID:      storage.BuilderID{"tryserver.chromium.linux", "linux_chromium_rel_ng"},
			IssueID: 54,
		}
		err := datastore.Put(c, chromiumRelNg)
		So(err, ShouldBeNil)

		// Mock Buildbot service.
		buildbotServer := prpctest.Server{}
		milo.RegisterBuildbotServer(&buildbotServer, &buildbotMock{
			builders: map[string]struct{}{
				"linux_chromium_rel_ng":      {},
				"linux_chromium_asan_rel_ng": {},
			},
		})
		buildbotServer.Start(c)
		defer buildbotServer.Close()
		buildbotPrpcClient, err := buildbotServer.NewClient()
		So(err, ShouldBeNil)

		// Mock Monorail.
		var actualInsertIssueReq *monorail.InsertIssueRequest
		monorailServer := &monorailMock{
			insertIssue: func(in *monorail.InsertIssueRequest) (*monorail.InsertIssueResponse, error) {
				actualInsertIssueReq = in
				return &monorail.InsertIssueResponse{Issue: &monorail.Issue{Id: 55}}, nil
			},
		}

		// Discover tryserver.chromium.linux builders.
		d := Builders{
			Buildbot: milo.NewBuildbotPRPCClient(buildbotPrpcClient),
			Monorail: monorailtest.NewTestClient(monorailServer),
		}
		linuxTryserver := &storage.Master{
			Name:           "tryserver.chromium.linux",
			SchedulingType: storage.TryScheduling,
			LUCIBucket:     "luci.chromium.try",
			Public:         true,
			OS:             storage.Linux,
		}
		err = d.discoverNewBuildersOf(c, linuxTryserver)
		So(err, ShouldBeNil)

		// Verify the request to create a bug for asan.
		expectedBugDescription := strings.TrimSpace(`
Migrate builder tryserver.chromium.linux:linux_chromium_asan_rel_ng to LUCI.

Buildbot: https://ci.chromium.org/buildbot/tryserver.chromium.linux/linux_chromium_asan_rel_ng
LUCI: https://ci.chromium.org/buildbucket/luci.chromium.try/LUCI%20linux_chromium_asan_rel_ng

I will be posting updates on changes of the migration status.
For the latest status, see
https://app.example.com/masters/tryserver.chromium.linux/builders/linux_chromium_asan_rel_ng
`)
		So(actualInsertIssueReq, ShouldResemble, &monorail.InsertIssueRequest{
			ProjectId: "chromium",
			SendEmail: false,
			Issue: &monorail.Issue{
				Status:      "Untriaged",
				Summary:     "Migrate \"linux_chromium_asan_rel_ng\" to LUCI",
				Description: expectedBugDescription,
				Components:  []string{"Infra>Platform"},
				Labels: []string{
					"Via-Luci-Migration-Dev",
					"Type-Task",
					"Pri-3",
					"Master-tryserver.chromium.linux",
					"Builder-linux_chromium_asan_rel_ng",
					"OS-Linux",
				},
			},
		})

		// Verify linux_chromium_asan_rel_ng was discovered.
		chromiumAsanRelNg := &storage.Builder{
			ID: storage.BuilderID{"tryserver.chromium.linux", "linux_chromium_asan_rel_ng"},
		}
		err = datastore.Get(c, chromiumAsanRelNg)
		So(err, ShouldBeNil)
		So(chromiumAsanRelNg, ShouldResemble, &storage.Builder{
			ID:                     chromiumAsanRelNg.ID,
			SchedulingType:         storage.TryScheduling,
			IssueID:                55,
			Public:                 true,
			LUCIBuildbucketBucket:  "luci.chromium.try",
			LUCIBuildbucketBuilder: "LUCI linux_chromium_asan_rel_ng",
			OS: storage.Linux,
		})

		// Verify linux_chromium_rel_ng was notrediscovered.
		chromiumRelNg.IssueID = 0
		err = datastore.Get(c, chromiumRelNg)
		So(err, ShouldBeNil)
		So(chromiumRelNg.IssueID, ShouldEqual, 54) // was not overwritten during discovery
	})
}

type buildbotMock struct {
	builders map[string]struct{}
}

func (m *buildbotMock) GetCompressedMasterJSON(context.Context, *milo.MasterRequest) (*milo.CompressedMasterJSON, error) {
	masterJSON := masterJSON{
		Builders: m.builders,
	}
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

type monorailMock struct {
	insertIssue func(*monorail.InsertIssueRequest) (*monorail.InsertIssueResponse, error)
}

func (m *monorailMock) InsertIssue(c context.Context, in *monorail.InsertIssueRequest) (*monorail.InsertIssueResponse, error) {
	return m.insertIssue(in)
}
func (*monorailMock) InsertComment(context.Context, *monorail.InsertCommentRequest) (*monorail.InsertCommentResponse, error) {
	panic("not implemented")
}
func (*monorailMock) IssuesList(context.Context, *monorail.IssuesListRequest) (*monorail.IssuesListResponse, error) {
	panic("not implemented")
}
