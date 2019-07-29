// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package storage

import (
	"encoding/json"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/dustin/go-humanize"
)

// Metadata is an interpreted metadata dict.
//
// Cloud Storage object metadata is nominally key=>value map, but we need a
// multi-map. This is accomplished by embedding timestamps inside keys (as
// "<key>@<microsec timestamp>"). Metadata struct handled such representation.
type Metadata struct {
	d map[string][]Metadatum // key => values sorted by timestamp, most recent first
}

// Metadatum is one parsed key-value metadata pair.
type Metadatum struct {
	Key       string // key with the timestamp stripped, if it had any
	Timestamp int64  // timestamp extracted from the key or 0 if it had none
	Value     string // value associated with the key
}

// ParseMetadata convert key[@timestamp]=>value map into Metadata object.
func ParseMetadata(m map[string]string) *Metadata {
	out := Metadata{d: make(map[string][]Metadatum)}

	for k, v := range m {
		md := Metadatum{Key: k, Value: v}
		if chunks := strings.Split(k, "@"); len(chunks) == 2 {
			if ts, err := strconv.ParseInt(chunks[1], 10, 64); err == nil {
				md.Key = chunks[0]
				md.Timestamp = ts
			}
		}
		out.d[md.Key] = append(out.d[md.Key], md)
	}

	for _, vals := range out.d {
		sort.Slice(vals, func(i, j int) bool { return vals[i].Timestamp > vals[j].Timestamp })
	}

	return &out
}

// Clone returns a deep copy of 'm'.
func (m *Metadata) Clone() *Metadata {
	cpy := Metadata{d: make(map[string][]Metadatum, len(m.d))}
	for k, v := range m.d {
		cpy.d[k] = append([]Metadatum(nil), v...)
	}
	return &cpy
}

// Equal returns true if 'm' is equal to 'o'.
func (m *Metadata) Equal(o *Metadata) bool {
	if len(m.d) != len(o.d) {
		return false
	}
	for k := range m.d {
		l, r := m.d[k], o.d[k]
		if len(l) != len(r) {
			return false
		}
		for i := range l {
			if l[i] != r[i] {
				return false
			}
		}
	}
	return true
}

// Empty is true if 'm' has no entries.
func (m *Metadata) Empty() bool {
	return len(m.d) == 0
}

// Keys returns a sorted list of keys.
func (m *Metadata) Keys() []string {
	keys := make([]string, 0, len(m.d))
	for k := range m.d {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

// Values returns all values of some key, most recent first.
//
// Should not be mutated directly. If you need to modify Metadata, use Add.
// There's no way to delete entries (other than trimming old ones via Trim).
func (m *Metadata) Values(k string) []Metadatum {
	return m.d[k]
}

// Add adds (or overrides) an entry.
func (m *Metadata) Add(md Metadatum) {
	if m.d == nil {
		m.d = make(map[string][]Metadatum, 1)
	}

	v := m.d[md.Key]

	i := sort.Search(len(v), func(j int) bool { return v[j].Timestamp <= md.Timestamp })
	if i < len(v) && v[i].Timestamp == md.Timestamp {
		v[i] = md
	} else {
		v = append(v, Metadatum{})
		copy(v[i+1:], v[i:])
		v[i] = md
	}

	m.d[md.Key] = v
}

// Trim for each individual key removes oldest values until only 'keep' entries
// remain.
//
// Helps to keep metadata small by "forgetting" old entries.
func (m *Metadata) Trim(keep int) {
	for k, v := range m.d {
		if len(v) > keep {
			m.d[k] = v[:keep]
		}
	}
}

// Assemble reconstructs back the metadata map.
func (m *Metadata) Assemble() map[string]string {
	out := make(map[string]string, 0)
	for _, vals := range m.d {
		for _, v := range vals {
			if v.Timestamp != 0 {
				out[fmt.Sprintf("%s@%d", v.Key, v.Timestamp)] = v.Value
			} else {
				out[v.Key] = v.Value
			}
		}
	}
	return out
}

// ToPretty returns multi-line pretty printed contents of 'm'.
func (m *Metadata) ToPretty(now time.Time, limit int) string {
	buf := strings.Builder{}

	for _, k := range m.Keys() {
		for _, v := range m.Values(k) {
			if v.Timestamp == 0 {
				buf.WriteString(k)
				buf.WriteRune(':')
			} else {
				fmt.Fprintf(&buf, "%s (%s):", k,
					humanize.RelTime(time.Unix(0, v.Timestamp*1000), now, "ago", "from now"))
			}
			if len(v.Value) < limit {
				// Inline short-ish values.
				buf.WriteRune(' ')
				buf.WriteString(v.Value)
				buf.WriteRune('\n')
			} else {
				// Split long ones into multiple lines.
				buf.WriteRune('\n')
				for _, line := range strings.Split(prettifyJSON(v.Value), "\n") {
					buf.WriteString("  ")
					buf.WriteString(line)
					buf.WriteRune('\n')
				}
			}
		}
	}

	return buf.String()
}

// prettifyJSON attempts to reformat 'v' as multi-line JSON object.
func prettifyJSON(v string) string {
	var obj map[string]interface{}
	if err := json.Unmarshal([]byte(v), &obj); err != nil {
		return v // give up
	}
	if blob, err := json.MarshalIndent(&obj, "", "  "); err == nil {
		return string(blob)
	}
	return v // give up
}
