
'use strict';
class MrActivityTable extends Polymer.Element {
  static get is() {
    return 'mr-activity-table';
  }

  static get properties() {
    return {
      daysOfWeek: {
        type: Array,
        value() {
          return 'Mon Tue Wed Thu Fri Sat Sun'.split(' ');
        },
      },
      weeks: {
        type: Array,
        value() {
          return [
            {
              label: 'Time Range',
              days: [
                {
                  day: 'May 21',
                  changes: 1,
                  bugs: 2,
                },
                {
                  day: 'May 22',
                  changes: 0,
                  bugs: 4,
                },
                {
                  day: 'May 23',
                  changes: 8,
                  bugs: 1,
                },
                {
                  day: 'May 24',
                  changes: 1,
                  bugs: 0,
                },
                {
                  day: 'May 25',
                  changes: 0,
                  bugs: 1,
                },
                {
                  day: 'May 26',
                  changes: 0,
                  bugs: 0,
                },
                {
                  day: 'May 27',
                  changes: 0,
                  bugs: 0,
                }
              ],
            },
          ];
        },
      },
      day: String,
    };
  }

  _computeIsSelected(day, itemDay) {
    return day == itemDay;
  }

  _onDaySelected(event) {
    this.day = event.target.day;
  }
}
customElements.define(MrActivityTable.is, MrActivityTable);
