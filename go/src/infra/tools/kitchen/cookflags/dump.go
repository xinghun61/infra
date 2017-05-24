// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package cookflags

import (
	"fmt"
	"sort"
)

type flagDumper []string

func (f *flagDumper) str(name, val string) {
	f.strDefault(name, val, "")
}

func (f *flagDumper) strDefault(name, val, dflt string) {
	if val != dflt {
		*f = append(*f, "-"+name, val)
	}
}

func (f *flagDumper) list(name string, vals []string) {
	arg := "-" + name
	for _, v := range vals {
		*f = append(*f, arg, v)
	}
}

func (f *flagDumper) stringMap(name string, vals map[string]string) {
	if len(vals) > 0 {
		arg := "-" + name
		keys := make([]string, 0, len(vals))
		for k := range vals {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			v := vals[k]
			if v == "" {
				*f = append(*f, arg, k)
			} else {
				*f = append(*f, arg, fmt.Sprintf("%s=%s", k, v))
			}
		}
	}
}

func (f *flagDumper) boolean(name string, val bool) {
	if val {
		*f = append(*f, "-"+name)
	}
}
