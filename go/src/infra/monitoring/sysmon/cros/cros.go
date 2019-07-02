// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cros

import (
	"os/user"
	"path/filepath"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/tsmon"
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
	"go.chromium.org/luci/common/tsmon/types"
	"golang.org/x/net/context"
)

var (
	dutStatus = metric.NewString("dev/cros/status",
		"DUT status (Online|Offline).",
		nil,
		field.String("container_hostname"))

	allMetrics = []types.Metric{
		dutStatus,
	}
)

// Register adds tsmon callbacks to set metrics
func Register() {
	tsmon.RegisterGlobalCallback(func(c context.Context) {
		usr, err := user.Current()
		if err != nil {
			logging.Errorf(c, "Failed to get current user: %s",
				err)
		} else if err = update(c, usr.HomeDir); err != nil {
			logging.Errorf(c, "Error updating DUT metrics: %s",
				err)
		}
	}, allMetrics...)
}

func update(c context.Context, usrHome string) (err error) {
	allFiles, err := filepath.Glob(
		filepath.Join(usrHome, fileGlob))
	if err != nil {
		return
	}
	if len(allFiles) == 0 {
		// This is usual case in most machines. So don't log an error
		// message.
		return
	}
	var lastErr error
	for _, filePath := range allFiles {
		statusFile, err := loadfile(c, filePath)
		if err != nil {
			logging.Errorf(c, "Failed to load file %s. %s",
				filePath, err)
			lastErr = err
		} else {
			updateMetrics(c, statusFile)
		}
	}
	err = lastErr
	return
}

func updateMetrics(c context.Context, deviceFile deviceStatusFile) {
	if deviceFile.Status != "" {
		dutStatus.Set(c, deviceFile.Status, deviceFile.ContainerHostname)
	} else {
		logging.Warningf(c, "Device status unknown")
	}
}
