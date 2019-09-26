// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package discovery files bugs and registers builders in the storage.
package discovery

import (
	"golang.org/x/net/context"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/sync/parallel"

	"infra/appengine/luci-migration/bugs"
	"infra/appengine/luci-migration/config"
)

const monorailProject = "chromium"

// Builders finds and registers new builders.
type Builders struct {
	Monorail         bugs.ClientFactory
	MonorailHostname string

	DatastoreOpSem parallel.Semaphore // bounds parallel datastore operations
}

// Discover fetches builder names of the master and registers new ones in the
// storage.
func (d *Builders) Discover(c context.Context, master *config.Master) error {
	return errors.New("no longer implemented")
}
