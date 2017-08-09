// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"net/http"
	"time"

	"infra/appengine/test-results/model"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/server/router"
)

const (
	// timeToStoreFiles is the time after which files are deleted.
	timeToStoreFiles = 24 * 365 * time.Hour // 1 year
)

func deleteOldResultsHandler(rc *router.Context) {
	c, w := rc.Context, rc.Writer

	// Buffer the channel to 2x batch size to ensure that we are not sending
	// keys faster than we can schedule deletion tasks.
	keyCh := make(chan *datastore.Key, 1000)
	entitiesDeleted := 0
	var queryErr error
	go func() {
		defer close(keyCh)
		storageHorizon := time.Now().Add(-timeToStoreFiles).UTC()
		q := datastore.NewQuery("TestFile").Lt("date", storageHorizon)
		queryErr = datastore.Run(c, q, func(tf *model.TestFile) {
			for _, dataKey := range tf.DataKeys {
				keyCh <- dataKey
			}
			keyCh <- datastore.KeyForObj(c, tf)
		})
	}()

	// We ignore returned error here, since the tasks we run never return errors
	// and the WorkPool itself does not produce any errors on its own.
	parallel.WorkPool(50, func(workC chan<- func() error) {
		keys := make([]*datastore.Key, 0, 500)
		doDelete := func() {
			keys2 := keys
			workC <- func() error {
				if err := datastore.Delete(c, keys2); err != nil {
					// It may happen that a TestFile entity has been deleted, while
					// DataEntry entities referenced from it are not, which may
					// result in dangling entities that we can not delete safely.
					// Since this should not happen frequently, we are okay just
					// logging a warning here and ignoring them. Also we are now
					// adding a timestamp to all new DataEntries entities and in
					// approximately 1 year we'll be able to detect all entities
					// without a timestamp as dangling and remove them. See
					// https://crbug.com/741236 for more details.
					logging.WithError(err).Warningf(c, "Failed to delete some entities")
				} else {
					entitiesDeleted += len(keys2)
				}
				return nil
			}
		}

		for key := range keyCh {
			keys = append(keys, key)
			if len(keys) == 500 {
				doDelete()
				keys = make([]*datastore.Key, 0, 500)
			}
		}

		if len(keys) > 0 {
			doDelete()
		}
	})

	if queryErr != nil && entitiesDeleted == 0 {
		// Normally the error would be datastore timeout from the Run operation
		// and we should not log it because we'll simply continue deleting
		// entities in the next cron job run. However, if for some chance
		// nothing got deleted before we've received the error, it may mean we
		// are not making progress and thus should log an error.
		logging.WithError(queryErr).Errorf(c, "Query failed, no progress was made")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	logging.Infof(c, "Deleted %d entities", entitiesDeleted)
	w.WriteHeader(http.StatusOK)
}
