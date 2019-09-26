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

	// EXPIRY tests
	Convey("Analyze XML file with no errors: good expiry date", t, func() {
		results := analyzeTestFile(t, "expiry/good_date.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			defaultExpiryInfo("expiry/good_date.xml"),
		})
	})

	Convey("Analyze XML file with no expiry", t, func() {
		results := analyzeTestFile(t, "expiry/no_expiry.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   noExpiryError,
				StartLine: 3,
				Path:      "expiry/no_expiry.xml",
			},
		})
	})

	Convey("Analyze XML file with expiry of never", t, func() {
		results := analyzeTestFile(t, "expiry/never_expiry_with_comment.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   neverExpiryInfo,
				StartLine: 3,
				Path:      "expiry/never_expiry_with_comment.xml",
			},
		})
	})

	Convey("Analyze XML file with expiry of never and no comment", t, func() {
		results := analyzeTestFile(t, "expiry/never_expiry_no_comment.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   neverExpiryInfo,
				StartLine: 3,
				Path:      "expiry/never_expiry_no_comment.xml",
			},
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   neverExpiryError,
				StartLine: 3,
				Path:      "expiry/never_expiry_no_comment.xml",
			},
		})
	})

	Convey("Analyze XML file with expiry in over one year", t, func() {
		results := analyzeTestFile(t, "expiry/over_year_expiry.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   farExpiryWarning,
				StartLine: 3,
				Path:      "expiry/over_year_expiry.xml",
			},
		})
	})

	Convey("Analyze XML file with expiry in past", t, func() {
		results := analyzeTestFile(t, "expiry/past_expiry.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   pastExpiryWarning,
				StartLine: 3,
				Path:      "expiry/past_expiry.xml",
			},
		})
	})

	Convey("Analyze XML file with badly formatted expiry", t, func() {
		results := analyzeTestFile(t, "expiry/unformatted_expiry.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   badExpiryError,
				StartLine: 3,
				Path:      "expiry/unformatted_expiry.xml",
			},
		})
	})

	// EXPIRY MILESTONE tests
	Convey("Analyze XML file with no errors: good milestone expiry", t, func() {
		results := analyzeTestFile(t, "expiry/milestone/good_milestone.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   fmt.Sprintf("[INFO]: Expiry date is in 30 days"),
				StartLine: 3,
				Path:      "expiry/milestone/good_milestone.xml",
			},
		})
	})

	Convey("Simulate failure in fetching milestone data from server", t, func() {
		results := analyzeTestFile(t, "expiry/milestone/milestone_fetch_failed.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   milestoneFailure,
				StartLine: 3,
				Path:      "expiry/milestone/milestone_fetch_failed.xml",
			},
		})
	})

	Convey("Analyze XML file with expiry in over one year: milestone", t, func() {
		results := analyzeTestFile(t, "expiry/milestone/over_year_milestone.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   farExpiryWarning,
				StartLine: 3,
				Path:      "expiry/milestone/over_year_milestone.xml",
			},
		})
	})

	Convey("Analyze XML file with expiry in over one year: 3-number milestone", t, func() {
		results := analyzeTestFile(t, "expiry/milestone/over_year_milestone_3.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   farExpiryWarning,
				StartLine: 3,
				Path:      "expiry/milestone/over_year_milestone_3.xml",
			},
		})
	})

	Convey("Analyze XML file with expiry in past: milestone", t, func() {
		results := analyzeTestFile(t, "expiry/milestone/past_milestone.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   pastExpiryWarning,
				StartLine: 3,
				Path:      "expiry/milestone/past_milestone.xml",
			},
		})
	})

	Convey("Analyze XML file with badly formatted expiry: similar to milestone", t, func() {
		results := analyzeTestFile(t, "expiry/milestone/unformatted_milestone.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   badExpiryError,
				StartLine: 3,
				Path:      "expiry/milestone/unformatted_milestone.xml",
			},
		})
	})

	// OBSOLETE tests
	Convey("Analyze XML file with no obsolete message and no errors", t, func() {
		currPath := "obsolete/good_obsolete_date.xml"
		results := analyzeTestFile(t, currPath)
		So(results, ShouldResemble, []*tricium.Data_Comment{
			defaultExpiryInfoLine(currPath, 3),
			defaultExpiryInfoLine(currPath, 13),
			defaultExpiryInfoLine(currPath, 23),
			defaultExpiryInfoLine(currPath, 33),
			defaultExpiryInfoLine(currPath, 43),
			defaultExpiryInfoLine(currPath, 53),
		})
	})

	Convey("Analyze XML file with no errors and good obsolete milestone", t, func() {
		results := analyzeTestFile(t, "obsolete/good_obsolete_milestone.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
				Message:   fmt.Sprintf("[INFO]: Expiry date is in 30 days"),
				StartLine: 3,
				Path:      "obsolete/good_obsolete_milestone.xml",
			},
		})
	})

	Convey("Analyze XML file with no date in obsolete message", t, func() {
		results := analyzeTestFile(t, "obsolete/obsolete_no_date.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Obsolete"),
				Message:   obsoleteDateError,
				StartLine: 4,
				Path:      "obsolete/obsolete_no_date.xml",
			},
			defaultExpiryInfo("obsolete/obsolete_no_date.xml"),
		})
	})

	Convey("Analyze XML file with badly formatted date in obsolete message", t, func() {
		currPath := "obsolete/obsolete_unformatted_date.xml"
		results := analyzeTestFile(t, currPath)
		So(results, ShouldResemble, []*tricium.Data_Comment{
			makeObsoleteDateError(currPath, 4),
			defaultExpiryInfoLine(currPath, 3),
			makeObsoleteDateError(currPath, 14),
			defaultExpiryInfoLine(currPath, 13),
			makeObsoleteDateError(currPath, 24),
			defaultExpiryInfoLine(currPath, 23),
			makeObsoleteDateError(currPath, 34),
			defaultExpiryInfoLine(currPath, 33),
			makeObsoleteDateError(currPath, 44),
			defaultExpiryInfoLine(currPath, 43),
		})
	})

	// OWNER tests
	Convey("Analyze XML file with no errors: both owners individuals", t, func() {
		results := analyzeTestFile(t, "owners/good_individuals.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			defaultExpiryInfo("owners/good_individuals.xml"),
		})
	})

	Convey("Analyze XML file with error: only one owner", t, func() {
		results := analyzeTestFile(t, "owners/one_owner.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Owners"),
				Message:   oneOwnerError,
				StartLine: 4,
				Path:      "owners/one_owner.xml",
			},
			defaultExpiryInfo("owners/one_owner.xml"),
		})
	})

	Convey("Analyze XML file with error: no owners", t, func() {
		results := analyzeTestFile(t, "owners/no_owners.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Owners"),
				Message:   oneOwnerError,
				StartLine: 3,
				Path:      "owners/no_owners.xml",
			},
			defaultExpiryInfo("owners/no_owners.xml"),
		})
	})

	Convey("Analyze XML file with error: first owner is team", t, func() {
		results := analyzeTestFile(t, "owners/first_team_owner.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Owners"),
				Message:   firstOwnerTeamError,
				StartLine: 4,
				Path:      "owners/first_team_owner.xml",
			},
			defaultExpiryInfo("owners/first_team_owner.xml"),
		})
	})

	Convey("Analyze XML file with multiple owner errors", t, func() {
		results := analyzeTestFile(t, "owners/first_team_one_owner.xml")
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  fmt.Sprintf("%s/%s", category, "Owners"),
				Message:   oneOwnerError,
				StartLine: 4,
				Path:      "owners/first_team_one_owner.xml",
			},
			{
				Category:  fmt.Sprintf("%s/%s", category, "Owners"),
				Message:   firstOwnerTeamError,
				StartLine: 4,
				Path:      "owners/first_team_one_owner.xml",
			},
			defaultExpiryInfo("owners/first_team_one_owner.xml"),
		})
	})

}

func defaultExpiryInfo(path string) *tricium.Data_Comment {
	return defaultExpiryInfoLine(path, 3)
}

func defaultExpiryInfoLine(path string, startLine int) *tricium.Data_Comment {
	return &tricium.Data_Comment{
		Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
		Message:   fmt.Sprintf("[INFO]: Expiry date is in 104 days"),
		StartLine: int32(startLine),
		Path:      path,
	}
}

func makeObsoleteDateError(path string, startLine int) *tricium.Data_Comment {
	return &tricium.Data_Comment{
		Category:  fmt.Sprintf("%s/%s", category, "Obsolete"),
		Message:   obsoleteDateError,
		StartLine: int32(startLine),
		Path:      path,
	}
}
