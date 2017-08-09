// Copyright 2016 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package frontend

import (
	"fmt"
	"net/http"
	"sort"

	"github.com/julienschmidt/httprouter"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/luci_config/common/cfgtypes"
	"go.chromium.org/luci/luci_config/server/cfgclient"
	"go.chromium.org/luci/server/templates"

	"infra/experimental/appengine/buildbucket-viewer/api/settings"

	"golang.org/x/net/context"
)

type projectViewList struct {
	Title   string
	URL     string
	Entries []*projectViewListEntry
}

type projectViewListEntry struct {
	Name string
	URL  string
}

func getAllViewsHandler(c context.Context, req *http.Request, resp http.ResponseWriter, p httprouter.Params) error {
	// Get all view project configs.
	pcfgs, err := getAllProjectConfigs(c)
	if err != nil {
		return makeHTTPError(http.StatusInternalServerError,
			errors.Annotate(err, "").InternalReason("could not load project configs").Err())
	}
	return renderProjectConfigs(c, req, resp, pcfgs, "")
}

func getProjectViewsHandler(c context.Context, req *http.Request, resp http.ResponseWriter, p httprouter.Params) error {
	projectName := cfgtypes.ProjectName(p.ByName("project"))
	if err := projectName.Validate(); err != nil {
		return errors.Annotate(err, "invalid project name").Err()
	}

	// Get all view project configs.
	var (
		projMap  map[cfgtypes.ProjectName]*settings.ProjectConfig
		errorMsg string
	)
	pcfg, err := getProjectConfig(c, projectName)
	switch errors.Unwrap(err) {
	case nil:
		projMap = map[cfgtypes.ProjectName]*settings.ProjectConfig{
			projectName: pcfg,
		}

	case cfgclient.ErrNoConfig:
		errorMsg = fmt.Sprintf("Unknown project name %q. You may need to log in.", projectName)

	default:
		return makeHTTPError(http.StatusInternalServerError,
			errors.Annotate(err, "").InternalReason("could not load project configs").Err())
	}
	return renderProjectConfigs(c, req, resp, projMap, errorMsg)
}

func renderProjectConfigs(c context.Context, req *http.Request, resp http.ResponseWriter,
	pcfgs map[cfgtypes.ProjectName]*settings.ProjectConfig, errorMsg string) error {

	// Sort project names (determinism).
	projNames := make([]string, 0, len(pcfgs))
	for projName := range pcfgs {
		projNames = append(projNames, string(projName))
	}
	sort.Strings(projNames)

	// Export a projectViewList for template rendering.
	allViews := make([]*projectViewList, len(projNames))
	for i, projName := range projNames {
		pcfg := pcfgs[cfgtypes.ProjectName(projName)]
		pvl := projectViewList{
			Title:   pcfg.Title,
			URL:     fmt.Sprintf("/builds/view/%s", projName),
			Entries: make([]*projectViewListEntry, len(pcfg.View)),
		}

		// Sort view names by their key. Export a projectViewListEntry for each
		// view.
		viewNames := make([]string, 0, len(pcfg.View))
		for viewName := range pcfg.View {
			viewNames = append(viewNames, viewName)
		}
		sort.Strings(viewNames)

		for j, viewName := range viewNames {
			view := pcfg.View[viewName]
			pvl.Entries[j] = &projectViewListEntry{
				Name: view.Title,
				URL:  fmt.Sprintf("%s/%s", pvl.URL, viewName),
			}
		}

		allViews[i] = &pvl
	}

	args, err := getDefaultTemplateArgs(c, req)
	if err != nil {
		return errors.Annotate(err, "").InternalReason("failed to get default template args").Err()
	}
	args["Views"] = allViews
	args["ErrorMessage"] = errorMsg
	templates.MustRender(c, resp, "pages/all_views.html", args)
	return nil
}

func getViewHandler(c context.Context, req *http.Request, resp http.ResponseWriter, p httprouter.Params) error {
	projectName := cfgtypes.ProjectName(p.ByName("project"))
	if err := projectName.Validate(); err != nil {
		return makeHTTPError(http.StatusBadRequest, errors.Annotate(err, "invalid project name").Err())
	}

	viewName := p.ByName("view")
	if viewName == "" {
		return makeHTTPError(http.StatusBadRequest, errors.New("empty view name"))
	}

	// Load project settings.
	pcfg, err := getProjectConfig(c, projectName)
	if err != nil {
		return makeHTTPError(http.StatusNotFound,
			errors.Annotate(err, "").InternalReason("could not get project %q config", projectName).Err())
	}

	// Load our application settings.
	s, err := getSettings(c, false)
	if err != nil {
		return errors.Annotate(err, "").InternalReason("failed to load settings").Err()
	}

	view := pcfg.View[viewName]
	if view == nil {
		return makeHTTPError(http.StatusNotFound, errors.Reason("undefined view %q", viewName).Err())
	}

	// Render the view.
	r, err := getBuildSetRenderer(c, req, s)
	if err != nil {
		return errors.Annotate(err, "").InternalReason("failed to get build set renderer").Err()
	}
	return r.render(view, resp)
}
