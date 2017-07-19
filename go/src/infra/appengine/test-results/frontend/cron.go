// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"time"

	"golang.org/x/net/context"

	"infra/appengine/test-results/model"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"
)

const (
	// timeToStoreFiles is the time after which files are deleted.
	timeToStoreFiles = 24 * 365 * time.Hour // 1 year
)

func deleteEntities(ctx context.Context, keys *[]*datastore.Key) {
	// Limit number of entities to be deleted to 500 to avoid hitting
	// datastore.Delete limit on the number of entities that it can operate on.
	var keysToDelete []*datastore.Key
	if len(*keys) > 500 {
		keysToDelete = (*keys)[:500]
	} else {
		keysToDelete = *keys
	}

	logging.Infof(ctx, "Deleting %d entities", len(keysToDelete))
	if err := datastore.Delete(ctx, keysToDelete); err != nil {
		logging.WithError(err).Warningf(ctx, "Failed to delete entities")
	}

	// Remove deleted keys from the passed slice.
	*keys = (*keys)[len(keysToDelete):]
}

func deleteOldResultsHandler(rc *router.Context) {
	ctx := rc.Context

	storageHorizon := time.Now().Add(-timeToStoreFiles).UTC()
	q := datastore.NewQuery("TestFile").Lt("date", storageHorizon)
	keysToDelete := make([]*datastore.Key, 0, 600)
	err := datastore.Run(ctx, q, func(tf *model.TestFile) {
		keysToDelete = append(keysToDelete, datastore.KeyForObj(ctx, tf))
		keysToDelete = append(keysToDelete, tf.DataKeys...)

		if len(keysToDelete) >= 500 {
			deleteEntities(ctx, &keysToDelete)
		}
	})

	if err == nil {
		for len(keysToDelete) > 0 {
			deleteEntities(ctx, &keysToDelete)
		}
	} else {
		logging.WithError(err).Warningf(ctx, "Failed to delete old results")
	}
}
