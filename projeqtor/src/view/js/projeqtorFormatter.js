/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 * This file is part of ProjeQtOr.
 * 
 * ProjeQtOr is free software: you can redistribute it and/or modify it under 
 * the terms of the GNU Affero General Public License as published by the Free 
 * Software Foundation, either version 3 of the License, or (at your option) 
 * any later version.
 * 
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
 * FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for 
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org 
 *     
 *** DO NOT REMOVE THIS NOTICE ************************************************/

// ============================================================================
// All specific ProjeQtOr functions and variables
// This file is included in the main.php page, to be reachable in every context
// ============================================================================
//=============================================================================
//= global formating functions)
//=============================================================================
/**
 * Format a JS date as YYYY-MM-DD
 * 
 * @param value
 *          the value
 * @return the formatted value
 */
function formatDate(date) {
  if (!date) {
    return '';
  }
  var month=date.getMonth() + 1;
  var year=date.getFullYear();
  var day=date.getDate();
  month=(month < 10) ? "0" + month : month;
  day=(day < 10) ? "0" + day : day;
  return year + "-" + month + "-" + day;
}
function formatTime(date) {
  if (!date) {
    return '';
  }
  var hours=date.getHours();
  var minutes=date.getMinutes();
  var seconds=date.getSeconds();
  hours=(hours < 10) ? "0" + hours : hours;
  minutes=(minutes < 10) ? "0" + minutes : minutes;
  seconds=(seconds < 10) ? "0" + seconds : seconds;
  return hours + ":" + minutes + ":" + seconds;
}

function getDate(dateString) {
  if (dateString.length != 10) return null;
  return new Date(dateString.substring(0,4),parseInt(dateString.substring(5,7),10) - 1,dateString.substring(8));
}

Date.isLeapYear = function (year) { 
  return (((year % 4 === 0) && (year % 100 !== 0)) || (year % 400 === 0)); 
};

Date.getDaysInMonth = function (year, month) {
  return [31, (Date.isLeapYear(year) ? 29 : 28), 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month];
};

Date.prototype.isLeapYear = function () { 
  return Date.isLeapYear(this.getFullYear()); 
};

Date.prototype.getDaysInMonth = function () { 
  return Date.getDaysInMonth(this.getFullYear(), this.getMonth());
};

Date.prototype.addMonths = function (value) {
  var n = this.getDate();
  this.setDate(1);
  this.setMonth(this.getMonth() + value);
  this.setDate(Math.min(n, this.getDaysInMonth()));
  return this;
};
// ============================================================================
// = FORMATTERS (available for dojox.DataGrid formating)
// ============================================================================

/**
 * ============================================================================
 * Format boolean to present a chechbox (checked or not depending on the value)
 * 
 * @param value
 *          the value of the boolean (true or false)
 * @return the formatted value as html code
 */
function booleanFormatter(value) {
  var checkedClass=(value != 0)?' booleanCheckBoxChecked':'';
  return '<div class="booleanCheckBoxContainer"><span class="booleanCheckBox' + checkedClass + '"></span></div>';
}

/**
 * ============================================================================
 * Format value to present a color
 * 
 * @param value
 *          the value of the boolean (true or false)
 * @return the formatted value as an image (html code)
 */
function colorFormatter(value) {
  notRounded=true;
  if (value) {
    // return '<table width="100%"><tr><td style="min-height:20px;border-radius:
    // 10px; padding: 5px 5px !important;background-color: '
    // + value + '; width: 100%;">&nbsp;</td></tr></table>';
    // return '<div class="colorDiv" style="'
    // +'min-height:10px !important;height:100% !important;text-align: center;'
    // +((notRounded)?'width:100%;':'width:90%;')
    // +((notRounded)?'':'border-radius: 10px;')
    // +((notRounded)?' margin:-5px; padding: 10px 5% !important;':'
    // margin:auto; padding: 5px 5% !important;')
    // +'background-color: '+ value + ';">&nbsp;</div>';
    return colorNameFormatter("&nbsp;#split#" + value);
  } else {
    return '';
  }
}

function hatchPatternFormatter(value) {
  if (!value || !/^(slash|backslash|vertical)(Dark)?(Large)?$/.test(value)) return '';
  var imageName='hatchPattern'+value.charAt(0).toUpperCase()+value.slice(1)+'.png';
  return '<table style="width:100%;height:100%"><tr><td style="text-align:center;vertical-align:middle">'
    +'<img style="display:block;margin:auto;width:39px;height:22px" src="images/'+imageName+'" />'
    +'</td></tr></table>';
}

/**
 * ============================================================================
 * Format value to present a name in a colored field
 * 
 * @param value
 *          the value of the boolean (true or false)
 * @return the formatted value as an image (html code)
 */
function colorNameFormatter(value) {
  notRounded=true;
  var heightPadding=(dojo.byId('GanttChartDIV')) ? '3' : '10';
  if (value) {
    var tab=value.split("#split#");
    if (tab.length > 1) {
      if (tab.length == 2) { // just found : val #split# color
        var val=tab[0];
        var color=tab[1];
        var order='';
      } else if (tab.length == 3) { // val #split# color #split# order
        var val=tab[1];
        var color=tab[2];
        var order=tab[0];
      } else { // should not be found
        return value;
      }
      var foreColor='#000000';
      if (color.length == 7) {
        var red=color.substr(1,2);
        var green=color.substr(3,2);
        var blue=color.substr(5,2);
        var light=(0.3) * parseInt(red,16) + (0.6) * parseInt(green,16) + (0.1) * parseInt(blue,16);
        if (light < 128) {
          foreColor='#FFFFFF';
        }
      }
      if (isModernUi) {
        return '<span style="display:none;">' + order + '</span>'
          + '<div data-formatter="color" style="overflow:hidden;display: flex;justify-content: center;align-items: center;flex-direction: column;vertical-align:middle;'
          + ' min-height: 18px;border-radius:10px;text-align: center;background-color:' + color + ';color:' + foreColor + ';width: 100%;margin-top:2px;">' 
          + val + '</div>';
      } else {
      return '<span style="display:none;">' + order + '</span>' + '<table style="margin:0px -5%; min-height:10px !important;width:110%; height:100%">' + '  <tr style="height:100% !important;">'
          + '    <td style="text-align: center;background-color:' + color + ';color:' + foreColor + ';width: 100%;">' + val + '</td>' // padding:3px
          // !important;
          + '  </tr>' + '</table>';
      }
      // + '<div class="colorNameDiv" style="'
      // +'min-height:10px !important;height:100% !important;text-align:
      // center;'
      // +((notRounded)?'width:100%;':'width:90%;')
      // +((notRounded)?'':'border-radius: 10px;')
      // +((notRounded)?' margin:-5px; padding: '+heightPadding+'px 5%
      // !important;':' margin:auto; padding: 5px 5% !important;')
      // +'background-color: '+ color + '; color:' + foreColor + ';">' + val
      // + '</div>';
    } else {
      return value;
    }
  } else {
    return '';
  }
}
function colorTranslateNameFormatter(value,notRounded) {
  notRounded=true;
  if (value) {
    var tab=value.split("#split#");
    if (tab.length > 1) {
      if (tab.length == 2) { // just found : val #split# color
        var val=tab[0];
        var color=tab[1];
        var order='';
      } else if (tab.length == 3) { // val #split# color #split# order
        var val=tab[1];
        var color=tab[2];
        var order=tab[0];
      } else { // should not be found
        return value;
      }
      var foreColor='#000000';
      if (color.length == 7) {
        var red=color.substr(1,2);
        var green=color.substr(3,2);
        var blue=color.substr(5,2);
        var light=(0.3) * parseInt(red,16) + (0.6) * parseInt(green,16) + (0.1) * parseInt(blue,16);
        if (light < 128) {
          foreColor='#FFFFFF';
        }
      }
      if (isModernUi) {
        return '<span style="display:none;">' + order + '</span>'
          + '<div data-formatter="color" style="overflow:hidden;display: flex;justify-content: center;align-items: center;flex-direction: column;vertical-align:middle;'
          + ' min-height: 18px;border-radius:10px;text-align: center;background-color:' + color + ';color:' + foreColor + ';width: 100%;margin-top:2px">' 
          + i18n(val) + '</div>';
      } else {
        return '<span style="display:none;">' + order + '</span>' + '<table style="position:relative; margin:0px -5%; min-height:10px !important;width:110%; height:100%">'
            + '  <tr style="height:100% !important;">' + '    <td style="text-align: center;padding:3px !important;background-color:' + color + ';color:' + foreColor + ';width: 100%;">' + i18n(val)
            + '</td>' + '  </tr>' + '</table>';
      }

      // + '<div class="colorNameDiv" style="'
      // +'min-height:10px !important;height:100% !important;text-align:
      // center;'
      // +((notRounded)?'width:100%;':'width:90%;')
      // +((notRounded)?'':'border-radius: 10px;')
      // +((notRounded)?' margin:-5px; padding: 10px 5% !important;':'
      // margin:auto; padding: 5px 5% !important;')
      // +'background-color: '+ color + '; color:' + foreColor + ';">' +
      // i18n(val)
      // + '</div>';
    } else {
      return i18n(value);
    }
  } else {
    return '';
  }
}

function statusColorFormatter(name, idStatus){
  var color = (idStatus)?statusColorArray[idStatus]:statusColorArray[1];
  var status = (name)?name+'#split#'+color:idStatus+'#split#'+color;
  return colorNameFormatter(status);
}
/**
 * ============================================================================
 * Format boolean to present a color
 * 
 * @param value
 *          the value of the boolean (true or false)
 * @return the formatted value as an image (html code)
 */
function translateFormatter(value,prefix) {
  if (value) {
    var val=value.split('#!#!#!#!#!#');
    return i18n(val[0]);
  } else {
    return '';
  }
}

function tagFormatter(value) {
  if (!value) return '';
  var tags=value.split('#');
  var result=[];
  for (var i=0; i<tags.length; i++) {
    if (tags[i]) result.push(tags[i]);
  }
  return result.join(', ');
}

/**
 * ============================================================================
 * Format percent value
 * 
 * @param value
 *          the value of the boolean (true or false)
 * @return the formatted value as an image (html code)
 */
function percentFormatter(value) {
  if (value) {
    var pct=parseInt(value,10);
    var pctTxt='<div style="width:100%;text-align:center;">' + pct + '&nbsp;%</div>';
    pctTxt+='<div style="height:3px;width:100%;position: relative; bottom:0px;">';
    pctTxt+='<div style="height:3px;width:' + pct + '%;position: absolute;left:0%;background-color:#AAFFAA">&nbsp;</div>';
    pctTxt+='<div style="height:3px;width:' + (100 - pct) + '%;position: absolute;left:' + pct + '%; background-color:#FFAAAA">&nbsp;</div>';
    pctTxt+='</div>';
    return pctTxt;
  } else {
    return '';
  }
}

function percentSimpleFormatter(value, whitoutZero) {
  if(whitoutZero == undefined)whitoutZero=true;
  if (value) {
    var result=(whitoutZero)?dojo.number.format(Math.round(value * 100) / 100).replace(/^0+/g,''):dojo.number.format(Math.round(value * 100) / 100);
    return '<div style="width:100%;text-align:center;">' + result + '&nbsp;%</div>';
  } else {
    return '';
  }
}

function dayFormatter(value) {
  var val=parseInt(value,10);
  if (value == '') {
    return '';
  } else if (val <= 1) {
    return value + ' ' + i18n('day');
  } else {
    return value + ' ' + i18n('days');
    ;
  }
}
/**
 * ============================================================================
 * Format numeric value (removes leading zeros)
 * 
 * @param value
 *          the value
 * @return the formatted value
 */
function numericFormatter(value, align) {
  var result=value;
  if (value === null || value=='NaN') result='';
  else result=dojo.number.format(value);
  // var result = value.replace(/^0+/g, '');
  // result = value.replace(/^0+/g,'');
  var textAlign = (typeof align === 'string' || align instanceof String)?align:'right';
  return '<div style="width:100%;text-align:'+textAlign+';">' + result + '</div>';
}
  
function idFormatter(value) {
  var result=value;
  if (value === null) result='';
  // else result=dojo.number.format(value);
  var result=value.replace(/^0+/g,'');
  result=value.replace(/^0+/g,'');
  return '<div style="width:100%;text-align:center;">' + result + '</div>';
}
function decimalFormatter(value) {
  var roundedValue=dojo.number.format(Math.round(value * 100) / 100);
  return '<div style="width:100%;text-align:right;">' + roundedValue + '</div>';
}
function decimalAsNumericFormatter(value) {
  var roundedValue=dojo.number.format(Math.round(value));
  return '<div style="width:100%;text-align:right;">' + roundedValue + '</div>';
}

function durationFormatter(value) {
  return value + ' ' + i18n('shortDay');
}

var hiddenField='<span style="color:#AAAAAA">(...)</span>';
// Show work in days into correct format
function workFormatter(value, align,forPlanningLine,withoutDecimals) {
  if (withoutDecimals==undefined) withoutDecimals=false;
  if (value == null) return null;
  if (value == '-') return hiddenField;
  // result=dojo.number.format(value);
  var paramUnit=window.top.paramWorkUnit;
  if (dojo.byId('objectClassList') && (dojo.byId('objectClassList').value == 'Ticket' || dojo.byId('objectClassList').value == 'TicketSimple' || dojo.byId('objectClassList').value == 'Resource')) {
    paramUnit=window.top.paramImputationUnit;
  }
  if (paramUnit != 'days') {
    value=value * window.top.paramHoursPerDay;
  }
  // roundedValue = dojo.number.format(Math.round(value * 100) / 100, {
  // places:2} );
  if (withoutDecimals===true) value=Math.round(value);
  roundedValue=dojo.number.format(Math.round(value * 100) / 100);
  // var result = roundedValue.replace(/^0+/g,'');
  // result = value.replace(/^0+/g,'');
  var unit=(paramUnit == 'days') ? i18n('shortDay') : i18n('shortHour');
  var textAlign = (typeof align === 'string' || align instanceof String)?align:'right';
  if (forPlanningLine) return roundedValue + '&nbsp;' + unit;
  return '<div style="width:100%;text-align:'+textAlign+';">' + roundedValue + '&nbsp;' + unit + '</div>';
}
// Convert work into days, depending on input unit
function workConverter(value) {
  paramUnit=window.top.paramImputationUnit;
  if (paramUnit != 'days') {
    value=value / window.top.paramHoursPerDay;
  }
  return value;
}

function costFormatter(value, align, forPlanningLine,withoutDecimals) {
  if (withoutDecimals==undefined) withoutDecimals=false;
  if (value == null) return null;
  if (value == '-') return hiddenField;
  if (forPlanningLine!==true) forPlanningLine=false;
  // result=dojo.number.format(value);
  //var rounding=(withoutZero && value==Math.round(value))?0:2;
  var rounding=(forPlanningLine)?0:2;
  if (withoutDecimals===true) rounding=0;
  roundedValue=dojo.number.format(Math.round(value * 100) / 100,{
    places:rounding
  });
  var textAlign = (typeof align === 'string' || align instanceof String)?align:'right';
  if (window.top.paramCurrencyPosition == 'before') {
    if (forPlanningLine) return window.top.paramCurrency + '&nbsp;' + roundedValue ;
    else return '<div style="width:100%;text-align:'+textAlign+';">' + window.top.paramCurrency + '&nbsp;' + roundedValue + '</div>';
  } else {
    if (forPlanningLine) return roundedValue + '&nbsp;' + window.top.paramCurrency;
    else return '<div style="width:100%;text-align:'+textAlign+';">' + roundedValue + '&nbsp;' + window.top.paramCurrency + '</div>';
  }
}
function costFormatterLocal(value, align) {
  if (value == null) return null;
  if (value == '-') return "";
  valSplit=value.split("#");
  value=valSplit[0];
  currency=(valSplit.length>1)?valSplit[1]:"";
  currencyPosition=(valSplit.length>2)?valSplit[2]:"";
  roundedValue=dojo.number.format(Math.round(value * 100) / 100,{
    places:2
  });
  var textAlign = (typeof align === 'string' || align instanceof String)?align:'right';
  if (currencyPosition == 'before') {
    return '<div style="width:100%;text-align:'+textAlign+';" class="localDisplayClassGrid">' + currency + '&nbsp;' + roundedValue + '</div>';
  } else if (currencyPosition == 'after') {
    return '<div style="width:100%;text-align:'+textAlign+';" class="localDisplayClassGrid">' + roundedValue + '&nbsp;' + currency + '</div>';
  } else if (currency) {
    return '<div style="width:100%;text-align:'+textAlign+';" class="localDisplayClassGrid">' + roundedValue + '</div>';
  } else {
    return "";
  }
}
/**
 * ============================================================================
 * Format date value (depends on locale)
 * 
 * @param value
 *          the value
 * @return the formatted value
 */
function dateFormatter(value) {
  fmt=window.top.getBrowserLocaleDateFormatJs();
  if (!value) return '';
  if (value.length == 19) {
    value=value.substr(0,10);
  }
  var inherited=false;
  if (value.length == 11 && value.substr(10,1)=='#') {
    value=value.slice(0,10);
    inherited=true;
  }
  if (value.length == 10) {
    vDate=dojo.date.locale.parse(value,{
      selector:"date",
      datePattern:"yyyy-MM-dd"
    });
    if (!vDate || !fmt) {
      return value;
    }
    var display=dojo.date.locale.format(vDate,{
      datePattern:fmt,
      formatLength:"short",
      fullYear:true,
      selector:"date"
    });
    if (inherited) {
      display='<span style="font-style:italic;color:#cccccc">'+display+"</span>";
    }
    return display;
  } else {
    return value;
  }
}

function longDateFormatter(value) {
  if (value.length == 10) {
    vDate=dojo.date.locale.parse(value,{
      selector:"date",
      datePattern:"yyyy-MM-dd"
    });
    return dojo.date.locale.format(vDate,{
      formatLength:"long",
      fullYear:true,
      selector:"date"
    });
  } else {
    return value;
  }
}
/**
 * ============================================================================
 * Format date & time value (depends on locale)
 * 
 * @param value
 *          the value
 * @return the formatted value
 */
/**
 * ============================================================================
 * Format date & time value (depends on locale)
 * 
 * @param value
 *          the value
 * @return the formatted value
 */
function dateTimeFormatter(value) {
  fmt=window.top.getBrowserLocaleDateFormatJs();
  if (value && value.length == 19) {
    vDate=dojo.date.locale.parse(value,{
      datePattern:"yyyy-MM-dd",
      timePattern:"HH:mm:ss",
      selector:'date and time'
    });
    if (!vDate) {
      vDate=new Date(value.substr(0,4),(parseInt(value.substr(5,2),10)) - 1,value.substr(8,2),value.substr(11,2),value.substr(14,2),value.substr(17,2),0);
      if (!vDate) {
        return dateFormatter(value.substr(0,10)) + " " + value.substr(11,5);
      }
    }
    var displayDate=dojo.date.locale.format(vDate,{
      datePattern:fmt,
      formatLength:"short",
      timePattern:window.top.browserLocaleTimeFormat,
      fullYear:true
    });
    if (displayDate.substr(11) == '00:00' || displayDate.substr(11) == '00:00:00') {
      displayDate=displayDate.substr(0,10);
    }
    return displayDate;
  } else {
    return value;
  }
}
function timeFormatter(value) {
  if (value.length == 19) {
    vDate=dojo.date.locale.parse(value,{
      datePattern:"yyyy-MM-dd",
      timePattern:"HH:mm:ss",
      selector:'date and time'
    });
    if (!vDate) {
      vDate=new Date(value.substr(0,4),(parseInt(value.substr(5,2),10)) - 1,value.substr(8,2),value.substr(11,2),value.substr(14,2),value.substr(17,2),0);
      if (!vDate) {
        return value.substr(11,5);
      }
    }
    if (!vDate || vDate == undefined) return value;
    return dojo.date.locale.format(vDate,{
      formatLength:"time",
      timePattern:window.top.browserLocaleTimeFormat
    });
  } else {
    var dateFormattedValue="2000-01-01 " + value;
    if (dateFormattedValue.length == 19) return timeFormatter(dateFormattedValue);
    else return value;
  }
}

function sortableFormatter(value) {
  if (!value) {
    return '';
  }
  var tab=value.split('.');
  var result='';
  for (var i=0;i < tab.length;i++) {
    result+=(result != "") ? "." : "";
    result+=tab[i].replace(/^0+/,"");
  }
  return result;
}

function classNameFormatter(value) {
  var res=value.split('|');
  var className=res[0];
  var classId=(res.length > 1) ? res[1] : '';
  return '<div><table><tr><td><div class="imageColorNewGuiNoSelection icon' + classId + '16 icon' + classId + ' iconSize16"></div></td><td>&nbsp;</td><td>' + className + '</td></tr></table></div>';
}

function thumb16(value) {
  return thumb(value,16);
}
function thumb22(value) {
  return thumb(value,22);
}
function thumb32(value) {
  return thumb(value,32);
}
function thumb48(value) {
  return thumb(value,48);
}
function thumb64(value) {
  return thumb(value,64);
}
function thumbName16(value) {
  return thumbNameSize(value,16);
}
function thumbName22(value) {
  return thumbNameSize(value,22);
}
function thumbName32(value) {
  return thumbNameSize(value,32);
}
function thumbName48(value) {
  return thumbNameSize(value,48);
}
function thumbName64(value) {
  return thumbNameSize(value,64);
}
function thumbNameSize(value,size) {
  var tab=value.split('#!#');
  if (tab.length > 1) value=tab[1];
  var name=tab[0];
  return thumb(value,size,name);
}
function thumb(value,size,nameAffectable) {
  if (nameAffectable == undefined) nameAffectable='';
  if (value == "##" || value == "####") return "";
  if (!size) size=32;
  var tab=value.split('#');
  filePath=tab[0];
  var nocache='';
  var searchNocache=filePath.indexOf('?');
  if (searchNocache > 0) {
    nocache=filePath.substring(searchNocache);
  }
  thumbName="";
  if (tab.length > 4) {
    thumbName=tab[4];
  }

  thumbObjectClass='Attachment';
  if (nameAffectable) {
    thumbObjectClass='Affectable';
  } else if (tab.length > 3) {
    thumbObjectClass=tab[3];
  }  
  thumbObjectId=tab[1];
  fileName=tab[2];
  var radius=Math.round(size / 2);
  var result='';
  if (filePath) {
    if (filePath == 'letter') {
      var arrayColors=new Array('#1abc9c','#2ecc71','#3498db','#9b59b6','#34495e','#16a085','#27ae60','#2980b9','#8e44ad','#2c3e50','#f1c40f','#e67e22','#99CC00','#e74c3c','#95a5a6','#d35400',
          '#c0392b','#bdc3c7','#7f8c8d');
      var ind=tab[1] % arrayColors.length;
      var bgColor=arrayColors[ind]; // TODO : test if is set
      var fontSize=(size == 32) ? 24 : ((size == 16) ? 10 : 15);
      var name=tab[2];
      var initial=tab[2].substr(0,1).toUpperCase();
      if (tab.length >= 4 && tab[3] != "") initial=tab[3].toUpperCase();
      if (nameAffectable!=name && nameAffectable) {
        name=nameAffectable;
        initial=name.charAt(0).toUpperCase(); 
      }
      if (name) {
        result+='<div style="text-align:left">';
      } else {
        result+='<div style="text-align:center">';
      }
      result+='<table style="width:100%;height:100%;"><tr style="height:100%">';
      result+='<td style="width:10px;vertical-align:middle;"><span style="position:relative;color:#ffffff;background-color:' + bgColor + ';display:inline-block;';
      if (name) result+='float:left;';
      result+='font-size:' + fontSize + 'px;border-radius:50%;font-weight:300;text-shadow:none;text-align:center;border:1px solid #eeeeee;height:' + (size - 2) + 'px;width:' + (size - 2)
          + 'px; top:1px;" >';
      result+=initial;
      result+='</span></td>';
      if (name) {
        result+='<td style="width:1px">&nbsp;</td><td style="vertical-align:middle;">';
        result+=name;
        result+='</td>';
      }
      result+='</tr></table>';
      result+='</div>';
    } else {
      result+='<div style="' + ((thumbName) ? 'text-align:left;' : 'text-align:center;') + '">';
      result+='<table style="width:100%;height:100%;"><tr style="height:100%">';
      result+='<td style="width:10px;vertical-align:middle;"><img style="border-radius:' + radius + 'px;height:' + size + 'px;' + ((thumbName) ? 'float:left;' : '') + '" src="' + filePath + '"';
      if (filePath.substr(0,23) != '../view/img/Affectable/') {
        result+=' onMouseOver="showBigImage(\'' + thumbObjectClass + '\',\'' + thumbObjectId + '\',this,null,null,\'' + nocache + '\');"';
        result+=' onMouseOut="hideBigImage();"';
      }
      result+=' /></td>';
      if (thumbName) {
        // text-shadow:1px 1px #FFFFFF; Can ease view when test is over thumb,
        // but is ugly when line is selected (when text color is white)
        result+='<td style="width:1px">&nbsp;</td><td style="vertical-align:middle;">' + thumbName + '</td>';
      }
      result+='</tr></table>';
      result+='</div>';
    }
  } else {
    result=thumbName;
  }
  return result;
}

function iconFormatter(value) {
  if (!value) return "";
  return '<table style="width:100%"><tr><td style="text-align:center"><img style="height:22px" src="icons/' + value + '" /></td></tr></table>';
}
function iconName16(value) {
  return iconName(value,16);
}
function iconName22(value) {
  return iconName(value,22);
}
function iconName32(value) {
  return iconName(value,32);
}
function iconName(value,size) {
  if (!value) return "";
  if (!size) size=22;
  var tab=value.split('#!#');
  if (tab.length < 2) return value;
  var icon=tab[1];
  var name=tab[0];
  if (icon) return '<table><tr><td><img style="height:' + size + 'px" src="icons/' + icon + '" /></td><td>&nbsp;</td><td >' + name + '</td></tr></table>';
  else return '<table><tr><td></td><td>&nbsp;</td><td >' + name + '</td></tr></table>';
}

function privateFormatter(value) {
  if (value == 0) {
    return "";
  } else {
    return '<div style="width:100%;text-align:center"><img style="height:16px" src="img/private.png" /></div>';
  }
}

var cryptFrom="A;B;C;D;E;F;G;H;I;J;K;L.M;N;O;P;Q;R;S;T;U;V;W;X;Y;Z;a;à;â;b;c;ç;d;e;é;è;ê;f;g;h;i;î;ï;j;k;l;m;n;o;ô;p;q;r;s;t;u;û;ù;v;w;x;y;z;; ;?;';(;)1;2;3;4;5;6;7;8;9;0".split(';');
var cryptTo="2;3;4;5;6;7;8;9;0;A;B;C;D;E;F;G;H;I;J;K;L.M;N;O;P;Q;R;S;T;U;V;W;X;Y;Z;a;à;â;b;c;ç;d;e;é;è;ê;f;g;h;i;î;ï;j;k;l;m;n;o;ô;p;q;r;s;t;u;û;ù;v;w;x;y;z;1; ;?;';(;)".split(';');
function simpleCrypt(inStr) {
  var outStr="";
  if (inStr.charAt(0) == '=') return btoa(inStr.substr(1));
  for (var i=0;i < inStr.length;i++) {
    outStr+=cryptTo[cryptFrom.indexOf(inStr.charAt(i))];
  }
  return outStr;
}
function simpleDecrypt(inStr) {
  var outStr="";
  if (inStr.charAt(0) == '=') return atob(inStr.substr(1));
  for (var i=0;i < inStr.length;i++) {
    outStr+=cryptFrom[cryptTo.indexOf(inStr.charAt(i))];
  }
  return outStr;
}

function formatSmallButton(classname,imageColorNewGuiNoSelection) {
  var result="<span class='" + (imageColorNewGuiNoSelection ? '' : 'roundedButtonSmall') + "' style='top:0px;display:inline-block;width:16px;height:16px;'><div class='iconButton" + classname + "16 iconButton" + classname
      + " iconSize16' style='' >&nbsp;</div></span>";
  return result;
}

if (document.addEventListener) {
  var keys=[];
  var konami="38,38,40,40,37,39,37,39,66,65";
  document.addEventListener("keydown",function(e) {
    keys.push(e.keyCode);
    if (konami.indexOf(keys.toString()) == 0) {
      if (keys.toString().indexOf(konami) >= 0) {
        var rnd=Math.floor(Math.random() * konamiMsg.length);
        showInfo(simpleDecrypt(konamiMsg[rnd]));
        keys=[];
      }
      ;
    } else {
      keys=[];
    }
  },true);
};

function formatUpperName(name) {
  var spl=name.split('#!#!#!#!#!#');
  var iconClass = '';
  var result='';
  if(spl[0].indexOf('#:#:#:#:#:#') != -1){
    iconClass = spl[0].split('#:#:#:#:#:#')[0]; // Seperator for iconClass set in jsonQuery.php for iconResourceTeam
  }
  if(iconClass){
    splName = spl[0].split('#:#:#:#:#:#')[1];
    result = '<table><tr><td><img class="imageColorNewGui" style="height:16px" src="css/customIcons/new/' + iconClass + '.svg" /></td><td>&nbsp;</td><td >' + splName + '</td></tr></table>';
  }else{
    result = spl[1];
  }
  return result;
}

function indicatorFormatter(value) {
  var parts = value.split('#');
  var note = 0;
  var link = 0;
  var attach = 0;
  for (var i = 0; i < parts.length; i++) {
    if (parts[i] === 'Note' && parts[i+1]) {
      note = parts[i+1];
    } else if (parts[i] === 'Link' && parts[i+1]) {
      link = parts[i+1];
    } else if (parts[i] === 'Attach' && parts[i+1]) {
      attach = parts[i+1];
    }
  }
  var result = '';

  if (link != 0) {
    result += '<div style="display: flex; align-items: center;flex-direction: column;">';
    result += '<div style="font-size:9px;padding-left: 3px;">' + link + '</div>';
    result += "<div class='imageColorNewGuiNoSelection'>" + formatSmallButton('ListLnk', true) + "</div>";
    result += '</div>';
  }
  if (attach != 0) {
    result += '<div style="display: flex; align-items: center;flex-direction: column;">';
    result += '<div style="font-size:9px;padding-left: 3px;">' + attach + '</div>';
    result += "<div class='imageColorNewGuiNoSelection'>" + formatSmallButton('ListAtt', true) + "</div>"; 
    result += '</div>';
  }
  if (note != 0) {
    result += '<div style="display: flex;align-items: center;flex-direction: column;">';
    result += '<div style="font-size:9px;padding-left: 3px;">' + note + '</div>';
    result += "<div class='imageColorNewGuiNoSelection'>" + formatSmallButton('ListNot', true) + "</div>";
    result += '</div>';
  }
  return '<div style="display: flex; justify-content: flex-end; width: 100%;gap:4px;">' + result + '</div>';
}

// var konamiMsg = [ '5ùhmuôçYgluêYuôYgluû',
// 'FhmjïmhçuàljYufhXYklYuïmRgXuhguYkluêYufYçêêYmjuû', 'NcRluYêkYuû',
// 'NcRluXçXurhmuYqîYVluû'];
var konamiMsg=['=PGgzPjxiPlByb2plUXRPcjwvYj48L2gzPgp0aGUgUXVhbGl0eSBiYXNlZCBQcm9qZWN0IE9yZ2FuaXplciB0aGF0IGVubGlnaHRlbnMgeW91ciBwcm9qZWN0cy48YnIvPgpDb3B5cmlnaHQgKEMpIDIwMDktMjAyMSAtIFBST0pFUVRPUiBbUGFzY2FsIEJFUk5BUkRdPGJyLz4KPGJyLz4KVGhpcyBwcm9ncmFtIGlzIGZyZWUgc29mdHdhcmU6IHlvdSBjYW4gcmVkaXN0cmlidXRlIGl0IGFuZC9vciBtb2RpZnkgaXQgCnVuZGVyIHRoZSB0ZXJtcyBvZiB0aGUgR05VIEFmZmVybyBHZW5lcmFsIFB1YmxpYyBMaWNlbnNlIGFzIHB1Ymxpc2hlZCBieSB0aGUgCkZyZWUgU29mdHdhcmUgRm91bmRhdGlvbiwgdmVyc2lvbiAzIG9mIHRoZSBMaWNlbnNlLCBvciAoYXQgeW91ciBvcHRpb24pIAphbnkgbGF0ZXIgdmVyc2lvbi48YnIvPgo8YnIvPgpUaGlzIHByb2dyYW0gaXMgZGlzdHJpYnV0ZWQgaW4gdGhlIGhvcGUgdGhhdCBpdCB3aWxsIGJlIHVzZWZ1bCwgCmJ1dCBXSVRIT1VUIEFOWSBXQVJSQU5UWTsgd2l0aG91dCBldmVuIHRoZSBpbXBsaWVkIHdhcnJhbnR5IG9mIApNRVJDSEFOVEFCSUxJVFkgb3IgRklUTkVTUyBGT1IgQSBQQVJUSUNVTEFSIFBVUlBPU0UuPGJyLz4gClNlZSB0aGUgR05VIEdlbmVyYWwgUHVibGljIExpY2Vuc2UgZm9yIG1vcmUgZGV0YWlscy48YnIvPgpZb3UgY2FuIGZpbmQgYSBjb3B5IG9mIHRoZSBHTlUgR2VuZXJhbCBQdWJsaWMgTGljZW5zZSBhdCA8YSBocmVmPSdodHRwOi8vd3d3LmdudS5vcmcvbGljZW5zZXMvJz5odHRwOi8vd3d3LmdudS5vcmcvbGljZW5zZXMvPC9hPi48YnIvPgo8YnIvPgo8Yj5MaW1pdHM8L2I+PGJyLz4KPGJyLz4KSW4gYW55IGNhc2UsIGlmIHlvdSByZS1kaXN0cmlidXRlIHRoaXMgcHJvZHVjdCB5b3UgbXVzdCA6PGJyLz4KIC0gZGlzdHJpYnV0ZSBpdCB1bmRlciBBR0xQIFYzIGxpY2Vuc2UgKG9yIGFib3ZlKSBhbmQgc28gaGF2ZSB0byBwcm92aWRlIAogICBzb3VyY2UgY29kZTxici8+CiAtIHJlZmVyZW5jZSBvcmlnaW5hbCBwcm9kdWN0IChQcm9qZVF0T3IpPGJyLz4KIC0gbm90IGxldCBhbnkgYW1iaWd1aXR5IGFib3V0IG9yaWdpbiBvZiBwcm9kdWN0LCB3aGljaCBjb3VsZCBsZWFkIHRvIHRoaW5rIAogICB0aGF0IHlvdSBhcmUgdGhlIGF1dGhvciBvZiB0aGUgcHJvZHVjdDxici8+IApEaXN0cmlidXRpb24gYWxzbyBpbmNsdWRlcyBkZWxpdmVyeSBldmVuIHRvIG9uZSBvbmx5IGN1c3RvbWVyIGFuZCAKZGlzdHJpYnV0aW9uIG9mIGEgc2VydmljZSB1c2luZyBQcm9qZVF0T3IgY29kZSAoc2VlIEFHUEwgVjMgbGljZW5zZSkuPGJyLz4g'];
