package analyzer

import (
	"fmt"
	"regexp"
	"strings"

	"golang.org/x/net/context"

	"infra/appengine/sheriff-o-matic/som/client"
	"infra/monitoring/messages"

	"go.chromium.org/luci/common/logging"
)

var versionConfigureRegexp = regexp.MustCompile(`Version: ([0-9]+\.[0-9]+)\..*`)
var versionPropertiesRegexp = regexp.MustCompile(`([0-9]+\.[0-9]+)\..*`)

func getVersionNumberFromConfigure(b *messages.Build) (string, error) {
	version := ""
	for _, step := range b.Steps {
		if step.Name == "Configure" {
			fmt.Printf("checking official Configure step text for version regexp: %q", step.Text)
			results := versionConfigureRegexp.FindStringSubmatch(strings.Join(step.Text, ""))
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

func getVersionNumberFromProperties(b *messages.Build) (string, error) {
	if len(b.Properties) == 0 {
		return "", fmt.Errorf("build message had no properties, couldn't check it for version number")
	}

	for _, prop := range b.Properties {
		// TODO: convenience method for retrieving build properties by name.
		if len(prop) < 2 {
			return "", fmt.Errorf("prop too short: %v", prop)
		}
		propName, ok := prop[0].(string)
		if !ok {
			// or just continue?
			return "", fmt.Errorf("error converting properties[0] to string: %+v", prop)
		}
		if propName != "chrome_version" {
			continue
		}
		if version, ok := prop[1].(string); ok {
			results := versionPropertiesRegexp.FindStringSubmatch(version)
			if len(results) != 2 {
				return "", fmt.Errorf("invalid version property: property text %q", version)
			}
			return results[1], nil
		}
		return "", fmt.Errorf("found chrome_version build property, couldn't convert to string: %v", prop[1])
	}
	return "", fmt.Errorf("invalid official build; no 'chrome_version' build property in %+v", b.Properties)
}

// officialImportantFailures finds important failures for official builds.
// Official builds use buildbot in a strange way; they build multiple versions
// of chrome on the same builder. Ideally, these would all be on separate
// builders, but that would add too much overhead right now. So, they build
// one configuration (arm phones, for example), and have multiple versions of
// chrome built on the same builder (53.0, 52.0, etc...). This means we have
// to go through all recent builds, and split them up into multiple buckets,
// one per major version built, and then generate alerts from that.
func (a *Analyzer) officialImportantFailures(ctx context.Context, master *messages.MasterLocation, builderName string, recentBuildIDs []int64) ([]*messages.BuildStep, error) {
	buildPerVersion := make(map[string]int64)
	for _, buildNum := range recentBuildIDs {
		b, err := client.Build(ctx, master, builderName, buildNum)
		if err != nil {
			return nil, err
		}

		version, err := getVersionNumberFromConfigure(b)
		if err != nil {
			if version, err = getVersionNumberFromProperties(b); err != nil {
				logging.Errorf(ctx, "couldn't get version number from Configure step or from properties %s/%s/%d: %b", master, builderName, buildNum, err)
				// Keep going.
				continue
			}
			logging.Debugf(ctx, "got version number from properties: %s", version)
		}

		if buildPerVersion[version] == 0 || buildPerVersion[version] < buildNum {
			buildPerVersion[version] = buildNum
		}
	}

	allFailingBuilds := []*messages.BuildStep(nil)
	for _, buildNum := range buildPerVersion {
		builds, err := a.stepFailures(ctx, master, builderName, buildNum)
		if err != nil {
			return nil, err
		}

		allFailingBuilds = append(allFailingBuilds, builds...)
	}

	return allFailingBuilds, nil
}
