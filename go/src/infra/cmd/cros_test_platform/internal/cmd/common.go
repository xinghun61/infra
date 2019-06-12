// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

const (
	// failedWithoutResponse is returned by a script that failed without
	// producing a response.
	failedWithoutResponse = 1

	// retcodeFailedWithoutResponse is returned by a script that failed but
	// nevertheless produced a response.
	failedWithResponse = 2
)
