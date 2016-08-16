package model

import (
	"bytes"
	"fmt"
	"io"
	"io/ioutil"
	"math"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
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
	ID   int64  `gae:"$id"`
	Data []byte `gae:"data,noindex"`
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

	// Data is the data in the DataEntry(s) pointed to by DataKeys.
	// After loading a TestFile from the datastore, this field is
	// only available after GetData is called. To put updated
	// data in this field to the datastore, call PutData.
	//
	// Users will typically perform the following sequence of calls
	// in a transaction:
	//
	//   ds = datastore.Get(ctx)
	//   err = ds.Get(tf)
	//   err = tf.GetData(ctx)
	//   // manipulate tf.Data
	//   err = tf.PutData(ctx)
	//   err = ds.Put(tf)
	//   err = ds.Delete(tf.OldDataKeys)
	//
	Data io.Reader `gae:"-,noindex"`

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

// GetData fetches data from the DataEntry(s) pointed to by tf.DataKeys
// and sets tf.Data to the fetched data.
func (tf *TestFile) GetData(c context.Context) error {
	ids := make([]int64, len(tf.DataKeys))
	for i, dk := range tf.DataKeys {
		ids[i] = dk.IntID() // Intentional: ignores the Kind stored in dk.
	}
	ids, err := updatedBlobKeys(c, ids...)
	if err != nil {
		return err
	}

	dataEntries := make([]*DataEntry, len(tf.DataKeys))
	for i, id := range ids {
		dataEntries[i] = &DataEntry{ID: id}
	}
	if err := datastore.Get(c).Get(dataEntries); err != nil {
		logging.Errorf(c, "failed to get DataEntry(s) for TestFile: %v: %v", tf, err)
		return err
	}

	r := make([]io.Reader, 0, len(dataEntries))
	for _, de := range dataEntries {
		r = append(r, bytes.NewReader(de.Data))
	}
	tf.Data = io.MultiReader(r...)
	return nil
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
func (tf *TestFile) PutData(c context.Context) error {
	dataKeysCopy := make([]*datastore.Key, len(tf.DataKeys))
	copy(dataKeysCopy, tf.DataKeys)

	if err := tf.putDataEntries(c); err != nil {
		return err
	}

	tf.OldDataKeys = dataKeysCopy
	return nil
}

// putDataEntries creates DataEntry(s) in the datastore for data in
// tf.Data and updates tf.LastMod and tf.DataKeys locally.
// If the returned error is non-nil, tf will be unmodified,
// except that tf.Data may have been consumed.
func (tf *TestFile) putDataEntries(c context.Context) error {
	// Maximum data entries in a TestFile.
	const maxDataEntries = 30
	// 1 megabyte is the maximum allowed blob length.
	// See https://code.googlesource.com/gocloud/+/master/datastore/prop.go#29.
	const maxBlobLen = 1 << 20

	// TODO(maybe): Read maxBlobLen bytes at a time. See io.LimitedReader.

	data, err := ioutil.ReadAll(tf.Data)
	if err != nil {
		return err
	}

	if len(data) > maxDataEntries*maxBlobLen {
		return fmt.Errorf(
			"model: data too large %d bytes (max allowed %d bytes)",
			len(data),
			maxDataEntries*maxBlobLen,
		)
	}

	// Break data into chunks of max. allowed blob length.
	numEntries := int(math.Ceil(float64(len(data)) / maxBlobLen))
	dataEntries := make([]DataEntry, 0, numEntries)
	for i := 0; i < numEntries*maxBlobLen; i += maxBlobLen {
		end := min(i+maxBlobLen, len(data))
		dataEntries = append(dataEntries, DataEntry{Data: data[i:end]})
	}

	if err := datastore.Get(c).Put(dataEntries); err != nil {
		return err
	}

	newKeys := make([]*datastore.Key, 0, len(dataEntries))
	for _, de := range dataEntries {
		newKeys = append(newKeys, datastore.Get(c).KeyForObj(&de))
	}

	tf.DataKeys = newKeys
	tf.LastMod = time.Now().UTC()
	return nil
}

// updatedBlobKeys fetches the updated blob keys for the old keys from their blobstore migration
// records. len(n) will equal len(old) if there is no error. If len(old)>1 and there is an error,
// err will be of type MultiError and the error at index i will correspond to the
// error in retrieving the updated blob key for the key at index i in old. A
// nil error indicates that all values returned in n are valid.
func updatedBlobKeys(c context.Context, old ...int64) (n []int64, err error) {
	ds := datastore.Get(c)
	type record struct {
		ID         int64  `gae:"$id"`
		Kind       string `gae:"$kind,__MigrationRecord__"`
		NewBlobKey int64  `gae:"new_blob_key"`
	}

	records := make([]*record, len(old))
	for i := range records {
		records[i] = &record{ID: old[i]}
	}

	err = ds.Get(records)
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
