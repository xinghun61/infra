// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package backend

import (
	"context"
	"encoding/json"
	"fmt"
	"net/url"
	"testing"

	"github.com/golang/protobuf/proto"
	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/gae/service/urlfetch"
	"go.chromium.org/luci/common/clock/testclock"

	"infra/appengine/arquebus/app/config"
	"infra/appengine/arquebus/app/util"
	"infra/monorailv2/api/api_proto"
)

var (
	shifts = []*oncallShift{
		{
			Primary:     "r1pri@@test.com",
			Secondaries: []string{"r1sec1@test.com", "r1sec2@test.com"},
			Started:     testclock.TestRecentTimeUTC.Unix(),
		},
		{
			Primary:     "r2pri@@test.com",
			Secondaries: []string{"r2sec1@test.com", "r2sec2@test.com"},
			Started:     testclock.TestRecentTimeUTC.Unix(),
		},
		{
			Primary:     "r2pri@@test.com",
			Secondaries: []string{"r3sec1@test.com", "r3sec2@test.com"},
			Started:     testclock.TestRecentTimeUTC.Unix(),
		},
	}
)

func setShiftResponse(c context.Context, rotation string, shift *oncallShift) {
	data, _ := json.Marshal(shift)
	url := fmt.Sprintf(
		"https://%s/legacy/%s.json", config.Get(c).RotangHostname,
		url.QueryEscape(rotation),
	)
	transport := urlfetch.Get(c).(*util.MockHTTPTransport)
	transport.Responses[url] = string(data)
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

func createRawUserSources(sources ...*config.UserSource) [][]byte {
	raw := make([][]byte, len(sources))
	for i, source := range sources {
		raw[i], _ = proto.Marshal(source)
	}
	return raw
}

func TestAssignee(t *testing.T) {
	t.Parallel()
	assignerID := "test-assigner"

	Convey("findAssigneeAndCCs", t, func() {
		c := createTestContextWithTQ()
		c = config.SetConfig(c, &config.Config{
			AccessGroup:      "engineers",
			MonorailHostname: "example.com",
			RotangHostname:   "example.net",
		})

		// create sample assigner and tasks.
		assigner := createAssigner(c, assignerID)
		tasks := triggerScheduleTaskHandler(c, assignerID)
		So(tasks, ShouldNotBeNil)
		task := tasks[0]

		Convey("works with UserSource_Email", func() {
			Convey("for assignees", func() {
				assigner.AssigneesRaw = createRawUserSources(
					emailUserSource("oncall1@test.com"),
				)
				assigner.CCsRaw = createRawUserSources()
				assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
				So(err, ShouldBeNil)
				So(assignee, ShouldResemble, monorailUser("oncall1@test.com"))
				So(ccs, ShouldBeNil)
			})

			Convey("for ccs", func() {
				assigner.AssigneesRaw = createRawUserSources()
				assigner.CCsRaw = createRawUserSources(
					emailUserSource("secondary1@test.com"),
					emailUserSource("secondary2@test.com"),
				)
				assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
				So(err, ShouldBeNil)
				So(assignee, ShouldBeNil)
				So(ccs[0], ShouldResemble, monorailUser("secondary1@test.com"))
				So(ccs[1], ShouldResemble, monorailUser("secondary2@test.com"))
			})
		})

		Convey("works with UserSource_Oncall", func() {
			setShiftResponse(c, "rotation1", shifts[0])

			Convey("for assignees", func() {
				assigner.AssigneesRaw = createRawUserSources(
					oncallUserSource("rotation1", config.Oncall_PRIMARY),
				)
				assigner.CCsRaw = createRawUserSources()
				assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
				So(err, ShouldBeNil)
				So(assignee, ShouldResemble, monorailUser(shifts[0].Primary))
				So(ccs, ShouldBeNil)
			})

			Convey("for ccs", func() {
				assigner.AssigneesRaw = createRawUserSources()
				assigner.CCsRaw = createRawUserSources(
					oncallUserSource("rotation1", config.Oncall_SECONDARY),
				)
				assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
				So(err, ShouldBeNil)
				So(assignee, ShouldBeNil)
				So(
					ccs[0], ShouldResemble,
					monorailUser(shifts[0].Secondaries[0]),
				)
				So(
					ccs[1], ShouldResemble,
					monorailUser(shifts[0].Secondaries[1]),
				)
			})
		})

		Convey("pick the first available one as the assignee", func() {
			Convey("with multiple UserSource_Emails", func() {
				assigner.AssigneesRaw = createRawUserSources(
					emailUserSource("oncall1@test.com"),
					emailUserSource("oncall2@test.com"),
					emailUserSource("oncall3@test.com"),
				)
				assigner.CCsRaw = createRawUserSources()

				// UserRef with email is considered always available.
				assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
				So(err, ShouldBeNil)
				So(assignee, ShouldResemble, monorailUser("oncall1@test.com"))
				So(ccs, ShouldBeNil)
			})

			Convey("with multiple UserSource_Oncalls", func() {
				setShiftResponse(c, "rotation1", shifts[0])
				setShiftResponse(c, "rotation2", shifts[1])
				setShiftResponse(c, "rotation3", shifts[2])
				assigner.AssigneesRaw = createRawUserSources(
					oncallUserSource("rotation1", config.Oncall_PRIMARY),
					oncallUserSource("rotation2", config.Oncall_PRIMARY),
					oncallUserSource("rotation3", config.Oncall_PRIMARY),
				)
				assigner.CCsRaw = createRawUserSources()
				assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
				So(err, ShouldBeNil)
				// it should be the primary of rotation1
				So(assignee, ShouldResemble, monorailUser(shifts[0].Primary))
				So(ccs, ShouldBeNil)
			})

			Convey("with a mix of available and unavailable shifts", func() {
				setShiftResponse(c, "rotation1", &oncallShift{})
				setShiftResponse(c, "rotation2", shifts[1])
				setShiftResponse(c, "rotation3", shifts[2])
				assigner.AssigneesRaw = createRawUserSources(
					oncallUserSource("rotation1", config.Oncall_PRIMARY),
					oncallUserSource("rotation2", config.Oncall_PRIMARY),
					oncallUserSource("rotation3", config.Oncall_PRIMARY),
				)
				assigner.CCsRaw = createRawUserSources()
				assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
				So(err, ShouldBeNil)
				// it should be the primary of rotation2, as rotation1 is
				// not available.
				So(assignee, ShouldResemble, monorailUser(shifts[1].Primary))
				So(ccs, ShouldBeNil)
			})
		})

		Convey("CCs includes users from all the listed sources", func() {
			setShiftResponse(c, "rotation1", shifts[0])
			setShiftResponse(c, "rotation2", shifts[1])
			assigner.AssigneesRaw = createRawUserSources()
			assigner.CCsRaw = createRawUserSources(
				oncallUserSource("rotation1", config.Oncall_SECONDARY),
				oncallUserSource("rotation2", config.Oncall_SECONDARY),
				emailUserSource("oncall1@test.com"),
			)

			assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
			So(err, ShouldBeNil)
			So(assignee, ShouldBeNil)
			// ccs should be rotation1.secondaries + rotation2.secondaries +
			// oncall1@test.com
			var expected []*monorail.UserRef
			for _, user := range shifts[0].Secondaries {
				expected = append(expected, monorailUser(user))
			}
			for _, user := range shifts[1].Secondaries {
				expected = append(expected, monorailUser(user))
			}
			expected = append(expected, monorailUser("oncall1@test.com"))
			So(ccs, ShouldResemble, expected)
		})
	})
}
