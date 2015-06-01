// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package memlock allows multiple appengine handlers to coordinate best-effort
// mutual execution via memcache. "best-effort" here means "best-effort"...
// memcache is not reliable. However, colliding on memcache is a lot cheaper
// than, for example, colliding with datastore transactions.
package memlock

import (
	"bytes"
	"errors"
	"infra/gae/libs/wrapper"
	"sync/atomic"
	"time"

	"github.com/luci/luci-go/common/logging"
	"golang.org/x/net/context"

	"appengine/memcache"
)

// ErrFailedToLock is returned from TryWithLock when it fails to obtain a lock
// prior to invoking the user-supplied function.
var ErrFailedToLock = errors.New("memlock: failed to obtain lock")

// ErrEmptyClientID is returned from TryWithLock when you specify an empty
// clientID.
var ErrEmptyClientID = errors.New("memlock: empty clientID")

// memlockKeyPrefix is the memcache Key prefix for all user-supplied keys.
const memlockKeyPrefix = "memlock:"

type checkOp string

// var so we can override it in the tests
var delay = time.Second

const (
	release checkOp = "release"
	refresh         = "refresh"
)

// memcacheLockTime is the expiration time of the memcache entry. If the lock
// is correctly released, then it will be released before this time. It's a
// var so we can override it in the tests.
var memcacheLockTime = 16 * time.Second

// TryWithLock attempts to obtains the lock once, and then invokes f if
// sucessful. The `check` function can be used within f to see if the lock is
// still held.
//
// TryWithLock function returns ErrFailedToLock if it fails to obtain the lock,
// otherwise returns the error that f returns.
//
// `key` is the memcache key to use (i.e. the name of the lock). Clients locking
// the same data must use the same key. clientID is the unique identifier for
// this client (lock-holder). If it's empty then TryWithLock() will return
// ErrEmptyClientID.
func TryWithLock(c context.Context, key, clientID string, f func(check func() bool) error) error {
	if len(clientID) == 0 {
		return ErrEmptyClientID
	}

	c = logging.SetField(c, "key", key)
	c = logging.SetField(c, "clientID", clientID)
	log := logging.Get(c)
	mc := wrapper.GetMC(c)

	key = memlockKeyPrefix + key
	cid := []byte(clientID)

	// checkAnd gets the current value from memcache, and then attempts to do the
	// checkOp (which can either be `refresh` or `release`). These pieces of
	// functionality are necessarially intertwined, because CAS only works with
	// the exact-same *Item which was returned from a Get.
	//
	// refresh will attempt to CAS the item with the same content to reset it's
	// timeout.
	//
	// release will attempt to CAS the item to remove it's contents (clientID).
	// another lock observing an empty clientID will know that the lock is
	// obtainable.
	checkAnd := func(op checkOp) bool {
		itm, err := mc.Get(key)
		if err != nil {
			log.Warningf("error getting: %s", err)
			return false
		}

		if len(itm.Value) > 0 && !bytes.Equal(itm.Value, cid) {
			log.Infof("lock owned by %q", string(itm.Value))
			return false
		}

		if op == refresh {
			itm.Value = cid
			itm.Expiration = memcacheLockTime
		} else {
			if len(itm.Value) == 0 {
				// it's already unlocked, no need to CAS
				log.Infof("lock already released")
				return true
			}
			itm.Value = []byte{}
			itm.Expiration = delay
		}

		err = mc.CompareAndSwap(itm)
		if err != nil {
			log.Warningf("failed to %s lock: %q", op, err)
			return false
		}

		return true
	}

	// Now the actual logic begins. First we 'Add' the item, which will set it if
	// it's not present in the memcache, otherwise leaves it alone.
	err := mc.Add(&memcache.Item{
		Key: key, Value: cid, Expiration: memcacheLockTime})
	if err != nil {
		if err != memcache.ErrNotStored {
			log.Warningf("error adding: %s", err)
		}
		if !checkAnd(refresh) {
			return ErrFailedToLock
		}
	}

	// At this point we nominally have the lock (at least for memcacheLockTime).

	stopChan := make(chan struct{})
	stoppedChan := make(chan struct{})
	held := uint32(1)

	defer func() {
		close(stopChan)
		<-stoppedChan // this blocks TryWithLock until the goroutine below quits.
	}()

	// This goroutine checks to see if we still posess the lock, and refreshes it
	// if we do. It will stop doing this when either stopChan is activated (e.g.
	// the user's function returns) or we lose the lock (memcache flake, etc.).
	go func() {
		defer close(stoppedChan)

	checkLoop:
		for {
			select {
			case <-stopChan:
				break checkLoop
			case <-time.After(delay):
			}
			if !checkAnd(refresh) {
				atomic.StoreUint32(&held, 0)
				log.Warningf("lost lock: %s", err)
				break
			}
		}

		checkAnd(release)
		atomic.StoreUint32(&held, 0)
	}()

	return f(func() bool { return atomic.LoadUint32(&held) == 1 })
}
