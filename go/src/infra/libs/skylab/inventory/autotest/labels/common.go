// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package labels

import "strings"

// RemoveLabel removes a label from the slice without reallocation.
func removeLabel(labels []string, n int) []string {
	size := len(labels)
	copy(labels[n:size-1], labels[n+1:size])
	return labels[:size-1]
}

// SplitLabel splits Autotest colon separated keyval labels into key
// and value.  If the label doesn't have a colon, the value string
// will be empty.  If the label is an empty string (invalid), both key
// and value will be empty.
func splitLabel(label string) (key string, value string) {
	parts := strings.SplitN(label, ":", 2)
	switch len(parts) {
	case 0:
		return "", ""
	case 1:
		return parts[0], ""
	case 2:
		return parts[0], parts[1]
	default:
		panic("unexpected length for split string")
	}
}
