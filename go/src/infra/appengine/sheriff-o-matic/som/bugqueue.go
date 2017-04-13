// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package som implements HTTP server that handles requests to default module.
package som

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"infra/monorail"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/memcache"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/tsmon/field"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"
)

var (
	bugQueueLength = metric.NewInt("bug_queue_length", "Number of bugs in queue.",
		nil, field.String("label"))
)

// A bit of a hack to let us mock getBugsFromMonorail.
var getBugsFromMonorail = func(c context.Context, q string,
	can monorail.IssuesListRequest_CannedQuery) (*monorail.IssuesListResponse, error) {
	// Get authenticated monorail client.
	ctx, cancel := context.WithDeadline(c, clock.Now(c).Add(time.Second*30))
	defer cancel()

	client, err := getOAuthClient(ctx)

	if err != nil {
		return nil, err
	}

	mr := monorail.NewEndpointsClient(client, monorailEndpoint)

	// TODO(martiniss): make this look up request info based on Tree datastore
	// object
	req := &monorail.IssuesListRequest{
		ProjectId: "chromium",
		Q:         q,
	}

	req.Can = can

	before := clock.Now(c)

	res, err := mr.IssuesList(c, req)
	if err != nil {
		return nil, err
	}

	logging.Debugf(c, "Fetch to monorail took %v. Got %d bugs.", clock.Now(c).Sub(before), res.TotalResults)
	return res, nil
}

func getBugQueueHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	label := p.ByName("label")
	key := fmt.Sprintf(bugQueueCacheFormat, label)

	item, err := memcache.GetKey(c, key)

	if err == memcache.ErrCacheMiss {
		logging.Debugf(c, "No bug queue data for %s in memcache, refreshing...", label)
		item, err = refreshBugQueue(c, label)
	}

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	result := item.Value()

	w.Header().Set("Content-Type", "application/json")
	w.Write(result)
}

func getUncachedBugsHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	label := p.ByName("label")

	user := auth.CurrentIdentity(c)
	email := getAlternateEmail(user.Email())
	q := fmt.Sprintf("label:%[1]s -has:owner OR label:%[1]s owner:%s OR owner:%s label:%[1]s",
		label, user.Email(), email)

	bugs, err := getBugsFromMonorail(c, q, monorail.IssuesListRequest_OPEN)

	bugQueueLength.Set(c, int64(bugs.TotalResults), label)

	out, err := json.Marshal(bugs)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(out)
}

// Makes a request to Monorail for bugs in a label and caches the results.
func refreshBugQueue(c context.Context, label string) (memcache.Item, error) {
	q := fmt.Sprintf("label:%s", label)

	// We may eventually want to make this an option that's configurable per bug
	// queue.
	if label == "infra-troopers" {
		q = fmt.Sprintf("%s -has:owner", q)
	}

	res, err := getBugsFromMonorail(c, q, monorail.IssuesListRequest_OPEN)
	if err != nil {
		return nil, err
	}

	bytes, err := json.Marshal(res)
	if err != nil {
		return nil, err
	}

	item := memcache.NewItem(c, fmt.Sprintf(bugQueueCacheFormat, label)).SetValue(bytes)

	if err = memcache.Set(c, item); err != nil {
		return nil, err
	}

	return item, nil
}

func refreshBugQueueHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params
	label := p.ByName("label")
	item, err := refreshBugQueue(c, label)

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(item.Value())
}
