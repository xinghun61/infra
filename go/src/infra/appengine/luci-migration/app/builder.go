// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package app

import (
	"html/template"
	"net/http"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"

	"infra/appengine/luci-migration/storage"
)

const internalAccessGroup = "luci-migration-internal-access"

type builderViewModel struct {
	Builder *storage.Builder

	StatusKnown       bool
	StatusClassSuffix string // Bootstrap label class suffix
	Details           template.HTML
}

func handleBuilderPage(c *router.Context) error {
	id := storage.BuilderID{
		Master:  c.Params.ByName("master"),
		Builder: c.Params.ByName("builder"),
	}
	if id.Master == "" {
		http.Error(c.Writer, "master unspecified in URL", http.StatusBadRequest)
		return nil
	}
	if id.Builder == "" {
		http.Error(c.Writer, "builder unspecified in URL", http.StatusBadRequest)
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
	templates.MustRender(c.Context, c.Writer, "pages/builder.html", templates.Args{"Model": viewModel})
	return nil
}

func builderPage(c context.Context, id storage.BuilderID) (*builderViewModel, error) {
	model := &builderViewModel{Builder: &storage.Builder{ID: id}}
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

	// Check access.
	hasInternalAccess, err := auth.IsMember(c, internalAccessGroup)
	if err != nil {
		return nil, err
	}
	if !model.Builder.Public && !hasInternalAccess {
		return nil, errNotFound
	}

	mig := model.Builder.Migration
	model.StatusKnown = mig.Status != storage.StatusUnknown && model.Details != ""
	model.StatusClassSuffix = migrationStatusLabelClassSuffix(mig.Status)
	return model, nil
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
