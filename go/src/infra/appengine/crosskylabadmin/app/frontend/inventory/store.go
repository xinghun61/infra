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
	"infra/libs/skylab/inventory"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/proto/gerrit"
	"go.chromium.org/luci/common/proto/gitiles"
	"golang.org/x/net/context"
)

// GitStore exposes skylab inventory data in git.
//
// TODO(pprabhu): The following statement is not (yet) true. Make it so.
// GitStore.Refresh() and GitStore.Commit() together provide an atomic
// inventory update transaction.
//
// Call GitStore.Refresh() to obtain the initial inventory data. After making
// modifications to the inventory, call GitStore.Commit().
// Call GitStore.Refresh() again if you want to use the object beyond a
// GitStore.Commit(), to re-validate the store.
type GitStore struct {
	*inventory.Lab

	gerritC  gerrit.GerritClient
	gitilesC gitiles.GitilesClient
	valid    bool
}

// NewGitStore returns a new GitStore.
//
// The returned store is not refreshed, hence all inventory data is empty.
func NewGitStore(gerritC gerrit.GerritClient, gitilesC gitiles.GitilesClient) *GitStore {
	return &GitStore{
		gerritC:  gerritC,
		gitilesC: gitilesC,
		valid:    false,
	}
}

// Commit commits the current inventory data in the store to git.
func (g *GitStore) Commit(ctx context.Context) (string, error) {
	if !g.valid {
		return "", errors.New("can not commit invalid store")
	}
	u, err := commitLabInventory(ctx, g.gerritC, g.Lab)
	if err == nil {
		// Successful commit implies our refreshed data is not longer current, so
		// the store cache is invalid.
		g.valid = false
		g.Lab = nil
	}
	return u, err
}

// Refresh populates inventory data in the store from git.
func (g *GitStore) Refresh(ctx context.Context) error {
	l, err := fetchLabInventory(ctx, g.gitilesC)
	if err != nil {
		return errors.Annotate(err, "gitstore refresh").Err()
	}
	g.Lab = l
	g.valid = true
	return nil
}
