// Copyright 2018 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package inventory

import (
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/frontend/inventory/internal/dutpool"

	"go.chromium.org/luci/common/errors"
	"golang.org/x/net/context"
)

// setDutHealths updates DUTs in pb with their health retrieved from tasker.
func setDutHealths(ctx context.Context, tr fleet.TrackerServer, pb *dutpool.Balancer) error {
	if err := setDutHealthsForPool(ctx, tr, pb.Target); err != nil {
		return err
	}
	if err := setDutHealthsForPool(ctx, tr, pb.Spare); err != nil {
		return err
	}
	return nil
}

func setDutHealthsForPool(ctx context.Context, tr fleet.TrackerServer, dutHealths map[string]fleet.Health) error {
	if len(dutHealths) == 0 {
		// Calling SummarizeBots without filter is the same as summarizing all
		// bots, but we want to summarize no bots instead.
		return nil
	}

	sels := make([]*fleet.BotSelector, 0, len(dutHealths))
	for d := range dutHealths {
		sels = append(sels, &fleet.BotSelector{DutId: d})
	}
	sbr, err := tr.SummarizeBots(ctx, &fleet.SummarizeBotsRequest{Selectors: sels})
	if err != nil {
		return errors.Annotate(err, "get bot summaries").Err()
	}

	for _, s := range sbr.Bots {
		dutHealths[s.DutId] = s.Health
	}
	return nil
}
