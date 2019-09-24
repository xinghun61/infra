package main

import (
	"bufio"
	"errors"
	"fmt"
	"log"
	"os"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"

	tricium "infra/tricium/api/v1"
)

func analyzeTestFile(t *testing.T, name string) []*tricium.Data_Comment {
	// Mock current time for testing
	now = func() time.Time { return time.Date(2019, time.September, 18, 0, 0, 0, 0, time.UTC) }
	getMilestoneDate = mockMilestoneDate
	f, err := os.Open("test/src/" + name)
	if err != nil {
		t.Errorf("Failed to open %s: %v", name, err)
		return nil
	}
	defer f.Close()
	return analyzeFile(bufio.NewScanner(f), name)
}

// Mock function to get milestone date from server
func mockMilestoneDate(milestone int) (time.Time, error) {
	var date time.Time
	var err error
	switch milestone {
	// Use 50 to simulate if server responds with error
	case 50:
		err = errors.New("Bad milestone request")
	case 77:
		date, _ = time.Parse(dateMilestoneFormat, "2019-07-25T00:00:00")
	case 79:
		date, _ = time.Parse(dateMilestoneFormat, "2019-10-17T00:00:00")
	case 87:
		date, _ = time.Parse(dateMilestoneFormat, "2020-10-22T00:00:00")
	case 101:
		date, _ = time.Parse(dateMilestoneFormat, "2022-08-11T00:00:00")
	default:
		log.Fatalf("Invalid milestone date in test. Please add your own case")
	}
	return date, err
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

	Convey("Analyze XML file with no errors: milestone expiry", t, func() {
		results := analyzeTestFile(t, "good_milestone.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   fmt.Sprintf("[INFO]: Expiry date is in 30 days"),
				StartLine: 3,
				Path:      "good_milestone.xml",
			},
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

	Convey("Analyze XML file with badly formatted expiry: similar to milestone", t, func() {
		results := analyzeTestFile(t, "unformatted_milestone.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   badExpiryError,
				StartLine: 3,
				Path:      "unformatted_milestone.xml",
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

	Convey("Analyze XML file with expiry in past: milestone", t, func() {
		results := analyzeTestFile(t, "past_milestone.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   pastExpiryWarning,
				StartLine: 3,
				Path:      "past_milestone.xml",
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

	Convey("Analyze XML file with expiry in over one year: milestone", t, func() {
		results := analyzeTestFile(t, "over_year_milestone.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   farExpiryWarning,
				StartLine: 3,
				Path:      "over_year_milestone.xml",
			},
		})
	})

	Convey("Analyze XML file with expiry in over one year: 3-number milestone", t, func() {
		results := analyzeTestFile(t, "over_year_milestone_3.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   farExpiryWarning,
				StartLine: 3,
				Path:      "over_year_milestone_3.xml",
			},
		})
	})

	Convey("Simulate failure in fetching milestone data from server", t, func() {
		results := analyzeTestFile(t, "milestone_fetch_failed.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   milestoneFailure,
				StartLine: 3,
				Path:      "milestone_fetch_failed.xml",
			},
		})
	})
}

func defaultExpiryInfo(path string) *tricium.Data_Comment {
	return &tricium.Data_Comment{
		Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
		Message:   fmt.Sprintf("[INFO]: Expiry date is in 104 days"),
		StartLine: 3,
		Path:      path,
	}
}
