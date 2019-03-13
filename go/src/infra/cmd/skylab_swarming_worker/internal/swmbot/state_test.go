// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swmbot

import (
	"reflect"
	"testing"
)

// Test that Dumping and Loading a BotInfo struct returns an identical struct.
func TestMarshalAndUnmarshal(t *testing.T) {
	t.Parallel()
	bi := LocalState{
		HostState: HostReady,
		ProvisionableLabels: ProvisionableLabels{
			"cros-version":        "lumpy-release/R00-0.0.0.0",
			"firmware-ro-version": "Google_000",
		},
		ProvisionableAttributes: ProvisionableAttributes{
			"job_repo_url": "http://127.0.0.1",
		},
	}
	data, err := Marshal(&bi)
	if err != nil {
		t.Fatalf("Error dumping dimensions: %s", err)
	}
	var got LocalState
	err = Unmarshal(data, &got)
	if err != nil {
		t.Fatalf("Error loading test file: %s", err)
	}
	if !reflect.DeepEqual(got, bi) {
		t.Errorf("Got %v, expected %v", got, bi)
	}
}

func TestUnmarshalInitializesBotInfo(t *testing.T) {
	t.Parallel()
	var bi LocalState
	data, err := Marshal(&bi)
	if err != nil {
		t.Fatalf("Error dumping dimensions: %s", err)
	}
	err = Unmarshal(data, &bi)
	if err != nil {
		t.Fatalf("Error loading test file: %s", err)
	}

	exp := LocalState{
		ProvisionableLabels:     ProvisionableLabels{},
		ProvisionableAttributes: ProvisionableAttributes{},
	}
	if !reflect.DeepEqual(bi, exp) {
		t.Errorf("Got %v, expected %v", bi, exp)
	}
}
