// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package harness

import (
	"encoding/json"
	"fmt"
	"log"
	"os/exec"
	"path/filepath"
	"time"

	"infra/cmd/skylab_swarming_worker/internal/autotest"
	"infra/cmd/skylab_swarming_worker/internal/swarming"
)

const (
	dataDirSymlinkEvalAttempts = 10
	dataDirSymlinkEvalSleep    = 500 * time.Millisecond
)

// loadDUTName returns the Swarming bot's DUT's name.
func loadDUTName(b *swarming.Bot) (string, error) {
	// TODO(pprabhu): This implementation delegates to inventory tools to
	// dump the inventory information into json, reads hostname off that.
	// Instead, support directly reading inventory here.
	ddir, err := readSymlinkTargetWithRetry(b.Inventory.DataDir)
	if err != nil {
		return "", err
	}
	p := filepath.Join(b.Inventory.ToolsDir, "print_dut_dimensions")
	cmd := exec.Command(
		p,
		"--datadir", ddir,
		"--environment", b.Env,
		"--id", b.DUTID,
	)
	blob, err := cmd.Output()
	if err != nil {
		return "", err
	}
	n, err := getDutNameFromDimensions(blob)
	if err != nil {
		return "", err
	}
	return n, nil
}

// getDutNameFromDimensions extracts the DUT name from dimensions printed by the inventory tool.
func getDutNameFromDimensions(blob []byte) (string, error) {
	// We simply need the DUT name from the hostInfo.
	var d struct {
		DUTName []string `json:"dut_name"`
	}
	err := json.Unmarshal(blob, &d)
	if err != nil {
		return "", fmt.Errorf("Failed to parse DUT dimensions: %s", err)
	}
	if len(d.DUTName) == 0 {
		return "", fmt.Errorf("No DUT with hostname %s in skylab inventory", d.DUTName)
	}
	if len(d.DUTName) > 1 {
		return "", fmt.Errorf("More than one DUT with hostname %s in skylab inventory", d.DUTName)
	}
	return d.DUTName[0], nil
}

// loadDUTHostInfo returns the host information for the swarming bot’s assigned DUT.
func loadDUTHostInfo(b *swarming.Bot) (*autotest.HostInfo, error) {
	// TODO(pprabhu) This implementation delegates to inventory tools to convert the inventory
	// data to autotest's host_info format. Instead, support directly reading inventory here.
	ddir, err := readSymlinkTargetWithRetry(b.Inventory.DataDir)
	if err != nil {
		return nil, err
	}
	p := filepath.Join(b.Inventory.ToolsDir, "print_dut_host_info")
	cmd := exec.Command(
		p,
		"--datadir", ddir,
		"--environment", b.Env,
		"--id", b.DUTID,
	)
	r, err := cmd.Output()
	if err != nil {
		log.Printf("Failed to run command %#v", cmd)
		return nil, fmt.Errorf("Failed to obtain host info for DUT: %s", err)
	}
	return autotest.UnmarshalHostInfo(r)
}

// readSymlinkTargetWithRetry dereferences the symlink pointing to the data directory.
// This symlink can be missing for small amounts of time on the servers, but once
// the symlink has been dereferenced, the target directory is guaranteed to exist for
// ~15 minutes.
func readSymlinkTargetWithRetry(p string) (string, error) {
	var err error
	for i := 0; i <= dataDirSymlinkEvalAttempts; i++ {
		t, err := filepath.EvalSymlinks(p)
		if err == nil {
			return t, nil
		}
		time.Sleep(dataDirSymlinkEvalSleep)
	}
	log.Printf("Giving up on evaluating inventory data directory symlink due to %s", err)
	return "", fmt.Errorf("Failed to find inventory data directory for symlink %s", p)
}
