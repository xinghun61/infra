package model

import (
	"bytes"
	"fmt"
	"io"
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

// buildNum is needed to handle TestFile records with nil build_number.
type buildNum int64

func (b *buildNum) Nil() bool { return *b == -1 }

func (b *buildNum) ToProperty() (p datastore.Property, err error) {
	if b.Nil() {
		return
	}
	p = datastore.MkProperty(*b)
	return
}

func (b *buildNum) FromProperty(p datastore.Property) error {
	switch p.Type() {
	case datastore.PTNull:
		*b = -1
	case datastore.PTInt:
		*b = buildNum(p.Value().(int64))
	default:
		return fmt.Errorf("wrong type for property: %s", p.Type())
	}
	return nil
}

var _ datastore.PropertyConverter = (*buildNum)(nil)

// DataEntry represents a DataEntry record.
type DataEntry struct {
	ID   int64  `gae:"$id"`
	Data []byte `gae:"data,noindex"`
}

// TestFile represents a TestFile record.
type TestFile struct {
	ID          int64            `gae:"$id"`
	BuildNumber buildNum         `gae:"build_number"`
	Builder     string           `gae:"builder"`
	DataKeys    []*datastore.Key `gae:"data_keys,noindex"`
	LastMod     time.Time        `gae:"date"`
	Master      string           `gae:"master"`
	Name        string           `gae:"name"`
	NewDataKeys []*datastore.Key `gae:"new_data_keys,noindex"`
	TestType    string           `gae:"test_type"`

	// Data is the data in the DataEntry(s) pointed to by DataKeys.
	//
	// After loading a TestFile from the datastore, this field is
	// only available after GetData is called.
	//
	// PutData must be called to persist the contents of this field to
	// the datastore DataEntry(s) pointed to by DataKeys.
	Data io.Reader `gae:"-,noindex"`
}

// GetData fetches data from the DataEntry(s) pointed to by tf.DataKeys
// and updated tf.Data.
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

// TestFileQueryParams represents the parameters in a TestFile query.
//
// If a field has a zero value, a default value is used to make the query
// or the constraint is omitted from the query.
type TestFileQueryParams struct {
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
func (p *TestFileQueryParams) Query() *datastore.Query {
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
		// TODO(nishanths): This fails due to lack of index in Python app and
		// here.
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

func min(a, b int32) int32 {
	if a < b {
		return a
	}
	return b
}
