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
	"archive/tar"
	"bytes"
	"compress/gzip"
	"fmt"
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/config"
	"testing"

	"github.com/golang/mock/gomock"
	"github.com/golang/protobuf/ptypes/empty"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/common/proto/gerrit"
	"go.chromium.org/luci/common/proto/gitiles"
	"golang.org/x/net/context"
	"google.golang.org/grpc"
)

type testFixture struct {
	T *testing.T
	C context.Context

	Inventory fleet.InventoryServer

	FakeGerrit  *fakeGerritClient
	FakeGitiles *fakeGitilesClient
	MockTracker *fleet.MockTrackerServer
}

// newTextFixture creates a new testFixture to be used in unittests.
//
// The function returns the created testFixture and a validation function that
// must be deferred by the caller.
//
// TODO(pprabhu) Deduplicate common setup code with frontend/test_common.go as
// part of moving all services to sub-packages. (See TODO in inventory.go)
func newTestFixture(t *testing.T) (testFixture, func()) {
	tf := testFixture{T: t, C: testingContext()}

	tf.FakeGerrit = &fakeGerritClient{}
	tf.FakeGitiles = &fakeGitilesClient{
		ArchiveDir: "testdata",
		Archived:   make(map[string][]byte),
	}
	tf.Inventory = &ServerImpl{
		GerritFactory: func(context.Context, string) (gerrit.GerritClient, error) {
			return tf.FakeGerrit, nil
		},
		GitilesFactory: func(context.Context, string) (gitiles.GitilesClient, error) {
			return tf.FakeGitiles, nil
		},
		TrackerFactory: func() fleet.TrackerServer {
			return tf.MockTracker
		},
	}

	mc := gomock.NewController(t)
	tf.MockTracker = fleet.NewMockTrackerServer(mc)

	validate := func() {
		mc.Finish()
	}
	return tf, validate
}

func testingContext() context.Context {
	c := gaetesting.TestingContextWithAppID("dev~infra-crosskylabadmin")
	c = config.Use(c, &config.Config{
		AccessGroup: "fake-access-group",
		Inventory: &config.Inventory{
			GitilesHost:            "some-gitiles-host",
			GerritHost:             "some-gerrit-host",
			Project:                "some-project",
			Branch:                 "master",
			LabDataPath:            "data/skylab/lab.textpb",
			InfrastructureDataPath: "data/skylab/server_db.textpb",
			Environment:            "ENVIRONMENT_STAGING",
		},
	})
	datastore.GetTestable(c).Consistent(true)

	c = gologger.StdConfig.Use(c)
	c = logging.SetLevel(c, logging.Debug)
	return c
}

type fakeGitilesClient struct {
	ArchiveDir string
	Archived   map[string][]byte
}

// Log implements gitiles.GitilesClient interface.
func (g *fakeGitilesClient) Log(context.Context, *gitiles.LogRequest, ...grpc.CallOption) (*gitiles.LogResponse, error) {
	return nil, fmt.Errorf("fakeGitilesClient does not support Log")
}

// Refs implements gitiles.GitilesClient interface.
func (g *fakeGitilesClient) Refs(context.Context, *gitiles.RefsRequest, ...grpc.CallOption) (*gitiles.RefsResponse, error) {
	return nil, fmt.Errorf("fakeGitilesClient does not support Refs")
}

// Archive implements gitiles.GitilesClient interface.
func (g *fakeGitilesClient) Archive(ctx context.Context, in *gitiles.ArchiveRequest, opts ...grpc.CallOption) (*gitiles.ArchiveResponse, error) {
	k := projectRefKey(in.Project, in.Ref)
	d, ok := g.Archived[k]
	if !ok {
		return nil, fmt.Errorf("Unkonwn project reference %s", k)
	}
	return &gitiles.ArchiveResponse{
		Filename: fmt.Sprintf("fake_gitiles_archive"),
		Contents: d,
	}, nil
}

// TODO(akeshet/pprabhu): Consider splitting this into separate helpers for labData and inventoryData. Or, if callers will
// be specifying both lab and inventory data, add a struct that holds both rather than passing each as individual arguments.
func (g *fakeGitilesClient) addArchive(ic *config.Inventory, labData []byte, inventoryData []byte) error {
	var buf bytes.Buffer
	gw := gzip.NewWriter(&buf)
	tw := tar.NewWriter(gw)

	if err := tw.WriteHeader(&tar.Header{
		Name: ic.LabDataPath,
		Mode: 0777,
		Size: int64(len(labData)),
	}); err != nil {
		return err
	}
	if _, err := tw.Write(labData); err != nil {
		return err
	}
	if err := tw.WriteHeader(&tar.Header{
		Name: ic.InfrastructureDataPath,
		Mode: 0777,
		Size: int64(len(inventoryData)),
	}); err != nil {
		return err
	}
	if _, err := tw.Write(inventoryData); err != nil {
		return err
	}
	if err := tw.Close(); err != nil {
		return err
	}
	if err := gw.Close(); err != nil {
		return err
	}
	g.Archived[projectRefKey(ic.Project, ic.Branch)] = buf.Bytes()
	return nil
}

// testInventoryDut contains a subset of inventory fields for a DUT.
type testInventoryDut struct {
	id    string
	model string
	pool  string
}

// setupLabInventoryArchive sets up fake gitiles to return the inventory of
// duts provided.
func setupLabInventoryArchive(c context.Context, g *fakeGitilesClient, duts []testInventoryDut) error {
	return g.addArchive(config.Get(c).Inventory, []byte(labInventoryStrFromDuts(duts)), nil)
}

func projectRefKey(project, ref string) string {
	return fmt.Sprintf("%s::%s", project, ref)
}

type trackerPartialFake struct {
	DutHealths map[string]fleet.Health
}

// SummarizeBots implements the fleet.TrackerService interface.
func (t *trackerPartialFake) SummarizeBots(c context.Context, req *fleet.SummarizeBotsRequest) (*fleet.SummarizeBotsResponse, error) {
	summaries := make([]*fleet.BotSummary, 0, len(req.Selectors))
	for _, s := range req.Selectors {
		h, ok := t.DutHealths[s.DutId]
		// Tracker silently skips any selectors that don't match existing DUTs.
		if !ok {
			continue
		}
		summaries = append(summaries, &fleet.BotSummary{DutId: s.DutId, Health: h})
	}
	return &fleet.SummarizeBotsResponse{Bots: summaries}, nil
}

type fakeGerritClient struct {
	nextNumber int64
	Changes    []*fakeChange
}

type fakeChange struct {
	gerrit.ChangeInfo
	fakeChangeEdit
	IsSubmitted bool
}

type fakeChangeEdit struct {
	Path        string
	Content     string
	IsPublished bool
	IsAbandoned bool
}

func (gc *fakeGerritClient) GetChange(ctx context.Context, in *gerrit.GetChangeRequest, opts ...grpc.CallOption) (*gerrit.ChangeInfo, error) {
	for _, c := range gc.Changes {
		if in.Number == c.Number {
			ret := c.ChangeInfo
			return &ret, nil
		}
	}
	return nil, fmt.Errorf("No change for %+v", in)
}

func (gc *fakeGerritClient) CreateChange(ctx context.Context, in *gerrit.CreateChangeRequest, opts ...grpc.CallOption) (*gerrit.ChangeInfo, error) {
	c := &fakeChange{
		ChangeInfo: gerrit.ChangeInfo{
			Number:          gc.nextNumber,
			Project:         in.Project,
			Ref:             in.Ref,
			Status:          gerrit.ChangeInfo_NEW,
			CurrentRevision: "patch_set_1",
		},
	}
	gc.nextNumber++
	gc.Changes = append(gc.Changes, c)

	// return a copy
	ret := c.ChangeInfo
	return &ret, nil
}

func (gc *fakeGerritClient) ChangeEditFileContent(ctx context.Context, in *gerrit.ChangeEditFileContentRequest, opts ...grpc.CallOption) (*empty.Empty, error) {
	for _, c := range gc.Changes {
		if in.Number == c.Number {
			c.fakeChangeEdit.Path = in.FilePath
			c.fakeChangeEdit.Content = string(in.Content)
			return &empty.Empty{}, nil
		}
	}
	return &empty.Empty{}, fmt.Errorf("No change edit for %+v", in)
}

func (gc *fakeGerritClient) ChangeEditPublish(ctx context.Context, in *gerrit.ChangeEditPublishRequest, opts ...grpc.CallOption) (*empty.Empty, error) {
	for _, c := range gc.Changes {
		if in.Number == c.Number {
			c.fakeChangeEdit.IsPublished = true
			return &empty.Empty{}, nil
		}
	}
	return &empty.Empty{}, fmt.Errorf("No change edit for %+v", in)
}

func (gc *fakeGerritClient) SetReview(ctx context.Context, in *gerrit.SetReviewRequest, opts ...grpc.CallOption) (*gerrit.ReviewResult, error) {
	// Not needed for tests.
	return &gerrit.ReviewResult{}, nil
}

func (gc *fakeGerritClient) SubmitChange(ctx context.Context, in *gerrit.SubmitChangeRequest, opts ...grpc.CallOption) (*gerrit.ChangeInfo, error) {
	for _, c := range gc.Changes {
		if in.Number == c.Number {
			c.IsSubmitted = true
			c.ChangeInfo.Status = gerrit.ChangeInfo_MERGED
			// return a copy
			ret := c.ChangeInfo
			return &ret, nil
		}
	}
	return nil, fmt.Errorf("No change for %+v", in)
}

func (gc *fakeGerritClient) AbandonChange(ctx context.Context, in *gerrit.AbandonChangeRequest, opts ...grpc.CallOption) (*gerrit.ChangeInfo, error) {
	for _, c := range gc.Changes {
		if in.Number == c.Number {
			c.IsAbandoned = true
			// return a copy
			ret := c.ChangeInfo
			return &ret, nil
		}
	}
	return nil, fmt.Errorf("No change for %+v", in)
}

func labInventoryStrFromDuts(duts []testInventoryDut) string {
	ptext := ""
	for _, dut := range duts {
		ptext = fmt.Sprintf(`%s
			duts {
				common {
					id: "%s"
					hostname: "%s"
					labels {
						model: "%s"
						critical_pools: %s
					}
					environment: ENVIRONMENT_STAGING
				}
			}`,
			ptext,
			dut.id, dut.id, dut.model, dut.pool,
		)
	}
	return ptext
}
