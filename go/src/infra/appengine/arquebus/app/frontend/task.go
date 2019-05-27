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
	"net/http"
	"strconv"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"infra/appengine/arquebus/app/backend"
	"infra/appengine/arquebus/app/util"
)

func taskPage(c *router.Context) {
	// check for invalid requests.
	assignerID := c.Params.ByName("AssignerID")
	taskID, err := strconv.ParseInt(c.Params.ByName("TaskID"), 10, 64)
	if assignerID == "" || err != nil {
		util.ErrStatus(c, http.StatusNotFound, "Not found")
		return
	}

	assigner, task, err := backend.GetTask(c.Context, assignerID, taskID)
	if err == datastore.ErrNoSuchEntity {
		e := http.StatusNotFound
		util.ErrStatus(c, e, "Task(%s,%d) was not found", assignerID, taskID)
		return
	} else if err != nil {
		logging.Errorf(c.Context, "%s", err)
		e := http.StatusInternalServerError
		util.ErrStatus(c, e, "Failed to load Task(%s,%d)", assignerID, taskID)
		return
	}

	// render
	templates.MustRender(
		c.Context,
		c.Writer,
		"pages/task.html",
		map[string]interface{}{
			"Assigner": assigner,
			"Task":     task,
		},
	)
}
