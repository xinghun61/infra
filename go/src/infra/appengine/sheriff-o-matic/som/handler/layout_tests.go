package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"time"

	"golang.org/x/net/context"

	te "infra/appengine/sheriff-o-matic/som/testexpectations"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
)

type shortExp struct {
	FileName     string
	LineNumber   int
	TestName     string
	Bugs         []string
	Modifiers    []string
	Expectations []string
}

type byTestName []*shortExp

func (a byTestName) Len() int           { return len(a) }
func (a byTestName) Swap(i, j int)      { a[i], a[j] = a[j], a[i] }
func (a byTestName) Less(i, j int) bool { return a[i].TestName < a[j].TestName }

// GetLayoutTestsHandler returns a JSON summary of webkit layout tests and
// their expected results.
func GetLayoutTestsHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer
	c, cancelFunc := context.WithTimeout(c, 60*time.Second)
	defer cancelFunc()

	fs, err := te.LoadAll(c)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	res := []*shortExp{}
	for _, f := range fs.Files {
		for _, e := range f.Expectations {
			if e.TestName != "" {
				res = append(res, &shortExp{
					FileName:     f.Path,
					LineNumber:   e.LineNumber + 1,
					Bugs:         e.Bugs,
					TestName:     e.TestName,
					Modifiers:    e.Modifiers,
					Expectations: e.Expectations,
				})
			}
		}
	}

	sort.Sort(byTestName(res))

	b, err := json.Marshal(res)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	fmt.Fprintf(w, "%v\n", string(b))
}

// PostLayoutTestExpectationChangeHandler enqueues an asynchronous task to
// create a Gerrit changelist to change test expectations based on the fields
// POSTed to it.
func PostLayoutTestExpectationChangeHandler(ctx *router.Context) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request

	c, cancelFunc := context.WithTimeout(c, 60*time.Second)
	defer cancelFunc()

	newExp := &shortExp{}
	if err := json.NewDecoder(r.Body).Decode(newExp); err != nil {
		logging.Errorf(c, "decoding body: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	fs, err := te.LoadAll(c)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	stmt := &te.ExpectationStatement{
		TestName:     newExp.TestName,
		Expectations: newExp.Expectations,
		Modifiers:    newExp.Modifiers,
		Bugs:         newExp.Bugs,
	}

	logging.Infof(c, "new expectation: %+v", *stmt)

	if err = fs.UpdateExpectation(stmt); err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	resp := struct {
		CL map[string]string
	}{
		CL: fs.ToCL(),
	}

	respBytes, err := json.Marshal(resp)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Write(respBytes)
}
