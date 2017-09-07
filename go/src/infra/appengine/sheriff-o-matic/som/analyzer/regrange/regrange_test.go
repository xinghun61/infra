package regrange

import (
	"testing"

	"infra/monitoring/messages"

	. "github.com/smartystreets/goconvey/convey"
)

func Test(t *testing.T) {
	t.Parallel()
	Convey("RegRange", t, func() {
		URLToNameMapping = map[string]string{
			"http://foo": "bar",
		}

		Convey("getNameForURL", func() {
			Convey("basic", func() {
				So(getNameForURL("http://foo"), ShouldEqual, "bar")
			})

			Convey(".git", func() {
				So(getNameForURL("http://foo.git"), ShouldEqual, "bar")
			})

			Convey("trailing slash", func() {
				So(getNameForURL("http://foo.git/"), ShouldEqual, "bar")
			})

			Convey("unknown", func() {
				So(getNameForURL("http://lolwat"), ShouldEqual, "unknown")
			})
		})

		Convey("Default", func() {
			b := &messages.Build{
				SourceStamp: messages.SourceStamp{
					Changes:    []messages.Change{},
					Repository: "http://foo",
				},
			}
			Convey("empty", func() {
				So(Default(b), ShouldResemble, []*messages.RegressionRange(nil))
			})

			b.SourceStamp.Changes = []messages.Change{
				{
					Revision:   "deadbeef",
					Repository: "http://foo",
				},
			}
			Convey("change with no CommitPosition", func() {
				So(Default(b), ShouldResemble, []*messages.RegressionRange{
					{
						Repo:      "bar",
						URL:       "http://foo",
						Revisions: []string{"deadbeef"},
					},
				})
			})

			b.SourceStamp.Changes[0].Comments = "Cr-Commit-Position: branch/thing@{#1234}"
			Convey("change", func() {
				So(Default(b), ShouldResemble, []*messages.RegressionRange{
					{
						Repo:      "bar",
						URL:       "http://foo",
						Revisions: []string{"deadbeef"},
						Positions: []string{"branch/thing@{#1234}"},
					},
				})
			})

			b.SourceStamp.Changes = append(b.SourceStamp.Changes, messages.Change{
				Revision:   "deadbee5",
				Repository: "http://foo",
				Comments:   "Cr-Commit-Position: branch/thing@{#1235}",
			})
			b.SourceStamp.Changes = append(b.SourceStamp.Changes, messages.Change{
				Revision:   "deadbee6",
				Repository: "http://foo",
				Comments:   "Cr-Commit-Position: branch/thing@{#1236}",
			})
			b.SourceStamp.Changes = append(b.SourceStamp.Changes, messages.Change{
				Revision:   "deadbee7",
				Repository: "http://foo",
				Comments:   "Cr-Commit-Position: branch/thing@{#1237}",
			})

			// We only report the first and last commit position
			Convey("multiple changes", func() {
				So(Default(b), ShouldResemble, []*messages.RegressionRange{
					{
						Repo: "bar",
						URL:  "http://foo",
						Revisions: []string{
							"deadbeef",
							"deadbee7",
						},
						Positions: []string{
							"branch/thing@{#1234}",
							"branch/thing@{#1237}",
						},
					},
				})
			})

			URLToNameMapping["http://thing"] = "bestrepo"

			b.SourceStamp.Changes = append(b.SourceStamp.Changes, messages.Change{
				Revision:   "deadbeef",
				Repository: "http://thing",
				Comments:   "Cr-Commit-Position: branch/other_thing@{#2222}",
			})
			Convey("with other repo", func() {
				So(Default(b), ShouldResemble, []*messages.RegressionRange{
					{
						Repo: "bar",
						URL:  "http://foo",
						Revisions: []string{
							"deadbeef",
							"deadbee7",
						},
						Positions: []string{
							"branch/thing@{#1234}",
							"branch/thing@{#1237}",
						},
					},
					{
						Repo: "bestrepo",
						URL:  "http://thing",
						Revisions: []string{
							"deadbeef",
						},
						Positions: []string{
							"branch/other_thing@{#2222}",
						},
					},
				})
			})
		})
	})
}
