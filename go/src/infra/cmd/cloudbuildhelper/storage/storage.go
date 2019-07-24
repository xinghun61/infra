// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package storage wraps Google Storage routines into a simpler interface.
package storage

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"net/url"
	"path"
	"sort"
	"strings"
	"time"

	"cloud.google.com/go/storage"
	"github.com/dustin/go-humanize"
	"golang.org/x/oauth2"
	"google.golang.org/api/option"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
)

// Storage knows how to upload tarballs to a predefined Google Storage prefix.
type Storage struct {
	bucket string // e.g. "bucket"
	prefix string // e.g. "dir/dir" or even just ""
	client *storage.Client
}

// Object is a pointer to a concrete version of a file in Google Storage,
// along with its custom metadata.
type Object struct {
	Bucket     string            // e.g. "bucket-name"
	Name       string            // e.g. "dir/dir/123456.tar.gz"
	Generation int64             // e.g. 12312423452345
	Created    time.Time         // when it was created
	Owner      string            // FYI who uploaded it
	MD5        string            // FYI for logs only
	Metadata   map[string]string // custom metadata
}

// String return gs://... string.
func (o *Object) String() string {
	return fmt.Sprintf("gs://%s/%s", o.Bucket, o.Name)
}

// Log logs all fields of Object at info level.
func (o *Object) Log(ctx context.Context) {
	logging.Infof(ctx, "Metadata of %s", o)
	logging.Infof(ctx, "    Generation: %d", o.Generation)
	logging.Infof(ctx, "    Created:    %s", o.Created)
	logging.Infof(ctx, "    Owner:      %s", strings.TrimPrefix(o.Owner, "user-"))
	logging.Infof(ctx, "    MD5:        %s", o.MD5)
	if len(o.Metadata) != 0 {
		logging.Infof(ctx, "    Metadata:")
		keys := make([]string, 0, len(o.Metadata))
		for k := range o.Metadata {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			logging.Infof(ctx, "        %s: %q", k, o.Metadata[k])
		}
	} else {
		logging.Infof(ctx, "    Metadata:   none")
	}
}

// setAttrs populates Object field from its ObjectAttrs.
func (o *Object) setAttrs(a *storage.ObjectAttrs) {
	o.Generation = a.Generation
	o.Created = a.Created
	o.Owner = a.Owner
	o.MD5 = hex.EncodeToString(a.MD5)
	o.Metadata = a.Metadata
}

// New returns a Storage that uploads tarballs Google Storage.
//
// 'location' should have form "gs://<bucket>[/<path>]".
func New(ctx context.Context, location string, ts oauth2.TokenSource) (*Storage, error) {
	url, err := url.Parse(location)
	if err != nil {
		return nil, errors.Annotate(err, "bad format in %q", location).Err()
	}
	if url.Scheme != "gs" {
		return nil, errors.Reason("expecting gs:// storage, got %q", location).Err()
	}
	client, err := storage.NewClient(ctx, option.WithTokenSource(ts))
	if err != nil {
		return nil, errors.Annotate(err, "failed to initialize storage.Client").Err()
	}
	return &Storage{
		bucket: url.Host,
		prefix: strings.Trim(url.Path, "/"),
		client: client,
	}, nil
}

// Check fetches information about existing Google Storage object.
//
// Returns:
//   (*Object, nil) if such object already exists.
//   (nil, nil) if such object doesn't exist.
//   (nil, error) on errors.
func (s *Storage) Check(ctx context.Context, name string) (*Object, error) {
	obj := s.object(name)
	logging.Infof(ctx, "Checking presence of %s...", obj)

	switch attrs, err := s.client.Bucket(s.bucket).Object(obj.Name).Attrs(ctx); {
	case err == storage.ErrObjectNotExist:
		return nil, nil
	case err != nil:
		return nil, errors.Annotate(err, "failed to check object attrs").Err()
	default:
		obj.setAttrs(attrs)
		return obj, nil
	}
}

// Upload uploads the tarball with the given hex SHA256 digest to the storage.
//
// Its body is produced by 'r' and the Storage will double check that the body
// matches the digest. On mismatch the upload operation is abandoned (i.e.
// the bucket is left unchanged).
//
// The object is named as "<prefix>/<name>", where <prefix> is taken from
// <location> passed to New(...) when the Storage was initialized.
//
// Unconditionally overwrites an existing object, if any. Doesn't try to set
// any ACLs. The bucket must exist already.
//
// Respects context deadlines and cancellation. On success returns a pointer to
// the uploaded object (including its generation number).
func (s *Storage) Upload(ctx context.Context, name, digest string, r io.Reader) (*Object, error) {
	ctx, abort := context.WithCancel(ctx)
	defer abort()

	obj := s.object(name)

	wr := s.client.Bucket(s.bucket).Object(obj.Name).NewWriter(ctx)
	wr.ContentType = "application/x-tar"
	wr.ProgressFunc = func(offset int64) { logging.Infof(ctx, "... uploaded %s", humanize.Bytes(uint64(offset))) }

	// Note: per storage.Writer doc, to abandon an upload all we need to do is
	// to cancel the underlying context (which we do in 'defer'). So it is
	// sufficient just to exit this function on errors. Note that calling Close()
	// will create (perhaps incomplete) Google Storage object. We don't want that.

	logging.Infof(ctx, "Uploading to %s...", obj)

	h := sha256.New()
	if _, err := io.Copy(io.MultiWriter(wr, h), r); err != nil {
		return nil, errors.Annotate(err, "upload failed").Err()
	}
	if got := hex.EncodeToString(h.Sum(nil)); got != digest {
		return nil, errors.Reason("digest of uploaded data is %q, expecting %q; did the file change on disk?", got, digest).Err()
	}

	// This actually materializes the Google Storage object.
	if err := wr.Close(); err != nil {
		return nil, errors.Annotate(err, "failed to finalize the upload").Err()
	}

	// Attrs() are available only after successful Close().
	obj.setAttrs(wr.Attrs())
	return obj, nil
}

// object returns partially filled Object struct.
func (s *Storage) object(name string) *Object {
	return &Object{
		Bucket: s.bucket,
		Name:   path.Join(s.prefix, name), // full name inside the bucket
	}
}
