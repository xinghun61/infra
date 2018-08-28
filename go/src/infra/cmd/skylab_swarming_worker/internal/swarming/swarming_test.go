// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"io/ioutil"
	"os"
	"reflect"
	"testing"

	"infra/cmd/skylab_swarming_worker/internal/swarming/botcache"
)

func TestGetDutNameFromDimensions(t *testing.T) {
	t.Parallel()
	cases := []struct {
		dimensions string
		hostname   string
	}{
		{
			"{\"label-power\": [\"battery\"], \"environment\": [\"ENVIRONMENT_PROD\"], \"dut_name\": [\"abcd\"]}",
			"abcd",
		},
	}

	for _, c := range cases {
		h, e := getDutNameFromDimensions([]byte(c.dimensions))
		if e != nil {
			t.Errorf("For %v, expected no error, got %v", c.dimensions, e)
		}
		if h != c.hostname {
			t.Errorf("For %v, expected hostname %v, got %v",
				c.dimensions, c.hostname, h)
		}
	}
}

func TestGetDutNameFromDimensionsErrors(t *testing.T) {
	t.Parallel()
	dimensions := []string{
		"{\"label-power\": [\"battery\"], \"environment\": [\"ENVIRONMENT_PROD\"]}",
		"",
	}

	for _, d := range dimensions {
		h, e := getDutNameFromDimensions([]byte(d))
		if e == nil {
			t.Errorf("For %v, expected an error, got hostname %v with no error", d, h)
		}
	}
}

// Test that Dumping and Loading a BotInfo struct returns an identical struct.
func TestDumpingAndLoading(t *testing.T) {
	t.Parallel()
	td, err := ioutil.TempDir("", "hostinfo_test")
	if err != nil {
		t.Fatalf("Failed to create temporary directory: %v", err)
	}
	defer os.RemoveAll(td)
	bi := botcache.BotInfo{
		HostState: botcache.HostReady,
		ProvisionableLabels: botcache.ProvisionableLabels{
			"cros-version":        "lumpy-release/R00-0.0.0.0",
			"firmware-ro-version": "Google_000",
		},
		ProvisionableAttributes: botcache.ProvisionableAttributes{
			"job_repo_url": "http://127.0.0.1",
		},
	}
	b := &Bot{
		AutotestPath: td,
		DUTID:        "fake_dut_id",
		BotInfo:      &bi,
	}
	os.Mkdir(botcacheDirPath(b), 0777)
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
		BotInfo:      &botcache.BotInfo{},
	}
	os.Mkdir(botcacheDirPath(b), 0777)

	if err := b.DumpBotInfo(); err != nil {
		t.Fatalf("Error dumping dimensions: %s", err)
	}
	b.BotInfo = nil
	if err := b.LoadBotInfo(); err != nil {
		t.Fatalf("Error loading test file: %s", err)
	}

	bi := botcache.BotInfo{
		ProvisionableLabels:     botcache.ProvisionableLabels{},
		ProvisionableAttributes: botcache.ProvisionableAttributes{},
	}
	if !reflect.DeepEqual(*b.BotInfo, bi) {
		t.Errorf("Got %v, expected %v", *b.BotInfo, bi)
	}
}
