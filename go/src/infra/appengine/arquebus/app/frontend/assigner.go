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

package frontend

import (
	"fmt"
	"net/http"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"infra/appengine/arquebus/app/backend"
	"infra/appengine/arquebus/app/util"
)

const (
	// TaskFetchLimit is the maximum number of Task entities to to be fetched.
	//
	// TODO(crbug/849469): Make this limit adjustable when paging option
	// is supported.
	taskFetchLimit = 20

	chromeInternalRepoHostName = "chrome-internal.googlesource.com"
)

func isValidRequest(c *router.Context, assignerID *string) bool {
	// check for invalid requests.
	*assignerID = c.Params.ByName("AssignerID")
	if *assignerID == "" {
		util.ErrStatus(c, http.StatusNotFound, "Not found")
		return false
	}
	return true
}

func assignerPage(c *router.Context) {
	var assignerID string
	if !isValidRequest(c, &assignerID) {
		return
	}

	assigner, tasks, err := backend.GetAssignerWithTasks(
		// TODO(crbug/849469): add a param for alternating includeNoopSuccess
		c.Context, assignerID, taskFetchLimit, true,
	)
	if err == datastore.ErrNoSuchEntity {
		e := http.StatusNotFound
		util.ErrStatus(c, e, "Assigner(%s) was not found", assignerID)
		return
	} else if err != nil {
		logging.Errorf(c.Context, "%s", err)
		e := http.StatusInternalServerError
		util.ErrStatus(c, e, "Failed to load Assigner (%s)", assignerID)
		return
	}
	if err != nil {
		panic(err)
	}
	templates.MustRender(
		c.Context,
		c.Writer,
		"pages/assigner.html",
		map[string]interface{}{
			"Assigner": assigner,
			"Tasks":    tasks,
			"ConfigLink": fmt.Sprintf(
				"https://%s/infradata/config/+/%s/configs/%s/config.cfg",
				chromeInternalRepoHostName, assigner.ConfigRevision,
				info.AppID(c.Context),
			),
		},
	)
}
