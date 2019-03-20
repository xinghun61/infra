// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package harness

// Option is passed to Open to configure the harness.
type Option func(*Info)

// UpdateInventory returns an Option that enables inventory updates.
// The admin service for updating needs to be provided,
// e.g. foo.appspot.com.
func UpdateInventory(adminService string) Option {
	return func(i *Info) {
		i.labelUpdater.adminService = adminService
		i.labelUpdater.updateLabels = true
	}
}

// TaskName returns an Option that sets the task name.  The task name
// is for informational purposes only.  For example, it is used to
// provide context for inventory label updates.
func TaskName(name string) Option {
	return func(i *Info) {
		i.labelUpdater.taskName = name
	}
}
