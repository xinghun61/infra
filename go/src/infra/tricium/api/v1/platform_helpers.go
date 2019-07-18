// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tricium

import (
	"go.chromium.org/luci/common/errors"
)

var validPlatforms = [...]Platform_Name{
	Platform_LINUX,
	Platform_UBUNTU,
	Platform_ANDROID,
	Platform_MAC,
	Platform_OSX,
	Platform_IOS,
	Platform_WINDOWS,
	Platform_CHROMEOS,
	Platform_FUCHSIA,
}

// GetPlatforms translates a platform bit field to Platform_Name values.
func GetPlatforms(platforms int64) ([]Platform_Name, error) {
	if platforms == int64(Platform_ANY) {
		return []Platform_Name{Platform_ANY}, nil
	}

	out := []Platform_Name{}
	for _, p := range validPlatforms {
		mask := int64(1<<uint64(p) - 1)
		if platforms&mask != 0 {
			out = append(out, p)
			platforms = platforms &^ mask
		}
	}

	if platforms != 0 {
		return nil, errors.Reason("Unknown platform: %#x", platforms).Err()
	}

	return out, nil
}

// PlatformBitPosToMask returns a bit field with the given position set.
//
// As a special case, it returns 0 for position 0 (Platform_ANY).
func PlatformBitPosToMask(pos Platform_Name) int64 {
	if pos == 0 {
		return 0
	}
	return int64(1 << uint64(pos-1))
}
