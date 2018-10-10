// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package harness

import (
	"io/ioutil"
	"os"
	"reflect"
	"testing"

	"infra/cmd/skylab_swarming_worker/internal/botinfo"
	"infra/cmd/skylab_swarming_worker/internal/swarming"
)

// Test that Dumping and Loading a BotInfo struct returns an identical struct.
func TestDumpingAndLoading(t *testing.T) {
	t.Parallel()
	td, err := ioutil.TempDir("", "hostinfo_test")
	if err != nil {
		t.Fatalf("Failed to create temporary directory: %v", err)
	}
	defer os.RemoveAll(td)
	bi := botinfo.BotInfo{
		HostState: botinfo.HostReady,
		ProvisionableLabels: botinfo.ProvisionableLabels{
			"cros-version":        "lumpy-release/R00-0.0.0.0",
			"firmware-ro-version": "Google_000",
		},
		ProvisionableAttributes: botinfo.ProvisionableAttributes{
			"job_repo_url": "http://127.0.0.1",
		},
	}
	b := &swarming.Bot{
		AutotestPath: td,
		DUTID:        "fake_dut_id",
	}
	os.Mkdir(botinfoDirPath(b), 0777)
	if err := dumpBotInfo(b, &bi); err != nil {
		t.Fatalf("Error dumping dimensions: %s", err)
	}
	got, err := loadBotInfo(b)
	if err != nil {
		t.Fatalf("Error loading test file: %s", err)
	}
	if !reflect.DeepEqual(*got, bi) {
		t.Errorf("Got %v, expected %v", *got, bi)
	}
}
