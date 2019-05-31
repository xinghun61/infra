// Copyright 2019 The LUCI Authors.
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

package backend

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"time"

	"go.chromium.org/gae/service/memcache"
	"go.chromium.org/gae/service/urlfetch"
	"go.chromium.org/luci/common/logging"

	"infra/appengine/arquebus/app/backend/model"
	"infra/appengine/arquebus/app/config"
	"infra/monorailv2/api/api_proto"
)

var (
	// maxShiftCacheDuration is the maximum cache duration for shifts.
	//
	// This is to have caches updated even before the shift ends, just in
	// case the shift has been modified.
	maxShiftCacheDuration = 5 * time.Minute
)

type oncallShift struct {
	Primary     string   `json:"primary"`
	Secondaries []string `json:"secondaries"`
	Started     int64    `json:"update_unix_timestamp"`
}

func findAssigneeAndCCs(c context.Context, assigner *model.Assigner, task *model.Task) (*monorail.UserRef, []*monorail.UserRef, error) {
	assigneeSrcs, err := assigner.Assignees()
	if err != nil {
		return nil, nil, err
	}
	ccSrcs, err := assigner.CCs()
	if err != nil {
		return nil, nil, err
	}

	// resolve the user sources to find the assignee and ccs.
	ccs, err := resolveUserSources(c, task, ccSrcs)
	if err != nil {
		return nil, nil, err
	}
	assignees, err := resolveUserSources(c, task, assigneeSrcs)
	if err != nil {
		return nil, nil, err
	}
	if len(assignees) == 0 {
		return nil, ccs, nil
	}
	return assignees[0], ccs, nil
}

func resolveUserSources(c context.Context, task *model.Task, sources []config.UserSource) (users []*monorail.UserRef, err error) {
	for _, source := range sources {
		if oncall := source.GetOncall(); oncall != nil {
			userRefs, err := findOncallers(c, task, oncall)
			if err != nil {
				return nil, err
			}
			users = append(users, userRefs...)
		} else if email := source.GetEmail(); email != "" {
			task.WriteLog(c, "Found Monorail User %s", email)
			users = append(users, &monorail.UserRef{DisplayName: email})
		}
	}
	return users, err
}

func getCachedShift(c context.Context, key string, shift *oncallShift) error {
	item, err := memcache.GetKey(c, key)
	if err != nil {
		return err
	}
	return json.Unmarshal(item.Value(), shift)
}

func setShiftCache(c context.Context, key string, shift *oncallShift) error {
	item := memcache.NewItem(c, key)
	bytes, err := json.Marshal(shift)
	if err != nil {
		return err
	}
	// TODO(crbug/967523), if RotaNG provides an RPC to return
	// the end timestamp of a shift, update this logic to maximise the cache
	// duration, based on the shift end timestamp.
	item.SetValue(bytes).SetExpiration(maxShiftCacheDuration)
	return memcache.Set(c, item)
}

func findShift(c context.Context, task *model.Task, rotation string) (*oncallShift, error) {
	var shift oncallShift
	u := fmt.Sprintf(
		"https://%s/legacy/%s.json", config.Get(c).RotangHostname,
		url.QueryEscape(rotation),
	)
	// ignore cache lookup failures, but log the error.
	switch err := getCachedShift(c, u, &shift); {
	case err != nil:
		if err != memcache.ErrCacheMiss {
			task.WriteLog(c, "Shift cache lookup failed: %s", err.Error())
		}
	default:
		return &shift, nil
	}

	// TODO(crbug/967523), use RotaNG PRPC APIs instead.
	req, err := http.NewRequest(http.MethodGet, u, nil)
	if err != nil {
		return nil, err
	}

	// Associate the request with the context, expecting that the context
	// is set with a timeout.
	req = req.WithContext(c)
	client := &http.Client{Transport: urlfetch.Get(c)}
	task.WriteLog(
		c, "Querying the current shift information for rotation %s", rotation,
	)
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	decoder := json.NewDecoder(resp.Body)
	if err := decoder.Decode(&shift); err != nil {
		return nil, err
	}
	if err := setShiftCache(c, u, &shift); err != nil {
		// ignore cache save failures, but log the error.
		msg := fmt.Sprintf("Failed to cache the shift; %s", err.Error())
		task.WriteLog(c, msg)
		logging.Errorf(c, msg)
	}

	return &shift, nil
}

func findOncallers(c context.Context, task *model.Task, oncall *config.Oncall) ([]*monorail.UserRef, error) {
	shift, err := findShift(c, task, oncall.Rotation)
	if err != nil {
		return nil, err
	}

	var oncallers []*monorail.UserRef
	switch oncall.GetPosition() {
	case config.Oncall_PRIMARY:
		if shift.Primary != "" {
			oncallers = append(oncallers, &monorail.UserRef{
				DisplayName: shift.Primary},
			)
			task.WriteLog(
				c, "Found primary oncaller %s of %s",
				shift.Primary, oncall.Rotation,
			)
		}
	case config.Oncall_SECONDARY:
		for _, secondary := range shift.Secondaries {
			oncallers = append(oncallers, &monorail.UserRef{
				DisplayName: secondary},
			)
			task.WriteLog(
				c, "Found secondary oncaller %s of %s",
				secondary, oncall.Rotation,
			)
		}
	}
	return oncallers, nil
}
