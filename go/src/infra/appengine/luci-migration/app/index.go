// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package app

import (
	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"

	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"
)

type indexViewModel struct {
	Masters []*indexMasterViewModel
}

type indexMasterViewModel struct {
	Name string

	MigratedBuilderCount   int
	TotalBuilderCount      int
	MigratedBuilderPercent int
}

func handleIndexPage(c *router.Context) error {
	viewModel, err := indexPage(c.Context)
	if err != nil {
		return err
	}
	templates.MustRender(c.Context, c.Writer, "pages/index.html", templates.Args{"Model": viewModel})
	return nil
}

func indexPage(c context.Context) (*indexViewModel, error) {
	model := &indexViewModel{}

	hasInternalAccess, err := auth.IsMember(c, internalAccessGroup)
	if err != nil {
		return nil, err
	}

	// Get masters from config.
	cfg, err := config.Get(c)
	if err != nil {
		return nil, err
	}
	model.Masters = make([]*indexMasterViewModel, 0, len(cfg.GetBuildbot().GetMasters()))
	masterMap := make(map[string]*indexMasterViewModel, len(model.Masters))

	for _, m := range cfg.GetBuildbot().GetMasters() {
		if !m.Public && !hasInternalAccess {
			continue
		}
		mvm := &indexMasterViewModel{Name: m.Name}
		model.Masters = append(model.Masters, mvm)
		masterMap[m.Name] = mvm
	}

	// Note: may have to cache this if we have a lot of builders.
	q := datastore.NewQuery(storage.BuilderKind)
	if !hasInternalAccess {
		q = q.Eq("Public", true) // be paranoid
	}
	err = datastore.Run(c, q, func(b *storage.Builder) {
		m := masterMap[b.ID.Master]
		if m == nil {
			// Perhaps an internal master.
			return
		}

		m.TotalBuilderCount++
		if b.Migration.Status == storage.StatusMigrated {
			m.MigratedBuilderCount++
		}
	})
	if err != nil {
		return nil, err
	}

	// Compute migration percentage.
	for _, m := range model.Masters {
		if m.TotalBuilderCount > 0 {
			m.MigratedBuilderPercent = 100 * m.MigratedBuilderCount / m.TotalBuilderCount
		}
	}

	return model, nil
}
