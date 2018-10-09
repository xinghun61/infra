// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"io/ioutil"
	"os"
	"reflect"
	"testing"

	"github.com/kylelemons/godebug/pretty"

	"infra/cmd/skylab_swarming_worker/internal/botinfo"
	"infra/cmd/skylab_swarming_worker/internal/lucifer"
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
	b := &Bot{
		AutotestPath: td,
		DUTID:        "fake_dut_id",
		BotInfo:      &bi,
	}
	os.Mkdir(botinfoDirPath(b), 0777)
	if err := b.DumpBotInfo(); err != nil {
		t.Fatalf("Error dumping dimensions: %s", err)
	}
	b.BotInfo = nil
	if err := b.LoadBotInfo(); err != nil {
		t.Fatalf("Error loading test file: %s", err)
	}
	if !reflect.DeepEqual(*b.BotInfo, bi) {
		t.Errorf("Got %v, expected %v", *b.BotInfo, bi)
	}
}

func TestLoadInitializesBotInfo(t *testing.T) {
	t.Parallel()
	td, err := ioutil.TempDir("", "hostinfo_test")
	if err != nil {
		t.Fatalf("Failed to create temporary directory: %v", err)
	}
	defer os.RemoveAll(td)
	b := &Bot{
		AutotestPath: td,
		DUTID:        "fake_dut_id",
		BotInfo:      &botinfo.BotInfo{},
	}
	os.Mkdir(botinfoDirPath(b), 0777)

	if err := b.DumpBotInfo(); err != nil {
		t.Fatalf("Error dumping dimensions: %s", err)
	}
	b.BotInfo = nil
	if err := b.LoadBotInfo(); err != nil {
		t.Fatalf("Error loading test file: %s", err)
	}

	bi := botinfo.BotInfo{
		ProvisionableLabels:     botinfo.ProvisionableLabels{},
		ProvisionableAttributes: botinfo.ProvisionableAttributes{},
	}
	if !reflect.DeepEqual(*b.BotInfo, bi) {
		t.Errorf("Got %v, expected %v", *b.BotInfo, bi)
	}
}

func TestBot_LuciferConfig(t *testing.T) {
	t.Parallel()
	b := &Bot{
		AutotestPath:  "/usr/local/autotest",
		LuciferBinDir: "/opt/lucifer",
	}
	got := b.LuciferConfig()
	want := lucifer.Config{
		AutotestPath: "/usr/local/autotest",
		BinDir:       "/opt/lucifer",
	}
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("LuciferConfig() differs -want +got:\n %s", diff)
	}
}
