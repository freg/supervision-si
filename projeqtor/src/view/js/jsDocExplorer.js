/*** COPYRIGHT NOTICE *********************************************************
/*
* Copyright (c) 2009, Shlomy Gantz BlueBrick Inc. All rights reserved.
*
* Redistribution and use in source and binary forms, with or without
* modification, are permitted provided that the following conditions are met:
*     * Redistributions of source code must retain the above copyright
*       notice, this list of conditions and the following disclaimer.
*     * Redistributions in binary form must reproduce the above copyright
*       notice, this list of conditions and the following disclaimer in the
*       documentation and/or other materials provided with the distribution.
*     * Neither the name of Shlomy Gantz or BlueBrick Inc. nor the
*       names of its contributors may be used to endorse or promote products
*       derived from this software without specific prior written permission.
*
* THIS SOFTWARE IS PROVIDED BY SHLOMY GANTZ/BLUEBRICK INC. ''AS IS'' AND ANY
* EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
* WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
* DISCLAIMED. IN NO EVENT SHALL SHLOMY GANTZ/BLUEBRICK INC. BE LIABLE FOR ANY
* DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
* (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
* LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
* ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
* (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
* SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*
* =============================================================================
*
* This file has bee adapted and is part of ProjeQtOr.
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


var refreshJsonDocumentExplorerInProgress = false;
var documentExplorerDirectoryList = null;
var documentExplorerDocumentList = null;

var documentExplorerColumnOrder = new Array();

planningFieldsDescription[getIndiceForPlanningType('directory')] = new Array(
  {name:"Name",        show:true,  order:0, width:300, minWidth:100, showSpecif:true, type:"text",    inputType:"dijit/form/TextBox",         rawValue:new Array(), showValue:new Array(), editable:true,  custom:false, customName:null},
  {name:"Id",          show:false, order:1, width:60,  minWidth:50,  showSpecif:true, type:"number",  inputType:"dijit/form/NumberTextBox",   rawValue:new Array(), showValue:new Array(), editable:false, custom:false, customName:null},
  {name:"Location",    show:false, order:4, width:200, minWidth:50,  showSpecif:true, type:"text",    inputType:"dijit/form/TextBox",         rawValue:new Array(), showValue:new Array(), editable:false, custom:false, customName:null},
  {name:"IdProject", show:false, order:2, width:120, minWidth:50,  showSpecif:true, type:"select",  inputType:"dijit/form/FilteringSelect", rawValue:new Array(), showValue:new Array(), editable:true,  custom:false, customName:null},
  {name:"IdProduct", show:false, order:3, width:120, minWidth:50,  showSpecif:true, type:"select",  inputType:"dijit/form/FilteringSelect", rawValue:new Array(), showValue:new Array(), editable:true,  custom:false, customName:null},
  {name:"Idle",        show:false, order:5, width:60,  minWidth:50,  showSpecif:true, type:"boolean", inputType:"dijit/form/CheckBox",        rawValue:new Array(), showValue:new Array(), editable:false, custom:false, customName:null}
);
planningFieldsDescription[getIndiceForPlanningType('document')] = new Array(
  {name:"Name",                show:true,  order:0, width:260, minWidth:100, showSpecif:true, type:"text",    inputType:"dijit/form/TextBox",         rawValue:new Array(), showValue:new Array(), editable:true,  custom:false, customName:null},
  {name:"Id",                  show:true,  order:1, width:60,  minWidth:50,  showSpecif:true, type:"number",  inputType:"dijit/form/NumberTextBox",   rawValue:new Array(), showValue:new Array(), editable:false, custom:false, customName:null},
  {name:"IdProject",         show:true,  order:2, width:120, minWidth:50,  showSpecif:true, type:"select",  inputType:"dijit/form/FilteringSelect", rawValue:new Array(), showValue:new Array(), editable:true,  custom:false, customName:null},
  {name:"IdProduct",         show:true,  order:4, width:120, minWidth:50,  showSpecif:true, type:"select",  inputType:"dijit/form/FilteringSelect", rawValue:new Array(), showValue:new Array(), editable:true,  custom:false, customName:null},
  {name:"IdDocumentType",    show:true,  order:3, width:120, minWidth:50,  showSpecif:true, type:"select",  inputType:"dijit/form/FilteringSelect", rawValue:new Array(), showValue:new Array(), editable:true,  custom:false, customName:null},
  {name:"DocumentReference",   show:true,  order:6, width:160, minWidth:50,  showSpecif:true, type:"text",    inputType:"dijit/form/TextBox",         rawValue:new Array(), showValue:new Array(), editable:false, custom:false, customName:null},
  {name:"IdStatus",     show:true,  order:7, width:120, minWidth:50,  showSpecif:true, type:"select",  inputType:"dijit/form/FilteringSelect", rawValue:new Array(), showValue:new Array(), editable:true,  custom:false, customName:null},
  {name:"IdDocumentVersion", show:false, order:5, width:120, minWidth:50,  showSpecif:true, type:"select",  inputType:"dijit/form/FilteringSelect", rawValue:new Array(), showValue:new Array(), editable:false, custom:false, customName:null},
  {name:"Locked",              show:false, order:9, width:60,  minWidth:50,  showSpecif:true, type:"boolean", inputType:"dijit/form/CheckBox",        rawValue:new Array(), showValue:new Array(), editable:false, custom:false, customName:null},
  {name:"Idle",                show:false, order:8, width:60,  minWidth:50,  showSpecif:true, type:"boolean", inputType:"dijit/form/CheckBox",        rawValue:new Array(), showValue:new Array(), editable:false, custom:false, customName:null}
);

function documentExplorerSetFieldLabel(field, value, planningType) {
  return setPlanningField('label', field, value, planningType);
}
function documentExplorerGetFieldLabel(field, planningType) {
  return getPlanningField('label', field, planningType);
}

function documentExplorerResetFieldsDescription() {
  ['directory', 'document'].forEach(function(explorerType) {
    var idx = getIndiceForPlanningType(explorerType);
    if (! planningFieldsDescription[idx]) return;
    for (var j = 0; j < planningFieldsDescription[idx].length; j++) {
      planningFieldsDescription[idx][j].showValue = new Array();
      planningFieldsDescription[idx][j].rawValue  = new Array();
    }
  });
}

var DocumentExplorerItem = function(pItem, pPlanningType) {
  var vPlanningTypeIndice=getIndiceForPlanningType(pPlanningType);

  var pName        = pItem.refname || pItem.name || '';
  var pParent      = (pItem.topid === undefined || pItem.topid === null) ? '' : pItem.topid;
  var pScope       = 'Planning_' + pItem.reftype + '_' + pItem.refid;
  var pComp        = 0;
  var pEnd         = null;
  var pRefItem = pItem.reftype+'_'+pItem.refid;
  for (var i=0;i<planningFieldsDescription[vPlanningTypeIndice].length;i++) {
    var col = planningFieldsDescription[vPlanningTypeIndice][i].name.toLowerCase();
    var type = planningFieldsDescription[vPlanningTypeIndice][i].type;
    if (pItem[col] !== undefined) {
      var typeToPass=((pPlanningType == 'portfolio' || pPlanningType == 'planning') && type=='date' || type=='datetime' || type=='time' || type=='tags')?type:null;
      setPlanningFieldValue(planningFieldsDescription[vPlanningTypeIndice][i].name, pRefItem, pItem[col], typeToPass, pPlanningType);
    }
    if(pItem[col+'display'] !== undefined){
      setPlanningFieldValue(planningFieldsDescription[vPlanningTypeIndice][i].name, pRefItem, pItem[col+'display'], 'show', pPlanningType);
    }
    if (pItem[col.substr(2)] !== undefined) {
      setPlanningFieldValue(planningFieldsDescription[vPlanningTypeIndice][i].name, pRefItem, pItem[col.substr(2)], 'show', pPlanningType);
    }
    if(col == 'name'){
	  setPlanningFieldValue(planningFieldsDescription[vPlanningTypeIndice][i].name, pRefItem, htmlEncode(pItem.refname), 'raw', pPlanningType);
      setPlanningFieldValue(planningFieldsDescription[vPlanningTypeIndice][i].name, pRefItem, htmlEncode(pName), 'show', pPlanningType);
    }
	if(pItem[col+'color'] !== undefined && col!='id'){
	  setPlanningFieldValue(planningFieldsDescription[vPlanningTypeIndice][i].name, pRefItem, colorNameFormatter(pItem[col+'color']), 'show', pPlanningType);
	}
	if(type == 'boolean' && pItem[col] !== undefined && pItem[col] !== null){
	  setPlanningFieldValue(planningFieldsDescription[vPlanningTypeIndice][i].name, pRefItem, booleanFormatter(pItem[col]), 'show', pPlanningType);
	}
	if(type == 'color'){
	  setPlanningFieldValue(planningFieldsDescription[vPlanningTypeIndice][i].name, pRefItem, colorFormatter('#'+pItem[col]), 'show', pPlanningType);
	}
  }
  var vID = pItem.id;
  var vName  = pName;
  var vId  = pItem.refid;
  var vStart = new Date();
  var vEnd   = new Date();
  var vComp  = pComp;
  var vGroup = (pItem.elementary == '0') ? 1 : 0;
  var vParent = pParent;
  var vOpen   = (pItem.collapsed == '1') ? '0' : '1';
  var vLevel = 0;
  var vVisible  = 1;
  var vClass=pItem.reftype;
  var vScope=pScope;
  var vEndInit   = pEnd;
  var vIconClass=pItem.iconClass;

  this.getFieldValue = function(pField) {
    if (pField=='Name') return vName;
    else if (pField=='ID') return vID;
    else if (pField=='Id') return vId;
    else return getPlanningFieldValue(pField, pRefItem, 'show', pPlanningType);
  };

  this.setFieldValueFromEdit = function(pField) {
    var name = pField;
    var nameWidget='editInput'+pField;
    var isCustomField = isPlanningFieldCustom(pPlanningType, name);
    var customName = getPlanningFieldCustomName(pPlanningType, name);
    if(!isCustomField && customName){
      nameWidget = 'editInput'+customName.charAt(0).toUpperCase() + customName.slice(1);
    }
    var widget=dijit.byId(nameWidget);
    var pValue=(widget)?widget.get('value'):'?';
    var pDispl=(widget)?widget.get('displayedValue'):'?';
    var refItem = pRefItem;
    var currentValue=getPlanningFieldValue(pField, pRefItem, 'raw', pPlanningType);

    if (pField=='IdStatus') currentValue=this.getItem().activitystatus;
    if (pValue=='?') {
      return;
    } else if (pValue==currentValue ) {
      return;
    }

	if (pField=='Name'){
		pValue=htmlEncode(pValue);
    vName=pDispl;
		pDispl=htmlEncode(pDispl);
	}
    if (pField=='IdStatus') {pDispl=statusColorFormatter(pDispl, pValue); this.getItem().activitystatus=pValue; }
    setPlanningFieldValue(pField, refItem, pValue, 'raw', pPlanningType);
    setPlanningFieldValue(pField, refItem, pDispl, 'show', pPlanningType)
  };

  this.getItem     = function(){ return pItem; };
  this.getRefItem     = function(){ return pRefItem; };
  this.getID       = function(){ return vID; };
  this.getId       = function(){ return vId; };
  this.getName     = function(){ return vName; };
  this.setName     = function(pName){ vName = pName; };
  this.getNameTitle=function(){ return vName.replace(/"/g,"''"); };
  this.getStart    = function(){ return vStart;};
  this.getEnd      = function(){ return vEnd;  };
  this.getEndInit      = function(){ return vEndInit;  };
  this.getParent   = function(){ return vParent; };
  this.getGroup    = function(){ return vGroup; };
  this.getOpen     = function(){ return vOpen; };
  this.getLevel    = function(){ return vLevel; };
  this.getVisible  = function(){ return vVisible; };
  this.getScope    = function(){ return vScope; };
  this.getClass    = function(){ return vClass; };
  this.getIconClass = function(){
    if(!vIconClass){
      vIconClass=this.getClass();
    }
    return vIconClass;
  };
  this.setStart             = function(pStart){ vStart = pStart;};
  this.setEnd               = function(pEnd)  { vEnd   = pEnd;  };
  this.setLevel             = function(pLevel){ vLevel = pLevel;};
  this.setCompVal           = function(pCompVal){ vComp = pCompVal;};
  this.setOpen              = function(pOpen) {vOpen = pOpen; };
  this.setVisible           = function(pVisible) {vVisible = pVisible; };
  this.getProjectId = function(){
    if (this.getClass()=='Project'){
      return this.getID();
    }else{
      return pItem.idproject;
    }
  }
};

var DocumentExplorerList =  function(pGanttVar, pDiv, pFormat) {
  var vGanttVar = pGanttVar;
  var vPlanningType = 'directory';
  var vIdPrefix = '';
  this.getIdPrefix = function(){ return vIdPrefix; };
  this.setIdPrefix = function(p){ vIdPrefix = p || ''; };
  this.getPlanningType = function(){ return vPlanningType; };
  this.setPlanningType = function(pType){ vPlanningType = pType; };
  this.getGanttVar     = function(){ return vGanttVar; };
  var vDiv      = pDiv;
  var vFormat   = pFormat;
  var vSortArray=new Array();
  var vTaskList     = new Array();
  var vChildTaskListByParent = {};
  var vFormatArr  = new Array("day","week","month","quarter");
  this.setSortArray = function(pSortArray) { vSortArray = pSortArray; };
  this.getSortArray = function(){ return vSortArray; };

  this.ClearList = function () {
    vTaskList = new Array();
    vChildTaskListByParent = {};
  };
  this.AddTaskItem = function(value) {
    var taskIndex = vTaskList.length;
    vTaskList.push(value);
    var parentId = value.getParent();
    if (parentId) {
      if (!vChildTaskListByParent[parentId]) vChildTaskListByParent[parentId] = new Array();
      vChildTaskListByParent[parentId].push({taskItem:value, taskIndex:taskIndex});
    }
  };
  this.getList   = function() { return vTaskList; };
  this.getArrayLocationByID = function(pId)  {
    var vList = this.getList();
    for(var i = 0; i < vList.length; i++) {
      if(vList[i].getID()==pId) {
        return i;
      }
    }
    return null;
  };

  this.getRefItemByID = function(pId)  {
    var vList = this.getList();
    for(var i = 0; i < vList.length; i++) {
      if(vList[i].getID()==pId) {
        return vList[i].getRefItem();
      }
    }
  };
  this.getLineByID = function(pId)  {
    var vList = this.getList();
    for(var i = 0; i < vList.length; i++) {
      if(vList[i].getID()==pId) {
        return vList[i];
      }
    }
    return null;
  };

  this.Draw = function(){
    window.top.showWait();
    var vID = 0;
    var VId = 0;
    var vLeftTable = "";
    var vRowType="";
    var vIconWidth=24;
    var vNameWidth = 300;
    var sortArray=this.getSortArray();
    var planningType = vPlanningType;
    var vLeftWidth = vIconWidth+getPlanningFieldWidth('Name',planningType)+2;
      for (var iSort=0;iSort<sortArray.length;iSort++) {
        if(sortArray[iSort] === undefined)continue;
        var field=sortArray[iSort];
        if (field.substr(0,6)=='Hidden') field=field.substr(6);
        var showField=getPlanningFieldShow(field,planningType);
        var fieldWidth=getPlanningFieldWidth(field,planningType);
        if (showField && field!='Name') vLeftWidth+=1+fieldWidth;
      }

    var ffSpecificHeight=(dojo.isFF<16)?' class="ganttHeight"':'';
    var vLeftTable="";
    var specificRightClickDiv="";
    if(vTaskList.length > 0) {
      documentExplorerProcessRows(vTaskList, 0, -1, 1, 1);
    }
      vNameWidth=getPlanningFieldWidth('Name',planningType);
      vLeftTable = '<DIV class="scrollLeftTop" id="' + vIdPrefix + 'leftsideTop" style="width:' + vLeftWidth + 'px;">'
      +'<TABLE jsId="' + vIdPrefix + 'topSourceTable" id="' + vIdPrefix + 'topSourceTable" class="ganttTable"><TBODY>'
        +'<TR class="ganttHeight" style="height:24px">';
      if (vGanttVar == 'documentExplorerDocumentList') {
        /* One cell spanning every column : the band holds the current directory
         * path, which is unrelated to the column layout of the list below. Split
         * per column, the text would be confined to the width of Name. */
        var vBandCols = 2;
        for (var iBand=0;iBand<sortArray.length;iBand++) {
          if(sortArray[iBand] === undefined)continue;
          var fBand=sortArray[iBand];
          if (fBand.substr(0,6)=='Hidden') fBand=fBand.substr(6);
          if (getPlanningFieldShow(fBand,planningType) && fBand!='Name') vBandCols++;
        }
        vLeftTable += '<TD class="ganttLeftTopLine" colspan="' + vBandCols + '"'
          + ' style="width:' + vLeftWidth + 'px;max-width:' + vLeftWidth + 'px;">'
          + documentExplorerDrawFormat(vFormatArr, vFormat, vGanttVar,'top')
          + '</TD>';
      } else {
        vLeftTable += '<TD class="ganttLeftTopLine" colspan="2" style="width: ' + (vNameWidth+vIconWidth) + 'px;"><span class="nobr">';
        vLeftTable += documentExplorerDrawFormat(vFormatArr, vFormat, vGanttVar,'top');
        vLeftTable += '</span></TD>';

        for (var iSort=0;iSort<sortArray.length;iSort++) {
          if(sortArray[iSort] === undefined)continue;
          var field=sortArray[iSort];
          if (field.substr(0,6)=='Hidden') field=field.substr(6);
          var showField=getPlanningFieldShow(field,planningType);
          var fieldWidth=getPlanningFieldWidth(field,planningType);
          if(showField && field!='Name') {
            vLeftTable += '<TD class="ganttLeftTopLine" style="width: ' + fieldWidth + 'px;"></TD>' ;
          }
        }
      }
        /* Filler cell : the columns have fixed widths and the table is stretched to
           the pane. All the surplus width goes here, where the browser would
           otherwise spread it over the columns and distort them. */
        vLeftTable += '<TD class="ganttLeftTopLine"></TD>';

        var columnNameMinWidth = getPlanningFieldMinWidth('Name',planningType);
        var vHdrDnd = vIdPrefix + 'dndDocumentExplorerHeaderColumn';
        var vHdrType = vIdPrefix + 'planningHeaderColumn';
        vLeftTable += '</TR><TR dojoType="dojo.dnd.Source" withHandles="true" jsId="' + vHdrDnd + '" id="' + vHdrDnd + '"'
          +'dndType="' + vHdrType + '" data-dojo-props="accept: [\'' + vHdrType + '\']" class="ganttHeight" style="height:24px">'
          +'<TD class="ganttLeftTitle" style="width:22px;"><div style="overflow: hidden; white-space: nowrap; text-overflow: ellipsis; width:22px; z-index:1000;" class="namePartgroup"><span class="nobr">&nbsp;</span></div></TD>'
          +'<TD id="' + vIdPrefix + 'jsGanttHeaderTDName" class="ganttLeftTitle ganttAlignLeft ganttNoLeftBorder" style="position:relative;width: ' + vNameWidth + 'px;" oncontextmenu="documentExplorerToggleColumnList()">'
          +'<div id="' + vIdPrefix + 'jsGanttHeaderName" style="overflow: hidden; white-space: nowrap; text-overflow: ellipsis; width:' + vNameWidth + 'px; z-index:1000;" class="namePartgroup">'
          +'<span class="nobr">'+(documentExplorerGetTaskCaption(planningType)==''?'&nbsp;':documentExplorerGetTaskCaption(planningType))+'</span></div>'
          +'<div id="' + vIdPrefix + 'NameColumnResizer" style="width:10px !important" class="planningColumnResizer" onmouseenter="if(!documentExplorerIsResizingHeaderColumn)documentExplorerHandleResizeHeaderColumn(\'Name\','+columnNameMinWidth+', 1, \''+planningType+'\');"></div>'
          +'<div id="' + vIdPrefix + 'NameColumnResizerIndicator" class="planningColumnResizerIndicator" style="display:none;"></div>'
          +'</TD>' ;

        for (var iSort=0;iSort<sortArray.length;iSort++) {
          if(sortArray[iSort] === undefined)continue;
          var field=sortArray[iSort];
          if (field.substr(0,6)=='Hidden') field=field.substr(6);
          var nameField=field;
          var showField=getPlanningFieldShow(field,planningType);
          var fieldWidth=getPlanningFieldWidth(field,planningType);
          var handleDndWidth = fieldWidth-10;
          if(showField && field!='Name') {
            var columnMinWidth = getPlanningFieldMinWidth(field,planningType);
            var isCustomField = isPlanningFieldCustom(planningType, field);
            var colName = documentExplorerGetFieldLabel(field, planningType)
                       || JSGantt.i18n( ('col'+nameField).replace('Work',''));
            if(isCustomField)colName = getPlanningFieldCustomName(planningType, field);
            vLeftTable += '<TD id="' + vIdPrefix + 'jsGanttHeaderTD'+field+'" class="dojoDndItem planningHeaderColumn ganttLeftTitle" dndtype="' + vHdrType + '" style="position:relative;width: ' + fieldWidth + 'px;padding:unset !important;" nowrap oncontextmenu="documentExplorerToggleColumnList()">'
              +'<span class="dojoDndHandle handleCursor planningColumnDndHandle" style="width:'+handleDndWidth+'px !important"></span>'
              +'<div id="' + vIdPrefix + 'jsGanttHeader'+field+'" style="overflow: hidden; white-space: nowrap; text-overflow: ellipsis; width:' + fieldWidth + 'px; z-index:1000;" class="namePartgroup">'
              +'<span class="nobr">'+ colName + '</span>'
              +'</div>'
              +'<div id="' + vIdPrefix + field + 'ColumnResizer" style="width:10px !important" class="planningColumnResizer" onmouseenter="if(!documentExplorerIsResizingHeaderColumn)documentExplorerHandleResizeHeaderColumn(\''+field+'\','+columnMinWidth+', 1, \''+planningType+'\');"></div>'
              +'<div id="' + vIdPrefix + field + 'ColumnResizerIndicator" class="planningColumnResizerIndicator" style="display:none;"></div>'
              +'</TD>' ;
          }
        }
      // Same filler as the top band, so both rows end at the edge of the pane.
      vLeftTable += '<TD class="ganttLeftTitle"></TD>';
      vLeftTable += '</TR>';
      vLeftTable += '</TBODY></TABLE></DIV>'
        +'<DIV class="scrollLeft" id="' + vIdPrefix + 'leftside" style="z-index:-1;position:relative;width:' + vLeftWidth + 'px;">'
        +'<form dojoType="dijit.form.Form" id="' + planningType + 'ListForm" name="' + planningType + 'ListForm" action="" method="post">'
        +'<input type="hidden" id="' + vIdPrefix + 'idProjectRow" name="idProjectRow" value="">'
        + ( (dojo.ifFF)?'<div style="height:1px"></div>':'')
        + ((planningType == 'directory') ? documentExplorerDrawRootDropZone() : '')
        +'<TABLE dojoType="dojo.dnd.Source" withHandles="true" jsId="' + vIdPrefix + 'dndDocumentExplorerSource" id="' + vIdPrefix + 'dndDocumentExplorerSource" type="documentExplorerTask"'
        + ((planningType == 'directory') ? ' accept="documentExplorerTask"' : '')
        +' class="ganttTable"  ><TBODY>';
      for(var i = 0; i < vTaskList.length; i++) {
        {
          var vRowType=(vTaskList[i].getGroup())?"group":"row";
          vID = vTaskList[i].getID();
          var invisibleDisplay=(vTaskList[i].getVisible() == 0)?'style="display:none"':'';
          var extraColorStyle='';
          vLeftTable += '<TR id=child_'+vID+' dndType="documentExplorerTask" class="dojoDndItem ganttTask' + vRowType + '" tabindex="-1" onfocus="focusEditRowLine=true" onblur="focusEditRowLine=false"'
            + invisibleDisplay + ' style="height:21px;min-height:21px;'+extraColorStyle+'">' ;
          vLeftTable += '</TR>';
        }
      }
      vLeftTable += '</TBODY></TABLE></form></DIV>';

      var vTarget = vDiv || dojo.byId('leftGanttChartDIV');
      if (vTarget) {
        if (vTarget.id && dijit.byId(vTarget.id)) dijit.byId(vTarget.id).set('content', null);
        vTarget.innerHTML = vLeftTable;
        if (vTarget.id) dojo.parser.parse(vTarget.id);
      }
    window.top.hideWait();
  };

};

/**
 * Recursively process task tree ... set min, max dates of parent tasks and
 * identfy task level.
 *
 * @method processRows
 * @param pList
 *            {Array} - Array of TaskItem Objects
 * @param pID
 *            {Number} - task ID
 * @param pRow
 *            {Number} - Row in chart
 * @param pLevel
 *            {Number} - Current tree level
 * @param pOpen
 *            {Boolean}
 * @return void
 */
var documentExplorerProcessRows = function(pList, pID, pRow, pLevel, pOpen) {
  var vList    = pList;
  var vLevel   = pLevel;
  var i        = 0;
  var vVisible = pOpen;
  if (pRow==0) {
    for(i=pList.length-1; i>0; i--) {
      parentId=null;
      if (pList[i].getParent()) {
        for (j=0;j<pList.length;j++) {
          if (pList[j].getID()==pList[i].getParent()) {
            parentId=j;
            break;
          }
        }
        if (parentId!==null && pList[i].getStart() && pList[parentId].getStart()>pList[i].getStart()) { pList[parentId].setStart(pList[i].getStart());}
        if (parentId!==null && pList[i].getEnd() && pList[parentId].getEnd()<pList[i].getEnd()) { pList[parentId].setEnd(pList[i].getEnd());}
      }
    }
  }
  for(i = 0; i < pList.length; i++) {
    if(pList[i].getParent() == pID || (pID==0 && i==0) ) {
      vVisible = pOpen;
      pList[i].setVisible(vVisible);
      if(vVisible==1 && pList[i].getOpen() == 0) {
        vVisible = 0;
      }
      pList[i].setLevel(vLevel);
      if(pList[i].getGroup() == 1) {
        documentExplorerProcessRows(vList, pList[i].getID(), i, vLevel+1, vVisible);
      };
    }
  }
};

/**
 * Folds or unfolds a directory row and its descendants.
 *
 * @param pID      {String}  - row id of the directory
 * @param ganttObj {Object}  - list holding the row
 * @param all      {Boolean} - true when called from collapse all / expand all
 */
var documentExplorerFolder= function (pID,ganttObj, all) {
  if (all==undefined) all=false;
  if (! all) window.top.showField('wait');
  var vList = ganttObj.getList();
  for(i = 0; i < vList.length; i++) {
    if(vList[i].getID() == pID) {
      var objFound = JSGantt.findObj('group_' + pID);
      var callBack = (all) ? null : function() { window.top.hideWait(); };
      if( vList[i].getOpen() == 1 ) {
        vList[i].setOpen(0);
        documentExplorerHide(pID,ganttObj);
        if (objFound) objFound.className = "ganttExpandClosed";
        saveCollapsed(vList[i].getScope(),callBack);
      } else {
        vList[i].setOpen(1);
        documentExplorerShow(pID, ganttObj);
        if (objFound) objFound.className = "ganttExpandOpened";
        saveExpanded(vList[i].getScope(),callBack);
      }
	  break;
    }
  }
  if (! all) {
    documentExplorerShowVisibleLines();
    top.hideWait();
  }
};

var documentExplorerCollapseAll= function (vGanttVar) {
  if (refreshJsonDocumentExplorerInProgress==true) {
    showInfo(i18n("alertOngoingQuery"));
    var fnc=function() {
        documentExplorerCollapseAll(vGanttVar);
    };
    setTimeout(fnc,100);
    return;
  }
  window.top.showField('wait');
  var fnc=function() {
    documentExplorerCollapse(vGanttVar);
  };
  setTimeout(fnc,10);
};
var documentExplorerCollapse= function (ganttObj) {
  var vList = ganttObj.getList();
  for(var i = vList.length -1; i >=0 ; i--) {
    if (vList[i].getGroup()) {
      if (vList[i].getOpen() == 1) {
        documentExplorerFolder(vList[i].getID(),ganttObj, true);
      }
    }
  }
  documentExplorerShowVisibleLines();
};
var documentExplorerExpandAll= function (vGanttVar) {
  window.top.showField('wait');
  var fnc=function() {
    documentExplorerExpand(vGanttVar);
    if (dojo.byId('objectClass') && dojo.byId('objectId') && dojo.byId('objectId').value) {
      documentExplorerSelectLineByObject(dojo.byId('objectClass').value, dojo.byId('objectId').value, true, true);
    }
  };
  setTimeout(fnc,10);
};
var documentExplorerExpand= function (ganttObj) {
  var vList = ganttObj.getList();
  for(var i = vList.length -1; i >=0 ; i--) {
    if(vList[i].getGroup()) {
      if (! vList[i].getOpen() || vList[i].getOpen()==0) {
        documentExplorerFolder(vList[i].getID(),ganttObj, true);
      }
    }
  }
  showWait();
  documentExplorerShowVisibleLines();
};

var documentExplorerHide=function (pID,ganttObj) {
  var vList = ganttObj.getList();
  for(var i = 0; i < vList.length; i++) {
    if(vList[i].getParent()==pID) {
      var vID = vList[i].getID();
      var node = JSGantt.findObj('child_' + vID);
      if (node) node.style.display = "none";
      vList[i].setVisible(0);
      if(vList[i].getGroup() == 1) {
        documentExplorerHide(vID,ganttObj);
      }
    }
  }
};

var documentExplorerShow =  function (pID, ganttObj) {
  var vList = ganttObj.getList();
  var pIDindex=0;
  for(var i = 0; i < vList.length; i++) {
    if (vList[i].getID()==pID) {
      pIDindex=i;
    }
    if(vList[i].getParent() == pID) {
      var vID = vList[i].getID();
      if (vList[pIDindex].getOpen()==1) {
        var node = JSGantt.findObj('child_' + vID);
        if (node) node.style.display = "";
        vList[i].setVisible(1);
      }
      if(vList[i].getGroup() == 1 && vList[i].getVisible()) {
        documentExplorerShow(vID, ganttObj);
      }
    }
  }
};

var documentExplorerOpenContextMenu = function(taskId, refId, refType, idProject){
  var contextMenu = dijit.byId('planningContextMenu');
  var contextMenuDiv = dojo.byId('dialogPlanningContextMenu');
  var planningType = (documentExplorerListFor(refType) && documentExplorerListFor(refType).getPlanningType) ? documentExplorerListFor(refType).getPlanningType() : 'directory';
  var mousePosition = {};
  mousePosition.x = event.clientX;
  if(dojo.byId('isMenuLeftOpen').value == 'true'){
    mousePosition.x -= 250;
  }
  mousePosition.y = event.clientY-110;
  if(dojo.byId('timelineGanttDiv') && dojo.byId('timelineGanttDiv').style.display != 'none'){
    mousePosition.y -= dojo.byId('timelineGanttDiv').offsetHeight;
  }
  dojo.query('.contextMenuClass').forEach(function(node){
    node.style.cssText='position:absolute;width:0px;height:0px;overflow:hidden;top:'+mousePosition.y+'px;left:'+mousePosition.x+'px';
  });

  if(dojo.byId('contextMenuRefId'))dojo.byId('contextMenuRefId').value = refId;
  if(dojo.byId('contextMenuRefType'))dojo.byId('contextMenuRefType').value = refType;

  if(dojo.byId('cm_explorerExtract')){
    dojo.byId('cm_explorerExtract').style.display = '';
    dojo.byId('cm_explorerExtract').setAttribute('onClick',
        'JSGantt.hideMenu();showExtractDocument(\''+refId+'\', \''+refType+'\')');
  }

  var selectedPlanningItems = (typeof documentExplorerGetSelectedItemsForDelete == 'function')
    ? documentExplorerGetSelectedItemsForDelete(refId, refType)
    : new Array();
  var deletePlanningLabel = dojo.byId('cm_removeFromPlanning_label');
  if (deletePlanningLabel) {
    deletePlanningLabel.innerHTML = i18n(
      (selectedPlanningItems.length > 1)
        ? 'contextMenuButtonDeleteMultiplePlanning'
        : 'contextMenuButtonDelete'
    );
  }

  var currentClass = null;
  var currentId = null;

  if(dojo.byId('objectClass'))currentClass=dojo.byId('objectClass').value;
  if(dojo.byId('objectId'))currentId=dojo.byId('objectId').value;

  if(checkFormChangeInProgress())return;

  /* Open and close swap in the context menu : with the pane open on this object,
     Close takes the place of Show detail. Opening always shows the record, where a
     click on the row would show the file in preview mode. */

  if(dojo.byId('cm_openFromPlanning')){
    dojo.byId('cm_openFromPlanning').style.display = '';
    dojo.byId('cm_openFromPlanning').setAttribute('onClick', 'documentExplorerShowDetailFromContextMenu(\''+refType+'\', '+refId+', \''+taskId+'\', \''+idProject+'\')');
  }

  if(dojo.byId('cm_closeFromPlanning') && coverListAction == 'OPEN' && (refType==currentClass && refId==currentId)){
    dojo.byId('cm_closeFromPlanning').style.display = '';
    dojo.byId('cm_closeFromPlanning').setAttribute('onClick', 'documentExplorerCloseObjectFromContextMenu(\''+refType+'\', '+refId+', \''+taskId+'\', \''+idProject+'\')');
    dojo.byId('cm_openFromPlanning').style.display = 'none';
  }else if(dojo.byId('cm_closeFromPlanning')){
    dojo.byId('cm_closeFromPlanning').style.display = 'none';
  }
  if(dojo.byId('cm_emailFromPlanning')){
    dojo.byId('cm_emailFromPlanning').style.display = '';
    dojo.byId('cm_emailFromPlanning').setAttribute('onClick', 'sendMailFromContextMenu('+refId+', \''+refType+'\', \''+taskId+'\', \''+idProject+'\')');
  }
  if(dojo.byId('cm_historyFromPlanning')){
    dojo.byId('cm_historyFromPlanning').style.display = '';
    dojo.byId('cm_historyFromPlanning').setAttribute('onClick', 'showHistoryFromContextMenu('+refId+', \''+refType+'\', \''+taskId+'\', \''+idProject+'\')');
  }
  dojo.xhrGet({
    url:'../tool/getSingleData.php?dataType=canUpdateObject&objectClass=' + refType + '&objectId='+refId+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      if(data){
        if(dojo.byId('cm_editFromPlanning') && coverListAction == 'CLOSE'){
          if(data == 'YES'){
            dojo.byId('cm_editFromPlanning').style.display = '';
            dojo.byId('cm_editFromPlanning').setAttribute('onClick', 'editObjectFromContextMenu(\''+refId+'\', \''+refType+'\', \''+taskId+'\', \''+idProject+'\')');
          }else{
            dojo.byId('cm_editFromPlanning').style.display = 'none';
            dojo.byId('cm_editFromPlanning').setAttribute('onClick', '');
          }
        }else if(dojo.byId('cm_editFromPlanning')){
          dojo.byId('cm_editFromPlanning').style.display = 'none';
        }
        if(dojo.byId('cm_editOnlineFromPlanning')){
          if(data == 'YES'){
            dojo.byId('cm_editOnlineFromPlanning').style.display = '';
            dojo.byId('cm_editOnlineFromPlanning').setAttribute('onClick', 'editRowObjectFromContextMenu(\''+taskId+'\', '+refId+', \''+refType+'\', \''+idProject+'\')');
          }else{
            dojo.byId('cm_editOnlineFromPlanning').style.display = 'none';
          }
        }
      }
    }
  });
  dojo.xhrGet({
    url:'../tool/getSingleData.php?dataType=canCreateObject&objectClass=' + refType + '&objectId='+refId+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      if(data){
        if(dojo.byId('cm_addFromPlanning')){
          if(data == 'YES'){
            dojo.byId('cm_addFromPlanning').style.display = '';
            dojo.byId('cm_addFromPlanning').setAttribute('onClick', 'addObjectFromContextMenu(\''+refId+'\', \''+refType+'\', \''+taskId+'\', \''+idProject+'\')');
          }else{
            dojo.byId('cm_addFromPlanning').style.display = 'none';
            dojo.byId('cm_addFromPlanning').setAttribute('onClick', '');
          }
        }
      }
    }
  });
  dojo.xhrGet({
    url:'../tool/getSingleData.php?dataType=canDeleteObject&objectClass=' + refType + '&objectId='+refId+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      if(data){
        if(dojo.byId('cm_removeFromPlanning')){
          if(data == 'YES'){
            dojo.byId('cm_removeFromPlanning').style.display = '';
            dojo.byId('cm_removeFromPlanning').setAttribute('onClick', 'documentExplorerDeleteObjectFromContextMenu('+refId+', \''+refType+'\')');
          }else{
            dojo.byId('cm_removeFromPlanning').style.display = 'none';
            dojo.byId('cm_removeFromPlanning').setAttribute('onClick', '');
          }
        }
      }
    }
  });
  dojo.xhrGet({
    url:'../tool/getSingleData.php?dataType=canCopyObject&objectClass=' + refType + '&objectId='+refId+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      if(data){
        if(dojo.byId('cm_copyFromPlanning')){
          if(data == 'YES'){
            dojo.byId('cm_copyFromPlanning').style.display = '';
            dojo.byId('cm_copyFromPlanning').setAttribute('onClick', 'copyObjectFromContextMenu('+refId+', \''+refType+'\', \''+taskId+'\', \''+idProject+'\')');
          }else{
            dojo.byId('cm_copyFromPlanning').style.display = 'none';
            dojo.byId('cm_copyFromPlanning').setAttribute('onClick', ')');
          }
        }
      }
    }
  });

  contextMenu.openDropDown();
  contextMenuDiv.focus();
};

var documentExplorerGetTaskCaption = function(planningType) {
  if (planningType=='document') return JSGantt.i18n('menuDocument');
  return JSGantt.i18n('menuDocumentDirectory');
}

var documentExplorerDrawFormat = function(vFormatArr, vFormat, vGanttVar, vPos) {
  var vLeftTable='<div style="position:relative;" id="ganttScale" class="ganttScale">';
  if (vGanttVar == 'documentExplorerDocumentList') {
    return vLeftTable
         + '<span id="explorerDocumentPath" class="explorerDocumentPath">&nbsp;</span>'
         + '</div>';
  }
  vLeftTable+='<span style="position:relative;top:0px; left:2px;">';
  vLeftTable+='<button dojoType="dijit.form.Button" showlabel="false"'
       +' title="' + i18n('buttonCollapse') + '"'
       +' style="font-size:5px; text-align: center; position: relative; top: -1px;'
       +'vertical-align: middle; height:16px; width:16px;"'
       +' onclick="documentExplorerCollapseAll('+vGanttVar+', false);"'
       +' iconClass="ganttExpandOpened whiteIcon iconSize16">'
       +'</button>&nbsp;';
  vLeftTable+='</span><span style="position:relative;top:0px">';
  vLeftTable+='<button dojoType="dijit.form.Button" showlabel="false"'
       +' title="' + i18n('buttonExpand') + '"'
       +' style="font-size:5px;position: relative; top: -1px;vertical-align: middle;'
       +'height:16px; width:16px;"'
       +' onclick="documentExplorerExpandAll('+vGanttVar+', false);"'
       +' iconClass="ganttExpandClosed whiteIcon iconSize16" >'
       +'</button>&nbsp;';
  vLeftTable+='</span>&nbsp;';
  return vLeftTable + '</div>';
}

var documentExplorerSaveLeftSize = function() {
  var leftGantt=dojo.byId('leftGanttChartDIV');
  if (!leftGantt) return;
  var width=leftGantt.offsetWidth;
  if (!width) width=parseFloat(leftGantt.style.width);
  if (!width) return;
  saveUserParameter('documentExplorerLeftSize',Math.round(width)+'px');
};

function documentExplorerSetColumnsVisibility(documentExplorerDirectoryList, ganttType) {
  if (!ganttType) ganttType='directory';
  var idx=getIndiceForPlanningType(ganttType);
  for (var i=0; i<planningFieldsDescription[idx].length; i++) {
    planningFieldsDescription[idx][i].showSpecif=true;
  }
  documentExplorerDirectoryList.setSortArray(documentExplorerColumnOrder[idx]);
}
var documentExplorerMouseOver = function( pID, pPos, pType) {
  if (dojo.byId('bodyPrint')) return;
  if (pID==vGanttCurrentLine) return;
  var vRowObj1 = JSGantt.findObj('child_' + pID);
  if (vRowObj1){
    dojo.addClass(vRowObj1, 'ganttRowHover');
  }
  var vRowObj2 = JSGantt.findObj('childrow_' + pID);
  if (vRowObj2){
    dojo.addClass(vRowObj2, 'ganttRowHover');
  }
};

var documentExplorerMouseOut = function(pID, pPos, pType) {
  if (dojo.byId('bodyPrint')) return;
  if (pID==vGanttCurrentLine) return;
  var vRowObj1 = JSGantt.findObj('child_' + pID);
  if (vRowObj1){
    dojo.removeClass(vRowObj1, 'ganttRowHover');
    dojo.removeClass(vRowObj1, 'dojoxGridRowSelected');
  }
  var vRowObj2 = JSGantt.findObj('childrow_' + pID);
  if (vRowObj2){
    dojo.removeClass(vRowObj2, 'ganttRowHover');
    dojo.removeClass(vRowObj2, 'dojoxGridRowSelected');
  }
};

function documentExplorerListFor(refClass) {
  return (refClass == 'Document') ? documentExplorerDocumentList : documentExplorerDirectoryList;
}

function documentExplorerPrefixFor(refClass) {
  var vChart = documentExplorerListFor(refClass);
  return (vChart && vChart.getIdPrefix) ? vChart.getIdPrefix() : '';
}

function documentExplorerDndSourceFor(refClass) {
  return window[documentExplorerPrefixFor(refClass) + 'dndDocumentExplorerSource'] || null;
}

/**
 * Name of the list form holding this class : one for the tree, one for the
 * documents. The only place that knows it ; inline editing drops its hidden fields
 * there and reads the form back to save.
 */
function documentExplorerListFormNameFor(refClass) {
  var vChart = documentExplorerListFor(refClass);
  var vType = (vChart && vChart.getPlanningType) ? vChart.getPlanningType() : 'directory';
  return vType + 'ListForm';
}

var documentExplorerCurrentEditList = null;


function documentExplorerEditList() {
  return documentExplorerCurrentEditList || documentExplorerDirectoryList;
}


/**
 * Root drop zone, drawn on top of the directory tree.
 *
 * Not a row of the list : it takes part in no loop over vTaskList, hence in no
 * selection, edit or context menu. It borrows the anatomy of a row so as to read
 * as the parent of every directory - widths come from
 * documentExplorerDrawLeftPart : 24px handle, 3px margin, 22px icon, then name.
 *
 * It carries neither the indent cell nor the expand cell that a row has, which
 * is what sets its icon one 16px step left of a top level directory.
 */
var documentExplorerDrawRootDropZone = function () {
  var vIconWidth=24;
  var vNameWidth = getPlanningFieldWidth('Name','directory');
  var vLabelWidth = vNameWidth - 18;
  if (vLabelWidth < 20) vLabelWidth = 20;
  //JSGantt.i18n('documentExplorerRoot')
  return '<div dojoType="dojo.dnd.Source" accept="documentExplorerTask"'
    + ' id="documentExplorerRootDropZone" jsId="documentExplorerRootDropZone"'
    + ' class="documentExplorerRootDropZone">'
    + '<table class="ganttTable"><tr>'
    + '<td class="ganttName" style="width:18px;"></td>'
    + '<td class="ganttName ganttAlignLeft" style="width:' + vNameWidth + 'px;" nowrap>'
    + '<div style="position:relative;width:' + vNameWidth + 'px;height:100%;">'
    + '<table style="margin-left:3px;height:100%;"><tr>'
    + '<td class="ganttIconBackground" style="width:22px;padding-right:4px;">'
    + '<div class="iconDocumentDirectory16 iconDocumentDirectory iconSize16"'
    + ' style="width:16px;height:16px;">&nbsp;</div>'
    + '</td>'
    + '<td class="namePart">'
    + '<div style="overflow:hidden;white-space:nowrap;text-overflow:ellipsis;width:'
    + vLabelWidth + 'px;font-weight: bold;" class="namePartgroup">'
    + '<span class="nobr">...</span>'
    + '</div></td>'
    + '</tr></table></div></td>'
    + '<td class="ganttName"></td>'
    + '</tr></table>'
    + '</div>';
};

var documentExplorerDrawLeftPart = function (i, chart) {
  var ganttObj=chart || documentExplorerDirectoryList;
  var vGanttVar=ganttObj.getGanttVar();
  vTaskList=ganttObj.getList();
  var vIconWidth=24;
  var sortArray=ganttObj.getSortArray();
  var planningType = ganttObj.getPlanningType();
  var vNameWidth = getPlanningFieldWidth('Name',planningType);
  var vRowType=(vTaskList[i].getGroup())?"group":"row";
  vID = vTaskList[i].getID();
  var idProject = vTaskList[i].getProjectId();

  vLeftTable="";
  var leftContextMenu = ' oncontextmenu="if(!event.defaultPrevented){event.preventDefault();documentExplorerOpenContextMenu(\'' + vID + '\',\'' + vTaskList[i].getId() + '\',\'' + vTaskList[i].getClass() + '\',\'' + idProject + '\');}return false;"';

  vLeftTable += '  <TD class="ganttName" align="center" style="width:'+vIconWidth+'px"'+leftContextMenu+'>';
  var iconName = vTaskList[i].getIconClass();
  vLeftTable +=
      '<span class="dojoDndHandle handleCursor"'
    + ' onclick="JSGantt.planningRowClickAction(\''+vID+'\',\'' + vTaskList[i].getId()+ '\', \'' + vTaskList[i].getClass() + '\',\'' + idProject + '\');">'
    + ' <table><tr>'
    + '  <td><img style="width:8px" src="css/images/iconDrag.gif" /></td>'
    + ' </tr></table>'
    + '</span>';
  vLeftTable += '</TD>'
    +'<TD class="ganttName ganttAlignLeft" style="width: ' + vNameWidth + 'px;" nowrap title="' + vTaskList[i].getNameTitle() + '"'+leftContextMenu+'>';
  vLeftTable+='<div class="ganttLeftHover" id="ganttLeftHover_'+vID+'" style="width:calc(100% - 25px);" ';
  vLeftTable+=' oncontextmenu=event.preventDefault();documentExplorerOpenContextMenu("'+vID+'","'+vTaskList[i].getId()+'","' + vTaskList[i].getClass() + '",\'' + idProject + '\');';
  vLeftTable+=' onclick="JSGantt.planningRowClickAction(\''+vID+'\',\'' + vTaskList[i].getId()+ '\', \'' + vTaskList[i].getClass() + '\',\'' + idProject + '\');"';
  vLeftTable+=' onMouseover=documentExplorerMouseOver("'+vID+'","left","' + vRowType + '")'
      + ' onMouseout=documentExplorerMouseOut("'+vID+'","left","' + vRowType + '")>&nbsp;</div>';
  vLeftTable += '<div style="position:relative;width: ' + vNameWidth + 'px;height:100%;">';
  var levl=vTaskList[i].getLevel();
  var levlWidth = (levl-1) * 16;
  vLeftTable +='<table style="margin-left:3px;height:100%;"><tr>';
  var vIsTree = (planningType != 'document');
  vLeftTable += vIsTree
    ? '<td id="ganttEditButton_'+vID+'">'
    : '<td id="ganttEditButton_'+vID+'" style="width:0px;padding:0;"></td>';
  if (vIsTree) vLeftTable += '<div style="width:' + levlWidth + 'px;" class="ganttSpacingDiv">';
  if (vTaskList[i].getGroup()) {
    vLeftTable += '<div style="margin-left:3px;width:8px;">&nbsp</div>';
  }
  if (vIsTree) vLeftTable += '</div>';
  if (vIsTree) vLeftTable +='</td>';
  if (vIsTree) vLeftTable +='<td>';
  if( vTaskList[i].getGroup() ) {
    if( vTaskList[i].getOpen() == 1) {
      vLeftTable += '<div id="group_'+vID+'" class="ganttExpandOpened"'
        + 'style="position: relative; z-index: 100000; width:16px; height:13px;"'
        +' onclick="documentExplorerFolder(\''+vID+'\','+vGanttVar+');"'
        +'>'
        +'</div>' ;
    } else {
      vLeftTable += '<div id="group_'+vID+'" class="ganttExpandClosed"'
        + 'style="position: relative; z-index: 100000; width:16px; height:13px;"'
        +' onclick="documentExplorerFolder(\''+vID+'\','+vGanttVar+');"'
        +' >'
        +'&nbsp;&nbsp;&nbsp;&nbsp;</div>' ;
    }
  } else if (vIsTree) {
    vLeftTable += '<div style="width:16px;height:13px;"></div>';
  }
  if (vIsTree) vLeftTable += '</td>';
  vLeftTable += '<td class="ganttIconBackground" style="width:22px;padding-right:4px;">'
    + '<div class="icon'+ iconName +'16 icon'+ iconName +' iconSize16"'
    + ' style="width:16px;height:16px;">&nbsp;</div>';
  vLeftTable +='</td><td class="namePart" id="ganttName_'+vID+'"'
  +' oncontextmenu=event.preventDefault();documentExplorerOpenContextMenu("'+vID+'","'+vTaskList[i].getId()+'","' + vTaskList[i].getClass() + '",\'' + idProject + '\');'
  +' onclick="JSGantt.SetEditableInputFieldFocus(\'Name\', \''+vID+'\',\'' + vTaskList[i].getId()+ '\', \'' + vTaskList[i].getClass() + '\',\'' + idProject + '\')">';
  var nameLeftWidth= vNameWidth - 16 - levlWidth - 18 ;
  vLeftTable += '<div style="overflow: hidden; white-space: nowrap; text-overflow: ellipsis; '
    +'width:'+ nameLeftWidth +'px;" class="namePart' + vRowType + '"><span class="nobr">' + vTaskList[i].getName() + '</span></div>' ;
  vLeftTable +='</td></tr></table></div>';
  vLeftTable +='</TD>';
  vLeftTable +='<TD style="width:0px;position:relative;"><div id="ganttEditButtonDetail_'+vID+'" style="position:absolute;top:0px;right:0px"></div></TD>';

      for (var iSort=0;iSort<sortArray.length;iSort++) {
        if(sortArray[iSort] === undefined)continue;
        var field=sortArray[iSort];
        if (field.substr(0,6)=='Hidden') field=field.substr(6);
        var showField=getPlanningFieldShow(field,planningType);
        var fieldWidth=getPlanningFieldWidth(field,planningType);
        if(showField==1 && field!='Name') {
          valueField=vTaskList[i].getFieldValue(field);
          if (field=='IdStatus') {
            valueField=colorNameFormatter(valueField);
            padding='';
          } else if (valueField.indexOf('margin:0px -5%;')!=-1) {
            padding='';
          } else if (isModernUi && valueField.indexOf('data-formatter="color"')>0) {
            padding='';
          } else if (getPlanningField('type',field,planningType)=='boolean') {
            padding='padding:0;line-height:0;overflow:hidden;';
          } else {
            padding='padding-top: 4px;';
          }
          height=(dojo.isFF)?'':'height:100%;';
          var extraStyle = (field == 'Id') ? 'user-select: text;' : '';
          vLeftTable += '<TD class="ganttDetail dndHidden gantt' + field + '" id="gantt' + field + '_' + vID + '" style="width: ' + fieldWidth + 'px;'+extraStyle+'"';
          + ' oncontextmenu="event.preventDefault();documentExplorerOpenContextMenu(\'' + vID + '\',\'' + vTaskList[i].getId() + '\',\'' + vTaskList[i].getClass() + '\',\'' + idProject + '\');"';

          if (field == 'Id') {
            vLeftTable += ' ondblclick="copyGanttCellValue(this,\'Id\');"';
          }else{
            vLeftTable += ' onclick="JSGantt.SetEditableInputFieldFocus(\'' + field + '\', \'' + vID + '\',\'' + vTaskList[i].getId() + '\', \'' + vTaskList[i].getClass() + '\',\'' + idProject + '\');"'
          }
          vLeftTable += '>';

          vLeftTable +='<span class="nobr hideLeftPart' + vRowType + '" style="' + height + 'width: ' + fieldWidth + 'px;text-overflow:ellipsis;' + padding + '">' + valueField + '</span>'
          vLeftTable +='</TD>';

        }
      }
  /* Same filler cell as the headers : the row reaches the edge of the pane, hover,
     selection and group background with it, and no width is spread over columns. */
  vLeftTable += '<TD class="ganttDetail"></TD>';

  return vLeftTable;
}

