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
	"encoding/json"
	"net/http"
	"sort"
	"strings"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"
)

type masterViewModel struct {
	*config.Master
	Tryjobs  bool
	Builders []masterBuilderViewModel
}

type masterBuilderViewModel struct {
	*storage.Builder
	ShowScores bool
}

func handleMasterPage(c *router.Context) error {
	masterName := c.Params.ByName("master")
	if masterName == "" {
		http.Error(c.Writer, "master unspecified in URL", http.StatusBadRequest)
		return nil
	}

	master := config.Get(c.Context).FindMaster(masterName)
	if master == nil {
		http.NotFound(c.Writer, c.Request)
		return nil
	}

	viewModel, err := masterPage(c.Context, master)
	if err != nil {
		return err
	}

	if strings.ToLower(c.Request.FormValue("format")) == "json" {
		c.Writer.Header().Add("Content-Type", "application/json")

		builders := map[string]interface{}{}
		for _, b := range viewModel.Builders {
			builders[b.Builder.ID.Builder] = map[string]interface{}{
				"is_prod": b.LUCIIsProd,
			}
		}

		return json.NewEncoder(c.Writer).Encode(map[string]interface{}{
			"bucket":   viewModel.LuciBucket,
			"builders": builders,
		})
	}

	templates.MustRender(c.Context, c.Writer, "pages/master.html", templates.Args{"Model": viewModel})
	return nil
}

func masterPage(c context.Context, master *config.Master) (*masterViewModel, error) {
	model := &masterViewModel{
		Master:  master,
		Tryjobs: master.SchedulingType == config.SchedulingType_TRYJOBS,
	}
	q := storage.BuilderMasterFilter(c, nil, master.Name)
	err := datastore.Run(c, q, func(b *storage.Builder) {
		model.Builders = append(model.Builders, masterBuilderViewModel{
			Builder:    b,
			ShowScores: b.Migration.Status != storage.StatusUnknown && b.Migration.Status != storage.StatusInsufficientData,
		})
	})

	sort.Slice(model.Builders, func(i, j int) bool {
		a := model.Builders[i]
		b := model.Builders[j]
		switch {
		case a.Migration.Status < b.Migration.Status:
			return true
		case a.Migration.Status > b.Migration.Status:
			return false
		default:
			return a.ID.Builder < b.ID.Builder
		}
	})

	switch {
	case err != nil:
		return nil, err
	default:
		return model, nil
	}
}
