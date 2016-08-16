package frontend

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"mime/multipart"
	"net/http"
	"strconv"
	"sync"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/server/router"

	"infra/appengine/test-results/model"
)

type statusError struct {
	error
	code int
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

// UploadParams is the multipart form values in a
// TestFile upload request.
type UploadParams struct {
	Master string
	// DeprecatedMaster is set when master.Name was provided
	// in the request, instead of master.Identifer.
	DeprecatedMaster string
	Builder          string
	TestType         string
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
// values are missing, WithParsed writes the HTTP error
// to the response writer and stops execution of the request.
func withParsedUploadForm(ctx *router.Context, next router.Handler) {
	w, r := ctx.Writer, ctx.Request
	const _1M = 1 << 20

	if err := r.ParseMultipartForm(_1M); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	u := &UploadParams{}

	if v := r.MultipartForm.Value["master"]; len(v) > 0 {
		if m := model.MasterByName(v[0]); m != nil {
			u.Master = m.Identifier
			u.DeprecatedMaster = v[0]
		} else {
			u.Master = v[0]
		}
	}

	if v := r.MultipartForm.Value["builder"]; len(v) > 0 {
		u.Builder = v[0]
	} else {
		http.Error(w, "missing builder", http.StatusBadRequest)
		return
	}

	if v := r.MultipartForm.Value["testtype"]; len(v) > 0 {
		u.TestType = cleanTestType(v[0])
	}

	if _, ok := r.MultipartForm.File["file"]; !ok {
		http.Error(w, "missing file", http.StatusBadRequest)
		return
	}

	ctx.Context = SetUploadParams(ctx.Context, u)
	next(ctx)
}

// uploadHandler is the HTTP handler for upload
// requests.
func uploadHandler(ctx *router.Context) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request
	fileheaders := r.MultipartForm.File["file"]

	for _, fh := range fileheaders {
		if err := doFileUpload(c, fh); err != nil {
			code := http.StatusInternalServerError
			if se, ok := err.(statusError); ok {
				code = se.code
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
		return statusError{err, http.StatusInternalServerError}
	}
	defer file.Close()

	switch fh.Filename {
	case "incremental_results.json":
		var incr model.AggregateResult
		if err := json.NewDecoder(file).Decode(&incr); err != nil {
			return statusError{err, http.StatusBadRequest}
		}
		return updateIncremental(c, &incr)
	case "full_results.json":
		return updateFullResults(c, file)
	default:
		return uploadTestFile(c, file, fh.Filename)
	}
}

// uploadTestFile creates a new TestFile from the values in context
// and supplied data, and puts it to the datastore.
func uploadTestFile(c context.Context, data io.Reader, filename string) error {
	var buf bytes.Buffer
	tee := io.TeeReader(data, &buf)

	aux := struct {
		N string `json:"build_number,omitempty"`
	}{}

	dec := json.NewDecoder(tee)
	if err := dec.Decode(&aux); err != nil {
		return statusError{err, http.StatusInternalServerError}
	}

	bn := 0

	if aux.N != "" {
		n, err := strconv.Atoi(aux.N)
		if err != nil {
			return statusError{errors.New("invalid build_number"), http.StatusBadRequest}
		}
		bn = n
	}

	p := GetUploadParams(c)
	tf := model.TestFile{
		Master:      p.Master,
		Builder:     p.Builder,
		TestType:    p.TestType,
		BuildNumber: model.BuildNum(bn),
		Name:        filename,
		Data:        io.MultiReader(&buf, dec.Buffered()),
	}
	if err := tf.PutData(c); err != nil {
		return statusError{err, http.StatusInternalServerError}
	}
	return nil
}

// updateFullResults puts the supplied data as "full_results.json"
// to the datastore, and updates corresponding "results.json" and
// "results-small.json" files in the datastore.
//
// The supplied data should unmarshal into model.FullResults.
// Otherwise, an error is returned.
func updateFullResults(c context.Context, data io.Reader) error {
	buf := &bytes.Buffer{}
	tee := io.TeeReader(data, buf)
	dec := json.NewDecoder(tee)

	var f model.FullResult
	if err := dec.Decode(&f); err != nil {
		return statusError{err, http.StatusBadRequest}
	}

	wg := sync.WaitGroup{}
	errCh := make(chan error, 2)

	wg.Add(1)
	go func() {
		defer wg.Done()
		errCh <- uploadTestFile(
			c, io.MultiReader(buf, dec.Buffered()), "full_results.json",
		)
	}()

	wg.Add(1)
	go func() {
		defer wg.Done()
		incr, err := f.AggregateResult()
		if err != nil {
			errCh <- statusError{err, http.StatusBadRequest}
			return
		}
		errCh <- updateIncremental(c, &incr)
	}()

	wg.Wait()
	close(errCh)
	for err := range errCh {
		if err != nil {
			return err
		}
	}
	return nil
}

// updateIncremental gets "results.json" and "results-small.json"
// for values in context, merges incr into them, and puts the updated
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
		i, name := i, name
		wg.Add(1)
		go func() {
			defer wg.Done()
			tf, err := getTestFileAlt(c, p, u.DeprecatedMaster)
			if err != nil {
				if _, ok := err.(ErrNoMatches); ok {
					files[i].tf = &model.TestFile{
						Master:      p.Master,
						Builder:     p.Builder,
						TestType:    p.TestType,
						BuildNumber: -1,
						Name:        name,
					}
				} else {
					files[i].err = err
				}
				return
			}
			files[i].tf = tf
			if err := tf.GetData(c); err != nil {
				files[i].err = err
				return
			}
			if err := json.NewDecoder(tf.Data).Decode(files[i].aggr); err != nil {
				files[i].err = err
				return
			}
		}()
	}

	wg.Wait()
	for _, file := range files {
		if file.err != nil {
			return file.err
		}
	}

	wg = sync.WaitGroup{}
	errs := make([]error, len(files))

	return datastore.Get(c).RunInTransaction(func(c context.Context) error {
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
			se, ok := err.(statusError)
			if ok && se.code == http.StatusInternalServerError {
				return se
			}
			e = err
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
// aggr.
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
			switch err {
			case model.ErrBuilderNameConflict:
				return statusError{err, http.StatusBadRequest}
			case model.ErrBuildNumberConflict:
				return statusError{err, http.StatusConflict}
			default:
				return statusError{err, http.StatusInternalServerError}
			}
		}
	}

	if err := aggr.Trim(size); err != nil {
		return statusError{err, http.StatusInternalServerError}
	}

	b := &bytes.Buffer{}
	if err := json.NewEncoder(b).Encode(&aggr); err != nil {
		return statusError{err, http.StatusInternalServerError}
	}

	tf.Data = b
	if err := tf.PutData(c); err != nil {
		return statusError{err, http.StatusInternalServerError}
	}

	return nil
}
