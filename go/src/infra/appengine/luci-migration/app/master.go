// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package app

import (
	"net/http"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"

	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"
)

type masterViewModel struct {
	Name     string
	Builders []masterBuilderViewModel
}

type masterBuilderViewModel struct {
	Name       string
	ShowScores bool
	Migration  storage.BuilderMigration
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

	// Get master config.
	cfg, err := config.Get(c)
	if err != nil {
		return nil, err
	}
	var masterCfg *config.Master
	for _, m := range cfg.GetMasters() {
		if m.Name == master {
			masterCfg = m
			break
		}
	}
	if masterCfg == nil {
		return nil, errNotFound
	}

	// Check access.
	hasInternalAccess, err := auth.IsMember(c, internalAccessGroup)
	if err != nil {
		return nil, err
	}
	if !masterCfg.Public && !hasInternalAccess {
		return nil, errNotFound
	}

	// Fetch builders.
	q := datastore.NewQuery(storage.BuilderKind)
	q = storage.BuilderMasterFilter(c, q, master)
	if !hasInternalAccess {
		q = q.Eq("Public", true) // be paranoid
	}
	err = datastore.Run(c, q, func(b *storage.Builder) {
		if !b.Public && !hasInternalAccess {
			return // be paranoid
		}

		model.Builders = append(model.Builders, masterBuilderViewModel{
			Name:       b.ID.Builder,
			ShowScores: b.Migration.Status != storage.StatusUnknown && b.Migration.Status != storage.StatusInsufficientData,
			Migration:  b.Migration,
		})
	})
	if err != nil {
		return nil, err
	}
	return model, nil
}
