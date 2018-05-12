// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"fmt"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/triciumtest"
)

func TestComposeChangesQueryURL(t *testing.T) {
	Convey("Test Environment", t, func() {
		host := "chromium-review.googlesource.com"
		project := "playground/gerrit-tricium"
		formattedProject := "playground%2Fgerrit-tricium"
		const form = "2006-01-02 15:04:05.000000000"
		time, err := time.Parse(form, "2016-10-01 10:00:05.640000000")
		So(err, ShouldBeNil)
		formattedTime := "2016-10-01+10%3A00%3A05.640000000"
		Convey("First page of poll", func() {
			So(composeChangesQueryURL(host, project, time, 0), ShouldEqual,
				fmt.Sprintf("https://%s/a/changes/?o=CURRENT_REVISION&o=CURRENT_FILES&o=DETAILED_ACCOUNTS&q=project%%3A%s+after%%3A%%22%s%%22&start=0",
					host, formattedProject, formattedTime))
		})
	})
}

func TestCreateRobotComment(t *testing.T) {
	Convey("Test Environment", t, func() {

		ctx := triciumtest.Context()
		runID := int64(1234567)
		uuid := "7ae6f43d-22e9-4350-ace4-1fee9014509a"

		Convey("Basic comment fields include UUID and URL", func() {
			roco := createRobotComment(ctx, runID, tricium.Data_Comment{
				Id:       uuid,
				Path:     "README.md",
				Message:  "Message",
				Category: "Hello",
			})
			So(roco, ShouldResemble, &robotCommentInput{
				Message:    "Message",
				RobotID:    "Hello",
				RobotRunID: "1234567",
				URL:        "https://app.example.com/run/1234567",
				Path:       "README.md",
				Properties: map[string]string{
					"tricium_comment_uuid": "7ae6f43d-22e9-4350-ace4-1fee9014509a",
				},
			})
		})

		Convey("File comment has no position info", func() {
			roco := createRobotComment(ctx, runID, tricium.Data_Comment{
				Id:       uuid,
				Path:     "README.md",
				Message:  "Message",
				Category: "Hello",
			})
			So(roco.Line, ShouldEqual, 0)
			So(roco.Range, ShouldBeNil)
		})

		Convey("Line comment has no range info", func() {
			line := int32(10)
			roco := createRobotComment(ctx, runID, tricium.Data_Comment{
				Id:        uuid,
				Path:      "README.md",
				Message:   "Message",
				Category:  "Hello",
				StartLine: line,
			})
			So(roco.Line, ShouldEqual, line)
			So(roco.Range, ShouldBeNil)
		})

		Convey("Range comment has range", func() {
			startLine := 10
			endLine := 20
			startChar := 2
			endChar := 18
			roco := createRobotComment(ctx, runID, tricium.Data_Comment{
				Id:        uuid,
				Path:      "README.md",
				Message:   "Message",
				Category:  "Hello",
				StartLine: int32(startLine),
				EndLine:   int32(endLine),
				StartChar: int32(startChar),
				EndChar:   int32(endChar),
			})
			So(roco.Line, ShouldEqual, startLine)
			So(roco.Range, ShouldResemble, &commentRange{
				StartLine:      startLine,
				EndLine:        endLine,
				StartCharacter: startChar,
				EndCharacter:   endChar,
			})
		})

	})
}
