package analyzer

import (
	"fmt"
	"regexp"
	"strings"

	"infra/monitoring/messages"
)

var versionRegexp = regexp.MustCompile(`Version: ([0-9]+\.[0-9]+)\..*`)

func getVersionNumber(b *messages.Build) (string, error) {
	version := ""
	for _, step := range b.Steps {
		if step.Name == "Configure" {
			results := versionRegexp.FindStringSubmatch(strings.Join(step.Text, ""))
			if len(results) != 2 {
				return "", fmt.Errorf("invalid Configure step: step text %q", step.Text)
			}

			return results[1], nil
		}
	}

	if version == "" {
		return "", fmt.Errorf("invalid official build; no 'Configure' step")
	}

	return version, nil
}

// officialImportantFailures finds important failures for official builds.
// Official builds use buildbot in a strange way; they build multiple versions
// of chrome on the same builder. Ideally, these would all be on separate
// builders, but that would add too much overhead right now. So, they build
// one configuration (arm phones, for example), and have multiple versions of
// chrome built on the same builder (53.0, 52.0, etc...). This means we have
// to go through all recent builds, and split them up into multiple buckets,
// one per major version built, and then generate alerts from that.
func (a *Analyzer) officialImportantFailures(master *messages.MasterLocation, builderName string, recentBuildIDs []int64) ([]*messages.BuildStep, error) {
	buildPerVersion := make(map[string]int64)
	for _, buildNum := range recentBuildIDs {
		b, err := a.Reader.Build(master, builderName, buildNum)
		if err != nil {
			return nil, err
		}

		version, err := getVersionNumber(b)
		if err != nil {
			return nil, err
		}

		if buildPerVersion[version] == 0 || buildPerVersion[version] < buildNum {
			buildPerVersion[version] = buildNum
		}
	}

	allFailingBuilds := []*messages.BuildStep(nil)
	for _, buildNum := range buildPerVersion {
		builds, err := a.stepFailures(master, builderName, buildNum)
		if err != nil {
			return nil, err
		}

		allFailingBuilds = append(allFailingBuilds, builds...)
	}

	return allFailingBuilds, nil
}
