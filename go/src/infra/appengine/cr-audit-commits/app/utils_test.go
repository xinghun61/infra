// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestUtils(t *testing.T) {
	t.Parallel()
	Convey("Ensure token (un)escaping works as intended", t, func() {
		for _, tc := range []string{
			"n\nn",
			"n\\nn",
			"n\\\nn",
			"n\\\\nn",
			"n\\\\\nn",
			"n\\\\\\nn",
			"n\nn",
			"n\n\n",
			"n\n\\n",
			"n\n\\\n",
			"n\n\\\\n",
			"n\n\\\\\n",
			"n\n\\\\\\n",
			"n\n:n",
			"n\\n:n",
			"n\\\n:n",
			"n\\\\n:n",
			"n\\\\\n:n",
			"n\\\\\\n:n",
			"n:\nn",
			"n:\n\n",
			"n:\n\\n",
			"n:\n\\\n",
			"n:\n\\\\n",
			"n:\n\\\\\n",
			"n:\n\\\\\\n",
			"c\n:c",
			"c\\c:c",
			"c\\\n:c",
			"c\\\\c:c",
			"c\\\\\n:c",
			"c\\\\\\c:c",
			"c:\nc",
			"c:\n\n",
			"c:\n\\c",
			"c:\n\\\n",
			"c:\n\\\\c",
			"c:\n\\\\\n",
			"c:\n\\\\\\c",
		} {
			So(tc, ShouldEqual, unescapeToken(escapeToken(tc)))
		}
	})
}
