// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"encoding/base64"
	"fmt"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"

	"encoding/json"
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

		Convey("Comment gets marshaled correctly", func() {
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
				Suggestions: []*tricium.Data_Suggestion{
					{
						Replacements: []*tricium.Data_Replacement{
							{
								Replacement: "",
								Path:        "README.md",
								StartLine:   int32(startLine),
								EndLine:     int32(endLine),
								StartChar:   int32(startChar),
								EndChar:     int32(endChar),
							},
						},
						Description: "Suggestion 1",
					},
				},
			})

			marshaledRoco, _ := json.MarshalIndent(roco, "", "  ")
			So(string(marshaledRoco), ShouldEqual, `{
  "robot_id": "Hello",
  "robot_run_id": "1234567",
  "url": "https://app.example.com/run/1234567",
  "properties": {
    "tricium_comment_uuid": "7ae6f43d-22e9-4350-ace4-1fee9014509a"
  },
  "fix_suggestions": [
    {
      "description": "Suggestion 1",
      "replacements": [
        {
          "path": "README.md",
          "replacement": "",
          "range": {
            "start_line": 10,
            "start_character": 2,
            "end_line": 20,
            "end_character": 18
          }
        }
      ]
    }
  ],
  "path": "README.md",
  "line": 10,
  "range": {
    "start_line": 10,
    "start_character": 2,
    "end_line": 20,
    "end_character": 18
  },
  "message": "Message"
}`)

		})
	})
}

func TestGetChangedLinesFromPatch(t *testing.T) {
	Convey("Extract changed lines", t, func() {
		patch := `commit 29943c31812f582bd174740d9f9414a99632c687 (HEAD -> master)
Author: Foo Bar <foobar@google.com>
Date:   Tue Jun 26 17:58:25 2018 -0700

    new commit

diff --git a/test.cpp b/test.cpp
new file mode 100644
index 0000000..382e810
--- /dev/null
+++ b/test.cpp
@@ -0,0 +1,6 @@
+#include <iostream>
+
+int main(int argc, char **arg) {
+  std::cout << "Hello, World!";
+  return 0;
+}
diff --git a/test2.cpp b/test2.cpp
new file mode 100644
index 0000000..ab8dadd
--- a/test2.cpp
+++ b/test2.cpp
@@ -1,7 +1,7 @@
 #include <iostream>

-int main() {
+int main(int argc, char **arg) {
+
   std::cout << "Hello, World!";
-  return 0;
 }
`

		base64Patch := base64.StdEncoding.EncodeToString([]byte(patch))
		expectedLines := ChangedLinesInfo{}
		expectedLines["test.cpp"] = []int{1, 2, 3, 4, 5, 6}
		expectedLines["test2.cpp"] = []int{2, 3}
		actualLines, err := getChangedLinesFromPatch(base64Patch)
		So(err, ShouldBeNil)
		So(actualLines, ShouldResemble, expectedLines)
	})

	Convey("Extract changed lines", t, func() {
		patch := `commit 29943c31812f582bd174740d9f9414a99632c687 (HEAD -> master)
Author: Foo Bar <foobar@google.com>
Date:   Tue Jun 26 17:58:25 2018 -0700

		delete commit

diff --git a/test.cpp b/test.cpp
deleted file mode 100644
index 382e810..0000000
--- a/test.cpp
+++ /dev/null
@@ -1,6 +0,0 @@
-#include <iostream>
-
-int main(int argc, char **arg) {
-  std::cout << "Hello, World!";
-  return 0;
-}
`

		base64Patch := base64.StdEncoding.EncodeToString([]byte(patch))
		expectedLines := ChangedLinesInfo{}
		actualLines, err := getChangedLinesFromPatch(base64Patch)
		So(err, ShouldBeNil)
		So(actualLines, ShouldResemble, expectedLines)
	})
}
