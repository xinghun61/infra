// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package puppet

import (
	"golang.org/x/sys/windows/registry"
)

var (
	cachedCommonAppdataPath string
)

func lastRunFile() (string, error) {
	appdata, err := commonAppdataPath()
	if err != nil {
		return "", err
	}
	return appdata + `\PuppetLabs\puppet\var\state\last_run_summary.yaml`, nil
}

func isPuppetCanaryFile() (string, error) {
	appdata, err := commonAppdataPath()
	if err != nil {
		return "", err
	}
	return appdata + `\PuppetLabs\puppet\var\lib\is_puppet_canary`, nil
}

func commonAppdataPath() (string, error) {
	if cachedCommonAppdataPath != "" {
		return cachedCommonAppdataPath, nil
	}

	key, err := registry.OpenKey(registry.LOCAL_MACHINE,
		`Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders`,
		registry.READ)
	if err != nil {
		return "", err
	}

	path, _, err := key.GetStringValue("Common AppData")
	if err == nil {
		cachedCommonAppdataPath = path
	}
	return path, err
}

func exitStatusFiles() []string {
	return []string{
		`C:\chrome-infra-logs\puppet_exit_status.txt`,
		`E:\chrome-infra-logs\puppet_exit_status.txt`,
	}
}
