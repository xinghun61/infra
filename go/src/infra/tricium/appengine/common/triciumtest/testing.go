// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package triciumtest implements common testing functionality for the Tricium
// service modules.
package triciumtest

import (
	"bytes"
	"context"
	"io/ioutil"
	"net/http"
	"time"

	"github.com/julienschmidt/httprouter"
	"go.chromium.org/gae/impl/memory"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/common/logging/memlogger"

	"infra/tricium/appengine/common"
)

// Context generates a context with queues and clock for testing.
func Context() context.Context {
	ctx := memory.Use(memlogger.Use(context.Background()))
	ctx, _ = testclock.UseTime(ctx, testclock.TestTimeUTC.Round(time.Millisecond))
	tq.GetTestable(ctx).CreateQueue(common.AnalyzeQueue)
	tq.GetTestable(ctx).CreateQueue(common.DriverQueue)
	tq.GetTestable(ctx).CreateQueue(common.LauncherQueue)
	tq.GetTestable(ctx).CreateQueue(common.PollProjectQueue)
	tq.GetTestable(ctx).CreateQueue(common.TrackerQueue)
	tq.GetTestable(ctx).CreatePullQueue(common.AnalysisResultsQueue)
	tq.GetTestable(ctx).CreatePullQueue(common.FeedbackEventsQueue)
	ds.GetTestable(ctx).Consistent(true)
	return ctx
}

// MakeGetRequest builds a basic http.Request with the given body.
// Body can be nil if it doesn't matter.
func MakeGetRequest(data []byte) *http.Request {
	body := ioutil.NopCloser(bytes.NewReader(data))
	req, _ := http.NewRequest("GET", "/testing-path", body)
	return req
}

// MakeParams builds and returns params, which can be used
// as part of router.Context passed to handler methods.
func MakeParams(items ...string) httprouter.Params {
	if len(items)%2 != 0 {
		return nil
	}

	params := make([]httprouter.Param, len(items)/2)
	for i := range params {
		params[i] = httprouter.Param{
			Key:   items[2*i],
			Value: items[2*i+1],
		}
	}

	return params
}
