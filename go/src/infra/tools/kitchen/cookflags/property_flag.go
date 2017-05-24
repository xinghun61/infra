// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package cookflags

import (
	"encoding/json"
	"flag"
)

// PropertyFlag parses a
type PropertyFlag map[string]interface{}

var _ flag.Value = (*PropertyFlag)(nil)

// Set implements flag.Value.
func (p *PropertyFlag) Set(v string) error {
	return json.Unmarshal([]byte(v), p)
}

func (p PropertyFlag) String() string {
	if p == nil {
		return ""
	}
	data, err := json.Marshal(p)
	if err != nil {
		panic(err)
	}
	return string(data)
}
