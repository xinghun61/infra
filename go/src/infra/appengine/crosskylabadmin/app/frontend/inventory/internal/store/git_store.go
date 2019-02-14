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

package store

import (
	"infra/appengine/crosskylabadmin/app/config"
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
	*inventory.Infrastructure

	gerritC     gerrit.GerritClient
	gitilesC    gitiles.GitilesClient
	latestFiles map[string]string
	latestSHA1  string
}

// NewGitStore returns a new GitStore.
//
// The returned store is not refreshed, hence all inventory data is empty.
func NewGitStore(gerritC gerrit.GerritClient, gitilesC gitiles.GitilesClient) *GitStore {
	store := &GitStore{
		gerritC:  gerritC,
		gitilesC: gitilesC,
	}
	store.clear()
	return store
}

// IsEmptyErr returns true if the given error is because of am empty
// commit.
func IsEmptyErr(e error) bool {
	_, ok := e.(emptyError)
	return ok
}

type emptyError struct {
	err error
}

func (e emptyError) Error() string {
	return e.err.Error()
}

// Commit commits the current inventory data in the store to git.
//
// Successful Commit() invalidates the data cached in GitStore().
// To continue using the store, call Refresh() again.
func (g *GitStore) Commit(ctx context.Context, reason string) (string, error) {
	if g.latestSHA1 == "" {
		return "", errors.New("can not commit invalid store")
	}

	ic := config.Get(ctx).Inventory
	changed := make(map[string]string)

	ls, err := inventory.WriteLabToString(g.Lab)
	if err != nil {
		return "", errors.Annotate(err, "gitstore commit").Err()
	}
	if ls != g.latestFiles[ic.LabDataPath] {
		changed[ic.LabDataPath] = ls
	}

	is, err := inventory.WriteInfrastructureToString(g.Infrastructure)
	if err != nil {
		return "", errors.Annotate(err, "gitstore commit").Err()
	}
	if is != g.latestFiles[ic.InfrastructureDataPath] {
		changed[ic.InfrastructureDataPath] = is
	}

	if len(changed) == 0 {
		return "", emptyError{errors.New("gitstore commit: nothing to commit")}
	}

	cn, err := commitFileContents(ctx, g.gerritC, ic.Project, ic.Branch, g.latestSHA1, reason, changed)
	if err != nil {
		return "", errors.Annotate(err, "gitstore commit").Err()
	}

	u, err := changeURL(ic.GerritHost, ic.Project, cn)
	if err != nil {
		return "", errors.Annotate(err, "gitstore commit").Err()
	}

	// Successful commit implies our refreshed data is not longer current, so
	// the store cache is invalid.
	g.clear()
	return u, err
}

// Refresh populates inventory data in the store from git.
func (g *GitStore) Refresh(ctx context.Context) (rerr error) {
	defer func() {
		if rerr != nil {
			g.clear()
		}
	}()

	ic := config.Get(ctx).Inventory
	// TODO(pprabhu) Replace these checks with config validation.
	if ic.LabDataPath == "" {
		return errors.New("no lab data file path provided in config")
	}
	if ic.InfrastructureDataPath == "" {
		return errors.New("no infrastructure data file path provided in config")
	}

	var err error
	g.latestSHA1, err = fetchLatestSHA1(ctx, g.gitilesC, ic.Project, ic.Branch)
	if err != nil {
		return errors.Annotate(err, "gitstore refresh").Err()
	}

	g.latestFiles, err = fetchFilesFromGitiles(ctx, g.gitilesC, ic.Project, g.latestSHA1, []string{ic.LabDataPath, ic.InfrastructureDataPath})
	if err != nil {
		return errors.Annotate(err, "gitstore refresh").Err()
	}

	data, ok := g.latestFiles[ic.LabDataPath]
	if !ok {
		return errors.New("No lab data in inventory")
	}
	g.Lab = &inventory.Lab{}
	if err := inventory.LoadLabFromString(data, g.Lab); err != nil {
		return errors.Annotate(err, "gitstore refresh").Err()
	}

	data, ok = g.latestFiles[ic.InfrastructureDataPath]
	if !ok {
		return errors.New("No infrastructure data in inventory")
	}
	g.Infrastructure = &inventory.Infrastructure{}
	if err := inventory.LoadInfrastructureFromString(data, g.Infrastructure); err != nil {
		return errors.Annotate(err, "gitstore refresh").Err()
	}

	return nil
}

func (g *GitStore) clear() {
	g.Lab = nil
	g.Infrastructure = nil
	g.latestSHA1 = ""
	g.latestFiles = make(map[string]string)
}
