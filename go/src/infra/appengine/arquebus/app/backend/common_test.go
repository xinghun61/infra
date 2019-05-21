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
	"go.chromium.org/luci/common/clock/testclock"

	"google.golang.org/grpc"

	"infra/appengine/arquebus/app/backend/model"
	"infra/appengine/arquebus/app/config"
	"infra/appengine/arquebus/app/util"
	"infra/monorailv2/api/api_proto"
)

var (
	// sample rotation shifts.
	mockShifts = map[string]*oncallShift{
		"rotation1": {
			Primary:     "r1pri@@test.com",
			Secondaries: []string{"r1sec1@test.com", "r1sec2@test.com"},
			Started:     testclock.TestRecentTimeUTC.Unix(),
		},
		"rotation2": {
			Primary:     "r2pri@@test.com",
			Secondaries: []string{"r2sec1@test.com", "r2sec2@test.com"},
			Started:     testclock.TestRecentTimeUTC.Unix(),
		},
		"rotation3": {
			Primary:     "r3pri@@test.com",
			Secondaries: []string{"r3sec1@test.com", "r3sec2@test.com"},
			Started:     testclock.TestRecentTimeUTC.Unix(),
		},
	}
)

// createTestContextWithTQ creates a test context with testable a TaskQueue.
func createTestContextWithTQ() context.Context {
	// create a context with config first.
	c := util.CreateTestContext()
	c = config.SetConfig(c, &config.Config{
		AccessGroup:      "engineers",
		MonorailHostname: "example.org",
		RotangHostname:   "example.net",

		Assigners: []*config.Assigner{},
	})

	// install TQ handlers
	d := &tq.Dispatcher{}
	registerTaskHandlers(d)
	tq := tqtesting.GetTestable(c, d)
	tq.CreateQueues()
	c = setDispatcher(c, d)

	// set sample rotation shifts
	for rotation, shift := range mockShifts {
		setShiftResponse(c, rotation, shift)
	}

	// install a mocked Monorail client with an empty response
	return mockListIssues(c)
}

// createAssigner creates a sample Assigner entity.
func createAssigner(c context.Context, id string) *model.Assigner {
	var cfg config.Assigner
	So(proto.UnmarshalText(util.SampleValidAssignerCfg, &cfg), ShouldBeNil)
	cfg.Id = id

	So(UpdateAssigners(c, []*config.Assigner{&cfg}, "rev-1"), ShouldBeNil)
	datastore.GetTestable(c).CatchupIndexes()
	assigner, err := GetAssigner(c, id)
	So(assigner.ID, ShouldEqual, id)
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

// ----------------------------------
// test Monorail Issue Client

type testIssueClientStorage struct {
	issuesToList   []*monorail.Issue
	issuesToUpdate map[string]*monorail.UpdateIssueRequest
}

type testIssueClient struct {
	monorail.IssuesClient
	storage *testIssueClientStorage
}

func newTestIssueClient(issues ...*monorail.Issue) testIssueClient {
	return testIssueClient{
		storage: &testIssueClientStorage{
			issuesToList:   issues,
			issuesToUpdate: map[string]*monorail.UpdateIssueRequest{},
		},
	}
}

func (client testIssueClient) UpdateIssue(c context.Context, in *monorail.UpdateIssueRequest, opts ...grpc.CallOption) (*monorail.IssueResponse, error) {
	client.storage.issuesToUpdate[genIssueKey(
		in.IssueRef.ProjectName, in.IssueRef.LocalId,
	)] = in
	return &monorail.IssueResponse{}, nil
}

func (client testIssueClient) ListIssues(c context.Context, in *monorail.ListIssuesRequest, opts ...grpc.CallOption) (*monorail.ListIssuesResponse, error) {
	return &monorail.ListIssuesResponse{
		Issues: client.storage.issuesToList,
	}, nil
}

func mockListIssues(c context.Context, issues ...*monorail.Issue) context.Context {
	return setMonorailClient(c, newTestIssueClient(issues...))
}

func getIssueUpdateRequests(c context.Context, projectName string, localID uint32) *monorail.UpdateIssueRequest {
	issuesToUpdate := getMonorailClient(c).(testIssueClient).storage.issuesToUpdate
	return issuesToUpdate[genIssueKey(projectName, localID)]
}

func genIssueKey(projectName string, localID uint32) string {
	return fmt.Sprintf("%s:%d", projectName, localID)
}
