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

package freeduts

import (
	"context"
	"reflect"
	"testing"
	"time"

	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
)

func TestDatastore(t *testing.T) {
	t.Parallel()
	d := DUT{
		ID:         "5208f074-8632-4665-ab9e-324579917f36",
		Hostname:   "yorktown.example.com",
		Bug:        "crbug.com/9999",
		Comment:    "evolved sentience",
		ExpireTime: time.Date(2019, 1, 2, 3, 4, 5, 0, time.UTC),
		Model:      "yorktown",
	}
	d2 := d
	d2.ID = "2ab996aa-e278-49c5-a5e1-797bcd6f4dcc"
	d2.Hostname = "enterprise.example.com"

	t.Run("add and get all", func(t *testing.T) {
		t.Parallel()
		ctx := memory.Use(context.Background())
		if err := Add(ctx, []DUT{d}); err != nil {
			t.Fatalf("Add returned error: %s", err)
		}
		// Force update since the fake datastore simulates update latency.
		datastore.Raw(ctx).GetTestable().CatchupIndexes()
		got, err := GetAll(ctx)
		if err != nil {
			t.Fatalf("Get returned error: %s", err)
		}
		want := []DUT{d}
		if !reflect.DeepEqual(got, want) {
			t.Errorf("GetAll() = %#v; want %#v", got, want)
		}
	})

	t.Run("remove", func(t *testing.T) {
		t.Parallel()
		ctx := memory.Use(context.Background())
		if err := Add(ctx, []DUT{d, d2}); err != nil {
			t.Fatalf("Add returned error: %s", err)
		}
		if err := Remove(ctx, []DUT{d2}); err != nil {
			t.Fatalf("Remove returned error: %s", err)
		}
		// Force update since the fake datastore simulates update latency.
		datastore.Raw(ctx).GetTestable().CatchupIndexes()
		got, err := GetAll(ctx)
		if err != nil {
			t.Fatalf("Get returned error: %s", err)
		}
		want := []DUT{d}
		if !reflect.DeepEqual(got, want) {
			t.Errorf("GetAll() = %#v; want %#v", got, want)
		}
	})

	t.Run("remove missing DUT does not error", func(t *testing.T) {
		t.Parallel()
		ctx := memory.Use(context.Background())
		if err := Remove(ctx, []DUT{d}); err != nil {
			t.Fatalf("Remove returned error: %s", err)
		}
	})
}
