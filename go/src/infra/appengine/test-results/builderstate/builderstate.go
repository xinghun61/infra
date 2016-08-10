// Package builderstate provides methods to get and set
// builder state data and update last modified times for builders.
package builderstate

import (
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/memcache"
	"golang.org/x/net/context"

	"infra/appengine/test-results/model"
)

// PythonISOTimeFormat is the time format used by
// Python's datetime.isoformat().
// Used to maintain compatibility with external code that
// depends on time being formatted in this format.
const PythonISOTimeFormat = "2006-01-02T15:04:05.999999"

// MemcacheKey is the memcache key for builder state data.
const MemcacheKey = "builder_state"

// BuildbotMemcacheKey is the memcache key for build extracts data.
const BuildbotMemcacheKey = "buildbot_data"

// BuilderState represents the state of builders.
type BuilderState struct {
	Masters           []Master `json:"masters"`
	NoUploadTestTypes []string `json:"no_upload_test_types"`
}

// Master represents details about a build master.
type Master struct {
	Groups     []string         `json:"groups"`
	Name       string           `json:"name"`
	Identifier string           `json:"url_name"`
	Tests      map[string]*Test `json:"tests"`
}

// Test is details about a test step.
type Test struct {
	// Builders is a map from builder name to last updated time.
	Builders map[string]time.Time `json:"-"`
}

// MarshalJSON marshals t to JSON bytes.
// Zero time.Time values in t.Builders field are encoded as null.
// Otherwise time.Time values are formatted as PythonISOTimeFormat
// and encoded as strings.
func (t *Test) MarshalJSON() ([]byte, error) {
	aux := struct {
		Builders map[string]*string `json:"builders"`
	}{make(map[string]*string)}

	for name, timestamp := range t.Builders {
		if timestamp.IsZero() {
			aux.Builders[name] = nil
			continue
		}
		str := timestamp.Format(PythonISOTimeFormat)
		aux.Builders[name] = &str
	}

	return json.Marshal(aux)
}

// UnmarshalJSON unmarshals the supplied JSON bytes into t.
//
// The "builders" key in the JSON decodes into t.Builders.
// The value of the "builders" key in the JSON should be either:
//
//    - Object<string, string>
//    - Array<string>
//
// If it is Object<string, string>, keys in the JSON object are the
// keys in t.Builders. Non-null values in the JSON object are parsed as
// time.Time using PythonISOTimeFormat. Null values in the JSON are
// decoded as zero time.Time.
//
// If it is Array<string>, each string in the JSON array is a key in
// t.Builders and the values in t.Builders are all zero time.Time.
func (t *Test) UnmarshalJSON(b []byte) error {
	aux := struct {
		Builders map[string]*string `json:"builders"`
	}{}
	err := json.Unmarshal(b, &aux)

	if err == nil {
		timeMap := make(map[string]time.Time, len(aux.Builders))
		for k, v := range aux.Builders {
			if v == nil {
				timeMap[k] = time.Time{}
				continue
			}
			t, e := time.Parse(PythonISOTimeFormat, *v)
			if e != nil {
				return e
			}
			timeMap[k] = t
		}
		t.Builders = timeMap
		return nil
	}

	aux2 := struct {
		Builders []string `json:"builders"`
	}{}
	err = json.Unmarshal(b, &aux2)

	if err == nil {
		t.Builders = make(map[string]time.Time, len(aux2.Builders))
		for _, name := range aux2.Builders {
			t.Builders[name] = time.Time{}
		}
		return nil
	}

	return err
}

// lastUpdated returns the last modified time of the
// "full_results.json" matching the supplied arguments.
func lastUpdated(c context.Context, master, builder, testType string) (t time.Time, e error) {
	p := model.TestFileParams{
		Master:   master,
		Builder:  builder,
		TestType: testType,
		Name:     "full_results.json",
		Limit:    1,
	}
	q := p.Query()

	var tfs []*model.TestFile
	if err := datastore.Get(c).GetAll(q, &tfs); err != nil {
		return time.Time{}, err
	}
	if len(tfs) == 0 {
		return time.Time{}, errors.New("no TestFile for query")
	}
	return tfs[0].LastMod, nil
}

// setLastUpdated sets the last updated time for each builder.
func (bs *BuilderState) setLastUpdated(c context.Context) error {
	for _, m := range bs.Masters {
		for testType, test := range m.Tests {
			timeMap := make(map[string]time.Time, len(test.Builders))
			for name := range test.Builders {
				t, err := lastUpdated(c, m.Identifier, name, testType)
				if err != nil {
					timeMap[name] = time.Time{}
					continue
				}
				timeMap[name] = t.UTC()
			}
			test.Builders = timeMap
			m.Tests[testType] = test
		}
	}
	return nil
}

// RefreshCache refreshes the data in memcache with latest
// from the build extracts memcache. The last updated time
// for each builder is set if known, otherwise it is set to
// zero time.Time.
//
// If the returned error is nil, the returned memcache.Item will
// contain the new data.
func RefreshCache(c context.Context) (memcache.Item, error) {
	item, err := memcache.Get(c).Get(BuildbotMemcacheKey)
	if err != nil {
		return nil, err
	}

	var bs BuilderState
	if err := json.Unmarshal(item.Value(), &bs); err != nil {
		return nil, err
	}
	if err := bs.setLastUpdated(c); err != nil {
		return nil, err
	}

	b, err := json.Marshal(&bs)
	if err != nil {
		return nil, err
	}

	newItem := memcache.Get(c).NewItem(MemcacheKey)
	newItem.SetValue(b)
	_ = memcache.Get(c).Set(newItem) // Ignore error: not critical to this function.
	return newItem, nil
}

// Update sets the last modified time to the supplied time
// for the builder that corresponds to the supplied arguments
// in memcache.
//
// If an error occurs when getting the item from memcache,
// the error is returned and the function has no effect.
func Update(c context.Context, master, builder, testType string, modified time.Time) error {
	item, err := memcache.Get(c).Get(MemcacheKey)
	if err != nil {
		return err
	}

	var bs BuilderState
	if err := json.Unmarshal(item.Value(), &bs); err != nil {
		return err
	}

	// Get master.

	idx := -1
	for i, m := range bs.Masters {
		if m.Identifier == master {
			idx = i
			break
		}
	}
	if idx == -1 {
		return fmt.Errorf("builderstate: master %q not found", master)
	}

	// Get testType.

	test, ok := bs.Masters[idx].Tests[testType]
	if !ok {
		return fmt.Errorf("builderstate: testType %q in master %q not found", testType, master)
	}

	// Update builder.

	test.Builders[builder] = modified.UTC()

	// Set in memcache.

	b, err := json.Marshal(&bs)
	if err != nil {
		return err
	}
	item.SetValue(b)
	return memcache.Get(c).CompareAndSwap(item)
}
