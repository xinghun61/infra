// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"golang.org/x/net/context"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/track"
)

type runInfo struct {
	ID        int64
	Received  time.Time
	GitRepo   string
	GitRef    string
	GerritURL string
	Paths     []string
	Functions map[string]*functionInfo
}

type functionInfo struct {
	Name    string
	State   tricium.State
	Workers map[string]*workerInfo
}

type workerInfo struct {
	Name           string
	IsolatedInput  string
	IsolatedOutput string
	SwarmingTaskID string
	NumComments    int
	State          tricium.State
	Result         string
}

// runPageHandler shows details of tracking entities for a given run ID.
//
// The initial version of this page can be used for debugging, but
// should be re-worked before it is suitable as a user-facing page
// that can be linked to.
func runPageHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	runID, err := strconv.ParseInt(ctx.Params.ByName("runId"), 10, 64)
	if err != nil {
		http.Error(w, "failed to parse run ID", 400)
		return
	}

	request := &track.AnalyzeRequest{ID: runID}
	if err = ds.Get(c, request); err != nil {
		http.Error(w, "failed to get AnalyzeRequest", 404)
		return
	}

	run, err := fetchRunInfo(c, request)
	if err != nil {
		common.ReportServerError(ctx, err)
		return
	}

	runJSON, err := json.MarshalIndent(run, "", "  ")
	if err != nil {
		common.ReportServerError(ctx, err)
		return
	}
	templates.MustRender(c, w, "pages/run.html", map[string]interface{}{
		"RunInfo": string(runJSON),
	})
	w.WriteHeader(http.StatusOK)
}

func fetchRunInfo(c context.Context, request *track.AnalyzeRequest) (*runInfo, error) {
	functionMap, err := fetchFunctionInfoMap(c, request.ID)
	if err != nil {
		return nil, err
	}
	return &runInfo{
		ID:        request.ID,
		Received:  request.Received,
		GitRepo:   request.GitRepo,
		GitRef:    request.GitRef,
		GerritURL: common.GerritURL(request.GerritHost, request.GerritRevision),
		Paths:     request.Paths,
		Functions: functionMap,
	}, nil
}

func fetchFunctionInfoMap(c context.Context, runID int64) (map[string]*functionInfo, error) {
	functionMap := map[string]*functionInfo{}
	functionRuns, err := track.FetchFunctionRuns(c, runID)
	if err != nil {
		return nil, err
	}
	workerMap, err := fetchWorkerInfoMap(c, runID)
	if err != nil {
		return nil, err
	}
	for _, fr := range functionRuns {
		result := &track.FunctionRunResult{ID: 1, Parent: ds.KeyForObj(c, fr)}
		if err := ds.Get(c, result); err != nil {
			return nil, err
		}
		functionMap[fr.ID] = &functionInfo{
			Name:    fr.ID,
			State:   result.State,
			Workers: map[string]*workerInfo{},
		}
		for _, name := range fr.Workers {
			functionMap[fr.ID].Workers[name] = workerMap[name]
		}
	}
	return functionMap, nil
}

func fetchWorkerInfoMap(c context.Context, runID int64) (map[string]*workerInfo, error) {
	workerRuns, err := track.FetchWorkerRuns(c, runID)
	if err != nil {
		return nil, err
	}
	workerMap := map[string]*workerInfo{}
	for _, wr := range workerRuns {
		result := &track.WorkerRunResult{ID: 1, Parent: ds.KeyForObj(c, wr)}
		if err := ds.Get(c, result); err != nil {
			return nil, err
		}
		workerMap[wr.ID] = &workerInfo{
			Name:           wr.ID,
			IsolatedInput:  result.IsolatedInput,
			IsolatedOutput: result.IsolatedOutput,
			SwarmingTaskID: result.SwarmingTaskID,
			NumComments:    result.NumComments,
			State:          result.State,
			Result:         result.Result,
		}
	}
	return workerMap, nil
}
