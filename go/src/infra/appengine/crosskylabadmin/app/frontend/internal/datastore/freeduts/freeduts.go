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

// Package freeduts implements datastore access for caching free
// (removed) DUTs info.
package freeduts

import (
	"context"
	"time"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"
)

// DUT contains info about a free DUT.
type DUT struct {
	_kind      string `gae:"$kind,freeDut"`
	ID         string `gae:"$id"`
	Hostname   string
	Bug        string `gae:",noindex"`
	Comment    string `gae:",noindex"`
	ExpireTime time.Time
	Model      string `gae:",noindex"`
}

// Add adds free DUTs to datastore.
func Add(ctx context.Context, duts []DUT) error {
	if err := datastore.Put(ctx, duts); err != nil {
		return errors.Annotate(err, "add free duts").Err()
	}
	return nil
}

// Remove removes free DUTs from datastore.
func Remove(ctx context.Context, duts []DUT) error {
	if err := datastore.Delete(ctx, duts); err != nil {
		return errors.Annotate(err, "remove free duts").Err()
	}
	return nil
}

// GetAll returns all free DUTs in datastore.
func GetAll(ctx context.Context) ([]DUT, error) {
	q := datastore.NewQuery("freeDut")
	var duts []DUT
	if err := datastore.GetAll(ctx, q, &duts); err != nil {
		return nil, errors.Annotate(err, "get free duts").Err()
	}
	return duts, nil
}
