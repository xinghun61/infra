// Copyright 2019 The LUCI Authors.
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

// Package frontend implements Web interface for Arquebus.
package frontend

import (
	"context"
	"net/http"
	"strings"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/xsrf"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"infra/appengine/arquebus/app/config"
	"infra/appengine/arquebus/app/util"
)

// InstallHandlers adds HTTP handlers that render HTML pages.
func InstallHandlers(r *router.Router, bm router.MiddlewareChain) {
	tmpl := prepareTemplates("templates")

	m := bm.Extend(
		templates.WithTemplates(tmpl),
		auth.Authenticate(
			server.UsersAPIAuthMethod{},
			&server.OAuth2Method{
				Scopes: []string{server.EmailScope},
			},
		),
	)
	m = m.Extend(hasAccess)

	r.GET("/", m, indexPage)
	r.GET("/assigner/:AssignerID", m, assignerPage)
	r.GET("/assigner/:AssignerID/task/:TaskID", m, taskPage)
}

// prepareTemplates constructs templates.Bundle for HTML handlers.
func prepareTemplates(templatesPath string) *templates.Bundle {
	args := func(c context.Context, e *templates.Extra) (templates.Args, error) {
		loginURL, err := auth.LoginURL(c, e.Request.URL.RequestURI())
		if err != nil {
			return nil, err
		}
		logoutURL, err := auth.LogoutURL(c, e.Request.URL.RequestURI())
		if err != nil {
			return nil, err
		}
		token, err := xsrf.Token(c)
		if err != nil {
			return nil, err
		}
		return templates.Args{
			"AppVersion": strings.Split(info.VersionID(c), ".")[0],
			"User":       auth.CurrentUser(c),
			"LoginURL":   loginURL,
			"LogoutURL":  logoutURL,
			"XsrfToken":  token,
		}, nil
	}
	return &templates.Bundle{
		Loader:          templates.FileSystemLoader(templatesPath),
		DebugMode:       info.IsDevAppServer,
		DefaultTemplate: "base",
		DefaultArgs:     args,
	}
}

// hasAccess checks whether the user is allowed to access Arquebus UI.
func hasAccess(rc *router.Context, next router.Handler) {
	c := rc.Context
	isMember, err := auth.IsMember(c, config.Get(c).AccessGroup)
	if err != nil {
		util.ErrStatus(rc, http.StatusInternalServerError, err.Error())
		return
	} else if !isMember {
		url, err := auth.LoginURL(c, rc.Request.URL.RequestURI())
		if err != nil {
			util.ErrStatus(
				rc, http.StatusForbidden,
				"Access denied err:"+err.Error())
			return
		}
		http.Redirect(rc.Writer, rc.Request, url, http.StatusFound)
		return
	}

	next(rc)
}
