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
	"strings"
	"time"

	"cloud.google.com/go/storage"
	"github.com/dustin/go-humanize"
	"golang.org/x/oauth2"
	"google.golang.org/api/googleapi"
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
	Bucket         string    // e.g. "bucket-name"
	Name           string    // e.g. "dir/dir/123456.tar.gz"
	Generation     int64     // e.g. 12312423452345
	Metageneration int64     // e.g. 12312423452345
	Created        time.Time // when it was created
	Owner          string    // FYI who uploaded it
	MD5            string    // FYI for logs only
	Metadata       *Metadata // custom metadata

	storage *Storage
}

// String returns "gs://<bucket>/<name>#<generation>" string.
func (o *Object) String() string {
	if o.Generation == 0 {
		return fmt.Sprintf("gs://%s/%s", o.Bucket, o.Name)
	}
	return fmt.Sprintf("gs://%s/%s#%d", o.Bucket, o.Name, o.Generation)
}

// Log pretty-prints fields of Object at info logging level.
func (o *Object) Log(ctx context.Context) {
	logging.Infof(ctx, "Metadata of %s", o)
	logging.Infof(ctx, "    Created:  %s", humanize.Time(o.Created))
	logging.Infof(ctx, "    Owner:    %s", strings.TrimPrefix(o.Owner, "user-"))
	logging.Infof(ctx, "    MD5:      %s", o.MD5)

	// A table with metadata sorted by key, and then timestamp.
	if o.Metadata.Empty() {
		logging.Infof(ctx, "    Metadata: none")
	} else {
		logging.Infof(ctx, "    Metadata:")
		for _, line := range strings.Split(o.Metadata.ToPretty(time.Now(), 80), "\n") {
			logging.Infof(ctx, "      %s", line)
		}
	}
}

// setAttrs populates Object field from its ObjectAttrs.
func (o *Object) setAttrs(a *storage.ObjectAttrs) {
	o.Generation = a.Generation
	o.Metageneration = a.Metageneration
	o.Created = a.Created
	o.Owner = a.Owner
	o.MD5 = hex.EncodeToString(a.MD5)
	o.Metadata = ParseMetadata(a.Metadata)
}

// New returns a Storage that uploads tarballs Google Storage.
//
// 'location' should have form "gs://<bucket>[/<path>]".
func New(ctx context.Context, ts oauth2.TokenSource, location string) (*Storage, error) {
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

// UpdateMetadata fetches existing metadata, calls 'cb' to mutate it, and pushes
// it back if it has changed.
//
// 'obj' must have come from Check or Upload. Panics otherwise.
//
// May call 'cb' multiple times if someone is updating the metadata concurrently
// with us. If 'cb' returns an error, returns exact same error as is.
func (s *Storage) UpdateMetadata(ctx context.Context, obj *Object, cb func(m *Metadata) error) error {
	if obj.storage != s {
		panic("wrong Object: not produced by this storage")
	}
	handle := s.client.Bucket(s.bucket).Object(obj.Name).Generation(obj.Generation)

	for i := 0; i < 5; i++ {
		var meta *Metadata
		var metaGen int64

		// On first iteration use whatever is in 'obj', otherwise refetch.
		if i == 0 {
			meta = obj.Metadata
			metaGen = obj.Metageneration
		} else {
			logging.Debugf(ctx, "Fetching metadata of %s...", obj)
			attrs, err := handle.Attrs(ctx)
			if err != nil {
				return err
			}
			meta = ParseMetadata(attrs.Metadata)
			metaGen = attrs.Metageneration
		}

		// Let the callback mutate a copy of 'meta'.
		updated := meta.Clone()
		if err := cb(updated); err != nil || updated.Equal(meta) {
			return err
		}

		// Do compare-and-swap of the metadata.
		logging.Debugf(ctx, "Updating metadata of %s...", obj)
		_, err := handle.If(storage.Conditions{MetagenerationMatch: metaGen}).Update(ctx, storage.ObjectAttrsToUpdate{
			Metadata: updated.Assemble(),
		})
		if e, ok := err.(*googleapi.Error); ok && e.Code == 412 {
			logging.Warningf(ctx, "Metageneration match precondition failed: %s", err)
			continue // someone updated the metadata before us, try again from scratch
		}
		return err
	}

	return errors.Reason("too many collisions, giving up").Err()
}

// object returns partially filled Object struct.
func (s *Storage) object(name string) *Object {
	return &Object{
		Bucket: s.bucket,
		Name:   path.Join(s.prefix, name), // full name inside the bucket

		storage: s,
	}
}
