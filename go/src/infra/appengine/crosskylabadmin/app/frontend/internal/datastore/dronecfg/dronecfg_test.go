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

package dronecfg

import (
	"context"
	"reflect"
	"testing"

	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
)

func TestUpdateAndGet(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	ctx = memory.Use(ctx)
	e := Entity{
		Hostname: "belfast-drone.example.com",
		DUTs: []DUT{
			{ID: "5208f074-8632-4665-ab9e-324579917f36", Hostname: "dut1.example.com"},
		},
	}
	entities := []Entity{e}
	if err := Update(ctx, entities); err != nil {
		t.Fatalf("Update returned error: %s", err)
	}
	// Force update since the fake datastore simulates update latency.
	datastore.Raw(ctx).GetTestable().CatchupIndexes()
	got, err := Get(ctx, "belfast-drone.example.com")
	if err != nil {
		t.Fatalf("Get returned error: %s", err)
	}
	// Hide the ConfigSet parent key because it gets set automatically.
	got.ConfigSet = nil
	if !reflect.DeepEqual(got, e) {
		t.Errorf("Get() = %#v; want %#v", got, e)
	}
}
