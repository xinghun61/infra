# Contacting troopers

This page can be found at: [g.co/bugatrooper](http://g.co/bugatrooper)

Have an issue with a piece of build infrastructure?
Our troopers are here to help.

The primary way to contact a trooper is via [crbug.com](http://crbug.com) using
the templates and priorities established below.

If you know your issue is with the physical hardware, or otherwise should be
handled by the Systems team, please follow their
[Rules of Engagement](https://docs.google.com/document/d/1Lhki-HAANF8NQzChDKA-ip_GE4D6c9WU1uBXB76XhnU/edit#).

## Bug Templates

For fastest response, please use the provided templates:

*   [Master restart requests](#Master-Restarts) (not for ChromeOS)
*   [Slave restart requests]
*   [Mobile device restart requests]
*   [ChromeOS Waterfall Pin Bumps / Restarts]
*   [General requests]

Also make sure to include the machine name (e.g. build11-m1)
as well as the waterfall name (Builder: Win).

## Priority Levels

Priorities are set using the `Pri=N` label. Use the following as your guideline:

*   Pri-0: Immediate attention desired.  The trooper will stop everything they are
    doing and investigate.
    *   Examples: CQ no longer committing changes, master offline, gnumbd broken.
*   Pri-1: Resolution desired within an hour or two.
    * Examples: disk full on device, device offline, sheriff-o-matic data stale.
*   Pri-2: Should be handled today.
    *   Examples: Master restart requests, tryserver restart requests.
*   Pri-3: Non-urgent. If the trooper cannot get to this today due to other
    incidents, it is ok to wait.
    *   Examples: Large change that will need trooper assistance, aka,
        "I'd like to land this gigantic change that may break the world"</span>

## Life of a Request

Status will be tracked using the Status field.

*   Untriaged: Your issue will show up in the queue to the trooper as untriaged.
    Once they acknowledge the bug, the status will change.
*   Available: Trooper has ack'ed, if not Pri-0, this means they have not started working on it.
*   Assigned:
    *   Trooper has triaged and determined there is a suitable owner and
        appropriately assigned.
    *   If that owner is YOU this indicates that they need more information from you
        in order to proceed.  Please provide the information, and then assign back
        to trooper.
*   Started: Your issue is being handled, either by the Trooper or other owner.
*   Fixed: The trooper believes the issue is resolved and no further action is required on their part.

## Master Restarts

### Self-service (Googlers only)

Master restarts are handled by master manager and only require running a single
command that mails a CL to schedule the restart.

With `depot_tools` in your path, run:

```bash
# Get an auth token for your @google.com account if you don't already have one.
depot-tools-auth login https://chromereviews.googleplex.com

# Restart chromium.fyi master in 15 minutes.
cit restart chromium.fyi -r <current trooper> [-b <bug number>]

# Restart chromium.fyi at the end of the PST/PDT work day (6:30PM).
cit restart chromium.fyi --eod -r <current trooper> [-b <bug number>]
```

Note: if you're not in the committers list CQ will try it first and you'll
have to ping the trooper to get an lgtm.

If you're having trouble you can file a bug with the trooper using the
[Master restart requests] bug template.

### Trooper-assisted Restart

Please file a bug using the [Master restart requests] bug template.

## Service Hours

Troopers provide full time coverage with the expected response times outlined
above during the PST work day. Support during EMEA work hours is limited to P0
only. Other times support is provided best-effort.

## Office Hours

Infra holds office hours on Thursdays 2pm in MTV-43-1-171 Kampala, as well as
on VC "cit-officehours".

Infra members go on Envoys from time to time. During visit days, infra memeber
generally are available to answer long standing questions, listen to gripes, and
give a tech talk (look for it on your office mailing list!).

If you would like an infra member to visit your office, drop a line to
chrome-infra@, we love visiting!

## More Information

View the [current trooper queue].

Common Non-Trooper Requests:

*   [Contact a Git Admin](https://bugs.chromium.org/p/chromium/issues/entry?template=Infra-Git)

[Master restart requests]: https://bugs.chromium.org/p/chromium/issues/entry?template=Build%20Infrastructure&labels=Restrict-View-Google,Infra-Troopers,Pri-2&summary=%5BMaster%20Restart%5D%20for%20%5Bmastername%5D&comment=Please%20provide%20the%20reason%20for%20restart%20(including%20CL%20link%20if%20possible).%0A%0ACc%20any%20users%20you%27d%20like%20notified%20of%20the%20restart.%0A%0ALeave%20at%20Pri-2%20for%20restart%20by%20end-of-day;%20Pri-1%20if%20you%20would%20like%20a%20restart%20sooner%20than%20that;%20or%20Pri-0%20if%20this%20is%20part%20of%20fixing%20an%20ongoing%20outage
[Slave restart requests]: https://bugs.chromium.org/p/chromium/issues/entry?template=Build%20Infrastructure&labels=Restrict-View-Google,Infra-Troopers,Pri-2&summary=%5BSlave%20Restart%5D%20for%20%5Bslave%20hostame%5D&comment=Please%20provide%20the%20reason%20for%20restart.%0A%0ALeave%20at%20Pri-2%20for%20restart%20by%20end-of-day;%20Pri-1%20if%20you%20would%20like%20a%20restart%20sooner%20than%20that;%20or%20Pri-0%20if%20this%20is%20part%20of%20fixing%20an%20ongoing%20outage.
[Mobile device restart requests]: https://bugs.chromium.org/p/chromium/issues/entry?template=Build%20Infrastructure&labels=Restrict-View-Google,Infra-Troopers,Pri-2&components=Infra%3ELabs&summary=%5BDevice%20Restart%5D%20for%20%5Bmastername%5D&comment=Please%20provide%20the%20reason%20for%20restart.%0A%0ALeave%20at%20Pri-2%20for%20restart%20by%20end-of-day;%20Pri-1%20if%20you%20would%20like%20a%20restart%20sooner%20than%20that;%20or%20Pri-0%20if%20this%20is%20part%20of%20fixing%20an%20ongoing%20outage.
[ChromeOS Waterfall Pin Bumps / Restarts]: https://bugs.chromium.org/p/chromium/issues/entry?template=Build%20Infrastructure&labels=Restrict-View-Google,Infra-Troopers,Pri-2&components=Infra&summary=%5BCrOS%20Chromite%20Pin%20Bump%20and%20Master%20Restart%5D&comment=Which%20Chromite%20branch%20should%20be%20updated%20(Leave%20blank%20for%20%22master%22)?%0A%0AReason%20for%20restart%20%28including%20CL%20link%20if%20possible%29:%0A%0ACc%20any%20users%20you%27d%20like%20notified%20of%20the%20restart.%0A%0ATROOPERS:%20please%20issue%20restart%20within%20a%20restart%20window%20(go/chrome-infra-cros-restart-windows).%0A%0AFor%20more%20information,%20see%20go/chrome-infra-doc-cros.
[General requests]: https://bugs.chromium.org/p/chromium/issues/entry?template=Build%20Infrastructure&labels=Restrict-View-Google,Infra-Troopers&summary=%5BBrief%20description%20of%20problem%5D&comment=Please%20provide%20the%20details%20for%20your%20request%20here.%0A%0ASet%20Pri-0%20iff%20it%20requires%20immediate%20attention,%20Pri-1%20if%20resolution%20within%20a%20few%20hours%20is%20acceptable,%20and%20Pri-2%20if%20it%20just%20needs%20to%20be%20handled%20today.
[current trooper queue]: https://bugs.chromium.org/p/chromium/issues/list?q=Infra=Troopers&sort=pri+-status.
[go/bug-a-trooper]: http://go/bug-a-trooper
