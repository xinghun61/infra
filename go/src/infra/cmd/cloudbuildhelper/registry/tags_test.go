// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package registry

import (
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

func TestValidateTag(t *testing.T) {
	t.Parallel()

	Convey("Works", t, func() {
		So(ValidateTag("good-TAG-.123_456"), ShouldBeNil)
		So(ValidateTag(strings.Repeat("a", 128)), ShouldBeNil)

		So(ValidateTag(""), ShouldErrLike, "can't be empty")
		So(ValidateTag("notascii\x02"), ShouldErrLike, "should match")
		So(ValidateTag(":forbiddenchar"), ShouldErrLike, "should match")
		So(ValidateTag(".noperiodinfront"), ShouldErrLike, "can't start with '.'")
		So(ValidateTag("-nodashinfront"), ShouldErrLike, "can't start with '-'")
		So(ValidateTag(strings.Repeat("a", 129)), ShouldErrLike, "can't have more than 128 characters")
	})
}
