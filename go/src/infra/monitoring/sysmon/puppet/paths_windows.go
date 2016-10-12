// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package puppet

import (
	"golang.org/x/sys/windows/registry"
)

func lastRunFile() (string, error) {
	appdata, err := commonAppdataPath()
	if err != nil {
		return "", err
	}
	return appdata + `\PuppetLabs\puppet\var\state\last_run_summary.yaml`, nil
}

func commonAppdataPath() (string, error) {
	key, err := registry.OpenKey(registry.LOCAL_MACHINE,
		`Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders`,
		registry.READ)
	if err != nil {
		return "", err
	}

	path, _, err := key.GetStringValue("Common AppData")
	return path, err
}
