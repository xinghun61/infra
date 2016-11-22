// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package som implements HTTP server that handles requests to default module.
package som

import (
	"bytes"
	"crypto/sha1"
	"encoding/json"
	"fmt"
	"net/http"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/auth/xsrf"
	"github.com/luci/luci-go/server/router"
)

func getAnnotationsHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	q := datastore.NewQuery("Annotation")
	results := []*Annotation{}
	datastore.GetAll(c, q, &results)

	data, err := json.Marshal(results)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(data)
}

type postRequest struct {
	XSRFToken string           `json:"xsrf_token"`
	Data      *json.RawMessage `json:"data"`
}

func postAnnotationsHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	annKey := p.ByName("annKey")
	action := p.ByName("action")

	if !(action == "add" || action == "remove") {
		errStatus(c, w, http.StatusNotFound, "Invalid action")
		return
	}

	req := &postRequest{}
	err := json.NewDecoder(r.Body).Decode(req)
	if err != nil {
		errStatus(c, w, http.StatusBadRequest, fmt.Sprintf("while decoding request: %s", err))
		return
	}

	if err := xsrf.Check(c, req.XSRFToken); err != nil {
		errStatus(c, w, http.StatusForbidden, err.Error())
		return
	}

	annotation := &Annotation{
		KeyDigest: fmt.Sprintf("%x", sha1.Sum([]byte(annKey))),
		Key:       annKey,
	}

	err = datastore.Get(c, annotation)
	if action == "remove" && err != nil {
		logging.Errorf(c, "while getting %s: %s", annKey, err)
		errStatus(c, w, http.StatusNotFound, fmt.Sprintf("Annotation %s not found", annKey))
		return
	}
	// The annotation probably doesn't exist if we're adding something

	data := bytes.NewReader([]byte(*req.Data))
	if action == "add" {
		err = annotation.add(c, data)
	} else if action == "remove" {
		err = annotation.remove(c, data)
	}

	if err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	err = r.Body.Close()
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	err = datastore.Put(c, annotation)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	resp, err := json.Marshal(annotation)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(resp)
}

func flushOldAnnotationsHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	numDeleted, err := flushOldAnnotations(c)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	s := fmt.Sprintf("deleted %d annotations", numDeleted)
	logging.Debugf(c, s)
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(s))
}

func flushOldAnnotations(c context.Context) (int, error) {
	q := datastore.NewQuery("Annotation")
	q = q.Lt("ModificationTime", clock.Get(c).Now().Add(-annotationExpiration))
	q = q.KeysOnly(true)

	results := []*Annotation{}
	err := datastore.GetAll(c, q, &results)
	if err != nil {
		return 0, fmt.Errorf("while fetching annotations to delete: %s", err)
	}

	for _, ann := range results {
		logging.Debugf(c, "Deleting %#v\n", ann)
	}

	err = datastore.Delete(c, results)
	if err != nil {
		return 0, fmt.Errorf("while deleting annotations: %s", err)
	}

	return len(results), nil
}
