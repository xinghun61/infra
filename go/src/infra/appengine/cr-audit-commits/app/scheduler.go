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
		var refConfigs []*RepoConfig
		var err error
		if config.DynamicRefFunction != nil {
			refConfigs, err = config.DynamicRefFunction(ctx, *config)
			if err != nil {
				logging.WithError(err).Errorf(ctx, "Could not determine the concrete ref for %s due to %s", configName, err.Error())
				RefAuditsDue.Add(ctx, 1, false)
				continue
			}
		} else {
			refConfigs = []*RepoConfig{config}
		}
		for _, refConfig := range refConfigs {
			state := &RepoState{RepoURL: refConfig.RepoURL()}
			err = ds.Get(ctx, state)
			switch err {
			case ds.ErrNoSuchEntity:
				state.ConfigName = configName
				state.Metadata = refConfig.Metadata
				state.BranchName = refConfig.BranchName
				state.LastKnownCommit = refConfig.StartingCommit
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
			err = taskqueue.Add(ctx, "default",
				&taskqueue.Task{
					Method: "GET",
					Path:   fmt.Sprintf("/_task/auditor?refUrl=%s", url.QueryEscape(refConfig.RepoURL())),
				})
			if err != nil {
				logging.WithError(err).Errorf(ctx, "Could not schedule audit for %s due to %s", refConfig.RepoURL(), err.Error())
				RefAuditsDue.Add(ctx, 1, false)
				continue
			}
			RefAuditsDue.Add(ctx, 1, true)
		}
	}
}
