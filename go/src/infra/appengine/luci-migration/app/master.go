// Copyright 2017 The LUCI Authors.
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

package app

import (
	"net/http"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"infra/appengine/luci-migration/storage"
)

type masterViewModel struct {
	Name     string
	Builders []masterBuilderViewModel
}

type masterBuilderViewModel struct {
	*storage.Builder
	ShowScores bool
}

func handleMasterPage(c *router.Context) error {
	master := c.Params.ByName("master")
	if master == "" {
		http.Error(c.Writer, "master unspecified in URL", http.StatusBadRequest)
		return nil
	}

	viewModel, err := masterPage(c.Context, master)
	if err == errNotFound {
		http.NotFound(c.Writer, c.Request)
		return nil
	}
	if err != nil {
		return err
	}
	templates.MustRender(c.Context, c.Writer, "pages/master.html", templates.Args{"Model": viewModel})
	return nil
}

func masterPage(c context.Context, master string) (*masterViewModel, error) {
	model := &masterViewModel{Name: master}
	q := storage.BuilderMasterFilter(c, nil, master)
	err := datastore.Run(c, q, func(b *storage.Builder) {
		model.Builders = append(model.Builders, masterBuilderViewModel{
			Builder:    b,
			ShowScores: b.Migration.Status != storage.StatusUnknown && b.Migration.Status != storage.StatusInsufficientData,
		})
	})
	switch {
	case err != nil:
		return nil, err
	case len(model.Builders) == 0:
		return nil, errNotFound
	default:
		return model, nil
	}
}
