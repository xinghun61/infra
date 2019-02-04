// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package harness

type config struct {
	adminServiceURL string
}

func makeConfig(os []Option) config {
	var c config
	for _, o := range os {
		o(&c)
	}
	return c
}

// Option is passed to Open to set harness options.
type Option func(*config)

// UpdateInventory returns an Option that enables inventory updates.
// The admin service URL for updating needs to be provided.
func UpdateInventory(adminServiceURL string) Option {
	return func(c *config) {
		c.adminServiceURL = adminServiceURL
	}
}
