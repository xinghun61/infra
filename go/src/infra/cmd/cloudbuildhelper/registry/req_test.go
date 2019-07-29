// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package registry

import (
	"testing"

	"go.chromium.org/luci/common/errors"

	. "github.com/smartystreets/goconvey/convey"
)

func TestErrors(t *testing.T) {
	t.Parallel()

	Convey("IsManifestUnknown", t, func() {
		manUnknownErr := &Error{
			Errors: []InnerError{
				{},
				{Code: "MANIFEST_UNKNOWN"},
			},
		}
		So(IsManifestUnknown(nil), ShouldBeFalse)
		So(IsManifestUnknown(&Error{}), ShouldBeFalse)
		So(IsManifestUnknown(manUnknownErr), ShouldBeTrue)
		So(IsManifestUnknown(errors.Annotate(manUnknownErr, "blah").Err()), ShouldBeTrue)
	})
}
