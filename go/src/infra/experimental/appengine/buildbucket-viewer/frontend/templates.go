// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"net/http"
	"time"

	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/identity"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"

	"github.com/luci/gae/service/info"

	"golang.org/x/net/context"
)

func getTemplateBundle() *templates.Bundle {
	return &templates.Bundle{
		Loader:    templates.FileSystemLoader("templates"),
		DebugMode: info.IsDevAppServer,
		FuncMap: map[string]interface{}{
			"timeToUTCString": func(v time.Time) string {
				return v.UTC().String()
			},
			"timeToEpochSeconds": func(v time.Time) int64 {
				return v.Unix()
			},
		},
		DefaultTemplate: "bootstrap",
		DefaultArgs: func(c context.Context) (templates.Args, error) {
			return templates.Args{
				"Title":       "BuildBucket Viewer",
				"IsAnonymous": auth.CurrentIdentity(c) == identity.AnonymousIdentity,
				"User":        auth.CurrentUser(c),
				"CurrentTime": clock.Now(c),
			}, nil
		},
	}
}

func withTemplates() router.Middleware {
	return templates.WithTemplates(getTemplateBundle())
}

func getDefaultTemplateArgs(c context.Context, req *http.Request) (templates.Args, error) {
	// Determine our login redirect. This is our request URL, bound to the current
	// scheme/host.
	loginRedirectURL := *req.URL
	loginRedirectURL.Scheme = ""
	loginRedirectURL.Host = ""
	loginRedirectURL.User = nil

	menuClass := map[string]string{}
	switch req.URL.Path {
	case "/builds/query":
		menuClass["Query"] = "active"
	default:
		menuClass["Home"] = "active"
	}

	loginRedirect := loginRedirectURL.String()

	loginURL, err := auth.LoginURL(c, loginRedirect)
	if err != nil {
		return nil, errors.Annotate(err, "").InternalReason("failed to generate login URL").Err()
	}
	logoutURL, err := auth.LogoutURL(c, loginRedirect)
	if err != nil {
		return nil, errors.Annotate(err, "").InternalReason("failed to generate logout URL").Err()
	}
	return templates.Args{
		"LoginURL":  loginURL,
		"LogoutURL": logoutURL,
		"MenuClass": menuClass,
	}, nil
}
