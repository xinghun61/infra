// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package monorail

// FindCC finds a CC'ed person by name.
func (i *Issue) FindCC(name string) *AtomPerson {
	for _, cc := range i.Cc {
		if cc.Name == name {
			return cc
		}
	}
	return nil
}
