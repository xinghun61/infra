package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"time"

	"golang.org/x/net/context"

	te "infra/appengine/sheriff-o-matic/som/testexpectations"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"

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

// QueuedUpdate represents a CL in progress, as requested by a user to change
// test expectations.
type QueuedUpdate struct {
	// ID is an opaque identifier assigned by datastore.
	ID int64 `gae:"$id"`
	// Requester is the email address of the user who originally requested the
	// change via SoM UI.
	Requester string
	// ChangeID is blank until the CL has been created by the worker task, at
	// which point it gets assigned to the Gerrit change ID created.
	ChangeID string
	// ErrorMessage is blank unless the worker encountered an error while trying
	// to generate the CL.
	ErrorMessage string
}

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
	updateID, err := strconv.Atoi(r.FormValue("updateID"))
	if err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	writeUpdate := func(changeID string, err error) {
		logging.Errorf(c, "writeUpdate: %v %v", changeID, err)
		if err := writeQueuedUpdate(c, int64(updateID), changeID, err); err != nil {
			logging.Errorf(c, "getting from datastore: %v", err.Error())
			errStatus(c, w, http.StatusInternalServerError, err.Error())
		}
	}

	fs, err := te.LoadAll(c)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		writeUpdate("", err)
		return
	}

	newExp := &shortExp{}
	if err := json.Unmarshal([]byte(r.FormValue("change")), newExp); err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		writeUpdate("", err)
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
		writeUpdate("", err)
		return
	}

	client, err := getGerritClient(c)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		writeUpdate("", err)
		return
	}

	logging.Infof(c, "creating a CL editing %d files", len(fs.ToCL()))
	changeID, err := createCL(client, "chromium/src", "master", fmt.Sprintf("update %s expecations", stmt.TestName), fs.ToCL())
	if err != nil {
		logging.Errorf(c, "error creating CL: %v", err.Error())
		writeUpdate(changeID, err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	logging.Infof(c, "created CL: %s editing %d files", changeID, len(fs.ToCL()))

	reviewer := r.FormValue("requester")

	if _, _, err := client.Changes.AddReviewer(changeID, &gerrit.ReviewerInput{
		Reviewer: reviewer,
	}); err != nil {
		logging.Errorf(c, "creating CL: %v", err.Error())
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		writeUpdate(changeID, err)
		return
	}

	if _, err := client.Changes.PublishDraftChange(changeID, "NONE"); err != nil {
		logging.Errorf(c, "publishing change: %v", err.Error())
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		writeUpdate(changeID, err)
		return
	}

	writeUpdate(changeID, nil)

	w.Write([]byte(changeID))
}

func writeQueuedUpdate(c context.Context, updateID int64, changeID string, err error) error {
	queuedUpdate := &QueuedUpdate{
		ID: updateID,
	}

	if err := datastore.RunInTransaction(c, func(c context.Context) error {
		if err := datastore.Get(c, queuedUpdate); err != nil {
			logging.Errorf(c, "getting from datastore: %v", err.Error())
			return err
		}
		queuedUpdate.ChangeID = changeID
		if err != nil {
			queuedUpdate.ErrorMessage = err.Error()
		}
		return datastore.Put(c, queuedUpdate)
	}, nil); err != nil {
		logging.Errorf(c, "updating datastore: %v", err.Error())
		return err
	}

	return nil
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

	user := auth.CurrentIdentity(c)

	queuedUpdate := &QueuedUpdate{
		Requester: user.Email(),
	}

	if err := datastore.RunInTransaction(c, func(c context.Context) error {
		if err := datastore.AllocateIDs(c, queuedUpdate); err != nil {
			logging.Errorf(c, "allocating id: %v", err)
			return err
		}
		return datastore.Put(c, queuedUpdate)
	}, nil); err != nil {
		logging.Errorf(c, "allocating id: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	params := url.Values{}
	params.Set("requester", user.Email())
	params.Set("updateID", fmt.Sprintf("%d", queuedUpdate.ID))
	body, err := json.Marshal(newExp)
	if err != nil {
		logging.Errorf(c, "marshaling newExp: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	params.Set("change", string(body))
	task := taskqueue.NewPOSTTask("/_ah/queue/changetestexpectations", params)

	workerHost, err := info.ModuleHostname(c, "analyzer", "", "")
	if err != nil {
		logging.Errorf(c, "getting worker backend hostname: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}
	task.Header["Host"] = []string{workerHost}

	if err := taskqueue.Add(c, changeQueue, task); err != nil {
		logging.Errorf(c, "adding to task queue: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	resp := map[string]interface{}{
		"QueuedRequestID": queuedUpdate.ID,
	}

	respBytes, err := json.Marshal(resp)
	if err != nil {
		logging.Errorf(c, "marshaling response: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Write(respBytes)
}

// GetTestExpectationCLStatusHandler gets the status of a queued change request.
func GetTestExpectationCLStatusHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	c, cancelFunc := context.WithTimeout(c, 60*time.Second)
	defer cancelFunc()

	updateID, err := strconv.Atoi(p.ByName("id"))
	if err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	logging.Debugf(c, "fetching update ID %v", updateID)

	queuedUpdate := &QueuedUpdate{
		ID: int64(updateID),
	}

	if err := datastore.Get(c, queuedUpdate); err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	resp := map[string]interface{}{
		"ChangeID": queuedUpdate.ChangeID,
		// TODO: return something other than 200 OK when this isn't blank?
		"ErrorMessage": queuedUpdate.ErrorMessage,
	}

	respBytes, err := json.Marshal(resp)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Write(respBytes)
}
