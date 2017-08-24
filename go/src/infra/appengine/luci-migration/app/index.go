// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package app

import (
	"sort"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"infra/appengine/luci-migration/storage"
)

type indexViewModel struct {
	Masters []*indexMasterViewModel
}

type indexMasterViewModel struct {
	Name string

	WAIBuilderCount        int
	WAIBuilderPercent      int
	MigratedBuilderCount   int
	MigratedBuilderPercent int
	TotalBuilderCount      int
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
	masters := map[string]*indexMasterViewModel{}
	masterNames := []string{}
	// Note: may have to cache this if we have a lot of builders.
	q := datastore.NewQuery(storage.BuilderKind)
	err := datastore.Run(c, q, func(b *storage.Builder) {
		m := masters[b.ID.Master]
		if m == nil {
			m = &indexMasterViewModel{Name: b.ID.Master}
			masters[b.ID.Master] = m
			masterNames = append(masterNames, m.Name)
		}

		m.TotalBuilderCount++
		switch b.Migration.Status {
		case storage.StatusMigrated:
			m.MigratedBuilderCount++
			fallthrough
		case storage.StatusLUCIWAI:
			m.WAIBuilderCount++
		}
	})
	if err != nil {
		return nil, err
	}

	sort.Strings(masterNames)
	model := &indexViewModel{Masters: make([]*indexMasterViewModel, len(masterNames))}
	for i, name := range masterNames {
		m := masters[name]
		if m.TotalBuilderCount > 0 {
			m.WAIBuilderPercent = 100 * m.WAIBuilderCount / m.TotalBuilderCount
			m.MigratedBuilderPercent = 100 * m.MigratedBuilderCount / m.TotalBuilderCount
		}
		model.Masters[i] = m
	}

	return model, nil
}
