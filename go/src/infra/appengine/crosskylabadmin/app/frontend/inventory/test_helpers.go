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
	"testing"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
	"infra/appengine/crosskylabadmin/app/clients/mock"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/fakes"
	"infra/libs/skylab/inventory"

	"github.com/golang/mock/gomock"
	"github.com/golang/protobuf/proto"
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

	FakeGerrit   *fakes.GerritClient
	FakeGitiles  *fakes.GitilesClient
	MockSwarming *mock.MockSwarmingClient
	MockTracker  *fleet.MockTrackerServer
}

// newTextFixture creates a new testFixture to be used in unittests.
//
// The function returns the created testFixture and a validation function that
// must be deferred by the caller.
//
// TODO(pprabhu) Deduplicate common setup code with frontend/test_common.go as
// part of moving all services to sub-packages. (See TODO in inventory.go)
func newTestFixture(t *testing.T) (testFixture, func()) {
	return newTestFixtureWithContext(testingContext(), t)
}

func newTestFixtureWithContext(ctx context.Context, t *testing.T) (testFixture, func()) {
	tf := testFixture{T: t, C: ctx}
	mc := gomock.NewController(t)

	tf.FakeGerrit = &fakes.GerritClient{}
	tf.FakeGitiles = fakes.NewGitilesClient()
	tf.MockSwarming = mock.NewMockSwarmingClient(mc)
	tf.MockTracker = fleet.NewMockTrackerServer(mc)
	tf.Inventory = &ServerImpl{
		GerritFactory: func(context.Context, string) (gerrit.GerritClient, error) {
			return tf.FakeGerrit, nil
		},
		GitilesFactory: func(context.Context, string) (gitiles.GitilesClient, error) {
			return tf.FakeGitiles, nil
		},
		SwarmingFactory: func(context.Context, string) (clients.SwarmingClient, error) {
			return tf.MockSwarming, nil
		},
		TrackerFactory: func() fleet.TrackerServer {
			return tf.MockTracker
		},
	}

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
	id       string
	hostname string
	model    string
	pool     string
}

// setGitilesDUTs sets up fake gitiles to return the inventory of
// duts provided.
func setGitilesDUTs(c context.Context, g *fakes.GitilesClient, duts []testInventoryDut) error {
	return g.SetInventory(config.Get(c).Inventory, fakes.InventoryData{
		Lab: inventoryBytesFromDUTs(duts),
	})
}

func inventoryBytesFromDUTs(duts []testInventoryDut) []byte {
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
			dut.id, dut.hostname, dut.model, dut.pool,
		)
	}
	return []byte(ptext)
}

// testDutOnServer contains a subset of the fields in infrastructure servers.
type testInventoryServer struct {
	hostname    string
	environment inventory.Environment
	dutIDs      []string
}

// setupInfraInventoryArchive sets up fake gitiles to return the inventory of
// duts provided.
func setupInfraInventoryArchive(c context.Context, g *fakes.GitilesClient, servers []testInventoryServer) error {
	return g.SetInventory(config.Get(c).Inventory, fakes.InventoryData{
		Infrastructure: inventoryBytesFromServers(servers),
	})
}

func inventoryBytesFromServers(servers []testInventoryServer) []byte {
	infra := &inventory.Infrastructure{
		Servers: make([]*inventory.Server, 0, len(servers)),
	}
	for _, s := range servers {
		status := inventory.Server_STATUS_PRIMARY
		hostname := s.hostname
		env := s.environment
		server := &inventory.Server{
			DutUids:     []string{},
			Environment: &env,
			Hostname:    &hostname,
			Roles:       []inventory.Server_Role{inventory.Server_ROLE_SKYLAB_DRONE},
			Status:      &status,
		}
		server.DutUids = append(server.DutUids, s.dutIDs...)
		infra.Servers = append(infra.Servers, server)
	}
	return []byte(proto.MarshalTextString(infra))
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
