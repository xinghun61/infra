// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/memcache"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"
	"golang.org/x/net/context"

	"infra/appengine/test-results/model"
)

const buildbotMemcacheKey = "buildbot_data"

var nonTestStepNames = []string{
	"archive",
	"Run tests",
	"find isolated tests",
	"read test spec",
	"Download latest chromedriver",
	"compile tests",
	"create_coverage_",
	"update test result log",
	"memory test:",
	"install_",
}

var noUploadTestSteps = []string{
	"java_tests(chrome",
	"python_tests(chrome",
	"run_all_tests.py",
	"test_report",
	"test CronetSample",
	"test_mini_installer",
	"webkit_python_tests",
}

// testTriple is used to de-dup (builder, master, test) triples.
type testTriple struct {
	Builder  string
	Master   string
	TestType string
}

// getRecentTests gets a set of (builder, master, test) triples with upload activity
// in the last `days` days.
func getRecentTests(c context.Context, days int) (map[testTriple]struct{}, error) {
	daysAgo := clock.Now(c).UTC().AddDate(0, 0, -days)
	tfp := model.TestFileParams{
		Name: "results.json",
	}
	q := tfp.Query()
	q = q.Gt("date", daysAgo)
	q = q.Project("master", "builder", "test_type").Distinct(true)
	// We can revisit this limit if we start uploading significantly more data.
	q = q.Limit(10000)

	tt := make(map[testTriple]struct{})
	err := datastore.Run(c, q, func(tf *model.TestFile) {
		// We only expect Master, Builder, and TestType to be set since we're
		// doing a projection query, but for some reason these other fields are
		// still populated. This doesn't matter since we discard them here but
		// it might affect other users.
		// TODO(estaab): Create a small repro case and file a bug in luci/gae.
		tt[testTriple{
			Builder:  tf.Builder,
			Master:   tf.Master,
			TestType: tf.TestType}] = struct{}{}
	})
	logging.Infof(c, "Found %v (master, builder, test type) triples.", len(tt))

	if err != nil {
		logging.WithError(err).Errorf(c, "GetAll failed for query: %+v", q)
		return nil, err
	}
	if len(tt) == 0 {
		e := fmt.Sprintf("no TestFile found for query: %+v", q)
		logging.Errorf(c, e)
		return nil, errors.New(e)
	}

	return tt, nil
}

// getBuilderData loads recently uploaded test types from datastore.
func getBuilderData(c context.Context) (*model.BuilderData, error) {
	triples, err := getRecentTests(c, 7)
	if err != nil {
		return nil, err
	}

	// Place triples into builder data.
	nameToMaster := make(map[string]*model.Master)
	for triple := range triples {
		m, ok := nameToMaster[triple.Master]
		if !ok {
			m = &model.Master{
				Name:       triple.Master,
				Identifier: triple.Master,
				Tests:      make(map[string]*model.Test),
			}
			nameToMaster[triple.Master] = m
		}
		test, ok := m.Tests[triple.TestType]
		if !ok {
			test = &model.Test{
				Builders: make([]string, 0, 10),
			}
			m.Tests[triple.TestType] = test
		}
		test.Builders = append(test.Builders, triple.Builder)
	}

	// Sort lists to make debugging easier.
	for _, m := range nameToMaster {
		for _, t := range m.Tests {
			sort.Strings(t.Builders)
		}
	}
	names := make([]string, 0, len(nameToMaster))
	for n := range nameToMaster {
		names = append(names, n)
	}
	sort.Strings(names)

	bd := model.BuilderData{
		NoUploadTestTypes: noUploadTestSteps,
	}
	bd.Masters = make([]model.Master, 0, len(nameToMaster))
	for _, n := range names {
		bd.Masters = append(bd.Masters, *nameToMaster[n])
	}

	return &bd, nil
}

// getBuildersHandler serves json of all known tests, builders, and masters.
func getBuildersHandler(ctx *router.Context) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request

	item, err := memcache.GetKey(c, buildbotMemcacheKey)
	var res []byte
	switch err {
	case memcache.ErrCacheMiss:
		logging.Infof(c, "Builder data not in memcache so loading from datastore.")
		bd, err := getBuilderData(c)
		if err != nil {
			logging.WithError(err).Errorf(c, "Failed to get known tests from datastore")
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		res, err = json.Marshal(&bd)
		if err != nil {
			logging.WithError(err).Errorf(c, "Failed to marshal json")
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		item.SetValue(res).SetExpiration(time.Hour)
		if err := memcache.Set(c, item); err != nil {
			// Log this error but do not return to the client because it is not critical
			// for this handler.
			logging.Fields{
				logging.ErrorKey: err,
				"item":           item,
			}.Errorf(c, "getBuildersHandler: set memcache")
		}

	case nil:
		logging.Infof(c, "Loaded builder data from memcache.")
		res = item.Value()

	default:
		logging.WithError(err).Errorf(c, "getBuildersHandler")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	var out io.Reader = bytes.NewReader(res)
	if c := r.FormValue("callback"); callbackNameRx.MatchString(c) {
		out = wrapCallback(out, c)
	} else {
		w.Header().Add("Content-Type", "application/json")
	}

	n, err := io.Copy(w, out)

	if err != nil {
		logging.Fields{
			logging.ErrorKey: err,
			"n":              n,
		}.Errorf(c, "getBuildersHandler: error writing HTTP response")
	}
}

var ignoreTestNameRx = regexp.MustCompile(`_only|_ignore|_perf$`)
var gtestUploaderStepRx = regexp.MustCompile(`Upload to test-results \[([^]]*)\]`)

func cleanTestStep(name string) (clean string, ok bool) {
	if !strings.Contains(name, "test") {
		return "", false
	}

	for _, n := range nonTestStepNames {
		if strings.Contains(name, n) {
			return "", false
		}
	}

	if ignoreTestNameRx.MatchString(name) {
		return "", false
	}

	// Ignore triggering and collecting steps on swarming:
	// they are not actual tests.
	for _, p := range []string{"[trigger]", "[collect]", "[skipped]"} {
		if strings.HasPrefix(name, p) {
			return "", false
		}
	}

	if m := gtestUploaderStepRx.FindStringSubmatch(name); len(m) == 2 {
		name = m[1]
	}

	// The following comments are copied from the Python version. Evaluate
	// correctness of the TODO before working on it:
	//
	// Skip all steps that don't have test in the first word (before
	// the first space), and remove platform cruft. This rule is based
	// on a manual audit of valid and invalid test types populated in
	// the dashboard in Q4 2015.
	//
	// Normalization also happens at upload time to ensure known
	// and actual test types match.
	//
	// TODO: Remove nonTestStepNames since this rule should remove all
	// of them already.

	name = cleanTestType(name)
	return name, strings.Contains(name, "test")
}

func cleanTestType(name string) string {
	withPatch := false
	if strings.Contains(name, " (with patch)") {
		withPatch = true
		name = strings.Replace(name, " (with patch)", "", 1)
	}

	// Special rule for Instrumentation test.
	instr := "Instrumentation test "
	if strings.HasPrefix(name, instr) {
		name = name[len(instr):]
	}

	// Clean platform noise. For simplicity and based on current
	// data, we just keep everything before the first space.
	if i := strings.Index(name, " "); i != -1 {
		name = name[:i]
	}

	if withPatch {
		name += " (with patch)"
	}
	return name
}
