package messages

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func Test(t *testing.T) {
	Convey("Change", t, func() {
		Convey("CommitPosition", func() {

			text := `
Revert "Media Controls: Replace painter with CSS."

This reverts commit 8a3b36ef9e6c6747876175f48f8cb24e6573dc30.

Reason for revert:

Seeing a lot of new WebKit media failures.

Please validate and fix/reland as appropriate.

Original change's description:
> Media Controls: Replace painter with CSS.
> 
> Replace MediaControlPainter with CSS. Add some classes to some
> elements to allow styling by state.
> 
> BUG=746872
> 
> Change-Id: I1c226a85ff133b9bf440925b238abf7810c9482a
> Reviewed-on: https://c
...skip...
Lamouri <mlamouri@chromium.org>
> Cr-Commit-Position: refs/heads/master@{#500312}

TBR=thakis@chromium.org,mlamouri@chromium.org,pfeldman@chromium.org,beccahughes@chromium.org

Change-Id: I681803781e9e60f1030589a7bd6a5cb0d91e061e
No-Presubmit: true
No-Tree-Checks: true
No-Try: true
Bug: 746872
Reviewed-on: https://chromium-review.googlesource.com/655739
Reviewed-by: Roger McFarlane <rogerm@chromium.org>
Commit-Queue: Roger McFarlane <rogerm@chromium.org>
Cr-Commit-Position: refs/heads/master@{#500363}`
			c := Change{
				Comments: text,
			}

			branch, pos, err := c.CommitPosition()
			So(err, ShouldBeNil)
			So(branch, ShouldResemble, "refs/heads/master")
			So(pos, ShouldResemble, 500363)
		})

	})

}
