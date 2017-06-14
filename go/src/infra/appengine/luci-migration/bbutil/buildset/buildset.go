// Package buildset can parse a buildset.
package buildset

import (
	"fmt"
	"strconv"
	"strings"
)

// RietveldPatchset is Rietveld patchset.
type RietveldPatchset struct {
	Hostname string
	Issue    int64
	Patchset int64
}

// URL returns patchset URL.
func (p *RietveldPatchset) URL() string {
	return fmt.Sprintf("https://%s/%d/#ps%d", p.Hostname, p.Issue, p.Patchset)
}

// GerritPatchset is a Gerrit patchset.
type GerritPatchset struct {
	Hostname string
	Change   int64
	Patchset int64
}

// URL returns patchset URL.
func (p *GerritPatchset) URL() string {
	return fmt.Sprintf("https://%s/c/%d/%d", p.Hostname, p.Change, p.Patchset)
}

// BuildSet is a parsed buildset.
type BuildSet struct {
	Rietveld *RietveldPatchset
	Gerrit   *GerritPatchset
}

// URL returns URL-form of b if possible, otherwise "".
func (b *BuildSet) URL() string {
	switch {
	case b == nil:
		return ""
	case b.Rietveld != nil:
		return b.Rietveld.URL()
	case b.Gerrit != nil:
		return b.Gerrit.URL()
	default:
		return ""
	}
}

// Parse parses a buildSet string.
// Returns nil if unrecognized.
func Parse(buildSet string) *BuildSet {
	parts := strings.Split(buildSet, "/")
	if len(parts) >= 5 && parts[0] == "patch" {
		change, changeErr := strconv.ParseInt(parts[3], 10, 64)
		patch, patchErr := strconv.ParseInt(parts[4], 10, 64)
		if changeErr == nil && patchErr == nil {
			switch parts[1] {
			case "rietveld":
				return &BuildSet{
					Rietveld: &RietveldPatchset{
						Hostname: parts[2],
						Issue:    change,
						Patchset: patch,
					},
				}
			case "gerrit":
				return &BuildSet{
					Gerrit: &GerritPatchset{
						Hostname: parts[2],
						Change:   change,
						Patchset: patch,
					},
				}
			}
		}
	}
	return nil
}
