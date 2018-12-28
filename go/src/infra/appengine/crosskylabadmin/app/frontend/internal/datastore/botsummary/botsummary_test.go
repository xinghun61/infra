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

package botsummary

import (
	"context"
	"sort"
	"testing"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
)

func TestInsertShouldReturnIDs(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	ctx = memory.Use(ctx)
	bs1 := fleet.BotSummary{DutId: "lexington", DutState: fleet.DutState_NeedsRepair}
	bs2 := fleet.BotSummary{DutId: "saratoga", DutState: fleet.DutState_Ready}
	ids, err := Insert(ctx, map[string]*fleet.BotSummary{
		"bot1": &bs1,
		"bot2": &bs2,
	})
	if err != nil {
		t.Fatalf("Insert returned error: %s", err)
	}
	wantIDs := []string{"lexington", "saratoga"}
	assertIDsEqual(t, wantIDs, ids)
}

func TestInsertAndGetAll(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	ctx = memory.Use(ctx)
	bs1 := fleet.BotSummary{DutId: "lexington", DutState: fleet.DutState_NeedsRepair}
	bs2 := fleet.BotSummary{DutId: "saratoga", DutState: fleet.DutState_Ready}
	_, err := Insert(ctx, map[string]*fleet.BotSummary{
		"bot1": &bs1,
		"bot2": &bs2,
	})
	if err != nil {
		t.Fatalf("Insert returned error: %s", err)
	}
	// Force update since the fake datastore simulates update latency.
	datastore.Raw(ctx).GetTestable().CatchupIndexes()
	es, err := GetAll(ctx)
	if err != nil {
		t.Fatalf("GetAll returned error: %s", err)
	}
	bs, err := decodeEntities(es)
	if err != nil {
		t.Fatalf("Decoding entities returned error: %s", err)
	}
	wantSummaries := []*fleet.BotSummary{&bs1, &bs2}
	cleanSummaries(bs)
	cleanSummaries(wantSummaries)
	assertSummariesEqual(t, wantSummaries, bs)
}

func TestInsertAndGetByDutID(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	ctx = memory.Use(ctx)
	bs1 := fleet.BotSummary{DutId: "lexington", DutState: fleet.DutState_NeedsRepair}
	bs2 := fleet.BotSummary{DutId: "saratoga", DutState: fleet.DutState_Ready}
	_, err := Insert(ctx, map[string]*fleet.BotSummary{
		"bot1": &bs1,
		"bot2": &bs2,
	})
	if err != nil {
		t.Fatalf("Insert returned error: %s", err)
	}
	// Force update since the fake datastore simulates update latency.
	datastore.Raw(ctx).GetTestable().CatchupIndexes()
	es, err := GetByDutID(ctx, []string{"lexington"})
	if err != nil {
		t.Fatalf("GetByDutID returned error: %s", err)
	}
	bs, err := decodeEntities(es)
	if err != nil {
		t.Fatalf("Decoding entities returned error: %s", err)
	}
	wantSummaries := []*fleet.BotSummary{&bs1}
	cleanSummaries(bs)
	cleanSummaries(wantSummaries)
	assertSummariesEqual(t, wantSummaries, bs)
}

func TestInsertAndGetByDimensions(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	ctx = memory.Use(ctx)
	bs1 := fleet.BotSummary{
		DutId:      "lexington",
		Dimensions: &fleet.BotDimensions{DutName: "CV-2"},
	}
	bs2 := fleet.BotSummary{
		DutId:      "saratoga",
		Dimensions: &fleet.BotDimensions{DutName: "CV-3"},
	}
	_, err := Insert(ctx, map[string]*fleet.BotSummary{
		"bot1": &bs1,
		"bot2": &bs2,
	})
	if err != nil {
		t.Fatalf("Insert returned error: %s", err)
	}
	// Force update since the fake datastore simulates update latency.
	datastore.Raw(ctx).GetTestable().CatchupIndexes()
	es, err := GetByDimensions(ctx, &fleet.BotDimensions{DutName: "CV-2"})
	if err != nil {
		t.Fatalf("GetAll returned error: %s", err)
	}
	bs, err := decodeEntities(es)
	if err != nil {
		t.Fatalf("Decoding entities returned error: %s", err)
	}
	wantSummaries := []*fleet.BotSummary{&bs1}
	cleanSummaries(bs)
	cleanSummaries(wantSummaries)
	assertSummariesEqual(t, wantSummaries, bs)
}

// assertIDsEqual asserts that the strings are as expected.  The
// slices are sorted as a side effect.
func assertIDsEqual(t *testing.T, want, got []string) {
	t.Helper()
	sort.Slice(got, func(i, j int) bool { return got[i] < got[j] })
	sort.Slice(want, func(i, j int) bool { return want[i] < want[j] })
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("IDs differ -want +got, %s", diff)
	}
}

// assertSummariesEqual asserts that the bot summaries are as
// expected.
func assertSummariesEqual(t *testing.T, want, got []*fleet.BotSummary) {
	t.Helper()
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("BotSummaries differ -want +got, %s", diff)
	}
}

// cleanSummaries cleans up the bot summaries slice for comparison.
// The slices are sorted and proto internal fields are zeroed out.
func cleanSummaries(bs []*fleet.BotSummary) {
	sort.Slice(bs, func(i, j int) bool { return bs[i].DutId < bs[j].DutId })
	for _, b := range bs {
		b.XXX_sizecache = 0
		if d := b.GetDimensions(); d != nil {
			d.XXX_sizecache = 0
		}
	}
}

func decodeEntities(es []*Entity) ([]*fleet.BotSummary, error) {
	bs := make([]*fleet.BotSummary, len(es))
	for i, e := range es {
		b, err := e.Decode()
		if err != nil {
			return nil, err
		}
		bs[i] = b
	}
	return bs, nil
}
