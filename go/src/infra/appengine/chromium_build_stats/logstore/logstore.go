// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package logstore provides an access to storage of ninja_log and compiler_proxy.INFO log.
package logstore

import (
	"context"
	"strings"

	"google.golang.org/appengine/file"
)

// Bucket returns url of the given obj.
func Bucket(ctx context.Context, obj string) (string, error) {
	obj = strings.TrimPrefix(obj, "/")
	if strings.HasPrefix(obj, "upload/") {
		return file.DefaultBucketName(ctx)
	}
	return "chrome-goma-log", nil
}
