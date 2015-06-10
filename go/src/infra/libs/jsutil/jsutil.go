// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package jsutil

import (
	"fmt"
)

// Get is like GetError, except that if GetError would return an error, this
// function panics instead.
func Get(data interface{}, pathElems ...interface{}) interface{} {
	r, err := GetError(data, pathElems...)
	if err != nil {
		panic(err)
	}
	return r
}

// GetError retrieves a value from a 'jsonish' data object, given a path to
// follow.
//
// data is assumed to be either a map[string]interface{}, or a []interface{}.
//
// pathElems should either be strings or int's. Any other type will cause a
// panic. So don't do it.
//
// A pathElem of a string implies that GetError should expect a map at that
// location in the jsonish data. An int implies that it should expect a list.
// If this expectation is false, an error is returned.
//
// If you attempt to index into a list such that the index is out of bounds,
// you'll get a panic just like if you passed an index to a slice that was out
// of bounds.
//
// Accessing a map key which doesn't exist will return nil.
//
// Example:
//   data = {
//     "some": [
//       {"nested": {"value": 10}}
//     ]
//   }
//
//   GetError(data, "some") #=> [{"nested":...}]
//   GetError(data, "some", 0) #=> {"nested":...}
//   GetError(data, "some", 0, "nested") #=> {"value": 10}
//   GetError(data, "some", 0, "nested", "value") #=> 10
//   GetError(data, "wat") #=> nil
//   GetError(data, "wat", "something") #=> panic(nil deref)
//   GetError(data, "some", 1) #=> panic(out of bounds)
func GetError(data interface{}, pathElems ...interface{}) (interface{}, error) {
	for len(pathElems) > 0 {
		idx := pathElems[0]
		pathElems = pathElems[1:]
		switch i := idx.(type) {
		case int:
			d, ok := data.([]interface{})
			if !ok {
				return nil, fmt.Errorf("jsutil.GetError: expected []interface{}, but got %T", data)
			}
			data = d[i]
		case string:
			d, ok := data.(map[string]interface{})
			if !ok {
				return nil, fmt.Errorf("jsutil.GetError: expected map[string]interface{}, but got %T", data)
			}
			data = d[i]
		default:
			return nil, fmt.Errorf("jsutil.GetError: expected string or int in pathElems, got %T instead", idx)
		}
	}
	return data, nil
}
