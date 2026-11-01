/*******************************************************************************
 * COPYRIGHT NOTICE *
 * 
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 * 
 * This file is part of ProjeQtOr.
 * 
 * ProjeQtOr is free software: you can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option) any
 * later version.
 * 
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
 * A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
 * details.
 * 
 * You should have received a copy of the GNU Affero General Public License
 * along with ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 * 
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org
 * 
 * DO NOT REMOVE THIS NOTICE **
 ******************************************************************************/

// =============================================================================
// = String
// =============================================================================
// gautier
String.prototype.toUpperCaseWithoutAccent=function() {
  var accent=[/[\300-\306]/g,/[\340-\346]/g, // A, a
  /[\310-\313]/g,/[\350-\353]/g, // E, e
  /[\314-\317]/g,/[\354-\357]/g, // I, i
  /[\322-\330]/g,/[\362-\370]/g, // O, o
  /[\331-\334]/g,/[\371-\374]/g, // U, u
  /[\321]/g,/[\361]/g, // N, n
  /[\307]/g,/[\347]/g, // C, c
  ];
  var noaccent=['A','a','E','e','I','i','O','o','U','u','N','n','C','c'];

  var str=this;
  for (var i=0;i < accent.length;i++) {
    str=str.replace(accent[i],noaccent[i]);
  }

  return str.toUpperCase();
};

function trim(myString,car) {
  if (!myString) {
    return myString;
  }
  ;
  myStringAsTring=myString + "";
  return myStringAsTring.replace(/^\s+/g,'').replace(/\s+$/g,'');
}

function trimTag(myString,car) {
  if (!myString) {
    return myString;
  }
  ;
  myStringAsTring=myString + "";
  return myStringAsTring.replace(/^</g,'').replace(/>$/g,'');
}

// =============================================================================
// = Dates manipulation
// =============================================================================

function transformDateToSqlDate(date) {
  var sqlDate="";
  if (isDate(date)) {
	// Other possible way (to test) : date.toISOString().slice(0,10); Tested but seems to change the date
    month=date.getMonth() + 1;
    year=date.getFullYear();
    day=date.getDate();
    sqlDate=year + '-' + (month < 10 ? '0' : '') + month + '-' + (day < 10 ? '0' : '') + day;
  }
  return sqlDate;
}

/**
 * ============================================================================
 * Return the current time, correctly formated as HH:MM
 * 
 * @return the current time correctly formated
 */
function getTime() {
  var currentTime=new Date();
  var hours=currentTime.getHours();
  var minutes=currentTime.getMinutes();
  if (minutes < 10) {
    minutes="0" + minutes;
  }
  return hours + ":" + minutes;
}

/**
 * calculate diffence (in work days) between dates
 */

function workDayDiffDates(paramStartDate,paramEndDate,idProject) {
  var currentDate=new Date();
  if (!isDate(paramStartDate)) return '';
  if (!isDate(paramEndDate)) return '';
  currentDate.setFullYear(paramStartDate.getFullYear(),paramStartDate.getMonth(),paramStartDate.getDate());
  currentDate.setHours(0,0,0,0);
  var endDate=new Date();
  endDate.setFullYear(paramEndDate.getFullYear(),paramEndDate.getMonth(),paramEndDate.getDate());
  endDate.setHours(0,0,0,0);
  if (endDate < currentDate) {
    return 0;
  }
  var duration=0;
  if (isOffDay(currentDate,idProject) && currentDate.valueOf() != endDate.valueOf()) duration++;
  while (currentDate <= endDate) {
    if (!isOffDay(currentDate,idProject) || currentDate.valueOf() == endDate.valueOf()) {
      duration++;
    }
    currentDate=addDaysToDate(currentDate,1);
  }
  return duration;
}
/**
 * calculate diffence (in days) between dates
 */
function dayDiffDates(paramStartDate,paramEndDate) {
  var startDate=paramStartDate;
  var endDate=paramEndDate;
  var valDay=(24 * 60 * 60 * 1000);
  var duration=(endDate - startDate) / valDay;
  duration=Math.round(duration);
  return duration;
}

/**
 * Return the day of the week like php function : date("N",$valDate) Monday=1,
 * Tuesday=2, Wednesday=3, Thursday=4, Friday=5, Saturday=6, Sunday=7 (not 0 !)
 */
function getDay(valDate) {
  var day=valDate.getDay();
  day=(day == 0) ? 7 : day;
  return day;
}

/**
 * ============================================================================
 * Calculate new date after adding some days
 * 
 * @param paramDate
 *          start date
 * @param days
 *          numbers of days to add (can be < 0 to subtract days)
 * @return new calculated date
 */
function addDaysToDate(paramDate,paramDays) {
  var date=paramDate;
  var days=paramDays;
  var endDate=date;
  endDate.setDate(date.getDate() + days);
  return endDate;
}

/**
 * ============================================================================
 * Calculate new date after adding some work days, subtracting week-ends
 * 
 * @param $ate
 *          start date
 * @param days
 *          numbers of days to add (can be < 0 to subtract days)
 * @return new calculated date
 */
function addWorkDaysToDate_old(paramDate,paramDays) {
  var startDate=paramDate;
  var days=paramDays;
  if (days <= 0) {
    return startDate;
  }
  days-=1;
  if (getDay(startDate) >= 6) {
    // startDate.setDate(startDate.getDate()+8-getDay(startDate));
  }
  var weekEnds=Math.floor(days / 5);
  var additionalDays=days - (5 * weekEnds);
  if (getDay(startDate) + additionalDays >= 6) {
    weekEnds+=1;
  }
  days+=(2 * weekEnds);
  var endDate=startDate;
  endDate.setDate(startDate.getDate() + days);
  return endDate;
}

function addWorkDaysToDate(paramDate,paramDays, idProject) {
  if (paramDays<0) return removeWorkDaysToDate(paramDate, (-1)*paramDays, idProject);
  endDate=new Date(paramDate);
  left=paramDays;
  left--;
  while (left > 0) {
    endDate=addDaysToDate(endDate,1);
    if (!window.top.isOffDay(endDate,idProject)) {
      left--;
    }
  }
  return endDate;
}
function removeWorkDaysToDate(paramDate,paramDays, idProject) {
  endDate=new Date(paramDate);
  left=paramDays;
  left--;
  while (left > 0) {
    endDate=addDaysToDate(endDate,-1);
    if (! window.top.isOffDay(endDate,idProject)) {
      left--;
    }
  }
  return endDate;
}

function isDate(date) {
  if (!date) return false;
  if (date instanceof Date && !isNaN(date.valueOf())) return true;
  return false;
}

function getFirstDayOfWeek(week,year) {
  if (week >= 53) {
    var testDate=new Date(year,11,31);
  } else {
    var testDate=new Date(year,0,5 + (week - 1) * 7);
  }
  var day=testDate.getDate();
  var month=testDate.getMonth() + 1;
  var year=testDate.getFullYear();
  var testWeek=getWeek(day,month,year);

  while (testWeek >= week) {
    testDate.setDate(testDate.getDate() - 1);
    day=testDate.getDate();
    month=testDate.getMonth() + 1;
    year=testDate.getFullYear();
    testWeek=getWeek(day,month,year);
    if (testWeek > 10 && week == 1) {
      testWeek=0;
    }
  }
  testDate.setDate(testDate.getDate() + 1);
  return testDate;
}
function getFirstDayOfWeekFromDate(directDate) {
  var year=directDate.getFullYear();
  var week=getWeek(directDate.getDate(),directDate.getMonth() + 1,directDate.getFullYear()) + '';
  if (week == 1 && directDate.getMonth() > 10) {
    year+=1;
  } else if (week == 0) {
    week=getWeek(31,12,year - 1);
    if (week == 1) {
      var day=getFirstDayOfWeek(1,year);
      week=getWeek(day.getDate() - 1,day.getMonth() + 1,day.getFullYear());
    }
    year=year - 1;
  } else if (parseInt(week,10) > 53) {
    week='01';
    year+=1;
  } else if (parseInt(week,10) > 52) {
    lastWeek=getWeek(31,12,year);
    if (lastWeek == 1) {
      var day=getFirstDayOfWeek(1,year + 1);
      lastWeek=getWeek(day.getDate() - 1,day.getMonth() + 1,day.getFullYear());
    }
    if (parseInt(week,10) > parseInt(lastWeek,10)) {
      week='01';
      year+=1;
    }
  }
  var day=getFirstDayOfWeek(week,year);
  return day;

}

dateGetWeek=function(paramDate,dowOffset) {
  /*
   * getWeek() was developed by Nick Baicoianu at MeanFreePath:
   * http://www.meanfreepath.com
   */
  dowOffset=(dowOffset == null) ? 1 : dowOffset; // default dowOffset to 1
  // (ISO 8601)
  var newYear=new Date(paramDate.getFullYear(),0,1);
  var day=newYear.getDay() - dowOffset; // the day of week the year begins
  // on
  day=(day >= 0 ? day : day + 7);
  var daynum=Math.floor((paramDate.getTime() - newYear.getTime() - (paramDate.getTimezoneOffset() - newYear.getTimezoneOffset()) * 60000) / 86400000) + 1;
  var weeknum;
  // if the year starts before the middle of a week
  if (day < 4) {
    weeknum=Math.floor((daynum + day - 1) / 7) + 1;
    if (weeknum > 52) {
      nYear=new Date(paramDate.getFullYear() + 1,0,1);
      nday=nYear.getDay() - dowOffset;
      nday=nday >= 0 ? nday : nday + 7;
      /*
       * if the next year starts before the middle of the week, it is week #1 of
       * that year
       */
      weeknum=nday < 4 ? 1 : 53;
    }
  } else {
    weeknum=Math.floor((daynum + day - 1) / 7);
    if (weeknum > 52) {
      nYear=new Date(paramDate.getFullYear() + 1,0,1);
      nday=nYear.getDay() - dowOffset;
      nday=nday >= 0 ? nday : nday + 7;
      /*
       * if the next year starts before the middle of the week, it is week #1 of
       * that year
       */
      weeknum=nday < 4 ? 1 : 55;
    }
  }
  return weeknum;
};

function getWeek(day,month,year) {
  var paramDate=new Date(year,month - 1,day);
  return dateGetWeek(paramDate,1);
}

function showDeleteDateTextbox(widgetName) {
  widget=dijit.byId(widgetName);
  var hasDownArrow=(widget.get('hasDownArrow'))?true:false;
  if (widget.get('readOnly')) return;
  if (! widget.get('value')) return;
  deleteDiv="delete_"+widgetName;
  if (dojo.byId(deleteDiv)) {
    dojo.byId(deleteDiv).style.display='block';
    return;
  }
  node=dojo.byId("widget_"+widgetName);
  var newNode=document.createElement('div');
  newNode.setAttribute("id",deleteDiv);
  //newNode.setAttribute("class",'imageColorNewGui clearDateIcon');
  newNode.setAttribute("class",'clearDateIcon');
  newNode.setAttribute("refwidget",widgetName);
  if (hasDownArrow) newNode.style.left='75px';
  newNode.onclick = function (event) {
    event.stopPropagation();
    clearDate(this.getAttribute('refwidget'));
  };
  node.appendChild(newNode);
}
function hideDeleteDateTextbox(widgetName) {
  widget=dijit.byId(widgetName);
  if (widget.get('readOnly')) return;
  deleteDiv="delete_"+widgetName;
  if (dojo.byId(deleteDiv)) {
    dojo.byId(deleteDiv).style.display='none';
    return;
  }
}
function clearDate(widgetName) {
  widget=dijit.byId(widgetName);
  if (! widget) return;
  widget.set('value',null);
  widget.closeDropDown();
}