// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

import (
	"fmt"
	"io"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
)

// IsAggregateTestFile returns whether filename is that of an aggregate test file.
func IsAggregateTestFile(filename string) bool {
	switch filename {
	case "results.json", "results-small.json":
		return true
	default:
		return false
	}
}

// BuildNum is int64 that is used to handle TestFile datastore records
// with null build_number. The value is >= 0 if the datastore value
// was not null. The value is -1 for null datastore value.
type BuildNum int64

var _ datastore.PropertyConverter = (*BuildNum)(nil)

// 1 megabyte is the maximum allowed length for a datastore
// entity. But use a smaller value because App Engine errors
// when we get close to the limit.
// See https://code.googlesource.com/gocloud/+/master/datastore/prop.go#29.
var datastoreBlobLimit = (1 << 20) - 2048

// IsNil returns whether b had null value in datastore.
func (b *BuildNum) IsNil() bool { return *b == -1 }

// ToProperty is for implementing datastore.PropertyConverter.
func (b *BuildNum) ToProperty() (p datastore.Property, err error) {
	if b.IsNil() {
		return
	}
	p = datastore.MkProperty(*b)
	return
}

// FromProperty is for implementing datastore.PropertyConverter.
func (b *BuildNum) FromProperty(p datastore.Property) error {
	switch p.Type() {
	case datastore.PTNull:
		*b = -1
	case datastore.PTInt:
		*b = BuildNum(p.Value().(int64))
	default:
		return fmt.Errorf("wrong type for property: %s", p.Type())
	}
	return nil
}

// DataEntry represents a DataEntry record.
type DataEntry struct {
	ID      int64     `gae:"$id"`
	Data    []byte    `gae:"data,noindex"`
	Created time.Time `gae:"created"`
}

// TestFile represents a TestFile record.
type TestFile struct {
	ID          int64    `gae:"$id"`
	BuildNumber BuildNum `gae:"build_number"`
	Builder     string   `gae:"builder"`
	Master      string   `gae:"master"`
	Name        string   `gae:"name"`
	TestType    string   `gae:"test_type"`

	// DataKeys is the keys to the DataEntry(s) that contain
	// the data for this TestFile.
	DataKeys []*datastore.Key `gae:"data_keys,noindex"`

	// LastMod is the last modified time.
	LastMod time.Time `gae:"date"`

	// OldDataKeys is the keys of the old DataEntry(s) used
	// before putting the new data. This field is set after a
	// successful call to PutData.
	//
	// Users are responsible for deleting the DataEntry(s)
	// pointed to by these keys if they are no longer needed.
	OldDataKeys []*datastore.Key `gae:"-,noindex"`

	// NewDataKeys is UNUSED in this implementation. It is
	// a remnant of the old Python implementation.
	NewDataKeys []*datastore.Key `gae:"new_data_keys,noindex"`
}

// DataReader fetches data from the DataEntry(s) pointed to by tf.DataKeys
// and sets tf.Data to the fetched data.
func (tf *TestFile) DataReader(c context.Context) (io.Reader, error) {
	ids := make([]int64, len(tf.DataKeys))
	for i, dk := range tf.DataKeys {
		ids[i] = dk.IntID() // Intentional: ignores the Kind stored in dk.
	}
	ids, err := updatedBlobKeys(c, ids...)
	if err != nil {
		return nil, err
	}

	keys := make([]*datastore.Key, len(ids))
	for i, id := range ids {
		de := &DataEntry{ID: id}
		keys[i] = datastore.KeyForObj(c, de)
	}

	return &dataEntryReader{
		Context: c,
		keys:    keys,
	}, nil
}

// PutData puts the contents of tf.Data to DataEntry(s) in the datastore
// and updates tf.LastMod and tf.DataKeys locally.
//
// datastore.Put(tf) should be called after PutData to put the
// the updated tf.LastMod and tf.DataKeys fields to the datastore.
// PutData does has no effect on the old DataEntry(s).
// tf.OldDataKeys will be modified only if PutData returns a non-nil
// error.
//
// It is safe to call PutData within a transaction: tf.DataKeys will
// point to the DataEntry(s) created in the successful attempt, and
// tf.LastMod will equal the time of the successful attempt.
func (tf *TestFile) PutData(c context.Context, dataFunc func(io.Writer) error) error {
	dataKeysCopy := make([]*datastore.Key, len(tf.DataKeys))
	copy(dataKeysCopy, tf.DataKeys)

	if err := tf.putDataEntries(c, dataFunc); err != nil {
		return err
	}

	tf.OldDataKeys = dataKeysCopy
	return nil
}

// putDataEntries creates DataEntry(s) in the datastore for data in
// tf.Data and updates tf.LastMod and tf.DataKeys locally.
// If the returned error is non-nil, tf will be unmodified,
// except that tf.Data may have been consumed.
func (tf *TestFile) putDataEntries(c context.Context, dataFunc func(io.Writer) error) error {
	var keys []*datastore.Key
	r, w := io.Pipe()
	err := parallel.RunMulti(c, 0, func(mr parallel.MultiRunner) error {
		return mr.RunMulti(func(workC chan<- func() error) {
			// Encode our data to the "writer" end of a pipe. We will read the data from
			// the pipe and load it into datastore.
			workC <- func() error {
				defer w.Close()

				if err := dataFunc(w); err != nil {
					logging.WithError(err).Errorf(c, "Failed to write TestFile data.")
					return err
				}
				return nil
			}

			// Ferry the data from the read end of the pipe into Datastore.
			workC <- func() (err error) {
				defer r.Close()

				keys, err = writeDataEntries(c, r)
				if err != nil {
					logging.WithError(err).Errorf(c, "Failed to write data entries.")
				}
				return
			}
		})
	})
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to create DataEntry entries.")

		// Best effort: delete any keys that were created.
		if len(keys) > 0 {
			if derr := datastore.Delete(c, keys); derr != nil {
				logging.Fields{
					logging.ErrorKey: derr,
					"count":          len(keys),
				}.Warningf(c, "Failed to delete DataEntry keys on failure.")
			}
		}
		return err
	}

	// We should never have zero keys (minimum JSON should result in some data).
	if len(keys) == 0 {
		panic(errors.New("zero keys generated for entry"))
	}

	tf.DataKeys = keys
	tf.LastMod = clock.Get(c).Now().UTC()
	return nil
}

func writeDataEntries(c context.Context, r io.Reader) ([]*datastore.Key, error) {

	// This may write a lot of entries, and so we do NOT want a transactional
	// datastore handle here. This is fine, since each DataEntry will be a new
	// auto-generated ID, so there will not be any conflicts.
	c = datastore.WithoutTransaction(c)

	// Read data from "r" one blob at a time.
	buf := make([]byte, datastoreBlobLimit)

	finished := false

	var dataEntries []*DataEntry

	for !finished {
		// Read as much as possible into "buf". If we read any data, add another
		// DataEntry and keep reading.
		count, err := io.ReadFull(r, buf)
		switch err {
		case io.EOF, io.ErrUnexpectedEOF:
			finished = true

		case nil:
			break

		default:
			// Actual Reader error.
			logging.WithError(err).Errorf(c, "Failed to read from Reader.")
			return nil, err
		}

		if count > 0 {
			copied := make([]byte, count)
			copy(copied, buf[:count])
			dataEntries = append(dataEntries,
				&DataEntry{
					Data:    copied,
					Created: clock.Get(c).Now().UTC(),
				})
		}
	}

	keys := make([]*datastore.Key, len(dataEntries))

	const datastorePutWokers = 16

	err := parallel.WorkPool(datastorePutWokers, func(workC chan<- func() error) {
		for i, dataEntry := range dataEntries {
			dataEntry := dataEntry
			i := i
			workC <- func() error {
				err := datastore.Put(c, dataEntry)
				if err != nil {
					logging.WithError(err).Errorf(c, "Failed to put DataEntry #%d.", i)
					return err
				}

				logging.Fields{
					"index": i,
					"size":  len(dataEntry.Data),
					"id":    dataEntry.ID,
				}.Debugf(c, "Added data entry.")
				keys[i] = datastore.KeyForObj(c, dataEntry)
				return nil
			}
		}
	})

	return keys, err
}

// updatedBlobKeys fetches the updated blob keys for the old keys from their blobstore migration
// recordatastore. len(n) will equal len(old) if there is no error. If len(old)>1 and there is an error,
// err will be of type MultiError and the error at index i will correspond to the
// error in retrieving the updated blob key for the key at index i in old. A
// nil error indicates that all values returned in n are valid.
func updatedBlobKeys(c context.Context, old ...int64) (n []int64, err error) {
	type record struct {
		ID         int64  `gae:"$id"`
		Kind       string `gae:"$kind,__MigrationRecord__"`
		NewBlobKey int64  `gae:"new_blob_key"`
	}

	records := make([]*record, len(old))
	for i := range records {
		records[i] = &record{ID: old[i]}
	}

	err = datastore.Get(c, records)
	errs, isMultiError := err.(errors.MultiError)

	switch {
	case err == nil:
		// New blob keys for all IDs.
		ret := make([]int64, len(records))
		for i, r := range records {
			ret[i] = r.NewBlobKey
		}
		return ret, nil

	case err == datastore.ErrNoSuchEntity:
		// len(old)==1 and no new blob key.
		return []int64{old[0]}, nil

	case isMultiError:
		ret := make([]int64, len(records))
		for i, r := range records {
			switch errs[i] {
			case nil:
				ret[i] = r.NewBlobKey
			case datastore.ErrNoSuchEntity:
				// No new blob key.
				ret[i] = old[i]
				errs[i] = nil
			}
		}
		hasErr := false
		for i, e := range errs {
			if e != nil {
				hasErr = true
				logging.Errorf(c, "failed to fetch updated blob key: %v: %v", old[i], err)
			}
		}
		if hasErr {
			return ret, errs
		}
		return ret, nil

	default:
		logging.Errorf(c, "failed to fetch updated blob keys: %v: %v", old, err)
		return nil, err
	}
}

// TestFileParams represents the parameters in a TestFile query.
type TestFileParams struct {
	Master            string
	Builder           string
	Name              string
	TestType          string
	BuildNumber       *int
	OrderBuildNumbers bool // Whether to order build numbers by latest.
	Before            time.Time

	// Limit is the limit on the query. If the value is negative or greater
	// than the default limit, the default limit will be used instead.
	Limit int32
}

// Query generates a datastore query for the parameters.
// If a field in p is the zero value, a default value is used in the query
// or the constraint is omitted from the query.
func (p *TestFileParams) Query() *datastore.Query {
	const defaultLimit int32 = 100

	setNonEmpty := func(q *datastore.Query, prop, value string) *datastore.Query {
		if value != "" {
			return q.Eq(prop, value)
		}
		return q
	}

	q := datastore.NewQuery("TestFile")
	q = setNonEmpty(q, "master", p.Master)
	q = setNonEmpty(q, "builder", p.Builder)
	q = setNonEmpty(q, "name", p.Name)
	q = setNonEmpty(q, "test_type", p.TestType)

	if p.BuildNumber != nil {
		q = q.Eq("build_number", *p.BuildNumber)
	}
	if p.OrderBuildNumbers {
		// TODO(nishanths): This fails due to lack of index in both the Python
		// application and in this application.
		q = q.Order("-build_number")
	}

	if !p.Before.IsZero() {
		q = q.Lt("date", p.Before)
	}
	q = q.Order("-date")

	if p.Limit < 0 || p.Limit > defaultLimit {
		q = q.Limit(defaultLimit)
	} else {
		q = q.Limit(p.Limit)
	}

	return q
}

// dataEntryReader is an io.Reader that reads from sequential DataEntry.
type dataEntryReader struct {
	context.Context

	keys    []*datastore.Key
	current []byte
}

func (r *dataEntryReader) Read(buf []byte) (int, error) {
	count := 0
	for len(buf) > 0 {
		// Do we have current data?
		if len(r.current) > 0 {
			// Yes, load its remaining data into "buf".
			amount := copy(buf, r.current)
			buf, r.current = buf[amount:], r.current[amount:]
			count += amount
			continue
		}

		// No. Load the next blob from datastore.
		if len(r.keys) == 0 {
			// No more keys, so no more data.
			return count, io.EOF
		}

		de := &DataEntry{}
		if !datastore.PopulateKey(de, r.keys[0]) {
			return count, errors.Reason("failed to populate object key").Err()
		}

		logging.Debugf(r, "Read loading DataEntry ID: %v", de.ID)
		if err := datastore.Get(r, de); err != nil {
			return count, errors.Annotate(err, "failed to load DataEntry object").Err()
		}

		// Entry loaded. Re-enter our read loop.
		r.keys = r.keys[1:]
		r.current = de.Data
	}

	return count, nil
}
