// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package bot

import (
	"errors"
	"testing"
	"time"
)

func TestFakeBot_StopWith(t *testing.T) {
	t.Parallel()
	t.Run("basic", func(t *testing.T) {
		t.Parallel()
		b := NewFakeBot()
		c := make(chan error)
		go func() {
			c <- b.Wait()
		}()
		select {
		case <-c:
			t.Fatal("bot exited before doing anything")
		case <-time.After(time.Millisecond):
		}
		err := errors.New("some error")
		b.StopWith(err)
		select {
		case got := <-c:
			if got != err {
				t.Errorf("Got wait error %v; want %v", got, err)
			}
		case <-time.After(time.Second):
			t.Fatal("bot didn't exist after calling StopWith")
		}
	})
	t.Run("multiple calls safe", func(t *testing.T) {
		t.Parallel()
		b := NewFakeBot()
		b.StopWith(nil)
		b.StopWith(nil)
	})
}
