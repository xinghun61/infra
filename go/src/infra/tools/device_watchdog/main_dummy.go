// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build !android

// device_watchdog is a watchdog daemon for android devices. It will attempt to
// reboot the device if its uptime exceeds a specified maximum.
//
// This executable is android-only.
package main

import "os"

func main() {
	os.Exit(1)
}
