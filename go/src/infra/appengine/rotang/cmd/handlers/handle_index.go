// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

import (
	"bytes"
	"encoding/json"
	"infra/appengine/rotang"
	"net/http"
	"text/template"

	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const (
	accessDenied = `
<!DOCTYPE html>
<body>
  Access denied. You must have access to the "{{.Group}}" group at <a href="https://chrome-infra-auth.appspot.com">chrome-infra-auth.appspot.com</a> to access this application.
  <br/>
	{{if eq $.NotLoggedIn true}}
		<a href="{{.LoginURL}}">
			Login
		</a>
	{{else}}
		<a href="{{.LogoutURL}}">
			Change account
		</a>
	{{end}}
</body>
`
)

var accessDeniedTemplate = template.Must(template.New("accessDenied").Parse(accessDenied))

// HandleIndex is the handler used for requests to '/'.
func (h *State) HandleIndex(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	usr := auth.CurrentUser(ctx.Context)

	isGoogler, err := auth.IsMember(ctx.Context, h.authGroup)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	if !isGoogler {
		logoutURL, err := auth.LogoutURL(ctx.Context, "/")
		if err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		loginURL, err := auth.LoginURL(ctx.Context, "/")
		if err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		if err := accessDeniedTemplate.Execute(ctx.Writer, map[string]interface{}{
			"Group":       h.authGroup,
			"LogoutURL":   logoutURL,
			"LoginURL":    loginURL,
			"NotLoggedIn": usr == nil || usr.Email == "",
		}); err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		}
		return
	}

	res := []struct {
		Rota      string
		Oncallers []rotang.ShiftMember
	}{}

	if usr == nil || usr.Email == "" {
		templates.MustRender(ctx.Context, ctx.Writer, "pages/index.html", templates.Args{"Rotas": res})
		return
	}
	rotas, err := h.configStore(ctx.Context).MemberOf(ctx.Context, usr.Email)
	if err != nil && status.Code(err) != codes.NotFound {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	if err := enc.Encode(rotas); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	templates.MustRender(ctx.Context, ctx.Writer, "pages/index.html", templates.Args{"Rotas": buf.String(), "User": usr.Email})
}
