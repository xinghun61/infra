// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package logstore

import (
	"compress/gzip"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"io"
	"path"

	"cloud.google.com/go/storage"
	"google.golang.org/appengine/file"
)

// Upload uploads data to logstore and returns logPath.
// data will be compressed.
func Upload(ctx context.Context, prefix string, data []byte) (_ string, rerr error) {
	closeCloser := func(c io.Closer) {
		err := c.Close()
		if rerr == nil {
			rerr = err
		}
	}

	client, err := storage.NewClient(ctx)
	if err != nil {
		return "", fmt.Errorf("failed to create storage client: %v", err)
	}
	defer closeCloser(client)

	bkt, err := file.DefaultBucketName(ctx)
	if err != nil {
		return "", fmt.Errorf("failed to get DefaultBucketName: %v", err)
	}

	hd := sha256.Sum256(data)
	h := base64.URLEncoding.EncodeToString(hd[:])
	logPath := path.Join("upload", fmt.Sprintf("%s.%s.gz", prefix, h))

	w := client.Bucket(bkt).Object(logPath).NewWriter(ctx)
	defer closeCloser(w)

	// no need to set content-encoding?
	// with this, uploaded file get error "gzip: invalid header".
	// https://bugs.chromium.org/p/chromium/issues/detail?id=1007149
	// w.ContentEncoding = "gzip"

	gw := gzip.NewWriter(w)
	defer closeCloser(gw)

	_, err = gw.Write(data)
	if err != nil {
		return "", fmt.Errorf("failed to write data: %v", err)
	}

	return logPath, nil
}
