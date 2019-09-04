// Copyright 2019 The LUCI Authors.
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

package frontend

import (
	"sort"
	"testing"
	"time"

	"infra/appengine/drone-queen/api"
	"infra/appengine/drone-queen/internal/entities"

	"github.com/golang/protobuf/ptypes"
	"github.com/golang/protobuf/ptypes/timestamp"
	"github.com/google/go-cmp/cmp"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"
	"golang.org/x/net/context"
)

func TestDroneQueenImpl_DeclareDuts(t *testing.T) {
	t.Parallel()
	t.Run("happy path", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		var d DroneQueenImpl
		duts := []string{"ion", "nelo"}
		_, err := d.DeclareDuts(ctx, &api.DeclareDutsRequest{Duts: duts})
		if err != nil {
			t.Fatal(err)
		}
		k := entities.DUTGroupKey(ctx)
		want := []*entities.DUT{
			{ID: "ion", Group: k},
			{ID: "nelo", Group: k},
		}
		assertDatastoreDUTs(ctx, t, want)
	})
	t.Run("declare invalid DUTs", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		var d DroneQueenImpl
		duts := []string{"ion", "nelo", "", ""}
		_, err := d.DeclareDuts(ctx, &api.DeclareDutsRequest{Duts: duts})
		if err != nil {
			t.Fatal(err)
		}
		k := entities.DUTGroupKey(ctx)
		want := []*entities.DUT{
			{ID: "ion", Group: k},
			{ID: "nelo", Group: k},
		}
		assertDatastoreDUTs(ctx, t, want)
	})
	t.Run("declare more DUTs", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		var d DroneQueenImpl
		duts := []string{"ion", "nelo"}
		_, err := d.DeclareDuts(ctx, &api.DeclareDutsRequest{Duts: duts})
		if err != nil {
			t.Fatal(err)
		}
		duts = []string{"ion", "nelo", "casty"}
		_, err = d.DeclareDuts(ctx, &api.DeclareDutsRequest{Duts: duts})
		if err != nil {
			t.Fatal(err)
		}
		k := entities.DUTGroupKey(ctx)
		want := []*entities.DUT{
			{ID: "ion", Group: k},
			{ID: "nelo", Group: k},
			{ID: "casty", Group: k},
		}
		assertDatastoreDUTs(ctx, t, want)
	})
	t.Run("declare fewer DUTs", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		var d DroneQueenImpl
		duts := []string{"ion", "nelo"}
		_, err := d.DeclareDuts(ctx, &api.DeclareDutsRequest{Duts: duts})
		if err != nil {
			t.Fatal(err)
		}
		duts = []string{"ion"}
		_, err = d.DeclareDuts(ctx, &api.DeclareDutsRequest{Duts: duts})
		if err != nil {
			t.Fatal(err)
		}
		k := entities.DUTGroupKey(ctx)
		want := []*entities.DUT{
			{ID: "ion", Group: k},
			{ID: "nelo", Group: k, Draining: true},
		}
		assertDatastoreDUTs(ctx, t, want)
	})
	t.Run("declare new and remove old DUTs", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		var d DroneQueenImpl
		duts := []string{"ion", "nelo"}
		_, err := d.DeclareDuts(ctx, &api.DeclareDutsRequest{Duts: duts})
		if err != nil {
			t.Fatal(err)
		}
		duts = []string{"ion", "casty"}
		_, err = d.DeclareDuts(ctx, &api.DeclareDutsRequest{Duts: duts})
		if err != nil {
			t.Fatal(err)
		}
		k := entities.DUTGroupKey(ctx)
		want := []*entities.DUT{
			{ID: "ion", Group: k},
			{ID: "nelo", Group: k, Draining: true},
			{ID: "casty", Group: k},
		}
		assertDatastoreDUTs(ctx, t, want)
	})
}

func TestDroneQueenImpl_ReleaseDuts(t *testing.T) {
	t.Parallel()
	t.Run("release all DUTs", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		k := entities.DUTGroupKey(ctx)
		duts := []*entities.DUT{
			{ID: "ionasal", Group: k, AssignedDrone: "earthes"},
			{ID: "nayaflask", Group: k, AssignedDrone: "earthes"},
		}
		if err := datastore.Put(ctx, duts); err != nil {
			t.Fatal(err)
		}
		var d DroneQueenImpl
		_, err := d.ReleaseDuts(ctx, &api.ReleaseDutsRequest{
			DroneUuid: "earthes",
			Duts:      []string{"ionasal", "nayaflask"},
		})
		if err != nil {
			t.Fatal(err)
		}
		want := []*entities.DUT{
			{ID: "ionasal", Group: k},
			{ID: "nayaflask", Group: k},
		}
		assertDatastoreDUTs(ctx, t, want)
	})
	t.Run("release partial DUTs", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		k := entities.DUTGroupKey(ctx)
		duts := []*entities.DUT{
			{ID: "ionasal", Group: k, AssignedDrone: "earthes"},
			{ID: "nayaflask", Group: k, AssignedDrone: "earthes"},
		}
		if err := datastore.Put(ctx, duts); err != nil {
			t.Fatal(err)
		}
		var d DroneQueenImpl
		_, err := d.ReleaseDuts(ctx, &api.ReleaseDutsRequest{
			DroneUuid: "earthes",
			Duts:      []string{"nayaflask"},
		})
		if err != nil {
			t.Fatal(err)
		}
		want := []*entities.DUT{
			{ID: "ionasal", Group: k, AssignedDrone: "earthes"},
			{ID: "nayaflask", Group: k},
		}
		assertDatastoreDUTs(ctx, t, want)
	})
	t.Run("release unassigned duts", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		k := entities.DUTGroupKey(ctx)
		duts := []*entities.DUT{
			{ID: "ionasal", Group: k},
		}
		if err := datastore.Put(ctx, duts); err != nil {
			t.Fatal(err)
		}
		var d DroneQueenImpl
		_, err := d.ReleaseDuts(ctx, &api.ReleaseDutsRequest{
			DroneUuid: "earthes",
			Duts:      []string{"ionasal"},
		})
		if err != nil {
			t.Fatal(err)
		}
		assertDatastoreDUTs(ctx, t, duts)
	})
	t.Run("release DUTs of another drone", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		k := entities.DUTGroupKey(ctx)
		duts := []*entities.DUT{
			{ID: "casty", Group: k, AssignedDrone: "delta"},
		}
		if err := datastore.Put(ctx, duts); err != nil {
			t.Fatal(err)
		}
		var d DroneQueenImpl
		_, err := d.ReleaseDuts(ctx, &api.ReleaseDutsRequest{
			DroneUuid: "earthes",
			Duts:      []string{"casty"},
		})
		if err != nil {
			t.Fatal(err)
		}
		assertDatastoreDUTs(ctx, t, duts)
	})
	t.Run("release nonexistent DUT", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		k := entities.DUTGroupKey(ctx)
		duts := []*entities.DUT{
			{ID: "casty", Group: k, AssignedDrone: "delta"},
		}
		if err := datastore.Put(ctx, duts); err != nil {
			t.Fatal(err)
		}
		var d DroneQueenImpl
		_, err := d.ReleaseDuts(ctx, &api.ReleaseDutsRequest{
			DroneUuid: "earthes",
			Duts:      []string{"nelo"},
		})
		if err != nil {
			t.Fatal(err)
		}
		assertDatastoreDUTs(ctx, t, duts)
	})
	t.Run("omit drone UUID", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		var d DroneQueenImpl
		_, err := d.ReleaseDuts(ctx, &api.ReleaseDutsRequest{})
		if err == nil {
			t.Errorf("Expected error, got no error")
		}
	})
}

func TestDroneQueenImpl_ReportDrone(t *testing.T) {
	t.Run("unknown UUID", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		d := DroneQueenImpl{}
		res, err := d.ReportDrone(ctx, &api.ReportDroneRequest{
			DroneUuid: "unicorn",
		})
		if err != nil {
			t.Fatal(err)
		}
		if s := res.Status; s != api.ReportDroneResponse_UNKNOWN_UUID {
			t.Errorf("Got report status %v; want UNKNOWN_UUID", s)
		}
	})
	t.Run("expired drone", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		now := time.Date(2000, 1, 2, 3, 4, 5, 6, time.UTC)
		d := DroneQueenImpl{
			nowFunc: staticTime(now),
		}
		dr := entities.Drone{
			ID:         "nelo",
			Expiration: now.Add(-10 * time.Second),
		}
		if err := datastore.Put(ctx, &dr); err != nil {
			t.Fatal(err)
		}
		res, err := d.ReportDrone(ctx, &api.ReportDroneRequest{
			DroneUuid: "nelo",
		})
		if err != nil {
			t.Fatal(err)
		}
		if s := res.Status; s != api.ReportDroneResponse_UNKNOWN_UUID {
			t.Errorf("Got report status %v; want UNKNOWN_UUID", s)
		}
	})
}

func TestDroneQueenImpl_workflows(t *testing.T) {
	t.Parallel()
	t.Run("happy path", testHappyPath)
}

func testHappyPath(t *testing.T) {
	t.Parallel()
	ctx := gaetesting.TestingContextWithAppID("go-test")
	datastore.GetTestable(ctx).Consistent(true)
	now := time.Date(2000, 1, 2, 3, 4, 5, 6, time.UTC)
	d := DroneQueenImpl{
		nowFunc: staticTime(now),
	}
	// Declare some DUTs.
	duts := []string{"ion", "nelo"}
	_, err := d.DeclareDuts(ctx, &api.DeclareDutsRequest{
		Duts: duts,
	})
	if err != nil {
		t.Fatal(err)
	}
	k := entities.DUTGroupKey(ctx)
	want := []*entities.DUT{
		{ID: "ion", Group: k},
		{ID: "nelo", Group: k},
	}
	assertDatastoreDUTs(ctx, t, want)
	// Call ReportDrone.
	res, err := d.ReportDrone(ctx, &api.ReportDroneRequest{
		LoadIndicators: &api.ReportDroneRequest_LoadIndicators{
			DutCapacity: 1,
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	if s := res.Status; s != api.ReportDroneResponse_OK {
		t.Errorf("Got report status %v; want OK", s)
	}
	if res.DroneUuid == "" {
		t.Errorf("Got empty drone UUID; expected a new UUID to be assigned")
	}
	if n := len(res.AssignedDuts); n != 1 {
		t.Errorf("Got %v DUTs; expected 1", n)
	}
	assertSubsetStrings(t, duts, res.AssignedDuts)
	if len(res.DrainingDuts) != 0 {
		t.Errorf("Got draining DUTs %v; want none", res.DrainingDuts)
	}
	if e := goTime(res.ExpirationTime); !e.After(now) {
		t.Errorf("Got expiration time %v; expected time after %v", e, now)
	}
}

// goTime converts a protobuf timestamp to a Go Time.
func goTime(t *timestamp.Timestamp) time.Time {
	gt, err := ptypes.Timestamp(t)
	if err != nil {
		panic(err)
	}
	return gt
}

// staticTime returns a nowFunc for DroneQueenImpl for a static time.
func staticTime(t time.Time) func() time.Time {
	return func() time.Time {
		return t
	}
}

func assertSubsetStrings(t *testing.T, all, got []string) {
	t.Helper()
	set := make(map[string]bool)
	for _, s := range all {
		set[s] = true
	}
	for _, s := range got {
		if !set[s] {
			t.Errorf("Got %v not in expected set %v", s, all)
		}
	}
}

func assertSameStrings(t *testing.T, want, got []string) {
	t.Helper()
	sort.Strings(want)
	sort.Strings(got)
	if diff := cmp.Diff(want, got); diff != "" {
		t.Errorf("Unexpected strings (-want +got):\n%s", diff)
	}
}

func assertDatastoreDUTs(ctx context.Context, t *testing.T, want []*entities.DUT) {
	t.Helper()
	q := datastore.NewQuery(entities.DUTKind)
	var got []*entities.DUT
	if err := datastore.GetAll(ctx, q, &got); err != nil {
		t.Fatal(err)
	}
	sortDUTs(got)
	sortDUTs(want)
	if diff := cmp.Diff(want, got); diff != "" {
		t.Errorf("Unexpected DUTs (-want +got):\n%s", diff)
	}
}

func sortDUTs(d []*entities.DUT) {
	sort.Slice(d, func(i, j int) bool { return d[i].ID < d[j].ID })
}
