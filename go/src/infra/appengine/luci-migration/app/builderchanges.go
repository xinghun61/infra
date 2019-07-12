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

package main

import (
	"net/http"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"infra/appengine/luci-migration/storage"
)

type builderChangesViewModel struct {
	BuilderID storage.BuilderID
	Changes   []*storage.BuilderChange
}

func handleBuilderUpdatesPage(c *router.Context) error {
	id, err := parseBuilderIDFromRequest(&c.Params)
	if err != nil {
		http.Error(c.Writer, err.Error(), http.StatusBadRequest)
		return nil
	}

	switch viewModel, err := builderChangesPage(c.Context, id); {
	case err == errNotFound:
		http.NotFound(c.Writer, c.Request)
		return nil
	case err != nil:
		return err
	default:
		templates.MustRender(c.Context, c.Writer, "pages/builder_changes.html", templates.Args{"Model": viewModel})
		return nil
	}
}

func builderChangesPage(c context.Context, id storage.BuilderID) (*builderChangesViewModel, error) {
	builder := &storage.Builder{ID: id}
	switch err := datastore.Get(c, builder); {
	case err == datastore.ErrNoSuchEntity:
		return nil, errNotFound
	case err != nil:
		return nil, err
	}

	viewModel := &builderChangesViewModel{
		BuilderID: builder.ID,
		Changes:   make([]*storage.BuilderChange, 0, 100),
	}

	q := datastore.NewQuery(storage.BuilderChangeKind).
		Ancestor(datastore.KeyForObj(c, builder)).
		Order("-When").
		Limit(int32(cap(viewModel.Changes)))
	if err := datastore.GetAll(c, q, &viewModel.Changes); err != nil {
		return nil, err
	}

	return viewModel, nil
}
