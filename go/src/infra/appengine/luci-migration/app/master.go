// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package app

import (
	"net/http"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"

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
	q := datastore.NewQuery(storage.BuilderKind)
	q = storage.BuilderMasterFilter(c, q, master)
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
