// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"strconv"
	"sync"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"

	"infra/appengine/test-results/masters"
	"infra/appengine/test-results/model"
)

func requestOK(ctx *router.Context) bool {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request
	if info.IsDevAppServer(c) {
		return true
	}
	// Only bots should upload test results. Check IP address against a whitelist.
	whitelisted, err := auth.GetState(c).DB().IsInWhitelist(
		c, auth.GetState(c).PeerIP(), "bots")
	if err != nil {
		logging.WithError(err).Errorf(c, "uploadHandler: check IP whitelist")
		http.Error(w, "Failed IP whitelist check", http.StatusInternalServerError)
		return false
	}
	if !whitelisted {
		logging.WithError(err).Errorf(
			c, "Uploading IP %s is not whitelisted", auth.GetState(c).PeerIP())
		http.Error(w, "IP is not whitelisted", http.StatusUnauthorized)
		return false
	}
	if r.TLS == nil {
		logging.Errorf(c, "uploadHandler: only allow HTTPS")
		http.Error(w, "Only HTTPS requests are allowed", http.StatusUnauthorized)
		return false
	}
	return true
}

type statusError struct {
	error
	code int // HTTP status code.
}

// MarshalJSON marshals status error to JSON.
func (se *statusError) MarshalJSON() ([]byte, error) {
	m := map[string]interface{}{}

	if se == nil || se.error == nil {
		return json.Marshal(m)
	}

	m["error"] = se.Error()
	m["status"] = se.code
	return json.Marshal(m)
}

// UploadParams represents the multipart form values in a
// TestFile upload request.
type UploadParams struct {
	Master string
	// DeprecatedMaster is set when master.Name was provided
	// in the request instead of master.Identifer.
	DeprecatedMaster string
	Builder          string
	TestType         string
	StepName         string
}

type contextKey int

const uploadContextKey = contextKey(0)

// GetUploadParams returns the UploadParams from the context if
// present or nil otherwise.
func GetUploadParams(c context.Context) *UploadParams {
	if v := c.Value(uploadContextKey); v != nil {
		return v.(*UploadParams)
	}
	return nil
}

// SetUploadParams returns a new context with the supplied
// UploadParams added to it.
func SetUploadParams(c context.Context, p *UploadParams) context.Context {
	return context.WithValue(c, uploadContextKey, p)
}

// withParsedUploadForm is middleware that verifies and adds
// multipart form upload data to the context.
//
// If there is an error parsing the form or required
// values are missing, the function writes the HTTP error
// to the response writer and does not call next.
func withParsedUploadForm(ctx *router.Context, next router.Handler) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request

	// Use 20 megabytes in memory. If the files are larger that 20
	// megabytes, App Engine will return an error when accessing the
	// file system to store the remaining parts.
	const maxMem = 20 * (1 << 20)

	if err := r.ParseMultipartForm(maxMem); err != nil {
		logging.WithError(err).Errorf(c, "withParsedUploadForm: error parsing form")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	u := &UploadParams{}

	if v := r.MultipartForm.Value["master"]; len(v) > 0 {
		if m := masters.ByName(v[0]); m != nil {
			u.Master = m.Identifier
			u.DeprecatedMaster = v[0]
		} else if m := masters.ByIdentifier(v[0]); m != nil {
			u.Master = m.Identifier
		} else {
			errMsg := fmt.Sprintf(
				"master %s is not whitelisted, see https://goo.gl/RHx4hS", v[0])
			logging.Errorf(c, errMsg)
			http.Error(w, errMsg, http.StatusBadRequest)
			return
		}
	}

	if v := r.MultipartForm.Value["builder"]; len(v) > 0 {
		u.Builder = v[0]
	} else {
		logging.Errorf(c, "withParsedUploadForm: missing builder")
		http.Error(w, "missing builder", http.StatusBadRequest)
		return
	}

	if v := r.MultipartForm.Value["testtype"]; len(v) > 0 {
		u.TestType = cleanTestType(v[0])
		u.StepName = v[0]
	}

	if _, ok := r.MultipartForm.File["file"]; !ok {
		logging.Errorf(c, "withParsedUploadForm: missing file")
		http.Error(w, "missing file", http.StatusBadRequest)
		return
	}

	ctx.Context = SetUploadParams(ctx.Context, u)
	next(ctx)
}

// uploadHandler is the HTTP handler for upload
// requests.
func uploadHandler(ctx *router.Context) {
	// Only bots should upload test results. Check IP address against a whitelist.
	c, w, r := ctx.Context, ctx.Writer, ctx.Request
	whitelisted, err := auth.GetState(c).DB().IsInWhitelist(
		c, auth.GetState(c).PeerIP(), "bots")
	if err != nil {
		logging.WithError(err).Errorf(c, "uploadHandler: check IP whitelist")
		http.Error(w, "Failed IP whitelist check", http.StatusInternalServerError)
		return
	}

	if !whitelisted {
		logging.WithError(err).Errorf(
			c, "Uploading IP %s is not whitelisted", auth.GetState(c).PeerIP())
		http.Error(w, "IP is not whitelisted", http.StatusUnauthorized)
		return
	}

	if r.TLS == nil {
		logging.Errorf(c, "uploadHandler: only allow HTTPS")
		http.Error(w, "Only HTTPS requests are allowed", http.StatusUnauthorized)
		return
	}

	fileheaders := r.MultipartForm.File["file"]

	for _, fh := range fileheaders {
		if err := doFileUpload(c, fh); err != nil {
			msg := logging.WithError(err)
			code := http.StatusInternalServerError
			if se, ok := err.(statusError); ok {
				code = se.code
			}
			if code >= http.StatusInternalServerError {
				msg.Errorf(c, "uploadHandler")
			} else {
				msg.Warningf(c, "uploadHandler")
			}
			http.Error(w, err.Error(), code)
			return
		}
	}

	io.WriteString(w, "OK")
}

func doFileUpload(c context.Context, fh *multipart.FileHeader) error {
	file, err := fh.Open()
	if err != nil {
		logging.WithError(err).Errorf(c, "doFileUpload: file open")
		return statusError{err, http.StatusInternalServerError}
	}
	defer file.Close()

	var r io.Reader = file

	switch fh.Filename {
	case "incremental_results.json":
		var incr model.AggregateResult
		if err := json.NewDecoder(file).Decode(&incr); err != nil {
			logging.WithError(err).Warningf(c, "doFileUpload: incremental_results.json: unmarshal JSON")
			return statusError{err, http.StatusBadRequest}
		}
		return updateIncremental(c, &incr)

	case "full_results.json":
		return updateFullResults(c, r)

	case "failing_results.json":
		r, err = model.CleanJSON(r)
		if err != nil {
			logging.WithError(err).Errorf(c, "doFileUpload: CleanJSON")
			return statusError{err, http.StatusInternalServerError}
		}
		fallthrough

	default:
		return uploadTestFile(c, r, fh.Filename)
	}
}

// ErrInvalidBuildNumber is returned when the extractBuildNumber fails
// to convert the build number value to an int.
var ErrInvalidBuildNumber = errors.New("invalid build_number: cannot convert to int")

// extractBuildNumber extracts the value of "build_number" key from
// the supplied JSON encoded data. The returned io.Reader will have
// the same contents as the supplied io.Reader.
//
// The error is ErrInvalidBuildNumber if the build number value
// could not be converted to an int.
func extractBuildNumber(data io.Reader) (int, io.Reader, error) {
	var buf bytes.Buffer
	tee := io.TeeReader(data, &buf)

	aux := struct {
		N string `json:"build_number,omitempty"`
	}{}
	dec := json.NewDecoder(tee)
	if err := dec.Decode(&aux); err != nil {
		return 0, io.MultiReader(&buf, dec.Buffered()), err
	}

	var bn int
	if aux.N != "" {
		n, err := strconv.Atoi(aux.N)
		if err != nil {
			return 0, io.MultiReader(&buf, dec.Buffered()), ErrInvalidBuildNumber
		}
		bn = n
	}

	return bn, io.MultiReader(&buf, dec.Buffered()), nil
}

// uploadTestFile creates a new TestFile from the UploadParams in context
// and supplied data, and puts it to the datastore.
func uploadTestFile(c context.Context, data io.Reader, filename string) error {
	bn, data, err := extractBuildNumber(data)
	if err != nil {
		msg := logging.Fields{logging.ErrorKey: err, "filename": filename}
		if err == ErrInvalidBuildNumber {
			msg.Warningf(c, "uploadTestFile")
			return statusError{err, http.StatusBadRequest}
		}
		msg.Errorf(c, "uploadTestFile")
		return statusError{err, http.StatusInternalServerError}
	}

	p := GetUploadParams(c)
	tf := model.TestFile{
		Master:      p.Master,
		Builder:     p.Builder,
		TestType:    p.TestType,
		BuildNumber: model.BuildNum(bn),
		Name:        filename,
	}
	err = tf.PutData(c, func(w io.Writer) error {
		_, err := io.Copy(w, data)
		return err
	})
	if err != nil {
		logging.Fields{logging.ErrorKey: err, "filename": filename}.Errorf(c, "uploadTestFile: PutData")
		return statusError{err, http.StatusInternalServerError}
	}

	return datastore.Put(c, &tf)
}

func createTestResUploadTask(c context.Context, f *model.FullResult, p *UploadParams) {
	payload, err := json.Marshal(struct {
		Master      string       `json:"master"`
		Builder     string       `json:"builder"`
		BuildNumber model.Number `json:"build_number"`
		TestType    string       `json:"test_type"`
		StepName    string       `json:"step_name"`
	}{
		Master:      p.Master,
		Builder:     p.Builder,
		BuildNumber: f.BuildNumber,
		TestType:    p.TestType,
		StepName:    p.StepName,
	})
	if err != nil {
		logging.WithError(err).Errorf(c, "taskqueue: %s", monitoringPath)
		return
	}

	h := make(http.Header)
	h.Set("Content-Type", "application/json")

	logging.Debugf(c, "adding taskqueue task for [%s]", monitoringPath)
	if err := taskqueue.Add(c, monitoringQueueName, &taskqueue.Task{
		Path:    monitoringPath,
		Payload: payload,
		Header:  h,
		Method:  "POST",
	}); err != nil {
		logging.WithError(err).Errorf(c, "Failed to add task queue task.")
	}
}

// updateFullResults puts the supplied data as "full_results.json"
// to the datastore, and updates corresponding "results.json" and
// "results-small.json" files in the datastore.
//
// The supplied data should unmarshal into model.FullResult.
// Otherwise, an error is returned.
func updateFullResults(c context.Context, data io.Reader) error {
	buf := &bytes.Buffer{}
	tee := io.TeeReader(data, buf)
	dec := json.NewDecoder(tee)
	p := GetUploadParams(c)

	var f model.FullResult
	if err := dec.Decode(&f); err != nil {
		logging.WithError(err).Errorf(c, "updateFullResults: unmarshal JSON")
		return statusError{err, http.StatusBadRequest}
	}

	if f.Builder != p.Builder {
		err := errors.New("Builder in query params does not match uploaded JSON")
		logging.WithError(err).Errorf(c, "updateFullResults: validate input")
		return statusError{err, http.StatusBadRequest}
	}

	// Validate timestamp for the results: it should be within a day from now.
	maxTimestamp := float64(time.Now().Add(24 * time.Hour).Unix())
	if f.SecondsEpoch <= 0 || f.SecondsEpoch >= maxTimestamp {
		err := errors.New("Invalid value for seconds_since_epoch")
		logging.WithError(err).Errorf(c, "updateFullResults: validate input")
		return statusError{err, http.StatusBadRequest}
	}

	logging.Debugf(c, "Processing full_results.json for master %s, builder %s, "+
		"build %d, test type %s", p.Master, f.Builder, f.BuildNumber, p.TestType)

	if err := uploadTestFile(c, io.MultiReader(buf, dec.Buffered()), "full_results.json"); err != nil {
		logging.WithError(err).Errorf(c, "updateFullResults: uploadTestFile")
		return statusError{err, http.StatusInternalServerError}
	}

	incr, err := f.AggregateResult()
	if err != nil {
		logging.WithError(err).Errorf(c, "updateFullResults: convert to AggregateResult")
		return statusError{err, http.StatusBadRequest}
	}
	if err := updateIncremental(c, &incr); err != nil {
		msg := logging.WithError(err)
		code := http.StatusInternalServerError
		if se, ok := err.(statusError); ok {
			code = se.code
			if code >= http.StatusInternalServerError {
				msg.Errorf(c, "updateFullResults: updateIncremental")
			} else {
				msg.Warningf(c, "updateFullResults: updateIncremental")
			}
		}
		return statusError{err, code}
	}

	wg := sync.WaitGroup{}

	wg.Add(1)
	go func() {
		defer wg.Done()
		createTestResUploadTask(c, &f, p)
	}()

	wg.Wait()
	return nil
}

func createEmptyAggregateTestFileEntity(p model.TestFileParams) *model.TestFile {
	return &model.TestFile{
		Master:      p.Master,
		Builder:     p.Builder,
		TestType:    p.TestType,
		BuildNumber: -1,
		Name:        p.Name,
	}
}

// updateIncremental gets "results.json" and "results-small.json"
// for UploadParams in context, merges incr into them, and puts the updated
// files to the datastore.
func updateIncremental(c context.Context, incr *model.AggregateResult) error {
	u := GetUploadParams(c)
	p := model.TestFileParams{
		Master:   u.Master,
		Builder:  u.Builder,
		TestType: u.TestType,
	}

	names := []string{"results.json", "results-small.json"}
	files := make([]struct {
		tf   *model.TestFile
		aggr *model.AggregateResult
		err  error
	}, len(names))

	wg := sync.WaitGroup{}

	for i, name := range names {
		i, name, p := i, name, p
		wg.Add(1)

		go func() {
			defer wg.Done()
			p.Name = name
			tf, err := getTestFileAlt(c, p, u.DeprecatedMaster)
			if err != nil {
				if _, ok := err.(ErrNoMatches); ok {
					files[i].tf = createEmptyAggregateTestFileEntity(p)
					return
				}
				logging.WithError(err).Errorf(c, "updateIncremental: getTestFileAlt")
				files[i].err = err
				return
			}

			reader, err := tf.DataReader(c)
			if err != nil {
				logging.WithError(err).Errorf(c, "updateIncremental: GetData")
				files[i].err = err
				return
			}
			var a model.AggregateResult
			if err := json.NewDecoder(reader).Decode(&a); err != nil {
				logging.WithError(err).Warningf(c, "updateIncremental: unmarshal TestFile data")
				files[i].err = statusError{err, http.StatusBadRequest}
				return
			}

			if tf.Builder != a.Builder {
				logging.Warningf(c, "Builder in TestFile entity for aggregated file "+
					"does not match data in linked JSON file. Deleting corrupted entity.")

				// Try to delete data entities linked to the corrupted aggregate file.
				if err = datastore.Delete(c, tf.DataKeys); err != nil {
					logging.WithError(err).Warningf(
						c, "Failed to delete data keys linked with corrupted entity")
				}

				// Delete entity for the corrupted aggregate file.
				err = datastore.Delete(c, datastore.KeyForObj(c, tf))
				if err != nil {
					logging.WithError(err).Errorf(c, "updateIncremental: delete entity")
					files[i].err = statusError{err, http.StatusInternalServerError}
					return
				}

				// Create a new empty entity.
				files[i].tf = createEmptyAggregateTestFileEntity(p)
				return
			}

			files[i].tf = tf
			files[i].aggr = &a
		}()
	}

	wg.Wait()
	for idx, file := range files {
		if file.err != nil {
			logging.Fields{
				logging.ErrorKey: file.err,
				"index":          idx,
			}.Errorf(c, "File encountered error.")
			return file.err
		}
	}

	return datastore.RunInTransaction(c, func(c context.Context) error {
		wg = sync.WaitGroup{}
		errs := make([]error, len(files))

		for i, file := range files {
			i, file := i, file
			wg.Add(1)
			go func() {
				defer wg.Done()
				errs[i] = updateAggregate(c, file.tf, file.aggr, incr)
			}()
		}

		wg.Wait()
		// Prioritize returning http.StatusInternalServerError status
		// code errors over other errors.
		var e error
		for _, err := range errs {
			if err != nil {
				msg := logging.WithError(err)
				se, ok := err.(statusError)
				if ok && se.code >= http.StatusInternalServerError {
					msg.Errorf(c, "updateIncremental: inside transaction")
					return se
				}

				msg.Warningf(c, "updateIncremental: inside transaction")
				e = err
			}
		}
		return e
	}, &datastore.TransactionOptions{XG: true})
}

// getTestFileAlt returns the the first TestFile in the datastore for
// the query formed by calling p.Query().
//
// The function tries to find the first TestFile using p. If no such TestFile
// exists the function sets p.Master to altMaster and tries again.
// If altMaster is empty, the function does not perform the additional try.
func getTestFileAlt(c context.Context, p model.TestFileParams, altMaster string) (ret *model.TestFile, err error) {
	a, err := getFirstTestFile(c, p.Query())
	if err == nil {
		return a, nil
	}
	if _, ok := err.(ErrNoMatches); ok && altMaster == "" {
		return nil, err
	}

	origMaster := p.Master
	p.Master = altMaster

	a, err = getFirstTestFile(c, p.Query())
	if err == nil {
		a.Master = origMaster
		return a, nil
	}

	return nil, err
}

// updateAggregate updates tf with the result of merging incr into
// aggr, and updates tf in datastore.
func updateAggregate(c context.Context, tf *model.TestFile, aggr, incr *model.AggregateResult) error {
	if !model.IsAggregateTestFile(tf.Name) {
		return errors.New("frontend: tf should be an aggregate test file")
	}

	size := model.ResultsSize
	if tf.Name == "results-small.json" {
		size = model.ResultsSmallSize
	}

	if aggr == nil {
		aggr = incr
	} else {
		if err := aggr.Merge(incr); err != nil {
			msg := logging.WithError(err)
			switch err {
			case model.ErrBuilderNameConflict:
				msg.Warningf(c, "updateAggregate: merge for master: %q, builder: %q, file: %q", tf.Master, tf.Builder, tf.Name)
				return statusError{err, http.StatusBadRequest}
			case model.ErrBuildNumberConflict:
				msg.Warningf(c, "updateAggregate: merge for master: %q, builder: %q, file: %q", tf.Master, tf.Builder, tf.Name)
				return statusError{err, http.StatusConflict}
			default:
				msg.Errorf(c, "updateAggregate: merge for master: %q, builder: %q, file: %q", tf.Master, tf.Builder, tf.Name)
				return statusError{err, http.StatusInternalServerError}
			}
		}
	}

	if err := aggr.Trim(size); err != nil {
		logging.WithError(err).Errorf(c, "updateAggregate: trim")
		return statusError{err, http.StatusInternalServerError}
	}

	err := tf.PutData(c, func(w io.Writer) error {
		if err := json.NewEncoder(w).Encode(&aggr); err != nil {
			logging.WithError(err).Errorf(c, "updateAggregate: marshal JSON")
			return err
		}
		return nil
	})
	if err != nil {
		logging.WithError(err).Errorf(c, "updateAggregate: PutData")
		return statusError{err, http.StatusInternalServerError}
	}

	if err := datastore.Put(c, tf); err != nil {
		logging.WithError(err).Errorf(c, "updateAggregate: datastore.Put")
		return statusError{err, http.StatusInternalServerError}
	}
	if err := deleteKeys(c, tf.OldDataKeys); err != nil {
		logging.Fields{
			logging.ErrorKey: err,
			"keys":           tf.OldDataKeys,
		}.Errorf(c, "upload: failed to delete keys")
	}
	return nil
}

// deleteKeys posts the supplied keys to the delete keys task queue.
func deleteKeys(c context.Context, k []*datastore.Key) error {
	if len(k) == 0 {
		return nil
	}

	keys := make([]string, 0, len(k))
	for _, key := range k {
		keys = append(keys, key.Encode())
	}

	payload, err := json.Marshal(struct {
		Keys []string `json:"keys"`
	}{
		keys,
	})
	if err != nil {
		return err
	}

	h := make(http.Header)
	h.Set("Content-Type", "application/json")

	logging.Fields{
		"keys": keys,
	}.Infof(c, "deleteKeys: enqueing")

	return taskqueue.Add(c, deleteKeysQueueName, &taskqueue.Task{
		Path:    deleteKeysPath,
		Payload: payload,
		Header:  h,
		Method:  "POST",
		Delay:   time.Duration(30) * time.Minute,
	})
}
