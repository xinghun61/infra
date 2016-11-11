// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build !windows

package puppet

func lastRunFile() (string, error) {
	return "/var/lib/puppet_last_run_summary.yaml", nil
}

func isPuppetCanaryFile() (string, error) {
	return "/var/lib/is_puppet_canary", nil
}

func exitStatusFiles() []string {
	return []string{"/var/log/puppet/puppet_exit_status.txt"}
}
