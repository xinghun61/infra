// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package skylab

import (
	"infra/libs/skylab/request"
	"testing"
)

func TestUpdateLogDogURL(t *testing.T) {
	var a request.Args
	url := `logdog://luci-logdog.appspot.com/chromeos/skylab/404d1172-2446-4bc2-bd53-dde0816e5541/+/annotations`
	a.Cmd.LogDogAnnotationURL = url
	updateLogDogURL(&a)
	if url == a.Cmd.LogDogAnnotationURL {
		t.Errorf("updateLogDogURL did not change the original URL from %s", url)
	}

	// Ensure that updated URL is still a valid URL.
	url = a.Cmd.LogDogAnnotationURL
	updateLogDogURL(&a)
	if url == a.Cmd.LogDogAnnotationURL {
		t.Errorf("updateLogDogURL did not change the updated URL from %s", url)
	}
}
