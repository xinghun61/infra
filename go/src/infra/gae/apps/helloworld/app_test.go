// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package helloworld

import (
	"testing"

	"appengine/aetest"
	"appengine/memcache"
	"appengine/user"

	. "github.com/smartystreets/goconvey/convey"
)

func TestGAETest(t *testing.T) {
	Convey("NewContext works", t, func() {
		c, err := aetest.NewContext(nil)
		So(err, ShouldBeNil)
		defer c.Close()

		c.Login(&user.User{Email: "dude@example.com"})
		u := user.Current(c)
		So(u.Email, ShouldEqual, "dude@example.com")
	})

	Convey("memcache example works", t, func() {
		c, err := aetest.NewContext(nil)
		So(err, ShouldBeNil)
		defer c.Close()

		it := &memcache.Item{
			Key:   "some-key",
			Value: []byte("some-value"),
		}
		err = memcache.Set(c, it)
		So(err, ShouldBeNil)
		it, err = memcache.Get(c, "some-key")
		So(err, ShouldBeNil)
		So(it.Value, ShouldResemble, []byte("some-value"))
	})
}
