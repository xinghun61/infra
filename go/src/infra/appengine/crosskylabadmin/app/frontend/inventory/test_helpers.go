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
	"fmt"
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/inventory/internal/fakes"
	"testing"

	"github.com/golang/mock/gomock"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/common/proto/gerrit"
	"go.chromium.org/luci/common/proto/gitiles"
	"golang.org/x/net/context"
)

type testFixture struct {
	T *testing.T
	C context.Context

	Inventory fleet.InventoryServer

	FakeGerrit  *fakes.GerritClient
	FakeGitiles *fakes.GitilesClient
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

	tf.FakeGerrit = &fakes.GerritClient{}
	tf.FakeGitiles = fakes.NewGitilesClient()
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

// testInventoryDut contains a subset of inventory fields for a DUT.
type testInventoryDut struct {
	id    string
	model string
	pool  string
}

// setupLabInventoryArchive sets up fake gitiles to return the inventory of
// duts provided.
func setupLabInventoryArchive(c context.Context, g *fakes.GitilesClient, duts []testInventoryDut) error {
	return g.AddArchive(config.Get(c).Inventory, []byte(labInventoryStrFromDuts(duts)), []byte{})
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
