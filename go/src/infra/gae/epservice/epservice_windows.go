// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build windows

package main

import (
	"syscall"
)

var serverStartParams *syscall.SysProcAttr
