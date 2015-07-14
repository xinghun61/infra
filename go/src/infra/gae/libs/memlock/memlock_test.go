// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package memlock

import (
	"fmt"
	"runtime"
	"testing"
	"time"

	"infra/gae/libs/gae"
	"infra/gae/libs/gae/memory"

	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/clock/testclock"
	. "github.com/smartystreets/goconvey/convey"
	"golang.org/x/net/context"
)

func init() {
	delay = time.Millisecond
	memcacheLockTime = time.Millisecond * 4
}

func TestSimple(t *testing.T) {
	// TODO(riannucci): Mock time.After so that we don't have to delay for real.

	const key = memlockKeyPrefix + "testkey"

	Convey("basic locking", t, func() {
		start := time.Date(1986, time.October, 26, 1, 20, 00, 00, time.UTC)
		ctx, clk := testclock.UseTime(context.Background(), start)
		blocker := make(chan struct{})
		clk.SetTimerCallback(func(clock.Timer) {
			clk.Add(delay)
			select {
			case blocker <- struct{}{}:
			default:
			}
		})
		ctx = memory.Use(ctx)
		mc := gae.GetMC(ctx).(interface {
			gae.Testable
			gae.Memcache
		})

		Convey("fails to acquire when memcache is down", func() {
			mc.BreakFeatures(nil, "Add")
			err := TryWithLock(ctx, "testkey", "id", func(check func() bool) error {
				// should never reach here
				So(false, ShouldBeTrue)
				return nil
			})
			So(err, ShouldEqual, ErrFailedToLock)
		})

		Convey("returns the inner error", func() {
			toRet := fmt.Errorf("sup")
			err := TryWithLock(ctx, "testkey", "id", func(check func() bool) error {
				return toRet
			})
			So(err, ShouldEqual, toRet)
		})

		Convey("returns the error", func() {
			toRet := fmt.Errorf("sup")
			err := TryWithLock(ctx, "testkey", "id", func(check func() bool) error {
				return toRet
			})
			So(err, ShouldEqual, toRet)
		})

		Convey("can acquire when empty", func() {
			err := TryWithLock(ctx, "testkey", "id", func(check func() bool) error {
				So(check(), ShouldBeTrue)

				waitFalse := func() {
					<-blocker
					for i := 0; i < 3; i++ {
						if check() {
							runtime.Gosched()
						}
					}
					So(check(), ShouldBeFalse)
				}

				Convey("waiting for a while keeps refreshing the lock", func() {
					// simulate waiting for 64*delay time, and ensuring that checkLoop
					// runs that many times.
					for i := 0; i < 64; i++ {
						<-blocker
						clk.Add(delay)
					}
					So(check(), ShouldBeTrue)
				})

				Convey("but sometimes we might lose it", func() {
					Convey("because it was evicted", func() {
						mc.Delete(key)
						clk.Add(memcacheLockTime)
						waitFalse()
					})

					Convey("or because it was stolen", func() {
						mc.Set(mc.NewItem(key).SetValue([]byte("wat")))
						waitFalse()
					})

					Convey("or because of service issues", func() {
						mc.BreakFeatures(nil, "CompareAndSwap")
						waitFalse()
					})
				})
				return nil
			})
			So(err, ShouldBeNil)
		})

		Convey("an empty context id is an error", func() {
			So(TryWithLock(ctx, "testkey", "", nil), ShouldEqual, ErrEmptyClientID)
		})
	})
}
