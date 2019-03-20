// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package harness

// Option is passed to Open to configure the harness.
type Option func(*Info)

// UpdateInventory returns an Option that enables inventory updates.
// A task name to be associated with the inventory update should be
// provided.
func UpdateInventory(name string) Option {
	return func(i *Info) {
		i.labelUpdater.taskName = name
		i.labelUpdater.updateLabels = true
	}
}
