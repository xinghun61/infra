// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ephelper

import (
	"github.com/luci/go-endpoints/endpoints"
	gaeauth "go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/server/auth"
	"golang.org/x/net/context"
)

// Middleware is a Context manipulation function that is called when
// initializing a ServiceBase.
type Middleware func(context.Context) (context.Context, error)

// TestMode is a no-op middleware layer.
var TestMode = []Middleware{}

// DefaultMiddleware is the default middleware stack for a ServiceBase. It:
//
//   - Installs the AppEngine production service base from standard.With.
//   - Installs and authenticates the using the Authenticator methods from the
//     ServiceBase.
func DefaultMiddleware(a *auth.Authenticator) Middleware {
	return func(c context.Context) (context.Context, error) {
		c = standard.With(c, endpoints.HTTPRequest(c))

		a := a
		if a == nil {
			mi := MethodInfo(c)
			a = &auth.Authenticator{
				Methods: []auth.Method{&gaeauth.OAuth2Method{Scopes: mi.Scopes}},
			}
		}
		return a.Authenticate(c, endpoints.HTTPRequest(c))
	}
}
