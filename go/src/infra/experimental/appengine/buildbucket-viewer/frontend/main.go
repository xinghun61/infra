// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package frontend is the main frontend entry point for the BuildBucket query-
// based build status app. It exposes user entry points for the various status
// pages.
package frontend

import (
	"fmt"
	"net/http"

	authServer "github.com/luci/luci-go/appengine/gaeauth/server"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"

	"github.com/julienschmidt/httprouter"
	"golang.org/x/net/context"
)

func init() {
	r := router.New()
	gaemiddleware.InstallHandlers(r)

	viewMW := gaemiddleware.BaseProd().Extend(
		auth.Authenticate(authServer.CookieAuth),
		withTemplates())

	// User-facing templates.
	r.GET("/", viewMW, redirectTo("/builds/views"))
	r.GET("/builds/views", viewMW, errorHandler(getAllViewsHandler))
	r.GET("/builds/view/:project", viewMW, errorHandler(getProjectViewsHandler))
	r.GET("/builds/view/:project/:view", viewMW, errorHandler(getViewHandler))
	r.GET("/builds/query", viewMW, errorHandler(getQueryHandler))

	http.Handle("/", r)
}

func redirectTo(path string) router.Handler {
	return func(ctx *router.Context) {
		http.Redirect(ctx.Writer, ctx.Request, path, http.StatusMovedPermanently)
	}
}

type httpError struct {
	code int
	err  error
}

func makeHTTPError(code int, err error) error { return &httpError{code, err} }

func (he *httpError) Error() string     { return fmt.Sprintf("%d:%s", he.code, he.err) }
func (he *httpError) InnerError() error { return he.err }

func getHTTPErrorCode(err error) (code int) {
	code = http.StatusInternalServerError
	errors.Walk(err, func(err error) bool {
		if he, ok := err.(*httpError); ok {
			code = he.code
			return false
		}
		return true
	})
	return
}

type httpHandlerWithError func(c context.Context, req *http.Request, resp http.ResponseWriter, p httprouter.Params) error

func errorHandler(h httpHandlerWithError) router.Handler {
	return func(ctx *router.Context) {
		if ctx.Request.Body == nil {
			defer ctx.Request.Body.Close()
		}

		bw := errorResponseWriter{
			base: ctx.Writer,
		}
		bw.handleErr(ctx.Context, h(ctx.Context, ctx.Request, ctx.Writer, ctx.Params))
	}
}

type errorResponseWriter struct {
	base http.ResponseWriter

	hasContent bool
}

func (w *errorResponseWriter) Header() http.Header { return w.base.Header() }

func (w *errorResponseWriter) Write(b []byte) (int, error) {
	w.hasContent = true
	return w.base.Write(b)
}

func (w *errorResponseWriter) WriteHeader(code int) {
	w.hasContent = true
	w.base.WriteHeader(code)
}

func (w *errorResponseWriter) handleErr(c context.Context, err error) {
	// If we have an explicit HTTP error, write this instead of our intended
	// output, unless another status has already been written.
	if err == nil {
		return
	}

	code := getHTTPErrorCode(err)
	log.Fields{
		log.ErrorKey: err,
		"code":       code,
	}.Errorf(c, "HTTP handler returned error.")
	if w.hasContent {
		log.Warningf(c, "Handler error pre-empted by response content.")
		return
	}

	// Log error lines to logger.
	rendered := errors.RenderStack(err,
		"github.com/luci/luci-go/server/router",
		"github.com/luci/luci-go/appengine/gaemiddleware",
		"net/http",
	)
	for _, line := range rendered {
		log.Errorf(c, "E> %s", line)
	}

	w.base.WriteHeader(code)
	errBody := err.Error()
	if _, err := w.base.Write([]byte(errBody)); err != nil {
		log.WithError(err).Errorf(c, "Failed to write error response body: %s", errBody)
	}
}
