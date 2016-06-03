// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package terminal

func ExamplePrint() {
	Print("This is a string.")
	Print("These are the numbers %d and %d.", 1, 2)
	// Output:
	// This is a string.
	// These are the numbers 1 and 2.
}

func ExampleDebug() {
	Debug("This will not be printed.")
	ShowDebug = true
	Debug("This will be printed.")
	// Output:
	// This will be printed.
}
