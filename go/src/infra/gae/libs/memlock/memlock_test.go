// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package memlock

import (
	"fmt"
	"infra/gae/libs/wrapper"
	"infra/gae/libs/wrapper/memory"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
	"golang.org/x/net/context"

	"appengine/memcache"
)

func init() {
	delay = time.Millisecond
	memcacheLockTime = time.Millisecond * 4
}

func TestSimple(t *testing.T) {
	// TODO(riannucci): Mock time.After so that we don't have to delay for real.

	Convey("basic locking", t, func() {
		c := memory.Use(context.Background())
		mc := wrapper.GetMC(c).(interface {
			wrapper.Testable
			wrapper.MCSingleReadWriter
		})

		Convey("fails to acquire when memcache is down", func() {
			mc.BreakFeatures(nil, "Add")
			err := TryWithLock(c, "testkey", "id", func(check func() bool) error {
				// should never reach here
				So(false, ShouldBeTrue)
				return nil
			})
			So(err, ShouldEqual, ErrFailedToLock)
		})

		Convey("returns the inner error", func() {
			toRet := fmt.Errorf("sup")
			err := TryWithLock(c, "testkey", "id", func(check func() bool) error {
				return toRet
			})
			So(err, ShouldEqual, toRet)
		})

		Convey("can acquire when empty", func() {
			err := TryWithLock(c, "testkey", "id", func(check func() bool) error {
				So(check(), ShouldBeTrue)

				Convey("waiting for a while keeps refreshing the lock", func() {
					time.Sleep(memcacheLockTime * 8)
					So(check(), ShouldBeTrue)
				})

				Convey("but sometimes we might lose it", func() {
					Convey("because it was evicted", func() {
						mc.Delete(memlockKeyPrefix + "testkey")
						time.Sleep(memcacheLockTime)
						So(check(), ShouldBeFalse)
					})

					Convey("because it got evicted (but we race)", func() {
						mc.Set(&memcache.Item{
							Key:   memlockKeyPrefix + "testkey",
							Value: []byte(""),
						})
					})

					Convey("or because it was stolen", func() {
						mc.Set(&memcache.Item{
							Key:   memlockKeyPrefix + "testkey",
							Value: []byte("wat"),
						})
						time.Sleep(memcacheLockTime)
						So(check(), ShouldBeFalse)
					})

					Convey("or because of service issues", func() {
						mc.BreakFeatures(nil, "CompareAndSwap")
						time.Sleep(memcacheLockTime)
						So(check(), ShouldBeFalse)
					})
				})
				return nil
			})
			So(err, ShouldBeNil)
		})

		Convey("an empty context id is an error", func() {
			So(TryWithLock(c, "testkey", "", nil), ShouldEqual, ErrEmptyClientID)
		})
	})
}
