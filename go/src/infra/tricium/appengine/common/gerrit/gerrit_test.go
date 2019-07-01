// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"encoding/base64"
	"testing"

	"github.com/golang/protobuf/jsonpb"
	. "github.com/smartystreets/goconvey/convey"

	"encoding/json"
	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
	"infra/tricium/appengine/common/triciumtest"
)

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
			So(roco.Line, ShouldEqual, endLine)
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
  "line": 20,
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
	Convey("Extract changed lines with added and modified files", t, func() {
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

	Convey("Extract changed lines with a deleted file", t, func() {
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

func TestCommentIsInChangedLines(t *testing.T) {
	Convey("Test Environment", t, func() {

		ctx := triciumtest.Context()

		Convey("Single line comment in changed lines", func() {
			json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
				Path:      "dir/file.txt",
				StartLine: 5,
				EndLine:   5,
				StartChar: 0,
				EndChar:   10,
			})
			So(err, ShouldBeNil)
			lines := map[string][]int{"dir/file.txt": {2, 5, 10}}
			comment := &track.Comment{Comment: []byte(json)}
			So(CommentIsInChangedLines(ctx, comment, lines), ShouldBeTrue)
		})

		Convey("Single line comment outside of changed lines", func() {
			json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
				Path:      "dir/file.txt",
				StartLine: 4,
				EndLine:   4,
				StartChar: 0,
				EndChar:   10,
			})
			So(err, ShouldBeNil)
			lines := map[string][]int{"dir/file.txt": {2, 5, 10}}
			comment := &track.Comment{Comment: []byte(json)}
			So(CommentIsInChangedLines(ctx, comment, lines), ShouldBeFalse)
		})

		Convey("Single line comment outside of changed files", func() {
			json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
				Path:      "DELETED.txt",
				StartLine: 5,
				EndLine:   5,
				StartChar: 5,
				EndChar:   10,
			})
			So(err, ShouldBeNil)
			lines := map[string][]int{"dir/file.txt": {2, 5, 10}}
			comment := &track.Comment{Comment: []byte(json)}
			So(CommentIsInChangedLines(ctx, comment, lines), ShouldBeFalse)
		})

		Convey("Comment with line range that overlaps changed line", func() {
			json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
				Path:      "dir/file.txt",
				StartLine: 3,
				EndLine:   8,
			})
			So(err, ShouldBeNil)
			lines := map[string][]int{"dir/file.txt": {2, 5, 10}}
			comment := &track.Comment{Comment: []byte(json)}
			So(CommentIsInChangedLines(ctx, comment, lines), ShouldBeTrue)
		})

		Convey("Comment with end char == 0, implying end line is not included", func() {
			json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
				Path:      "dir/file.txt",
				StartLine: 6,
				EndLine:   10,
			})
			So(err, ShouldBeNil)
			lines := map[string][]int{"dir/file.txt": {2, 5, 10}}
			comment := &track.Comment{Comment: []byte(json)}
			So(CommentIsInChangedLines(ctx, comment, lines), ShouldBeFalse)
		})

		Convey("File-level comments are included", func() {
			json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
				Path: "dir/file.txt",
			})
			So(err, ShouldBeNil)
			lines := map[string][]int{"dir/file.txt": {2, 5, 10}}
			comment := &track.Comment{Comment: []byte(json)}
			So(CommentIsInChangedLines(ctx, comment, lines), ShouldBeTrue)
		})

		Convey("Line comments on changed lines are included", func() {
			json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
				Path:      "dir/file.txt",
				StartLine: 2,
			})
			So(err, ShouldBeNil)
			lines := map[string][]int{"dir/file.txt": {2, 5, 10}}
			comment := &track.Comment{Comment: []byte(json)}
			So(CommentIsInChangedLines(ctx, comment, lines), ShouldBeTrue)
		})
	})
}

func TestIsInChangedLines(t *testing.T) {
	Convey("Overlapping cases", t, func() {
		So(isInChangedLines(1, 3, []int{2, 3, 4}), ShouldBeTrue)
		So(isInChangedLines(4, 5, []int{2, 3, 4}), ShouldBeTrue)
		// The end line is inclusive.
		So(isInChangedLines(1, 2, []int{2, 3, 4}), ShouldBeTrue)
		So(isInChangedLines(3, 3, []int{2, 3, 4}), ShouldBeTrue)
	})

	Convey("Non-overlapping cases", t, func() {
		So(isInChangedLines(5, 6, []int{2, 3, 4}), ShouldBeFalse)
		So(isInChangedLines(1, 1, []int{2, 3, 4}), ShouldBeFalse)
	})

	Convey("Invalid range cases", t, func() {
		So(isInChangedLines(2, 0, []int{2, 3, 4}), ShouldBeFalse)
	})
}

func TestAdjustCommitMessage(t *testing.T) {
	Convey("adjustCommitMessageComment changes positions in comment and replacements", t, func() {
		comment := &tricium.Data_Comment{
			Category:  "Foo",
			Message:   "Bar",
			StartLine: 5,
			EndLine:   5,
			StartChar: 2,
			EndChar:   4,
			Suggestions: []*tricium.Data_Suggestion{
				{
					Replacements: []*tricium.Data_Replacement{
						{
							StartLine: 5,
							EndLine:   5,
							StartChar: 2,
							EndChar:   4,
						},
					},
				},
			},
		}
		adjustCommitMessageComment(comment)
		So(comment, ShouldResemble, &tricium.Data_Comment{
			Category:  "Foo",
			Message:   "Bar",
			StartLine: 5 + numHeaderLines,
			EndLine:   5 + numHeaderLines,
			StartChar: 2,
			EndChar:   4,
			Suggestions: []*tricium.Data_Suggestion{
				{
					Replacements: []*tricium.Data_Replacement{
						{
							StartLine: 5 + numHeaderLines,
							EndLine:   5 + numHeaderLines,
							StartChar: 2,
							EndChar:   4,
						},
					},
				},
			},
		})
	})

	Convey("File level comments don't have line numbers adjusted", t, func() {
		comment := &tricium.Data_Comment{
			Category: "Foo",
			Message:  "Bar",
		}
		adjustCommitMessageComment(comment)
		So(comment, ShouldResemble, &tricium.Data_Comment{
			Category: "Foo",
			Message:  "Bar",
		})
	})
}
