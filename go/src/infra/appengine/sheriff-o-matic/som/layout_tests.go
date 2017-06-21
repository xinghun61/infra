package som

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"sort"
	"time"

	"golang.org/x/net/context"

	te "infra/libs/testexpectations"

	"github.com/luci/gae/service/taskqueue"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"

	gerrit "github.com/andygrunwald/go-gerrit"
)

const (
	changeQueue = "changetestexpectations"
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

// LayoutTestExpectationChangeWorker generates a Gerrit changelist to change
// test expectations based on the fields POSTed to it. It should be registered
// as a GAE task queue worker.
func LayoutTestExpectationChangeWorker(ctx *router.Context) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request

	c, cancelFunc := context.WithTimeout(c, 600*time.Second)
	defer cancelFunc()

	fs, err := te.LoadAll(c)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	newExp := &shortExp{}
	if err := json.Unmarshal([]byte(r.FormValue("change")), newExp); err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	stmt := &te.ExpectationStatement{
		TestName:     newExp.TestName,
		Expectations: newExp.Expectations,
		Modifiers:    newExp.Modifiers,
		Bugs:         newExp.Bugs,
	}

	logging.Infof(c, "new expectation: %+v", stmt)

	if err := fs.UpdateExpectation(stmt); err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	client, err := getGerritClient(c)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	logging.Infof(c, "creating a CL editing %d files", len(fs.ToCL()))
	changeID, err := createCL(client, "chromium/src", "master", fmt.Sprintf("update %s expecations", stmt.TestName), fs.ToCL())
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	logging.Infof(c, "created CL: %s editing %d files", changeID, len(fs.ToCL()))

	reviewer := r.FormValue("requester")

	if _, _, err := client.Changes.AddReviewer(changeID, &gerrit.ReviewerInput{
		Reviewer: reviewer,
	}); err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
	}

	if _, err := client.Changes.PublishDraftChange(changeID, "NONE"); err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Write([]byte(changeID))
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
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	user := auth.CurrentIdentity(c)
	params := url.Values{}
	params.Set("requester", user.Email())
	body, err := json.Marshal(newExp)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	params.Set("change", string(body))
	task := taskqueue.NewPOSTTask("/_ah/queue/changetestexpectations", params)

	if err := taskqueue.Add(c, changeQueue, task); err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Write([]byte("ok"))
}
