# Contacting troopers

[go/bug-a-trooper]

Have an issue with a piece of build infrastructure?
Our troopers are here to help.

The primary way to contact a trooper is via [crbug.com](http://crbug.com) using
the templates and priorities established below.

If you know your issue is with the physical hardware, or otherwise should be
handled by the Systems team, please follow their
[Rules of Engagement](https://docs.google.com/document/d/1Lhki-HAANF8NQzChDKA-ip_GE4D6c9WU1uBXB76XhnU/edit#).

## Bug Templates

For fastest response, please use the provided templates:

*   [Master restart requests]
*   [Slave restart requests]
*   [Mobile device restart requests]
*   [General requests]

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

## Service Hours

Troopers provide full time coverage with the expected response times outlined
above during the PST work day. Support during EMEA work hours is limited to P0
only. Other times support is provided best-effort.

## Office Hours

Infra holds office hours on Thursdays 2pm in MTV-43-1-171 Kampala, as well as
on VC "cit-officehours".

Infra members go on Envoys from time to time.  This is our current schedule:
* Stockholm: 9/22 - 9/25 estaab@
* Munich: 10/12 - 10/16 estaab@
* Sydney: 11/2 - 11/13 hinoka@
* Munich: 11/16 - 11/20 pgervais@
* Stockholm: 10/19 - 10/23 stip@

During visit days, infra memeber generally are available to answer long standing
questions, listen to gripes, and give a tech talk (look for it on your office
mailing list!).

If you would like an infra member to visit your office, drop a line to
chrome-infra@, we love visiting!

## More Information

View the [current trooper queue].

Common Non-Trooper Requests:

*   [Create a new repository](https://code.google.com/p/chromium/issues/entry?template=Infra-Git)

[Master restart requests]: https://code.google.com/p/chromium/issues/entry?template=Build%20Infrastructure&labels=Restrict-View-Google,Infra-Troopers,Pri-2&summary=%5BMaster%20Restart%5D%20for%20%5Bmastername%5D&comment=Please%20provide%20the%20reason%20for%20restart%20(including%20CL%20link%20if%20possible).%0A%0ACc%20any%20users%20you%27d%20like%20notified%20of%20the%20restart.%0A%0ALeave%20at%20Pri-2%20for%20restart%20by%20end-of-day;%20Pri-1%20if%20you%20would%20like%20a%20restart%20sooner%20than%20that;%20or%20Pri-0%20if%20this%20is%20part%20of%20fixing%20an%20ongoing%20outage
[Slave restart requests]: https://code.google.com/p/chromium/issues/entry?template=Build%20Infrastructure&labels=Restrict-View-Google,Infra-Troopers,Pri-2&summary=%5BSlave%20Restart%5D%20for%20%5Bslave%20hostame%5D&comment=Please%20provide%20the%20reason%20for%20restart.%0A%0ALeave%20at%20Pri-2%20for%20restart%20by%20end-of-day;%20Pri-1%20if%20you%20would%20like%20a%20restart%20sooner%20than%20that;%20or%20Pri-0%20if%20this%20is%20part%20of%20fixing%20an%20ongoing%20outage.
[Mobile device restart requests]: https://code.google.com/p/chromium/issues/entry?template=Build%20Infrastructure&labels=Restrict-View-Google,Infra-Troopers,Infra-Labs,Pri-2&summary=%5BDevice%20Restart%5D%20for%20%5Bmastername%5D&comment=Please%20provide%20the%20reason%20for%20restart.%0A%0ALeave%20at%20Pri-2%20for%20restart%20by%20end-of-day;%20Pri-1%20if%20you%20would%20like%20a%20restart%20sooner%20than%20that;%20or%20Pri-0%20if%20this%20is%20part%20of%20fixing%20an%20ongoing%20outage.
[General requests]: https://code.google.com/p/chromium/issues/entry?template=Build%20Infrastructure&labels=Restrict-View-Google,Infra-Troopers&summary=%5BBrief%20description%20of%20problem%5D&comment=Please%20provide%20the%20details%20for%20your%20request%20here.%0A%0ASet%20Pri-0%20iff%20it%20requires%20immediate%20attention,%20Pri-1%20if%20resolution%20within%20a%20few%20hours%20is%20acceptable,%20and%20Pri-2%20if%20it%20just%20needs%20to%20be%20handled%20today.
[current trooper queue]: https://code.google.com/p/chromium/issues/list?q=Infra=Troopers&sort=pri+-status.
[go/bug-a-trooper]: http://go/bug-a-trooper
