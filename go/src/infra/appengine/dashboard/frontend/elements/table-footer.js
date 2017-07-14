'use strict'

const WEEK_SPAN = 7;

class TableFooter extends Polymer.Element {
  static get is() { return 'table-footer'; }

  ready() {
    super.ready();
  }

  static get properties() {
    return {
      latestDate: {
        type: Number,
        notify: true,
      },
      tsNext: {
        type: Number,
        computed:'_computeTsNext(latestDate)',
      },
      tsPrev: {
        type: Number,
        computed: '_computeTsPrev(latestDate)',
      },
      prevButtonClass: {
        type: String,
        computed: '_computePrevButtonClass(tsPrev)',
      },
      nextButtonClass: {
        type: String,
        computed: '_computeNextButtonClass(tsNext)',
      },
    }
  }

  /**
   * This calculates the timestamp of the previous week's last date. The
   * timestamp returned will be undefined if the current week being viewed is
   * the very first week that this dashbaord started collecting data. If the
   * latestDate is within the second week the previous timestamp will be set to
   * endOfFirstWeek.
   */
  _computeTsPrev(latestDate) {
    // Wednesday, May 24, 2017 12:00:00 AM GMT
    const endOfFirstWeek = 1495584000000;
    const endOfSecondWeek = 1496275199000;
    const dateCenterLocal = new Date(latestDate);
    let prev;
    if (latestDate > endOfFirstWeek && latestDate <= endOfSecondWeek) {
      prev = endOfFirstWeek;
    } else if (latestDate > endOfSecondWeek) {
      prev = this._getTimeStamps(dateCenterLocal, -WEEK_SPAN);
    }
    return prev;
  }

   /**
    * This calculates the timestamp of the next week's last date. If the
    * latestDate is the current date then there should be no link for the next
    * button so the timestamp return should be undefined.
    */
  _computeTsNext(latestDate) {
    let dateCenterLocal = new Date(latestDate);
    let next;
    if (!this._isSameDay(dateCenterLocal, new Date())) {
      next = this._getTimeStamps(dateCenterLocal, WEEK_SPAN);
    }
    return next;
  }

  _computePrevButtonClass(tsPrev) {
    return tsPrev ? 'shown' : 'hidden';
  }

  _computeNextButtonClass(tsNext) {
    return tsNext ? 'shown' : 'hidden';
  }

  _goToPrevPage() {
    this.latestDate = this.tsPrev;
  }

  _goToNextPage() {
    this.latestDate = this.tsNext;
  }

  _getTimeStamps(baseDate, diff) {
    let date = new Date(baseDate);
    date.setDate(date.getDate() + diff);
    // A link should never take the user to a page showing days that haven't
    // happend yet.
    if (date > new Date()) {
      date = new Date();
    }
    return date.setHours(23, 59, 59, 0);
  }

  /**
   * isSameDay should be used to check if two Date objects occur within
   * the same day. Simply comparing the two objects would be too granular
   * as Date objects also include the time within a day.
   * @param {Date} dateOne - The first date to be compared.
   * @param {Date} dateTwo - The other date to be compared.
   */
  _isSameDay(dateOne, dateTwo) {
    return dateOne.getFullYear() === dateTwo.getFullYear() &&
    dateOne.getMonth() === dateTwo.getMonth() &&
    dateOne.getDate() === dateTwo.getDate();
  }
}
customElements.define(TableFooter.is, TableFooter);
