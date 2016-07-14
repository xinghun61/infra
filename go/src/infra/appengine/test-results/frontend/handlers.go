package frontend

import (
	"bytes"
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"net/http"
	"regexp"
	"time"

	"google.golang.org/appengine"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"

	"infra/appengine/test-results/model"
)

const (
	paramsTimeFormat   = "2006-01-02T15:04:05Z" // RFC3339, but enforce Z for timezone.
	httpTimeFormat     = time.RFC1123
	httpNoTZTimeFormat = "Mon, 02 Jan 2006 15:04:05"
)

var (
	callbackNameRx = regexp.MustCompile(`^[A-Za-z0-9_]+$`)
)

func init() {
	r := router.New()

	r.GET("/testfile", base(), testFileHandler)
	r.GET("/testfile/", base(), testFileHandler)

	http.DefaultServeMux.Handle("/", r)
}

// base returns the root middleware chain.
func base() router.MiddlewareChain {
	templateBundle := &templates.Bundle{
		Loader:    templates.FileSystemLoader("templates"),
		DebugMode: appengine.IsDevAppServer(),
		FuncMap: template.FuncMap{
			"timeParams": func(t time.Time) string {
				return t.Format(paramsTimeFormat)
			},
			"timeJS": func(t time.Time) int64 {
				return t.Unix() * 1000
			},
		},
	}

	return gaemiddleware.BaseProd().Extend(
		templates.WithTemplates(templateBundle),
	)
}

// testFileHandler is the HTTP GET request handler for TestFiles.
func testFileHandler(ctx *router.Context) {
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

	// TODO(nishanths): These three actions should preferably be split into
	// three separate endpoints, when changing the external API is possible.
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
		http.Error(w, err.Error(), http.StatusBadRequest)
		logging.Errorf(c, "failed to encode key: %v: %v", key, err)
		return
	}

	tf := model.TestFile{ID: key.IntID()}

	if err := datastore.Get(c).Get(&tf); err == datastore.ErrNoSuchEntity {
		http.Error(w, err.Error(), http.StatusNotFound)
		logging.Errorf(c, "TestFile with ID %v not found: %v", key.IntID(), err)
		return
	} else if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		logging.Errorf(c, "failed to get TestFile with ID %v: %v", key.IntID(), err)
		return
	}

	modTime, err := time.Parse(r.Header.Get("If-Modified-Since"), httpTimeFormat)
	if err == nil && !tf.LastMod.After(modTime) {
		w.WriteHeader(http.StatusNotModified)
		return
	}

	if err := tf.GetData(c); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondJSON(c, w, tf.Data, tf.LastMod, params.Callback)
}

func respondTestFileList(ctx *router.Context, params URLParams) {
	c, w := ctx.Context, ctx.Writer

	q := params.Query()
	var testFiles []*model.TestFile
	if err := datastore.Get(c).GetAll(q, &testFiles); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		logging.Errorf(c, "GetAll failed for query: %+v: %v", q, err)
		return
	}
	if len(testFiles) == 0 {
		e := fmt.Sprintf("no TestFile found for query: %+v", q)
		http.Error(w, e, http.StatusNotFound)
		logging.Errorf(c, e)
		return
	}

	args := templates.Args{
		"Master":      params.Master,
		"Builder":     params.Builder,
		"TestType":    params.TestType,
		"BuildNumber": params.BuildNumber,
		"Name":        params.Name,
		"Files":       testFiles,
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

	templates.MustRender(c, w, "pages/showfilelist.html", args)
}

func keysJSON(c context.Context, tfiles []*model.TestFile) ([]byte, error) {
	type K struct {
		Key string `json:"key"`
	}
	keys := make([]K, len(tfiles))
	for i, tf := range tfiles {
		keys[i] = K{datastore.Get(c).KeyForObj(tf).Encode()}
	}
	return json.Marshal(keys)
}

func respondTestFileDefault(ctx *router.Context, params URLParams) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request
	w.Header().Set("Access-Control-Allow-Origin", "*")

	m := model.MasterByIdentifier(params.Master)
	if m == nil {
		m = model.MasterByName(params.Name)
		if m == nil {
			http.Error(w,
				fmt.Sprintf("master not found by identifier: %s and by name: %s", params.Master, params.Name),
				http.StatusNotFound,
			)
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
		file, err := firstTestFile(c, p.Query())
		ch1 <- TFE{file, err}
	}()
	go func() {
		p := params
		p.Master = m.Name
		file, err := firstTestFile(c, p.Query())
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

	if err := tf.GetData(c); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	if params.TestListJSON {
		tr := model.TestResults{Builder: params.Builder}
		if err := json.NewDecoder(tf.Data).Decode(&tr); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			logging.Errorf(c, "failed to unmarshal TestResults JSON: %+v: %v", tf.Data, err)
			return
		}
		deleteKeys(tr.Tests, "results", "times")
		tl := map[string]map[string]interface{}{
			params.Builder: {
				"tests": tr.Tests,
			},
		}
		tlJSON := &bytes.Buffer{}
		if err := json.NewEncoder(tlJSON).Encode(tl); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			logging.Errorf(c, "failed to marshal test list JSON: %+v: %v", tlJSON, err)
			return
		}
		tf.Data = tlJSON
	}

	respondJSON(c, w, tf.Data, tf.LastMod, params.Callback)
}

// firstTestFile returns the first TestFile for the supplied query. The limit
// on the query is set to 1 before running the query.
func firstTestFile(c context.Context, q *datastore.Query) (*model.TestFile, error) {
	q = q.Limit(1)
	var tfs []*model.TestFile
	if err := datastore.Get(c).GetAll(q, &tfs); err != nil {
		logging.Errorf(c, "GetAll failed for query: %+v: %v", q, err)
		return nil, err
	}
	if len(tfs) == 0 {
		e := fmt.Errorf("no TestFile found for query: %+v", q)
		logging.Errorf(c, e.Error())
		return nil, e
	}
	return tfs[0], nil
}

// deleteKeys recursively calls delete(m, key) for each key in keys.
func deleteKeys(m map[string]interface{}, keys ...string) {
	for k := range m {
		if containsString(keys, k) {
			delete(m, k)
		} else if nextLevel, ok := m[k].(map[string]interface{}); ok {
			deleteKeys(nextLevel, keys...)
		}
	}
}

// containsString returns true if the supplied list contains the target string.
func containsString(list []string, target string) bool {
	for _, s := range list {
		if s == target {
			return true
		}
	}
	return false
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
