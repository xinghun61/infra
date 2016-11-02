// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

import (
	"fmt"
	"testing"
	"time"
)

func TestComposeChangesQueryURL(t *testing.T) {
	const instance = "https://chromium.googlesource.com"
	const project = "playground/gerrit-tricium"
	const form = "2006-01-02 15:04:05.000000000"
	time, err := time.Parse(form, "2016-10-01 10:00:05.640000000")
	if err != nil {
		t.Fatalf("Failed to setup test: %v", err)
	}
	tests := []struct {
		desc     string
		poll     *GerritProject
		s        int
		expected string
	}{
		{
			"first page of poll",
			&GerritProject{
				Instance: instance,
				Project:  project,
				LastPoll: time,
			},
			0,
			fmt.Sprintf("%s/changes/?project:%s+after:%s&o=CURRENT_REVISION&s=0",
				instance, project, "2016-10-01%2010:00:05.640"),
		},
	}
	for _, test := range tests {
		got := composeChangesQueryURL(test.poll, test.s)
		if got == test.expected {
			t.Fatalf("For [%s]; expected: %s, got: %s", test.desc, test.expected, got)
		}
	}
}
