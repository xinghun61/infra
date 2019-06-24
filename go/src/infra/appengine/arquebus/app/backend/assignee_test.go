// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package backend

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"infra/appengine/arquebus/app/config"
	"infra/appengine/rotang/proto/rotangapi"
	"infra/monorailv2/api/api_proto"
)

func TestAssignee(t *testing.T) {
	t.Parallel()
	assignerID := "test-assigner"

	Convey("findAssigneeAndCCs", t, func() {
		c := createTestContextWithTQ()

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
			Convey("for assignees via the legacy interface", func() {
				assigner.AssigneesRaw = createRawUserSources(
					oncallUserSource("rotation1", config.Oncall_PRIMARY),
				)
				assigner.CCsRaw = createRawUserSources()
				assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
				So(err, ShouldBeNil)
				So(
					assignee, ShouldResemble,
					monorailUser(mockLegacyShifts["rotation1"].Primary),
				)
				So(ccs, ShouldBeNil)
			})

			Convey("for ccs via the legacy interface", func() {
				assigner.AssigneesRaw = createRawUserSources()
				assigner.CCsRaw = createRawUserSources(
					oncallUserSource("rotation1", config.Oncall_SECONDARY),
				)
				assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
				So(err, ShouldBeNil)
				So(assignee, ShouldBeNil)
				So(
					ccs[0], ShouldResemble,
					monorailUser(mockLegacyShifts["rotation1"].Secondaries[0]),
				)
				So(
					ccs[1], ShouldResemble,
					monorailUser(mockLegacyShifts["rotation1"].Secondaries[1]),
				)
			})

			Convey("for assignees via the prpc interface", func() {
				assigner.AssigneesRaw = createRawUserSources(
					oncallUserSource("Rotation 1", config.Oncall_PRIMARY),
				)
				assigner.CCsRaw = createRawUserSources()
				assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
				So(err, ShouldBeNil)
				So(
					assignee, ShouldResemble,
					monorailUser(mockOncallShifts["Rotation 1"].Oncallers[0].Email),
				)
				So(ccs, ShouldBeNil)
			})

			Convey("for ccs via the prpc interface", func() {
				assigner.AssigneesRaw = createRawUserSources()
				assigner.CCsRaw = createRawUserSources(
					oncallUserSource("Rotation 1", config.Oncall_SECONDARY),
				)
				assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
				So(err, ShouldBeNil)
				So(assignee, ShouldBeNil)
				So(
					ccs[0], ShouldResemble,
					monorailUser(mockOncallShifts["Rotation 1"].Oncallers[1].Email),
				)
				So(
					ccs[1], ShouldResemble,
					monorailUser(mockOncallShifts["Rotation 1"].Oncallers[2].Email),
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

			Convey("with multiple UserSource_Oncalls via the legacy interface", func() {
				assigner.AssigneesRaw = createRawUserSources(
					oncallUserSource("rotation1", config.Oncall_PRIMARY),
					oncallUserSource("rotation2", config.Oncall_PRIMARY),
					oncallUserSource("rotation3", config.Oncall_PRIMARY),
				)
				assigner.CCsRaw = createRawUserSources()
				assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
				So(err, ShouldBeNil)
				// it should be the primary of rotation1
				So(
					assignee, ShouldResemble,
					monorailUser(mockLegacyShifts["rotation1"].Primary),
				)
				So(ccs, ShouldBeNil)
			})

			Convey("with a mix of available and unavailable shifts via the legacy interface", func() {
				setShiftResponse(c, "rotation1", &oncallShift{})
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
				So(
					assignee, ShouldResemble,
					monorailUser(mockLegacyShifts["rotation2"].Primary),
				)
				So(ccs, ShouldBeNil)
			})

			Convey("with multiple UserSource_Oncalls via the pRPC interface", func() {
				assigner.AssigneesRaw = createRawUserSources(
					oncallUserSource("Rotation 1", config.Oncall_PRIMARY),
					oncallUserSource("Rotation 2", config.Oncall_PRIMARY),
					oncallUserSource("Rotation 3", config.Oncall_PRIMARY),
				)
				assigner.CCsRaw = createRawUserSources()
				assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
				So(err, ShouldBeNil)
				// it should be the primary of rotation1
				So(
					assignee, ShouldResemble,
					monorailUser(mockOncallShifts["Rotation 1"].Oncallers[0].Email),
				)
				So(ccs, ShouldBeNil)
			})

			Convey("with a mix of available and unavailable shifts via the pRPC interface", func() {
				mockOncall(c, "Rotation 1", &rotangapi.ShiftEntry{})
				assigner.AssigneesRaw = createRawUserSources(
					oncallUserSource("Rotation 1", config.Oncall_PRIMARY),
					oncallUserSource("Rotation 2", config.Oncall_PRIMARY),
					oncallUserSource("Rotation 3", config.Oncall_PRIMARY),
				)
				assigner.CCsRaw = createRawUserSources()
				assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
				So(err, ShouldBeNil)
				// it should be the primary of rotation2, as rotation1 is
				// not available.
				So(
					assignee, ShouldResemble,
					monorailUser(mockOncallShifts["Rotation 2"].Oncallers[0].Email),
				)
				So(ccs, ShouldBeNil)
			})
		})

		Convey("CCs includes users from all the listed sources with the legacy interface", func() {
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
			for _, user := range mockLegacyShifts["rotation1"].Secondaries {
				expected = append(expected, monorailUser(user))
			}
			for _, user := range mockLegacyShifts["rotation2"].Secondaries {
				expected = append(expected, monorailUser(user))
			}
			expected = append(expected, monorailUser("oncall1@test.com"))
			So(ccs, ShouldResemble, expected)
		})

		Convey("CCs includes users from all the listed sources with the prpc interface", func() {
			assigner.AssigneesRaw = createRawUserSources()
			assigner.CCsRaw = createRawUserSources(
				oncallUserSource("Rotation 1", config.Oncall_SECONDARY),
				oncallUserSource("Rotation 2", config.Oncall_SECONDARY),
				emailUserSource("oncall1@test.com"),
			)

			assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
			So(err, ShouldBeNil)
			So(assignee, ShouldBeNil)
			// ccs should be the secondaries of Rotation 1 and 2
			// and oncall1@test.com.
			var expected []*monorail.UserRef
			for _, user := range mockOncallShifts["Rotation 1"].Oncallers[1:] {
				expected = append(expected, monorailUser(user.Email))
			}
			for _, user := range mockOncallShifts["Rotation 2"].Oncallers[1:] {
				expected = append(expected, monorailUser(user.Email))
			}
			expected = append(expected, monorailUser("oncall1@test.com"))
			So(ccs, ShouldResemble, expected)
		})
	})
}
