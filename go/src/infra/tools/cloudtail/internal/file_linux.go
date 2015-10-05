// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"os"
)

func OpenForSharedRead(path string) (*os.File, error) {
	// On Linux regular os.Open opens file in shared mode.
	return os.Open(path)
}
