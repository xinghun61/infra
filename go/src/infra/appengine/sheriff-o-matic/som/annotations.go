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
	"sort"
	"strings"

	"infra/monorail"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/memcache"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/data/stringset"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/auth/xsrf"
	"github.com/luci/luci-go/server/router"
)

// AnnotationResponse ... The Annotation object extended with cached bug data.
type AnnotationResponse struct {
	Annotation
	BugData map[string]monorail.Issue `json:"bug_data"`
}

func makeAnnotationResponse(a *Annotation, meta map[string]monorail.Issue) *AnnotationResponse {
	bugs := make(map[string]monorail.Issue)
	for _, b := range a.Bugs {
		if bugData, ok := meta[b]; ok {
			bugs[b] = bugData
		}
	}
	return &AnnotationResponse{*a, bugs}
}

func getAnnotationsHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	q := datastore.NewQuery("Annotation")
	annotations := []*Annotation{}
	datastore.GetAll(c, q, &annotations)

	meta, err := getAnnotationsMetaData(c)

	if err != nil {
		logging.Errorf(c, "while fetching annotation metadata")
	}

	output := make([]*AnnotationResponse, len(annotations))
	for i, a := range annotations {
		output[i] = makeAnnotationResponse(a, meta)
	}

	data, err := json.Marshal(output)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(data)
}

func getAnnotationsMetaData(c context.Context) (map[string]monorail.Issue, error) {
	item, err := memcache.GetKey(c, annotationsCacheKey)
	val := make(map[string]monorail.Issue)

	if err == memcache.ErrCacheMiss {
		logging.Debugf(c, "No annotation metadata in memcache, refreshing...")
		val, err = refreshAnnotations(c, nil)

		if err != nil {
			return nil, err
		}
	} else {
		if err = json.Unmarshal(item.Value(), &val); err != nil {
			logging.Errorf(c, "while unmarshaling metadata in getAnnotationsMetaData")
			return nil, err
		}
	}

	return val, nil
}

func refreshAnnotationsHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	bugMap, err := refreshAnnotations(c, nil)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	data, err := json.Marshal(bugMap)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(data)
}

// Update the cache for annotation bug data.
func refreshAnnotations(c context.Context, a *Annotation) (map[string]monorail.Issue, error) {
	q := datastore.NewQuery("Annotation")
	results := []*Annotation{}
	datastore.GetAll(c, q, &results)

	// Monorail takes queries of the format id:1,2,3 (gets bugs with those ids).
	mq := "id:"

	if a != nil {
		results = append(results, a)
	}

	allBugs := stringset.New(len(results))
	for _, ann := range results {
		for _, b := range ann.Bugs {
			allBugs.Add(b)
		}
	}

	bugsSlice := allBugs.ToSlice()
	// Sort so that tests are consistent.
	sort.Strings(bugsSlice)
	mq = fmt.Sprintf("%s%s", mq, strings.Join(bugsSlice, ","))

	issues, err := getBugsFromMonorail(c, mq, monorail.IssuesListRequest_ALL)
	if err != nil {
		return nil, err
	}

	// Turn the bug data into a map with the bug id as a key for easier searching.
	m := make(map[string]monorail.Issue)

	for _, b := range issues.Items {
		key := fmt.Sprintf("%d", b.Id)
		m[key] = *b
	}

	bytes, err := json.Marshal(m)
	if err != nil {
		return nil, err
	}

	item := memcache.NewItem(c, annotationsCacheKey).SetValue(bytes)

	err = memcache.Set(c, item)

	if err != nil {
		return nil, err
	}

	return m, nil
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

	// The annotation probably doesn't exist if we're adding something.
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

	// Refresh the annotation cache on a write. Note that we want the rest of the
	// code to still run even if this fails.
	m, err := refreshAnnotations(c, annotation)
	if err != nil {
		logging.Errorf(c, "while refreshing annotation cache on post: %s", err)
	}

	resp, err := json.Marshal(makeAnnotationResponse(annotation, m))
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
