
'use strict';
class MrActivityTable extends Polymer.Element {
  static get is() {
    return 'mr-activity-table';
  }

  static get properties() {
    return {
      user: {
        type: String,
      },
      viewedUserId: {
        type: Number,
      },
      commits: {
        type: Array,
      },
      comments: {
        type: Array,
      },
      startWeekday: {
        type: Array,
      },
      todayUnixEndTime: {
        type: Number,
        value: () => {
          const now = new Date();
          const today = new Date(Date.UTC(
            now.getUTCFullYear(),
            now.getUTCMonth(),
            now.getUTCDate(),
            24, 0, 0));
          const todayEndTime = today.getTime() / 1000;
          return todayEndTime;
        },
      },
      daysOfWeek: {
        type: Array,
        value: () => {
          return 'M T W T F S S'.split(' ');
        },
      },
      activityArray: {
        type: Array,
        reflectToAttribute: true,
        computed: 'computeActivityArray(commits, comments, todayUnixEndTime)',
        observer: '_computeWeekdayStart',
      },
      months: {
        type: Array,
        value: () => {
          var monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
          var now = new Date();
          return [monthNames[now.getMonth()],
                  monthNames[now.getMonth() - 1],
                  monthNames[now.getMonth() - 2]];
        }
      },
      selectedDate: {
        type: Number,
        notify: true,
      }
    };
  }

  _computeIsSelected(day, itemDay) {
    return this.selectedDate == itemDay;
  }

  _onDaySelected(event) {
    if(this.selectedDate == event.target.date){
      this.selectedDate = undefined;
    } else {
      this.selectedDate = event.target.date;
    }
  }

  _computeWeekdayStart() {
    let startDate = new Date(this.activityArray[0].date * 1000);
    let startWeekdayNum = startDate.getDay()-1;
    let emptyDays = [];
    for(let i = 0; i < startWeekdayNum; i++) {
      emptyDays.push(" ");
    }
    this.startWeekday = emptyDays;
  }

  _getTodayUnixTime() {
    let now = new Date();
    let today = new Date(Date.UTC(
      now.getUTCFullYear(),
      now.getUTCMonth(),
      now.getUTCDate(),
      24,0,0));
    let todayEndTime = today.getTime() / 1000;
    return todayEndTime;
  }

  computeActivityArray(commits, comments, todayUnixEndTime) {
    if(!todayUnixEndTime){
      return [];
    }
    commits = commits || [];
    comments = comments || [];

    let activityArray = [];
    for(let i = 0; i < 93; i++) {
      let arrayDate = (todayUnixEndTime - ((i) * 86400));
      activityArray.push({
        commits: 0,
        comments: 0,
        activityNum: 0,
        date: arrayDate,
      });
    }

    for (let i = 0; i < commits.length; i++) {
      let day = Math.floor((todayUnixEndTime - commits[i].commitTime) / 86400);
      if(day > 92){
        break;
      }
      activityArray[day].commits++;
      activityArray[day].activityNum++;
    }

    for (let i = 0; i < comments.length; i++) {
      let day = Math.floor((todayUnixEndTime - comments[i].timestamp) / 86400);
      if(day > 92){
        break;
      }
      activityArray[day].comments++;
      activityArray[day].activityNum++;
    }
    activityArray.reverse();
    return activityArray;
  }
}
customElements.define(MrActivityTable.is, MrActivityTable);
