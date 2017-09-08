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
	"testing"

	"golang.org/x/net/context"

	"infra/monorail"
	"infra/monorail/monorailtest"

	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/testing/prpctest"
	"go.chromium.org/luci/milo/api/proto"

	"infra/appengine/luci-migration/config"
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
			ID:      bid("tryserver.chromium.linux", "linux_chromium_rel_ng"),
			IssueID: storage.IssueID{Hostname: "monorail-prod.appspot.com", Project: "chromium", ID: 54},
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
		var monorailReqs []*monorail.InsertIssueRequest
		monorailServer := &monorailtest.ServerMock{
			InsertIssueImpl: func(c context.Context, in *monorail.InsertIssueRequest) (*monorail.InsertIssueResponse, error) {
				monorailReqs = append(monorailReqs, in)
				return &monorail.InsertIssueResponse{Issue: &monorail.Issue{Id: 55}}, nil
			},
		}

		// Discover tryserver.chromium.linux builders.
		d := Builders{
			Buildbot:         milo.NewBuildbotPRPCClient(buildbotPrpcClient),
			Monorail:         monorailtest.NewClient(monorailServer),
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

		// Verify the request to create a bug for asan.
		So(monorailReqs, ShouldHaveLength, 1)
		So(monorailReqs[0].Issue.Summary, ShouldEqual, "Migrate \"linux_chromium_asan_rel_ng\" to LUCI")

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

			IssueID: storage.IssueID{Hostname: "monorail-prod.appspot.com", Project: "chromium", ID: 55},

			LUCIBuildbucketBucket:  "luci.chromium.try",
			LUCIBuildbucketBuilder: "linux_chromium_asan_rel_ng",
		})

		// Verify linux_chromium_rel_ng was notrediscovered.
		chromiumRelNg.IssueID = storage.IssueID{}
		err = datastore.Get(c, chromiumRelNg)
		So(err, ShouldBeNil)
		So(chromiumRelNg.IssueID.ID, ShouldEqual, 54) // was not overwritten during discovery
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
