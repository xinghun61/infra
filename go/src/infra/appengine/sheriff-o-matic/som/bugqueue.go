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
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"
)

func getBugsFromMonorail(c context.Context, q string) (*monorail.IssuesListResponse, error) {
	// Get authenticated monorail client.
	ctx, _ := context.WithDeadline(c, clock.Now(c).Add(time.Second*30))

	client, err := getOAuthClient(ctx)

	if err != nil {
		return nil, err
	}

	mr := monorail.NewEndpointsClient(client, monorailEndpoint)

	// TODO(martiniss): make this look up request info based on Tree datastore
	// object
	req := &monorail.IssuesListRequest{
		ProjectId: "chromium",
		Can:       monorail.IssuesListRequest_OPEN,
		Q:         q,
	}

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

func getOwnedBugsHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	label := p.ByName("label")

	user := auth.CurrentIdentity(c)
	email := getAlternateEmail(user.Email())
	q := fmt.Sprintf("label:%[1]s owner:%s OR owner:%s label:%[1]s", label, user.Email(), email)

	bugs, err := getBugsFromMonorail(c, q)

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

	res, err := getBugsFromMonorail(c, q)
	if err != nil {
		return nil, err
	}

	bytes, err := json.Marshal(res)
	if err != nil {
		return nil, err
	}

	key := fmt.Sprintf(bugQueueCacheFormat, label)

	item := memcache.NewItem(c, key).SetValue(bytes)

	err = memcache.Set(c, item)

	if err != nil {
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
