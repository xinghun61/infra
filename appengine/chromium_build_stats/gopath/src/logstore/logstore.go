// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package logstore provides an access to storage of ninja_log and compiler_proxy.INFO log.
package logstore

import (
	"fmt"
	"net/url"
	"strings"
)

// URL returns url of the given obj.
func URL(obj string) (*url.URL, error) {
	obj = strings.TrimPrefix(obj, "/")
	if strings.HasPrefix(obj, "upload/") {
		// https://chromium-build-stats.appspot.com.storage.googleapis.com causes urlfetch: SSL_CERTIFICATE_ERROR.
		return url.Parse(fmt.Sprintf("https://storage.googleapis.com/chromium-build-stats.appspot.com/%s", obj))
	}
	return url.Parse(fmt.Sprintf("https://chrome-goma-log.storage.googleapis.com/%s", obj))
}
