// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package logstore

import (
	"context"
	"fmt"

	"cloud.google.com/go/storage"
)

// Fetch fetches file from path in logstore.
// Caller would need to uncompress the reader.
func Fetch(ctx context.Context, client *storage.Client, path string) (*storage.Reader, error) {
	bkt, err := Bucket(ctx, path)
	if err != nil {
		return nil, fmt.Errorf("failed to get Bucket name for %s: %v", path, err)
	}
	obj := client.Bucket(bkt).Object(path).ReadCompressed(true)

	return obj.NewReader(ctx)
}
