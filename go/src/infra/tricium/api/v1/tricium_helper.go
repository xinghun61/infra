// Copyright 2017 The Chromium Authors. All rights reserved. Use of this source
// code is governed by a BSD-style license that can be found in the LICENSE
// file.

package tricium

// IsDone returns true if the state is done.
//
// The state is considered done if it is not pending or running.
func IsDone(s State) bool {
	return s != State_PENDING && s != State_RUNNING
}
