// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"bytes"
	"encoding/json"
	"fmt"
	"infra/appengine/test-results/masters"
	"infra/appengine/test-results/model"
	"io"
	"net/http"
	"regexp"
	"time"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"golang.org/x/net/context"
)

const (
	// paramsTimeFormat is the time format string in incoming GET
	// /testfile requests.
	paramsTimeFormat = "2006-01-02T15:04:05Z" // RFC3339, but enforce Z for timezone.

	// httpTimeFormat is the time format used in HTTP headers.
	// See https://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html
	// (Section 14.18 Date).
	httpTimeFormat = time.RFC1123

	// httpNoTZTimeFormat is httpTimeFormat with the timezone removed.
	httpNoTZTimeFormat = "Mon, 02 Jan 2006 15:04:05"
)

// callbackNameRx matches start of strings that look like
// JavaScript function names. Not a comprehensive solution.
var callbackNameRx = regexp.MustCompile(`^[A-Za-z0-9_]+$`)

// getHandler is the HTTP handler for GET /testfile requests.
func getHandler(ctx *router.Context) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request
	if err := r.ParseForm(); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		logging.Errorf(c, "failed to parse form: %v", err)
		return
	}

	params, err := NewURLParams(r.Form)
	if err != nil {
		e := fmt.Sprintf("failed to parse URL parameters: %+v: %v", params, err)
		http.Error(w, e, http.StatusBadRequest)
		logging.Errorf(c, e)
		return
	}

	// This allows to query test results also based on the original step name.
	// Queries which are run against normalized (cleaned) test type already should
	// be unaffected since normalizing previously normalized test type should be a
	// no-op.
	params.TestType = cleanTestType(params.TestType)

	switch {
	case params.Key != "":
		respondTestFileData(ctx, params)
	case params.ShouldListFiles():
		respondTestFileList(ctx, params)
	default:
		respondTestFileDefault(ctx, params)
	}
}

func respondTestFileData(ctx *router.Context, params URLParams) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request
	w.Header().Set("Access-Control-Allow-Origin", "*")

	key, err := datastore.NewKeyEncoded(params.Key)
	if err != nil {
		logging.Fields{logging.ErrorKey: err, "key": key}.Errorf(c, "encode key")
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	tf := model.TestFile{ID: key.IntID()}

	if err := datastore.Get(c, &tf); err != nil {
		if err == datastore.ErrNoSuchEntity {
			http.Error(w, err.Error(), http.StatusNotFound)
			logging.Errorf(c, "TestFile with ID %v not found: %v", key.IntID(), err)
			return
		}
		http.Error(w, err.Error(), http.StatusInternalServerError)
		logging.Errorf(c, "failed to get TestFile with ID %v: %v", key.IntID(), err)
		return
	}

	modTime, err := time.Parse(r.Header.Get("If-Modified-Since"), httpTimeFormat)
	if err == nil && !tf.LastMod.After(modTime) {
		w.WriteHeader(http.StatusNotModified)
		return
	}

	reader, err := tf.DataReader(c)
	if err != nil {
		logging.WithError(err).Errorf(c, "respondTestFileData: DataReader")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondJSON(c, w, reader, tf.LastMod, params.Callback)
}

func respondTestFileList(ctx *router.Context, params URLParams) {
	c, w := ctx.Context, ctx.Writer

	q := params.Query()
	var testFiles []*model.TestFile
	if err := datastore.GetAll(c, q, &testFiles); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		logging.Errorf(c, "GetAll failed for query: %+v: %v", q, err)
		return
	}
	if len(testFiles) == 0 {
		e := fmt.Sprintf("no TestFile found for query: %+v", q)
		http.Error(w, e, http.StatusNotFound)
		logging.Infof(c, e)
		return
	}

	if params.Callback != "" {
		b, err := keysJSON(c, testFiles)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			logging.Errorf(c, "failed to create callback JSON: %v: %v", testFiles, err)
			return
		}
		respondJSON(c, w, bytes.NewReader(b), testFiles[0].LastMod, params.Callback)
		return
	}

	templates.MustRender(c, w, "pages/showfilelist.html", templates.Args{
		"Master":      params.Master,
		"Builder":     params.Builder,
		"TestType":    params.TestType,
		"BuildNumber": params.BuildNumber,
		"Name":        params.Name,
		"Files":       testFiles,
	})
}

func keysJSON(c context.Context, tfiles []*model.TestFile) ([]byte, error) {
	type wireFormat struct {
		*model.TestFile
		// Not sure if anything actually uses this, but it's already here,
		// so keep it around in case something relies on it.
		Key string `json:"key"`
	}
	toMarshal := make([]wireFormat, len(tfiles))
	for i, tf := range tfiles {
		toMarshal[i] = wireFormat{tf, datastore.KeyForObj(c, tf).Encode()}
	}
	return json.Marshal(toMarshal)
}

func respondTestFileDefault(ctx *router.Context, params URLParams) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request
	w.Header().Set("Access-Control-Allow-Origin", "*")

	m := masters.ByIdentifier(params.Master)
	if m == nil {
		m = masters.ByName(params.Master)
		if m == nil {
			logging.Fields{"master": params.Master}.Infof(c, "master not found")
			http.Error(w, fmt.Sprintf(
				"master %q not found by identifier or name", params.Master,
			), http.StatusNotFound)
			return
		}
	}

	// Get TestFile using master.Identifier. If that fails, get
	// TestFile using master.Name.
	type TFE struct {
		file *model.TestFile
		err  error
	}
	ch1, ch2 := make(chan TFE, 1), make(chan TFE, 1)
	go func() {
		p := params
		p.Master = m.Identifier
		file, err := getFirstTestFile(c, p.Query())
		ch1 <- TFE{file, err}
	}()
	go func() {
		p := params
		p.Master = m.Name
		file, err := getFirstTestFile(c, p.Query())
		ch2 <- TFE{file, err}
	}()
	tfe := <-ch1
	if tfe.err != nil {
		tfe = <-ch2
		if tfe.err != nil {
			http.Error(w, tfe.err.Error(), http.StatusNotFound)
			return
		}
	}

	tf := tfe.file

	modTime, err := time.Parse(r.Header.Get("If-Modified-Since"), httpTimeFormat)
	if err == nil && !tf.LastMod.After(modTime) {
		w.WriteHeader(http.StatusNotModified)
		return
	}

	reader, err := tf.DataReader(c)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	finalData := reader

	if params.TestListJSON {
		data, err := model.CleanJSON(reader)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			logging.Errorf(c, "failed to clean test results JSON: %v", err)
			return
		}
		aggr := model.AggregateResult{Builder: params.Builder}
		if err := json.NewDecoder(data).Decode(&aggr); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			logging.Errorf(c, "failed to unmarshal test results JSON: %+v: %v", data, err)
			return
		}

		tl := aggr.ToTestList()
		buf := bytes.Buffer{}
		if err := json.NewEncoder(&buf).Encode(&tl); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			logging.Errorf(c, "failed to marshal test list JSON: %+v, %v", aggr.Tests, err)
			return
		}
		finalData = &buf
	}

	respondJSON(c, w, finalData, tf.LastMod, params.Callback)
}

// ErrNoMatches is returned when a query returns 0 entities.
type ErrNoMatches string

func (e ErrNoMatches) Error() string {
	return string(e)
}

// getFirstTestFile returns the first TestFile for the supplied query. The limit
// on the query is set to 1 before running the query.
func getFirstTestFile(c context.Context, q *datastore.Query) (*model.TestFile, error) {
	q = q.Limit(1)
	logging.Infof(c, "getting testfile with query %+v", q)
	var tfs []*model.TestFile
	if err := datastore.GetAll(c, q, &tfs); err != nil {
		logging.Errorf(c, "GetAll failed for query: %+v: %v", q, err)
		return nil, err
	}
	if len(tfs) == 0 {
		e := ErrNoMatches(fmt.Sprintf("no TestFile found for query: %+v", q))
		logging.Infof(c, e.Error())
		return nil, e
	}
	return tfs[0], nil
}

// respondJSON writes the supplied JSON data to w. If the supplied callback string matches
// callbackNameRx, data is wrapped in a JSONP-style function with the supplied callback
// string as the function name.
func respondJSON(c context.Context, w http.ResponseWriter, data io.Reader, lastMod time.Time, callback string) {
	if callbackNameRx.MatchString(callback) {
		data = wrapCallback(data, callback)
	}
	w.Header().Set("Last-Modified", lastMod.Format(httpNoTZTimeFormat)+" GMT")
	w.Header().Set("Content-Type", "application/json")
	n, err := io.Copy(w, data)
	if err != nil {
		logging.Errorf(c, "error writing JSON response: %#v, %v, wrote %d bytes", data, err, n)
	}
}

// wrapCallback returns an io.Reader that wraps the data in r in a
// JavaScript-style function call with the supplied name as the function name.
func wrapCallback(r io.Reader, name string) io.Reader {
	start := bytes.NewReader([]byte(name + "("))
	end := bytes.NewReader([]byte(");"))
	return io.MultiReader(start, r, end)
}
