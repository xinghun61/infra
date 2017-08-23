// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package eventupload

import (
	"fmt"
	"testing"
)

func TestGenerate(t *testing.T) {
	t.Parallel()

	prefix := "testPrefix"
	id := InsertIDGenerator{}
	id.Prefix = prefix

	for i := 1; i < 10; i++ {
		want := fmt.Sprintf("%s:%d", prefix, i)
		if got := id.Generate(); got != want {
			t.Errorf("got: %s; want: %s", got, want)
		}
	}
}
