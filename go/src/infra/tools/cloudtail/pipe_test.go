// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestPipeFromReader(t *testing.T) {
	Convey("Works", t, func() {
		client := &fakeClient{}
		buf := NewPushBuffer(PushBufferOptions{Client: client})

		body := `
    line
        another

    last one
    `

		PipeFromReader(strings.NewReader(body), NullParser(), buf, nil)
		So(buf.Stop(), ShouldBeNil)

		text := []string{}
		for _, e := range client.getEntries() {
			text = append(text, e.TextPayload)
		}
		So(text, ShouldResemble, []string{"line", "another", "last one"})
	})
}
