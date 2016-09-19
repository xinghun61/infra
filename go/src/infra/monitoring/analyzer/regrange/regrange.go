package regrange

// package regrange is responsible for the regression range analysis logic
// in the analyzer package. Separated into its own package for simpler testing.

import (
	"fmt"
	"sort"
	"strings"

	"infra/monitoring/messages"
)

// URLToNameMapping is a mapping of URL to project name.
var URLToNameMapping = map[string]string{
	"https://chromium.googlesource.com/chromium/src": "chromium",
}

func getNameForURL(URL string) string {
	URL = strings.TrimRight(URL, "/")
	if strings.HasSuffix(URL, ".git") {
		URL = URL[:len(URL)-len(".git")]
	}

	name := URLToNameMapping[URL]
	if name != "" {
		return name
	}

	return "unknown"
}

// Finder is a function which finds regression ranges for a given build.
type Finder func(build *messages.Build) []*messages.RegressionRange

/* FIXME: Re-enable v8 and nacl revision range tracking
* builder_alerts detects revision changes in a different manner than we do.
* It would be fairly complicated to rework how we analyze it, and it's not
* that important to track explicit v8 and nacl revisions. Their rolls are
* included in the chromium regression range anyways, so sheriffs will see the
* changes; it just won't be presented in as nice of a manner.
* See https://crbug.com/647752 for more information.
**/

// Default returns the regression ranges this build contains. It is the default
// Finder provided by package regrange.
func Default(build *messages.Build) []*messages.RegressionRange {
	regRanges := []*messages.RegressionRange(nil)

	revisionsByRepo := map[string][]string{}
	positionsByRepo := map[string][]string{}

	// TODO(seanmccullough):  Nix this? It adds a lot to the alerts json size.
	// Consider posting this information to a separate endpoint.
	for _, change := range build.SourceStamp.Changes {
		revisionsByRepo[change.Repository] = append(revisionsByRepo[change.Repository], change.Revision)

		branch, position, err := change.CommitPosition()

		if err != nil || branch == "" || position == 0 {
			// Skipping this change, since it doesn't seem to have a commit position
			continue
		}
		positionsByRepo[change.Repository] = append(positionsByRepo[change.Repository], fmt.Sprintf("%s@{#%d}", branch, position))
	}

	for URL, revisions := range revisionsByRepo {
		positions := positionsByRepo[URL]
		if len(revisions) > 1 {
			revisions = []string{
				revisions[0],
				revisions[len(revisions)-1],
			}
		}
		rr := &messages.RegressionRange{
			Repo:      getNameForURL(URL),
			URL:       URL,
			Revisions: revisions,
		}
		if len(positions) > 0 {
			if len(positions) > 1 {
				positions = []string{
					positions[0],
					positions[len(positions)-1],
				}
			}
			rr.Positions = positions
		}

		regRanges = append(regRanges, rr)
	}

	sort.Sort(ByRepo(regRanges))
	return regRanges
}

// ByRepo is a slice of regression ranges which is sortable.
type ByRepo []*messages.RegressionRange

// Len implements the sort interface.
func (a ByRepo) Len() int { return len(a) }

// Swap implements the sort interface.
func (a ByRepo) Swap(i, j int) { a[i], a[j] = a[j], a[i] }

// Less implements the sort interface.
func (a ByRepo) Less(i, j int) bool { return a[i].Repo < a[j].Repo }
