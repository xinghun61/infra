// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package event

// Forwarder encapsulates cleanup for ForwardAbortSignal.
type Forwarder struct{}

// Close cleans up signal forwarding stuff.  Subsequent calls do
// nothing.
func (f *Forwarder) Close() {}

// ForwardAbortSignal catches termination signals and forwards them as
// abort messages to an abort socket.  This function spawns a
// goroutine and modifies the process signal handlers.  Both of these
// are cleaned up when the returned Forwarder is closed.
func ForwardAbortSignal(path string) *Forwarder {
	panic("not supported on windows")
}
