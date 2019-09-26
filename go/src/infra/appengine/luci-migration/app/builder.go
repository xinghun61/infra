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

package main

import (
	"encoding/json"
	"html/template"
	"net/http"
	"time"

	"github.com/julienschmidt/httprouter"
	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"
)

const (
	experimentLevelFormValueName = "experimentLevel"
	luciIsProdFormValueName      = "luciIsProd"
	reasonFormValueName          = "reason"
	changeBuilderSettingsGroup   = "luci-migration-writers"
)

type builderViewModel struct {
	Builder         *storage.Builder
	LUCIBucket      string
	ExperimentLevel int // ExperimentalPercentage / 10

	StatusKnown       bool
	StatusClassSuffix string // Bootstrap label class suffix
	StatusAge         time.Duration
	StatusOutdated    bool
	Details           template.HTML
	TryBuilder        bool
}

func parseBuilderIDFromRequest(params *httprouter.Params) (storage.BuilderID, error) {
	id := storage.BuilderID{
		Master:  params.ByName("master"),
		Builder: params.ByName("builder"),
	}
	var err error
	switch {
	case id.Master == "":
		err = errors.New("master unspecified in URL")
	case id.Builder == "":
		err = errors.New("builder unspecified in URL")
	}
	return id, err
}

func handleBuilderPage(c *router.Context) error {
	id, err := parseBuilderIDFromRequest(&c.Params)
	if err != nil {
		http.Error(c.Writer, err.Error(), http.StatusBadRequest)
		return nil
	}

	viewModel, err := builderPage(c.Context, id)
	if err == errNotFound {
		http.NotFound(c.Writer, c.Request)
		return nil
	}
	if err != nil {
		return err
	}

	if respondWithJSON(c.Request) {
		c.Writer.Header().Add("Content-Type", "application/json")
		return json.NewEncoder(c.Writer).Encode(map[string]interface{}{
			"luci_is_prod": viewModel.Builder.LUCIIsProd,
			"bucket":       viewModel.LUCIBucket,
		})
	}

	templates.MustRender(c.Context, c.Writer, "pages/builder.html", templates.Args{"Model": viewModel})
	return nil
}

func builderPage(c context.Context, id storage.BuilderID) (*builderViewModel, error) {
	master := config.Get(c).FindMaster(id.Master)
	if master == nil {
		return nil, errors.Reason("master %q is not configured", id.Master).Err()
	}

	model := &builderViewModel{
		Builder:    &storage.Builder{ID: id},
		LUCIBucket: master.LuciBucket,
	}
	migrationDetails := &storage.BuilderMigrationDetails{
		Parent: datastore.KeyForObj(c, model.Builder),
	}

	// Fetch both builder and most recent analysis report.
	switch err := datastore.Get(c, model.Builder, migrationDetails).(type) {
	case errors.MultiError:
		switch builderErr, detailsErr := err[0], err[1]; {
		case builderErr == datastore.ErrNoSuchEntity:
			return nil, errNotFound

		case builderErr != nil:
			return nil, builderErr

		case detailsErr == datastore.ErrNoSuchEntity:
			// leave model.MostRecentAnalysisReport empty

		case detailsErr != nil:
			return nil, detailsErr

		default:
			panic("impossible")
		}

	case nil:
		model.Details = template.HTML(migrationDetails.TrustedHTML)

	default:
		return nil, err
	}

	mig := model.Builder.Migration
	model.StatusKnown = mig.Status != storage.StatusUnknown && model.Details != ""
	model.StatusClassSuffix = migrationStatusLabelClassSuffix(mig.Status)
	model.StatusAge = clock.Now(c).Sub(model.Builder.Migration.AnalysisTime)
	model.TryBuilder = model.Builder.SchedulingType == config.SchedulingType_TRYJOBS
	model.StatusOutdated = model.TryBuilder && mig.Status != storage.StatusMigrated && model.StatusAge > 24*time.Hour
	model.ExperimentLevel = model.Builder.ExperimentPercentage / 10
	return model, nil
}

// handleBuilderPagePost handles POST request for the builder page.
// It updates builder properties in the datastore.
func handleBuilderPagePost(c *router.Context) error {
	if allow, err := auth.IsMember(c.Context, changeBuilderSettingsGroup); err != nil {
		return err
	} else if !allow {
		logging.Warningf(c.Context, "%s cannot change builder settings", auth.CurrentIdentity(c.Context))
		http.Error(c.Writer, "Access denied", http.StatusForbidden)
		return nil
	}

	id, err := parseBuilderIDFromRequest(&c.Params)
	if err != nil {
		http.Error(c.Writer, err.Error(), http.StatusBadRequest)
		return nil
	}

	builder := &storage.Builder{ID: id}
	switch err := datastore.Get(c.Context, builder); {
	case err == datastore.ErrNoSuchEntity:
		http.NotFound(c.Writer, c.Request)
		return nil
	case err != nil:
		return err
	}

	switch c.Request.FormValue("action") {
	case "update":
		return updateBuilder(c, builder)
	case "analyze":
		return analyzeBuilder(c, builder)
	default:
		http.Error(c.Writer, "invalid action", http.StatusBadRequest)
		return nil
	}
}

func analyzeBuilder(c *router.Context, builder *storage.Builder) error {
	task := builderAnalysisTask(builder.ID)
	if err := taskqueue.Add(c.Context, analysisTaskQueue, task); err != nil {
		return err
	}
	http.Redirect(c.Writer, c.Request, c.Request.URL.String(), http.StatusFound)
	return nil
}

func updateBuilder(c *router.Context, builder *storage.Builder) error {
	return errors.New("no longer implemented")
}

// migrationStatusLabelClassSuffix returns a Bootstrap label class suffix for a
// migration status.
func migrationStatusLabelClassSuffix(s storage.MigrationStatus) string {
	switch s {
	case storage.StatusLUCINotWAI:
		return "danger"
	case storage.StatusMigrated, storage.StatusLUCIWAI:
		return "success"
	default:
		return "default"
	}
}
