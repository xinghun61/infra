// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package backend

import (
	"context"
	"encoding/json"
	"fmt"
	"net/url"

	"github.com/golang/protobuf/proto"
	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/urlfetch"
	"go.chromium.org/luci/appengine/tq"
	"go.chromium.org/luci/appengine/tq/tqtesting"

	"infra/appengine/arquebus/app/backend/model"
	"infra/appengine/arquebus/app/config"
	"infra/appengine/arquebus/app/util"
	"infra/monorailv2/api/api_proto"
)

// createTestContextWithTQ creates a test context with testable a TaskQueue.
func createTestContextWithTQ() context.Context {
	d := &tq.Dispatcher{}
	registerTaskHandlers(d)

	c := util.CreateTestContext()
	tq := tqtesting.GetTestable(c, d)
	tq.CreateQueues()
	return setDispatcher(c, d)
}

// createAssigner creates a sample Assigner entity.
func createAssigner(c context.Context, id string) *model.Assigner {
	var cfg config.Assigner
	So(proto.UnmarshalText(util.SampleValidAssignerCfg, &cfg), ShouldBeNil)
	cfg.Id = id

	So(UpdateAssigners(c, []*config.Assigner{&cfg}, "revision-1"), ShouldBeNil)
	datastore.GetTestable(c).CatchupIndexes()
	assigner, err := GetAssigner(c, cfg.Id)
	So(assigner.ID, ShouldEqual, cfg.Id)
	So(err, ShouldBeNil)
	So(assigner, ShouldNotBeNil)

	return assigner
}

func triggerScheduleTaskHandler(c context.Context, id string) []*model.Task {
	req := &ScheduleAssignerTask{AssignerId: id}
	So(scheduleAssignerTaskHandler(c, req), ShouldBeNil)
	_, tasks, err := GetAssignerWithTasks(c, id, 99999, true)
	So(err, ShouldBeNil)
	return tasks
}

func triggerRunTaskHandler(c context.Context, assignerID string, taskID int64) *model.Task {
	req := &RunAssignerTask{AssignerId: assignerID, TaskId: taskID}
	So(runAssignerTaskHandler(c, req), ShouldBeNil)
	assigner, task, err := GetTask(c, assignerID, taskID)
	So(assigner.ID, ShouldEqual, assignerID)
	So(err, ShouldBeNil)
	So(task, ShouldNotBeNil)
	return task
}

func setShiftResponse(c context.Context, rotation string, shift *oncallShift) {
	data, _ := json.Marshal(shift)
	url := fmt.Sprintf(
		"https://%s/legacy/%s.json", config.Get(c).RotangHostname,
		url.QueryEscape(rotation),
	)
	transport := urlfetch.Get(c).(*util.MockHTTPTransport)
	transport.Responses[url] = string(data)
}

func createRawUserSources(sources ...*config.UserSource) [][]byte {
	raw := make([][]byte, len(sources))
	for i, source := range sources {
		raw[i], _ = proto.Marshal(source)
	}
	return raw
}

func monorailUser(email string) *monorail.UserRef {
	return &monorail.UserRef{DisplayName: email}
}

func emailUserSource(email string) *config.UserSource {
	return &config.UserSource{From: &config.UserSource_Email{Email: email}}
}

func oncallUserSource(rotation string, position config.Oncall_Position) *config.UserSource {
	return &config.UserSource{
		From: &config.UserSource_Oncall{Oncall: &config.Oncall{
			Rotation: rotation, Position: position,
		}},
	}
}
