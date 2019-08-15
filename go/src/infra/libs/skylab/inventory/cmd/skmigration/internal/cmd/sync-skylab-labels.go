// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"os"
	"strings"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/common/errors"
	"infra/libs/skylab/inventory/cmd/skmigration/internal/cmd/snapshotdevice"
)

// SyncSkylabLabels sync autotest labels to skylab inventory.
var SyncSkylabLabels = &subcommands.Command{
	UsageLine: "sync-skylab-labels [FLAGS]...",
	ShortDesc: "sync autotest labels to skylab based on device config snapshot",
	LongDesc:  "Sync autotest labels to skylab inventory, based on lab data snapshot.",
	CommandRun: func() subcommands.CommandRun {
		c := &syncSkylabLabelsRun{}
		c.Flags.StringVar(&c.rootDir, "root", "", "root `directory` of the inventory checkout")
		c.Flags.StringVar(&c.snapshotDir, "snapshot", "", "directory of the lab data snapshot")
		return c
	},
}

type syncSkylabLabelsRun struct {
	subcommands.CommandRunBase
	rootDir     string
	snapshotDir string
}

func (c *syncSkylabLabelsRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(os.Stderr, "%s\n", err)
		return 1
	}
	return 0
}

// makeDevicesMap takes a SnapshotDevice slice and creates a map from hostname to device.
func makeDevicesMap(snapshotData []snapshotdevice.SnapshotDevice) map[string]snapshotdevice.SnapshotDevice {
	devices := make(map[string]snapshotdevice.SnapshotDevice)
	for _, d := range snapshotData {
		h := d.Common.Hostname
		_, ok := devices[h]
		if ok {
			fmt.Printf("duplicated hostname: %s\n", h)
			continue
		}
		devices[h] = d
	}
	return devices
}

func (c *syncSkylabLabelsRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if c.rootDir == "" {
		return errors.New("-root is required")
	}
	if c.snapshotDir == "" {
		return errors.New("-snapshot is required")
	}

	labs, err := loadAllLabsData(c.rootDir)
	if err != nil {
		return err
	}

	snapshotData, err := loadSnapshotData(c.snapshotDir)
	if err != nil {
		return err
	}

	snapshotDevicesByHostname := makeDevicesMap(snapshotData)

	for _, d := range labs.Skylab.GetDuts() {
		h := d.GetCommon().GetHostname()
		snap, ok := snapshotDevicesByHostname[h]
		if !ok {
			fmt.Printf("cannot find hostname %s in snapshot Data\n", h)
			continue
		}
		labels := d.GetCommon().GetLabels()
		b := parseColonLabel(snap, "brand-code")
		if b != "" || labels.Brand == nil {
			labels.Brand = &b
		}
		sku := parseColonLabel(snap, "device-sku")
		if sku != "" || labels.Sku == nil {
			labels.Sku = &sku
		}
	}

	return writeSkylabLabData(c.rootDir, labs)
}

// parseColonLabel takes a snapshot device and the name of an
// autotest label and looks up the value associated with the label.
func parseColonLabel(snap snapshotdevice.SnapshotDevice, labelName string) string {
	for _, label := range snap.AutotestLabels {
		kv := strings.SplitN(label, ":", 2)
		if len(kv) >= 2 && kv[0] == labelName {
			return kv[1]
		}
	}
	return ""
}
