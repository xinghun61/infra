// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"fmt"
	"net/http"
	"net/url"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
)

// Scheduler is the periodic task that
//   - Determines the concrete ref for every audit configuration in RuleMap
//   - Creates a new RepoState entry for any new refs
//   - Schedules an audit task for each active ref in the appropriate queue
func Scheduler(rc *router.Context) {
	ctx, resp := rc.Context, rc.Writer
	for configName, config := range RuleMap {
		state := RepoState{RepoURL: config.RepoURL()}
		switch err := ds.Get(ctx, state); err {
		case ds.ErrNoSuchEntity:
			state.LastKnownCommit = config.StartingCommit
			state.ConfigName = configName
			err := ds.Put(ctx, state)
			if err != nil {
				logging.WithError(err).Errorf(ctx, "Could not save ref state for %s due to %s", configName, err.Error())
				RefAuditsDue.Add(ctx, 1, false)
				continue
			}
		case nil:
			break
		default:
			http.Error(resp, err.Error(), 500)
			return
		}
		err := taskqueue.Add(ctx, "default",
			&taskqueue.Task{
				Method: "GET",
				Path:   fmt.Sprintf("/_task/auditor?refUrl=%s", url.QueryEscape(config.RepoURL())),
			})
		if err != nil {
			logging.WithError(err).Errorf(ctx, "Could not schedule audit for %s due to %s", config.RepoURL(), err.Error())
			RefAuditsDue.Add(ctx, 1, false)
			continue
		}
		RefAuditsDue.Add(ctx, 1, true)
	}
}
