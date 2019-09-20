package main

import (
	"bufio"
	"fmt"
	"os"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"

	tricium "infra/tricium/api/v1"
)

func analyzeTestFile(t *testing.T, name string) []*tricium.Data_Comment {
	// Mock current time for testing
	now = func() time.Time { return time.Date(2019, time.January, 1, 0, 0, 0, 0, time.UTC) }
	f, err := os.Open("test/src/" + name)
	if err != nil {
		t.Errorf("Failed to open %s: %v", name, err)
		return nil
	}
	defer f.Close()
	return analyzeFile(bufio.NewScanner(f), name)
}

func TestHistogramsCheck(t *testing.T) {
	Convey("Analyze XML file with no errors", t, func() {
		results := analyzeTestFile(t, "good.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			defaultExpiryInfo("good.xml"),
		})
	})

	Convey("Analyze XML file with no errors: both owners individuals", t, func() {
		results := analyzeTestFile(t, "good_individuals.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			defaultExpiryInfo("good_individuals.xml"),
		})
	})

	// OWNER tests
	Convey("Analyze XML file with error: only one owner", t, func() {
		results := analyzeTestFile(t, "one_owner.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Owners"),
				Message:   oneOwnerError,
				StartLine: 4,
				Path:      "one_owner.xml",
			},
			defaultExpiryInfo("one_owner.xml"),
		})
	})

	Convey("Analyze XML file with error: no owners", t, func() {
		results := analyzeTestFile(t, "no_owners.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Owners"),
				Message:   oneOwnerError,
				StartLine: 3,
				Path:      "no_owners.xml",
			},
			defaultExpiryInfo("no_owners.xml"),
		})
	})

	Convey("Analyze XML file with error: first owner is team", t, func() {
		results := analyzeTestFile(t, "first_team_owner.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Owners"),
				Message:   firstOwnerTeamError,
				StartLine: 4,
				Path:      "first_team_owner.xml",
			},
			defaultExpiryInfo("first_team_owner.xml"),
		})
	})

	Convey("Analyze XML file with multiple owner errors", t, func() {
		results := analyzeTestFile(t, "first_team_one_owner.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Owners"),
				Message:   oneOwnerError,
				StartLine: 4,
				Path:      "first_team_one_owner.xml",
			},
			{
				Category:  fmt.Sprintf("%s/%s", category, "Owners"),
				Message:   firstOwnerTeamError,
				StartLine: 4,
				Path:      "first_team_one_owner.xml",
			},
			defaultExpiryInfo("first_team_one_owner.xml"),
		})
	})

	// EXPIRY tests
	Convey("Analyze XML file with no expiry", t, func() {
		results := analyzeTestFile(t, "no_expiry.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   noExpiryError,
				StartLine: 3,
				Path:      "no_expiry.xml",
			},
		})
	})

	Convey("Analyze XML file with expiry of never", t, func() {
		results := analyzeTestFile(t, "never_expiry_with_comment.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   neverExpiryInfo,
				StartLine: 3,
				Path:      "never_expiry_with_comment.xml",
			},
		})
	})

	Convey("Analyze XML file with expiry of never and no comment", t, func() {
		results := analyzeTestFile(t, "never_expiry_no_comment.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   neverExpiryInfo,
				StartLine: 3,
				Path:      "never_expiry_no_comment.xml",
			},
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   neverExpiryError,
				StartLine: 3,
				Path:      "never_expiry_no_comment.xml",
			},
		})
	})

	Convey("Analyze XML file with badly formatted expiry", t, func() {
		results := analyzeTestFile(t, "unformatted_expiry.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   badExpiryError,
				StartLine: 3,
				Path:      "unformatted_expiry.xml",
			},
		})
	})

	Convey("Analyze XML file with expiry in past", t, func() {
		results := analyzeTestFile(t, "past_expiry.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   pastExpiryWarning,
				StartLine: 3,
				Path:      "past_expiry.xml",
			},
		})
	})

	Convey("Analyze XML file with expiry in over one year", t, func() {
		results := analyzeTestFile(t, "over_year_expiry.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   farExpiryWarning,
				StartLine: 3,
				Path:      "over_year_expiry.xml",
			},
		})
	})
}

func defaultExpiryInfo(path string) *tricium.Data_Comment {
	return &tricium.Data_Comment{
		Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
		Message:   fmt.Sprintf("[INFO]: Expiry date is in 364 days"),
		StartLine: 3,
		Path:      path,
	}
}
