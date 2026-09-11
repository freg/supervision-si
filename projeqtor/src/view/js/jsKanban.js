/*******************************************************************************
 * COPYRIGHT NOTICE *
 * 
 * Copyright 2015 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * 
 * ***************************************************************************** **
 * WARNING *** T H I S F I L E I S N O T O P E N S O U R C E *
 * *****************************************************************************
 * 
 * This file is an add-on to ProjeQtOr, packaged as a plug-in module. It is NOT
 * distributed under an open source license. It is distributed in a proprietary
 * mode, only to the customer who bought corresponding licence. The company
 * ProjeQtOr remains owner of all add-ons it delivers. Any change to an add-ons
 * without the explicit agreement of the company ProjeQtOr is prohibited. The
 * diffusion (or any kind if distribution) of an add-on is prohibited. Violators
 * will be prosecuted.
 * 
 * DO NOT REMOVE THIS NOTICE **
 ******************************************************************************/

/* =============================================================================== */
/* KANBAN OBJECT FUNCTION */
/* =============================================================================== */

var lastIdKanban=-1;
var kanbanScrollTop=0;
var JSKanban; if (!JSKanban) JSKanban = {};

JSKanban.Kanban = function(pKanbanType, pKanbanClass){
	var vKanbanType	= pKanbanType;
	var vKanbanClass = pKanbanClass;
	var vKanbanColumnList = new Array();
	var vRefreshKanbanColumnList = new Array();
	
	this.getKanbanType = function() { return vKanbanType; };
	this.getKanbanClass = function() { return vKanbanClass; };
	this.setKanbanType = function(pKanbanType) { vKanbanType = pKanbanType; };
	this.setKanbanClass = function(pKanbanClass) { vKanbanClass = pKanbanClass; };
	
	this.setKanbanColumnItemCount = function(vColumnID){
		var vColumnList = this.getKanbanColumnList();
	    for(var i = 0; i < vColumnList.length; i++) {
			if(vColumnList[i].getID() == vColumnID){
				var vItemList = vColumnList[i].getKanbanItemList();
				var itemCount = 0;
				for(var j = 0; j < vItemList.length; j++){
					if(!vItemList[j].getIsHidden())itemCount++;
				}
				vColumnList[i].setItemCount(itemCount);
			}
	    }
	}
	
	this.setKanbanColumnWorksValue = function(vColumnID){
		var vColumnList = this.getKanbanColumnList();
	    for(var i = 0; i < vColumnList.length; i++) {
			if(vColumnList[i].getID() == vColumnID){
				var vItemList = vColumnList[i].getKanbanItemList();
				var vPlanned = 0;
				var vReal = 0;
				var vLeft = 0;
				for(var j = 0; j < vItemList.length; j++){
					if(!vItemList[j].getIsHidden()){
						vPlanned += vItemList[j].getPlannedWorks();
						vReal += vItemList[j].getRealWorks();
						vLeft += vItemList[j].getLeftWorks();
					}
				}
				vColumnList[i].setPlannedWorks(vPlanned);
				vColumnList[i].setRealWorks(vReal);
				vColumnList[i].setLeftWorks(vLeft);
			}
	    }
	}
	
	this.AddKanbanColumn = function(value) {
		vKanbanColumnList.push(value);
	};
	
	this.ReplaceKanbanColumn = function(value) {
	    var pId=value.getID();
	    var vList = this.getKanbanColumnList();
	    for(var i = 0; i < vList.length; i++) {
	      if(vList[i].getID()==pId){
	        vList[i]=value;
	        break;
	      }
	    }
	};
	
	this.RefreshKanbanColumn = function(value) {
	    vRefreshKanbanColumnList.push(value);
	};
	
	this.deleteItemFromKanbanColumn = function(pID){
		var vColumnList = this.getKanbanColumnList();
	    for(var i = 0; i < vColumnList.length; i++) {
			vColumnList[i].deleteKanbanItemFromList(pID);
	    }
	};
	
	this.getKanbanColumnList   = function(onlyRefresh) { 
		if(onlyRefresh==undefined)onlyRefresh=false;
		return (onlyRefresh)?vRefreshKanbanColumnList:vKanbanColumnList; 
	};
	
	this.clearRefreshKanbanColumn = function(){
		vRefreshKanbanColumnList = new Array();
	};
	
	this.getKanbanColumnArrayLocationByID = function(pId)  {
	    var vList = this.getKanbanColumnList();
	    for(var i = 0; i < vList.length; i++) {
	      if(vList[i].getID()==pId) {
	        return i;
	      }
	    }
	    return null;
	  };
	  this.getKanbanColumnByID = function(pId)  {
	    var vList = this.getKanbanColumnList();
	    for(var i = 0; i < vList.length; i++) {
	      if(vList[i].getID()==pId) {
	        return vList[i];
	      }
	    }
	    return null;
	  };
	  
	  this.getKanbanItemByIDFromColumn = function(pID){
		var vColumnList = this.getKanbanColumnList();
	    for(var i = 0; i < vColumnList.length; i++) {
			var item = vColumnList[i].getItemByID(pID);
			if(item)return item;
	    }
	    return null;
	  }
		
	  this.Draw = function(onlyRefresh){
		if(onlyRefresh==undefined)onlyRefresh=false;
		window.top.showWait();
		var vColumnList = this.getKanbanColumnList(onlyRefresh);
		if(vColumnList.length > 0){
			for(var i = 0; i < vColumnList.length; i++) {
				if(vColumnList[i].isHidden()){
					var hiddenBar = dojo.byId(vColumnList[i].getColumnName());
					if(hiddenBar){
						dojo.query('.dojoDndItem', hiddenBar).forEach(function(n){
							if(n.parentNode) n.parentNode.removeChild(n);
						});
					}
					continue;
				}
				var columnHtmlItem = '';
				var itemList = vColumnList[i].getKanbanItemList();
				var hideStatus = (vColumnList[i].getHideStatus())?'display:none':'';
				var hideActivityPlanning = (vColumnList[i].getHideActivityPlanning())?'display:none':'';
				var hidePlannedDate = (vColumnList[i].getHidePlannedDate())?'display:none':'';
				var hideProduct = (vColumnList[i].getHideProduct())?'display:none':'';
				var hideType = (vColumnList[i].getHideType())?'display:none':'';
				var hideResponsible = (vColumnList[i].getHideResponsible())?'display:none':'';
				var hidePriority = (vColumnList[i].getHidePriority())?'display:none':'';
				var hideUrgency = (vColumnList[i].getHideUrgency())?'display:none':'';
				var hideWorks = (vColumnList[i].getHideWorks())?'display:none':'';
				var fullWidthElement = vColumnList[i].getFullWidthElement();
				var hideResponsibleName = (!fullWidthElement)?'display:none':'';
				hideResponsibleName = (hideResponsible)?hideResponsible:hideResponsibleName;
				var hideProjectName = (vColumnList[i].getHideProjectName())?'display:none':'';
				hideProjectName = (!fullWidthElement)?'display:none':hideProjectName;
				var kanbanItemStyle = (fullWidthElement)?'ticketKanBanStyleFull':'ticketKanBanStyle';
				var kanbanItemClass = (fullWidthElement)?'backlogItemFull':'backlogItem';
				var kanbanDescriptionClass = (fullWidthElement)?'backlogItemDescriptionFull':'backlogItemDescription';
				var kanbanStatusClass = (fullWidthElement)?'backlogItemStatusFull':'backlogItemStatus';
				var useColorTitle = !vColumnList[i].getHideColorTitle();
				var useFullTileColor = vColumnList[i].getColorOnTitleOrFullTile();
				if(itemList.length > 0){
					for(var j = 0; j < itemList.length; j++) {
						if(!itemList[j].hasResponsible()){
							hideResponsible = 'display:none';
						}else{
							hideResponsible = (vColumnList[i].getHideResponsible())?'display:none':'';
						}
						if(!itemList[j].hasPriority()){
							hidePriority = 'display:none';
						}else{
							hidePriority = (vColumnList[i].getHidePriority())?'display:none':'';
						}
						if(!itemList[j].hasUrgency()){
							hideUrgency = 'display:none';
						}else{
							hideUrgency = (vColumnList[i].getHideUrgency())?'display:none':'';
						}
						var cardStyle = itemList[j].getCardStyle(useColorTitle, useFullTileColor);
						columnHtmlItem += '<div class="dojoDndItem dojoDndHandle '+kanbanItemStyle+' ticketKanBanColor '+kanbanItemClass+'" style="'+cardStyle+'" dndtype="'+itemList[j].getDndType()+'"';
						columnHtmlItem += '  oncontextmenu="openKanbanContextMenu(\''+itemList[j].getID()+'\', '+itemList[j].getId()+', \''+itemList[j].getClass()+'\', '+itemList[j].getProjectId()+', \'object\');" ';
						columnHtmlItem += '  fromc="'+vColumnList[i].getID()+'" id="'+itemList[j].getID()+'" reftype="'+itemList[j].getClass()+'" refid="'+itemList[j].getId()+'" >';
						columnHtmlItem += '	 <div style="position: relative;border-radius: 8px;cursor:move;">';
						columnHtmlItem += '		<div class="backlogItemHeader">';
						columnHtmlItem += '			<table style="width:100%"><tr title="'+i18n(itemList[j].getClass())+' #'+itemList[j].getId()+' '+i18n('Project')+' #'+itemList[j].getProjectId()+' - '+itemList[j].getProjectName()+'">';
						columnHtmlItem += '				<td style="font-size:10px;font-family:arial;width:75%">';
						columnHtmlItem += '					<div class="backlogItemProjectColorThumb">'+itemList[j].drawProjectColorThumb()+'</div>';
						columnHtmlItem += '					<div class="backlogItemId">#'+itemList[j].getId()+'</div>';
						columnHtmlItem += '					<div class="backlogItemTypeName" style="'+hideType+'">'+itemList[j].getTypeName()+'</div>';
						columnHtmlItem += '				</td>';
						columnHtmlItem += '				<td style="width:25%">';
						columnHtmlItem += '					<div class="backlogItemPlannedDate" style="'+hidePlannedDate+'">'+itemList[j].drawPlannedDateThumb(useColorTitle, vColumnList[i].getModeColorTitle(), useFullTileColor)+'</div>';
						columnHtmlItem += '				</td>';
						columnHtmlItem += '			</tr></table>';
						columnHtmlItem += '		</div>';
						columnHtmlItem += '		<div class="backlogItemTitle">'+itemList[j].drawTitle(useColorTitle, useFullTileColor)+'</div>';
						columnHtmlItem += '		<div style="position: relative;cursor:move;display: flex;gap: 5px;">';
						columnHtmlItem += '			<div class="'+kanbanStatusClass+'" style="'+hideStatus+'">'+itemList[j].drawStatusColorThumb()+'</div>';
						columnHtmlItem += '			<div class="backlogItemProjectName" style="'+hideProjectName+'">'+itemList[j].drawProjectName()+'</div>';
						columnHtmlItem += '		</div>';
						columnHtmlItem += '		<div class="'+kanbanDescriptionClass+'" >'+itemList[j].drawDescription()+'</div>';
						columnHtmlItem += '		<div class="backlogItemProduct" style="'+hideProduct+'">'+itemList[j].drawTargetProductVersion(useColorTitle, vColumnList[i].getModeColorTitle(), useFullTileColor)+'</div>';
						columnHtmlItem += '		<div class="backlogItemActivityPlanning" style="'+hideActivityPlanning+'">'+itemList[j].drawActivityPlanningName(useColorTitle, vColumnList[i].getModeColorTitle(), useFullTileColor)+'</div>';
						columnHtmlItem += '		<div class="backlogItemWorks" style="'+hideWorks+'">'+itemList[j].drawWorks()+'</div>';
						columnHtmlItem += '		<div class="backlogItemFooter">';
						columnHtmlItem += '			<div class="backlogItemUserThumb" style="'+hideResponsible+'">'+itemList[j].drawUserThumb()+'</div>';
						columnHtmlItem += '			<div style="'+hideResponsibleName+';float: left;padding: 5px 3px 5px 3px;">'+itemList[j].drawResponsibleName()+'</div>';
						columnHtmlItem += '			<div class="backlogItemPriorityThumb" style="'+hidePriority+'">'+itemList[j].drawPriorityColorThumb()+'</div>';
						columnHtmlItem += '			<div class="backlogItemUrgencyThumb" style="'+hideUrgency+'">'+itemList[j].drawUrgencyColorThumb()+'</div>';
						columnHtmlItem += '			<div class="backlogItemTableButton">'+itemList[j].drawTableButton()+'</div>';
						columnHtmlItem += '		</div>';
						columnHtmlItem += '	 </div>';
						columnHtmlItem += '</div>';
					}
					if(dojo.byId(vColumnList[i].getColumnName())){
						dojo.byId(vColumnList[i].getColumnName()).innerHTML = columnHtmlItem;
					}
				}
			}
			if (!this._tooltipInited) {
			  KanbanTooltip.init({
			    root: dojo.byId("kanbanContainer") || document
			  });
			  this._tooltipInited = true;
			}
		}
		window.top.hideWait();
	  };
};

JSKanban.KanbanColumn = function(pColumn){
  var vID = pColumn.id;
  var vColumnName = 'kanbanColumn'+vID;
  var vColumnBadgeName = 'badgeColumnItem'+vID;
  var vColumnPlannedWorksName = 'plannedWorkColumn'+vID;
  var vColumnRealWorksName = 'realWorkColumn'+vID;
  var vColumnLeftWorksName = 'leftWorkColumn'+vID;
  var vItemCount = 0;
  var vPlannedWorks = 0;
  var vRealWorks = 0;
  var vLeftWorks = 0;
  var vWorkUnit = pColumn.workunit;
  var vItemList = pColumn.itemlist
  var vKanbanItemList = new Array();
  var vColumnType = pColumn.type;
  var vHideWorks = pColumn.hideworks;
  var vHideIdle = pColumn.hideidle;
  var vFullWidthElement = pColumn.fullwidthelement;
  var vHideStatus = pColumn.hidestatus;
  var vHideActivityPlanning = pColumn.hideactivityplanning;
  var vHidePlannedDate = pColumn.hideplanneddate;
  var vHideProduct = pColumn.hideproduct;
  var vHideResponsible = pColumn.hideresponsible;
  var vHideType = pColumn.hidetype;
  var vHideProjectName = pColumn.hideprojectname;
  var vHidePriority = pColumn.hidepriority;
  var vHideUrgency = pColumn.hideurgency;
  var vHideColorTitle = pColumn.hidecolortitle;
  var vHidden = (pColumn.hidden == '1' || pColumn.hidden === true)?true:false;
  var vModeColorTitle = pColumn.modecolortitle;
  var vColorOnTitleOrFullTile = pColumn.colorontitleorfulltile;
  
  this.getID			  		= function(){ return vID; };
  this.getColumn      	  		= function(){ return pColumn; };
  this.getColumnName  	  		= function(){ return vColumnName; };
  this.getColumnType  	  		= function(){ return vColumnType; };
  this.getColumnBadgeName 		= function(){ return vColumnBadgeName; };
  this.getColumnPlannedWorksName= function(){ return vColumnPlannedWorksName; };
  this.getColumnRealWorksName	= function(){ return vColumnRealWorksName; };
  this.getColumnLeftWorksName	= function(){ return vColumnLeftWorksName; };
  this.getItemCount  	  		= function(){ return vItemCount; };
  this.getPlannedWorks   			= function(withUnit){
  									if(withUnit == undefined)withUnit=false;
  									var vWork = (withUnit)?vPlannedWorks+' '+vWorkUnit:vPlannedWorks;
   									return vWork;
  								};
  this.getRealWorks  				= function(withUnit){
  									if(withUnit == undefined)withUnit=false;
  									var vWork = (withUnit)?vRealWorks+' '+vWorkUnit:vRealWorks;
  									return vWork; 
  								};
  this.getLeftWorks  				= function(withUnit){
  									if(withUnit == undefined)withUnit=false;
  									var vWork = (withUnit)?vLeftWorks+' '+vWorkUnit:vLeftWorks; 
  									return vWork;
  								};
  this.getWorkUnit				= function(){ return vWorkUnit; };
  this.getModeColorTitle		= function(){ return vModeColorTitle; };
  this.getHideIdle      		= function(){ return (vHideIdle == 'on' || vHideIdle == '1')?true:false; };
  this.getFullWidthElement      = function(){ return (vFullWidthElement == 'on' || vFullWidthElement == '1')?true:false; };
  this.getHideStatus 			= function(){ return (vHideStatus == 'off' || vHideStatus == '0')?true:false; };
  this.getHideActivityPlanning 	= function(){ return (vHideActivityPlanning == 'off' || vHideActivityPlanning == '0')?true:false; };
  this.getHidePlannedDate		= function(){ return (vHidePlannedDate == 'off' || vHidePlannedDate == '0')?true:false; };
  this.getHideProduct 			= function(){ return (vHideProduct == 'off' || vHideProduct == '0')?true:false; };
  this.getHideResponsible 		= function(){ return (vHideResponsible == 'off' || vHideResponsible == '0')?true:false; };
  this.getHideWorks				= function(){ return (vHideWorks == 'off' || vHideWorks == '0')?true:false; };
  this.getHideType 				= function(){ return (vHideType == 'off' || vHideType == '0')?true:false; };
  this.getHideProjectName 		= function(){ return (vHideProjectName == 'off' || vHideProjectName == '0')?true:false; };
  this.getHidePriority			= function(){ return (vHidePriority == 'off' || vHidePriority == '0')?true:false; };
  this.getHideUrgency			= function(){ return (vHideUrgency == 'off' || vHideUrgency == '0')?true:false; };
  this.getHideColorTitle		= function(){ return (vHideColorTitle == 'off' || vHideColorTitle == '0')?true:false; };
  this.getColorOnTitleOrFullTile= function(){ return (vColorOnTitleOrFullTile == 'on' || vColorOnTitleOrFullTile == '1')?true:false; };
  this.isHidden                 = function(){ return vHidden; };
  this.setHideIdle  			= function(pHideIdle){ vHideIdle = pHideIdle; };
  this.setFullWidthElement  	= function(pFullWidthElement){ vFullWidthElement = pFullWidthElement; };
  this.setHideStatus 			= function(pHideStatus){ vHideStatus = pHideStatus; };
  this.setHideActivityPlanning 	= function(pHideActivityPlanning){ vHideActivityPlanning = pHideActivityPlanning; };
  this.setHidePlannedDate 		= function(pHidePlannedDate){ vHidePlannedDate = pHidePlannedDate; };
  this.setHideProduct 			= function(pHideProduct){ vHideProduct = pHideProduct; };
  this.setHideResponsible 		= function(pHideResponsible){ vHideResponsible = pHideResponsible; };
  this.setHideWorks 			= function(pHideWorks){ vHideWorks = pHideWorks; };
  this.setHideType 			    = function(pHideType){ vHideType = pHideType; };
  this.setHideProjectName 		= function(pHideProjectName){ vHideProjectName = pHideProjectName; };
  this.setHidePriority 			= function(pHidePriority){ vHidePriority = pHidePriority; };
  this.setHideUrgency 			= function(pHideUrgency){ vHideUrgency = pHideUrgency; };
  this.setHideColorTitle 		= function(pHideColorTitle){ vHideColorTitle = pHideColorTitle; };
  this.setColorOnTitleOrFullTile= function(pColorOnTitleOrFullTile){ vColorOnTitleOrFullTile = pColorOnTitleOrFullTile; };
  this.setItemCount 			= function(pItemCount){ vItemCount = pItemCount; };
  this.setPlannedWorks 			= function(pPlannedWorks){ vPlannedWorks = pPlannedWorks; };
  this.setRealWorks 			= function(pRealWorks){ vRealWorks = pRealWorks; };
  this.setLeftWorks 			= function(pLeftWorks){ vLeftWorks = pLeftWorks; };
  this.setModeColorTitle 		= function(pModeColorTitle){ vModeColorTitle = pModeColorTitle; };
  
  this.isColorPlannedMode = function(){
  	return !vHideColorTitle && vModeColorTitle == 'colorPlanned';
  };
  
  this.AddKanbanItem = function(value) {
	vKanbanItemList.push(value);
  };
  
  this.ReplaceKanbanItem = function(value) {
    var pId=value.getID();
    var vList = this.getKanbanItemList();
    for(var i = 0; i < vList.length; i++) {
      if(vList[i].getID()==pId){
        vList[i]=value;
        break;
      }
    }
  };
  
  for (var i = 0; i < vItemList.length; i++) {
    var item = vItemList[i];
    var newKanbanItem=new JSKanban.KanbanItems(item);
	newKanbanItem.setColumnID(vID);
  	vKanbanItemList.push(newKanbanItem);
  }
  
  this.deleteKanbanItemFromList = function(pID){
	var vItemList = this.getKanbanItemList();
	for(var i = 0; i < vItemList.length; i++) {
        if(vItemList[i].getID()==pID) {
        	vKanbanItemList.splice(i, 1);
        }
	}
  }
  
  this.getItemArrayLocationByID = function(pId)  {
    var vList = this.getKanbanItemList();
    for(var i = 0; i < vList.length; i++) {
      if(vList[i].getID()==pId) {
        return i;
      }
    }
    return null;
  };
  this.getItemByID = function(pId)  {
    var vList = this.getKanbanItemList();
    for(var i = 0; i < vList.length; i++) {
      if(vList[i].getID()==pId) {
        return vList[i];
      }
    }
    return null;
  };
  
  this.getKanbanItemList   = function() { return vKanbanItemList; };
};

JSKanban.KanbanItems = function(pItem){
  var vID = pItem.id;
  var vName = htmlDecode(pItem.name);
  var vTitleColor = pItem.titlecolor;
  var vTitleTextColor = pItem.titletextcolor;
  var vId = pItem.refid;
  var vClass = pItem.reftype;
  var vIdType = pItem.idtype;
  var vTypeName = htmlDecode(pItem.typename);
  var vTypeColor = pItem.typecolor;
  var vIdStatus = pItem.idstatus;
  var vStatusName = htmlDecode(pItem.statusname);
  var vStatusColor = pItem.statuscolor;
  var vStatusTextColor = pItem.statustextcolor;
  var vIsStatusColorLight = pItem.isstatusccolorlight;
  var vIsCopyStatus = pItem.iscopystatus;
  var vIdCopyStatusNext = pItem.idcopystatusnext;
  var vCopyStatusNextName = pItem.copystatusnextname;
  var vIdPriority = pItem.idpriority;
  var vPriorityName = htmlDecode(pItem.priorityname);
  var vPriorityColor = pItem.prioritycolor;
  var vIdUrgency = pItem.idurgency;
  var vUrgencyName = htmlDecode(pItem.urgencyname);
  var vUrgencyColor = pItem.urgencycolor;
  var vIdProject = pItem.idproject;
  var vProjectColor = pItem.projectcolor;
  var vProjectName = htmlDecode(pItem.projectname);
  var vPlannedDate = pItem.planneddate;
  var vPlannedDateColor = pItem.planneddatecolor;
  var vPlannedDateTextColor = pItem.planneddatetextcolor;
  var vIdResource = pItem.idresource;
  var vIconClass = pItem.iconclass;
  var vColumnID = null;
  var vDndType = pItem.dndtype;
  var vResponsible = pItem.responsible;
  var vPlannedWorks = pItem.plannedwork;
  var vRealWorks = pItem.realwork;
  var vLeftWorks = pItem.leftwork;
  var vWorkUnit = pItem.workunit;
  var vIdTargetProductVersion = pItem.idtargetproductversion;
  var vTargetProductVersionName = htmlDecode(pItem.targetproductversionname);
  var vIdActivityPlanning = pItem.idactivity;
  var vActivityPlanningName = htmlDecode(pItem.activityname);
  var vActivityColor = pItem.activitycolor;
  var vDescription = htmlDecode(pItem.description);
  var vNoteBadge = pItem.notebadge;
  var vCanVote = pItem.canvote;
  var vVoteExist = pItem.voteexist;
  var vVoteIdRule = pItem.voteidrule;
  var vVotePctRate = pItem.votepctrate;
  var vEditorType = pItem.editortype;
  var vIdle = pItem.idle;
  var vIsHidden = false;
  var vPlannedTextColor = pItem.plannedtextcolor;
  var vColorOnTitleOrFullTile = pItem.colorontitleorfulltile;
  
  var arrayColors = new Array(
  		  '#1abc9c', '#2ecc71', '#3498db', '#9b59b6', '#34495e',
  		  '#16a085', '#27ae60', '#2980b9', '#8e44ad', '#2c3e50',
  		  '#f1c40f', '#e67e22', '#99CC00', '#e74c3c', '#95a5a6',
  		  '#d35400', '#c0392b', '#bdc3c7', '#7f8c8d');
  
  this.getItem         				= function(){ return pItem; };
  this.getID           				= function(){ return vID; };
  this.getId           				= function(){ return vId; };
  this.getDndType      				= function(){ return vDndType; };
  this.getName         				= function(){ return vName; };
  this.getTitleColor				= function(){ return vTitleColor; };
  this.getTitleTextColor			= function(){ return vTitleTextColor; };
  this.getIdType       				= function(){ return vIdType; };
  this.getTypeName     				= function(){ return vTypeName; };
  this.getTypeColor     			= function(){ return vTypeColor; };
  this.getIdStatus     				= function(){ return vIdStatus; };
  this.getStatusName   				= function(){ return vStatusName; };
  this.getStatusColor  				= function(){ return vStatusColor; };
  this.getStatusTextColor  			= function(){ return vStatusTextColor; };
  this.getIsStatusColorLight  		= function(){ return vIsStatusColorLight; };
  this.getIsCopyStatus  			= function(){ return vIsCopyStatus; };
  this.getIdCopyStatusNext     		= function(){ return vIdCopyStatusNext; };
  this.getCopyStatusNextName   		= function(){ return vCopyStatusNextName; };
  this.getIdPriority     			= function(){ return vIdPriority; };
  this.getPriorityName   			= function(){ return vPriorityName; };
  this.getPriorityColor  			= function(){ return vPriorityColor; };
  this.getIdUrgency     			= function(){ return vIdUrgency; };
  this.getUrgencyName   			= function(){ return vUrgencyName; };
  this.getUrgencyColor  			= function(){ return vUrgencyColor; };
  this.getProjectId    				= function(){ return vIdProject;}
  this.getProjectName  				= function(){ return vProjectName;}
  this.getProjectColor 				= function(){ return vProjectColor; };
  this.getPlannedDate  				= function(){ return vPlannedDate;}
  this.getPlannedDateColor 			= function(){ return vPlannedDateColor; };
  this.getPlannedDateTextColor      = function(){ return vPlannedDateTextColor; };
  this.getModeColorTitle		    = function(){ return vModeColorTitle; };
  this.getIdResource   				= function(){ return vIdResource; };
  this.getClass        				= function(){ return vClass; };
  this.getPlannedWorks   			= function(withUnit){
										if(withUnit == undefined)withUnit=false;
										var vWork = (withUnit)?vPlannedWorks+' '+vWorkUnit:vPlannedWorks;
	 									return vWork;
									};
  this.getRealWorks  				= function(withUnit){
										if(withUnit == undefined)withUnit=false;
										var vWork = (withUnit)?vRealWorks+' '+vWorkUnit:vRealWorks;
										return vWork; 
									};
  this.getLeftWorks  				= function(withUnit){
										if(withUnit == undefined)withUnit=false;
										var vWork = (withUnit)?vLeftWorks+' '+vWorkUnit:vLeftWorks; 
										return vWork;
									};
  this.getWorkUnit					= function(){ return vWorkUnit; };
  this.getIdTargetProductVersion    = function(){ return vIdTargetProductVersion; };
  this.getTargetProductVersionName  = function(){ return vTargetProductVersionName; };
  this.getIdActivityPlanning    	= function(){ return vIdActivityPlanning; };
  this.getActivityPlanningName  	= function(){ return vActivityPlanningName; };
  this.getActivityColor 			= function(){ return vActivityColor; };
  this.getDescription				= function(){ return htmlDecode(vDescription); };
  this.getNoteBadge      			= function(){ return vNoteBadge; };
  this.getVoted      				= function(){ return vVoted; };
  this.getIdle      				= function(){ return vIdle; };
  this.getIsHidden      			= function(){ return vIsHidden; };
  this.setIsHidden					= function(pIsHidden){ vIsHidden = pIsHidden; };
  this.hasResponsible				= function(){ if(vResponsible){return true;}else{return false;}}
  this.hasPriority					= function(){ if(vIdPriority){return true;}else{return false;}}
  this.hasUrgency					= function(){ if(vIdUrgency){return true;}else{return false;}}
  this.getIconClass    				= function(){ 
    if(!vIconClass){
      vIconClass=this.getClass();
    }
    return vIconClass;
  };
  this.getColumnID					= function(){ return vColumnID; };
  this.setColumnID					= function(pColumnID){ vColumnID = pColumnID; };
  this.getPlannedTextColor          = function(){return vPlannedTextColor;};
  this.getColorOnTitleOrFullTile= function(){ return (vColorOnTitleOrFullTile == 'on' || vColorOnTitleOrFullTile == '1')?true:false; };
  
  this.drawProjectColorThumb = function(){
	var projectColorThumb = '';
	projectColorThumb += '<div style="color:#FFFFFF;background:'+vProjectColor+';width:12px;height:12px;float:left;border-radius:3px" title="">&nbsp;</div>';
	return projectColorThumb;
  };

  this.useFullTileColor = function(pUseColorTitle, pUseFullTileColor){
	return pUseColorTitle && pUseFullTileColor && vTitleColor;
  };

  this.isColorPlannedMode = function(pUseColorTitle, pModeColorTitle, pUseFullTileColor){
	return this.useFullTileColor(pUseColorTitle, pUseFullTileColor) && pModeColorTitle == 'colorPlanned';
  };

  this.getCardStyle = function(pUseColorTitle, pUseFullTileColor){
	if(this.useFullTileColor(pUseColorTitle, pUseFullTileColor)){
		return 'background-color:'+vTitleColor+';color:'+vTitleTextColor+';';
	}
	return '';
  };

  this.getTileDetailTextColor = function(pUseColorTitle, pUseFullTileColor){
	return (this.useFullTileColor(pUseColorTitle, pUseFullTileColor))?vTitleTextColor:'var(--color-medium)';
  };
  
  this.drawPlannedDateThumb = function(pUseColorTitle, pModeColorTitle, pUseFullTileColor){
	var plannedDateThumb = '';
	if(vPlannedDate){
		var plannedDateStyle = 'color:'+vPlannedDateTextColor+';background:'+vPlannedDateColor+';';
		if(this.isColorPlannedMode(pUseColorTitle, pModeColorTitle, pUseFullTileColor)){
			plannedDateStyle = 'background:#FFFFFF;color:black;';
		}
		plannedDateThumb += '<div style="padding: 5px;text-align: center;top: 0px;right: 0px;position: absolute;">';
		plannedDateThumb += '	<div style="'+plannedDateStyle+'font-size:7pt;padding:3px 8px 3px 8px;border-radius:8px;" title="">'+vPlannedDate+'</div>';
		plannedDateThumb += '</div>';
	}
	return plannedDateThumb;
  };
  
  this.drawTitle = function(pUseColorTitle, pUseFullTileColor){
	var title = '';
	var titleStyle = '';
	if(this.useFullTileColor(pUseColorTitle, pUseFullTileColor)){
		titleStyle = 'color:inherit;background-color:transparent;';
	}else if(pUseColorTitle && vTitleColor && vTitleTextColor){
		titleStyle = 'background-color:'+vTitleColor+';color:'+vTitleTextColor;
	}
	title += '<div style="font-size:13px;'+titleStyle+'" class="backlogItemTitle kanbanTitleTicket kanbanTitleSmallTiles">';
	title += '	&nbsp'+vName;
	title += '</div>';
	return title;
  };
  
  this.drawWorks = function(){
	var works = '';
	works += '<table style="color:black;background-color:#eeeeee;cursor:move;width:100%;"><tr>';
	works += '	 <td class="" title="'+i18n('colEstimated')+'" style="width:33%;text-align:center;padding:3px;font-size:75%;">';
	works += '		<span style="font-size:90%;color:var(--color-medium);">'+i18n('colEstimated')+'</span><br>'+this.getPlannedWorks(true)+'</td>';
	works += '	 <td class="" title="'+i18n('colReal')+'" style="width:33%;text-align:center;padding:3px;font-size:75%;">';
	works += '		<span style="font-size:90%;color:var(--color-medium);">'+i18n('colReal')+'</span><br>'+this.getRealWorks(true)+'</td>';
	works += '	 <td class="" title="'+i18n('colLeft')+'" style="width:33%;text-align:center;padding:3px;font-size:75%;">';
	works += '		<span style="font-size:90%;color:var(--color-medium);">'+i18n('colLeft')+'</span><br>'+this.getLeftWorks(true)+'</td>';
	works += '</tr></table>';
	return works;
  };
  
  this.drawDescription = function(){
	var description = '';
	description += htmlDecode(vDescription);
	return description;
  };
  
  this.drawStatusColorThumb = function(){
	var statusColorThumb = '';
	statusColorThumb += '<div style="padding:5px;width: 100%;text-align: center;">';
	statusColorThumb += '	<div style="color:'+vStatusTextColor+';background:'+vStatusColor+';font-size:7pt;padding:'+((vIsStatusColorLight)?'2px 8px 2px 8px':'3px 8px 3px 8px')+';border-radius:8px;'+((vIsStatusColorLight)?'border:1px solid black;':'')+'" title="">'+vStatusName+'</div>';
	statusColorThumb += '</div>';
	if(vIsCopyStatus == '1'){
		statusColorThumb += '<div style="cursor:pointer;padding-top:3px" title="'+i18n("moveStatusTo", new Array(vCopyStatusNextName, vCopyStatusNextName))+'" onclick="sendChangeKanbanMono(\''+vID+'\', \''+vId+'\', \''+vClass+'\', \''+vColumnID+'\', \''+vColumnID+'\')">';
	    statusColorThumb += '	<img src="css/customIcons/new/iconMoveTo.svg" class="imageColorNewGui" style="width:16px;height:16px"/>';
	    statusColorThumb += '</div>';
	}
	return statusColorThumb;
  };
  
  this.drawPriorityColorThumb = function(){
	  var priorityColorColorThumb = '';
	  if(vIdPriority){
		priorityColorColorThumb += ''
		+ '<div style="float:left;margin:5px 0 5px 5px;position:relative">'
		+ '  <div class="kanbanTooltipTrigger"'
		+ '       style="background:'+vPriorityColor+';width:20px;height:20px;float:left;border-radius:5px;cursor:default;"'
		+ '       data-ktip="1"'
		+ '       data-ktip-text="'+htmlDecode(vPriorityName)+'"'
		+ '       data-ktip-icon="imageColorNewGui iconPriority20 iconPriority iconSize20"'
		+ '       data-ktip-pos="bottom">'
		+ '    <div class="whiteIcon iconPriority16 iconPriorityFull iconSize16"'
		+ '         style="z-index:2;width:16px;height:16px;margin:2px;pointer-events:none;">&nbsp;</div>'
		+ '  </div>'
		+ '</div>';
	  }
	  return priorityColorColorThumb;
  };
	
  this.drawUrgencyColorThumb = function(){
	  var urgencyColorColorThumb = '';
	  if(vIdUrgency){
		urgencyColorColorThumb += ''
		+ '<div style="float:left;margin:5px 0 5px 5px;position:relative">'
		+ '  <div class="kanbanTooltipTrigger"'
		+ '       style="background:'+vUrgencyColor+';width:20px;height:20px;float:left;border-radius:5px;cursor:default;"'
		+ '       data-ktip="1"'
		+ '       data-ktip-text="'+htmlDecode(vUrgencyName)+'"'
		+ '       data-ktip-icon="imageColorNewGui iconUrgency20 iconUrgency iconSize20"'
		+ '       data-ktip-pos="bottom">'
		+ '    <div class="whiteIcon iconUrgency16 iconUrgencyFull iconSize16"'
		+ '         style="z-index:2;width:16px;height:16px;margin:2px;pointer-events:none;">&nbsp;</div>'
		+ '  </div>'
		+ '</div>';
	  }
	  return urgencyColorColorThumb;
  };
   
  this.drawProjectName = function(){
	var projectName = '';
	projectName += '<table><tr><td style="display:flex;gap:5px;">';
	projectName += '	<span class="imageColorNewGuiNoSelection"><div class="iconProject iconSize16"></div></span><div style="font-size: 12px;">'+vProjectName+'</div>';
	projectName += '</td></tr></table>';
	return projectName;
  };
  
  this.drawUserThumb = function(){
	  var userThumb = '';
	  if (!vResponsible) {
	    return userThumb;
	  }
	
	  var keyColor = vIdResource % arrayColors.length;
	  var bgColor = (keyColor in arrayColors) ? arrayColors[keyColor] : arrayColors[0];
	
	  var displayName = htmlDecode(vResponsible.nametitle || vResponsible.name || '');
	  var isFile = (vResponsible.isfile) ? true : false;
	
	  var tipText = htmlEncode(displayName);
	  var tipPos  = "bottom";
	
	  if (isFile) {
	    var imgSrc = htmlDecode(vResponsible.file);
	    userThumb += ''
	      + '<img'
	      + ' class="kanbanTooltipTrigger"'
	      + ' id="responsible_'+vID+'"'
	      + ' style="border-radius:5px;float:left;height:20px;width:20px;top:1px;"'
	      + ' src="'+htmlEncode(imgSrc)+'"'
	      + ' data-ktip="1"'
		  + ' data-ktip-html="1"'
	      + ' data-ktip-pos="'+tipPos+'"'
	      + ' data-ktip-text="'+tipText+'"'
	      + ' data-ktip-mode="user"'
	      + ' data-ktip-user-mode="img"'
	      + ' data-ktip-user-src="'+htmlEncode(imgSrc)+'"'
	      + ' />';
	  } else {
	    var initial = htmlDecode(vResponsible.file || '');
	    userThumb += ''
	      + '<span'
	      + ' class="kanbanTooltipTrigger"'
	      + ' id="responsible_'+vID+'"'
	      + ' style="color:#ffffff;background-color:'+bgColor+';float:left;font-size:15px;border-radius:5px;font-weight:300;text-shadow:none;text-align:center;height:20px;width:20px;top:1px;display:inline-block;line-height:20px;"'
	      + ' data-ktip="1"'
		  + ' data-ktip-html="1"'
	      + ' data-ktip-pos="'+tipPos+'"'
	      + ' data-ktip-text="'+tipText+'"'
	      + ' data-ktip-mode="user"'
	      + ' data-ktip-user-mode="initial"'
	      + ' data-ktip-user-initial="'+htmlEncode(initial)+'"'
	      + ' data-ktip-user-bg="'+htmlEncode(bgColor)+'"'
	      + '>'
	      + htmlEncode(initial)
	      + '</span>';
	  }
	  return userThumb;
  };

  
  this.drawResponsibleName = function(){
	var responsibleName = '';
	if(vResponsible){
		var keyColor = vIdResource % arrayColors.length;
		var bgColor = (keyColor in arrayColors)?arrayColors[keyColor]:arrayColors[0];
		responsibleName += '<div class="backlogResponsibleName" style="background-color:'+bgColor+';" >';
		responsibleName +=		htmlDecode(vResponsible.name);
		responsibleName += '</div>';
	}
	return responsibleName;
  };
  
  this.drawActivityPlanningName = function(pUseColorTitle, pModeColorTitle, pUseFullTileColor){
	var activityPlanning = '';
	activityPlanning += '<div style="height:20px;padding:0px 10px 0px 5px;overflow:hidden;white-space:nowrap;">';
	if(vIdActivityPlanning && vActivityPlanningName){
		activityPlanning += '	<table style="margin: 2px;"><tr>';
		activityPlanning += '		<td title="'+i18n('Sprint')+' #'+vIdActivityPlanning+' '+vActivityPlanningName+'">';
		activityPlanning += '			<div class="imageColorNewGuiNoSelection iconActivity16 iconActivity iconSize16" style="width:16px;height:16px;float:left"></div>';
		activityPlanning += '		</td>';
		activityPlanning += '		<td title="'+i18n('Sprint')+' #'+vIdActivityPlanning+' '+vActivityPlanningName+'" id="vSprintName'+vID+'"  style="float:left;overflow:hidden;margin-left:2px;color:'+this.getTileDetailTextColor(pUseColorTitle, pUseFullTileColor)+';">'+vActivityPlanningName+'</td>';
		activityPlanning += '	</tr></table>';
	}
	activityPlanning += '</div>';
	return activityPlanning;
  };
  
  this.drawTargetProductVersion = function(pUseColorTitle, pModeColorTitle, pUseFullTileColor){
	var targetProductVersion = '';
	targetProductVersion += '<div style="height:20px;padding:0px 10px 0px 5px;overflow:hidden;white-space:nowrap;">';
	if(vTargetProductVersionName){
		targetProductVersion += '	<table style="margin: 2px;"><tr>';
		targetProductVersion += '		<td title="'+i18n('colIdTargetProductVersion')+'">';
		targetProductVersion += '			<div class="imageColorNewGuiNoSelection iconProductVersion16 iconProductVersion iconSize16" style="width:16px;height:16px;float:left"></div>';
		targetProductVersion += '		</td>';
		targetProductVersion += '		<td title="'+vTargetProductVersionName+'" id="targetProductVersion'+vID+'"  style="float:left;overflow:hidden;margin-left:2px;color:'+this.getTileDetailTextColor(pUseColorTitle, pUseFullTileColor)+';">'+vTargetProductVersionName+'</td>';
		targetProductVersion += '	</tr></table>';
	}
	targetProductVersion += '</div>';
	return targetProductVersion;
  };
  
  this.drawTableButton = function(){
	var tableButton = '';
	var margin=(vNoteBadge>9)?'-10':'-7';
	tableButton += '<table style="float:right;margin:5px 0px;"><tr>';
	tableButton += '	<td><div class="roundedButtonSmall" style="width:16px;height:16px;cursor:pointer;vertical-align:text-bottom;margin-right:6px;float:left;padding-top: 2px;" onclick="showDetail(\'refreshActionAddItemKanban\',1,\''+vClass+'\',false,'+vId+');" title="'+i18n('kanbanEditItem', new Array(vId, vId))+'">';
	tableButton += '		<span class="roundedButtonSmall" style="top:0px;display:inline-block;width:16px;height:16px;"><div class="iconButtonEdit16 iconButtonEdit iconSize16" style="">&nbsp;</div></span>';
	tableButton += '	</div></td>';
	tableButton += '	<td><div style="position:relative">';
	tableButton += '		<div onclick="activityStreamKanban(\''+vID+'\', '+vId+', \''+vClass+'\', \''+i18n('textareaEnterText')+'\');" style="margin-right:5px;margin-top: 3px;" title="'+i18n('commentImputationAdd')+'">';
	tableButton += '			<span class="roundedButtonSmall" style="top:0px;display:inline-block;width:16px;height:16px;"><div class="iconButtonAddComment16 iconButtonAddComment iconSize16" style="">&nbsp;</div></span>';
	tableButton += '			<div style="pointer-events: none;position:absolute;bottom:-3px;margin-left:'+margin+'px;width:5px;"><div id="noteBadge_'+vID+'" class="kanbanBadge" style="">'+vNoteBadge+'</div></div>';
	tableButton += '		</div>';
	tableButton += '	</div></td>';
	if((vCanVote && !vVoteExist && vVoteIdRule) || (vVoteExist && vVoteIdRule)){
	  iconLogoVote = 'AddVote';
      if(vVotePctRate > 0){
        iconLogoVote = 'AddVote25';
      }
	  if(vVotePctRate > 24){
        iconLogoVote = 'AddVote25';
      }
	  if(vVotePctRate > 49){
        iconLogoVote = 'AddVote50';
      }
	  if(vVotePctRate > 74){
        iconLogoVote = 'AddVote75';
      }
	  if(vVotePctRate >=  100){
        iconLogoVote = 'AddVote100';
      }
	  voteButtonTitle=i18n('colPctRate')+' : '+vVotePctRate+' %';
	  if (vCanVote) voteButtonTitle +="\n"+i18n ('addVoteKanban');
	  onClick="";
	  if (vCanVote && vVoteIdRule) onClick="addVote('"+vClass+"','"+vId+"','"+vEditorType+"','add',"+vVoteIdRule+",true);";
	  tableButton += '	<td><div style="position:relative">';
	  tableButton += '		<div onclick="'+onClick+'" style="margin-right:5px;margin-top: 3px;" title="'+voteButtonTitle+'">';
	  tableButton += '			<span class="roundedButtonSmall" style="top:0px;display:inline-block;width:16px;height:16px;"><div class="iconButton'+iconLogoVote+'16 iconButton'+iconLogoVote+' iconSize16" style="">&nbsp;</div></span>';
	  tableButton += '		</div>';
	  tableButton += '	</div></td>';
	}
	tableButton += '	<td><div class="roundedButtonSmall" style="width:20px;height:16px;cursor:pointer;float:right;vertical-align:text-bottom;padding-top: 3px;" onclick="gotoElement( \''+vClass+'\','+vId+', true);" title="'+i18n('diaryGotoItem',new Array(vClass, vId))+'">';
	tableButton += '		<span class="roundedButtonSmall" style="top:0px;display:inline-block;width:16px;height:16px;"><div class="iconGoto16 iconGoto iconSize16" style="">&nbsp;</div></span>';
	tableButton += '	</div></td>';
	tableButton += '</tr></table>';
	return tableButton;
  };
};


// ======================================= KANBAN BACKLOG FUNCTION ======================================= //

function refreshKanban(oldColumn, newColumn, itemID) {
	showWait();
	if(oldColumn == undefined)oldColumn=null;
    if(newColumn == undefined)newColumn=null;
	if(itemID == undefined)itemID=null;
	if(!oldColumn && !newColumn && !itemID){
		var vKanbanColumnList = kbn.getKanbanColumnList();
		for(var i = 0; i < vKanbanColumnList.length; i++) {
			var columnNode = dojo.byId(vKanbanColumnList[i].getColumnName());
			var widgets = dijit.registry.findWidgets(columnNode);
		    dojo.forEach(widgets, function(w) {
		        w.destroyRecursive(false);
		    });
		}
	}
	if(itemID){
		var item = kbn.getKanbanItemByIDFromColumn(itemID);
		var itemClass = item.getClass();
		kbn.deleteItemFromKanbanColumn(itemID);
		var widgets = dijit.registry.findWidgets(dojo.byId(itemID));
		dojo.forEach(widgets, function(w) {
	        w.destroyRecursive(false);
	    });
		oldColumn = newColumn;
	}
	var url = getJsonKanbanUrl(oldColumn, newColumn);
	var jsonDiv = getJsonKanbanData(true);
	showWait();
	loadContent(url,jsonDiv);
}

function kanbanHideBacklog(value){
	showWait();
	saveDataToSession("kanbanHideBacklog",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.isBacklogColumn').forEach(function(node){
		node.style.display = display;
		if(hide){
			var widgets = dijit.registry.findWidgets(node);
		    dojo.forEach(widgets, function(w) {
		        w.destroyRecursive(false);
		    });
		}
	});
	if(!hide)refreshKanban('backlog', 'backlog');
	hideWait();
}

function kanbanShowIdle(value){
	showWait();
	saveDataToSession("kanbanShowIdle",value,true);
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		vKanbanColumnList[i].setHideIdle(value);
	}
	hideWait();
	refreshKanban();
}

function kanbanHideParentActivities(value){
	showWait();
	saveDataToSession("kanbanHideParentActivities",value,true,function(){
		refreshKanban();
	});
}

function kanbanFullWidthElement(value){
	showWait();
	saveDataToSession("kanbanFullWidthElement",value,true);
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		vKanbanColumnList[i].setFullWidthElement(value);
	}
	refreshKanban();
}

function kanbanHideStatus(value){
	showWait();
	saveDataToSession("kanbanHideStatus",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemStatus').forEach(function(node){
		node.style.display = display;
	});
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		vKanbanColumnList[i].setHideStatus(value);
	}
	hideWait();
}

function kanbanHidePlannedDate(value){
	showWait();
	saveDataToSession("kanbanHidePlannedDate",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemPlannedDate').forEach(function(node){
		node.style.display = display;
	});
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		vKanbanColumnList[i].setHidePlannedDate(value);
	}
	hideWait();
}

function kanbanHideActivityPlanning(value){
	showWait();
	saveDataToSession("kanbanHideActivityPlanning",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemActivityPlanning').forEach(function(node){
		node.style.display = display;
	});
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		vKanbanColumnList[i].setHideActivityPlanning(value);
	}
	hideWait();
}

function kanbanHideProduct(value){
	showWait();
	saveDataToSession("kanbanHideProduct",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemProduct').forEach(function(node){
		node.style.display = display;
	});
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		vKanbanColumnList[i].setHideProduct(value);
	}
	hideWait();
}

function kanbanHideResponsible(value){
	showWait();
	saveDataToSession("kanbanHideResponsible",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemUserThumb').forEach(function(node){
		node.style.display = display;
	});
	var vKanbanColumnList = kbn.getKanbanColumnList();
	var vFullWidthElement = false;
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		vKanbanColumnList[i].setHideResponsible(value);
		vFullWidthElement = vKanbanColumnList[i].getFullWidthElement();
	}
	dojo.query('.backlogResponsibleName').forEach(function(node){
		node.style.display = (!vFullWidthElement)?'none':display;
	});
	hideWait();
}

function kanbanHidePriority(value){
	showWait();
	saveDataToSession("kanbanHidePriority",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemPriorityThumb').forEach(function(node){
		node.style.display = display;
	});
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		vKanbanColumnList[i].setHidePriority(value);
	}
	hideWait();
}

function kanbanHideUrgency(value){
	showWait();
	saveDataToSession("kanbanHideCriticality",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemUrgencyThumb').forEach(function(node){
		node.style.display = display;
	});
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		vKanbanColumnList[i].setHideUrgency(value);
	}
	hideWait();
}

function kanbanHideWorks(value){
	showWait();
	saveDataToSession("kanbanSeeWork",value,true);
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		vKanbanColumnList[i].setHideWorks(value);
	}
	refreshGlobalKanban();
	hideWait();
}

function kanbanHideType(value){
	showWait();
	saveDataToSession("kanbanHideType",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemTypeName').forEach(function(node){
		node.style.display = display;
	});
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		vKanbanColumnList[i].setHideType(value);
	}
	hideWait();
}

function kanbanHideProjectName(value){
	showWait();
	saveDataToSession("kanbanHideProjectName",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		vKanbanColumnList[i].setHideProjectName(value);
		display = (!vKanbanColumnList[i].getFullWidthElement())?'display:none':display;
	}
	dojo.query('.backlogItemProjectName').forEach(function(node){
		node.style.display = display;
	});
	hideWait();
}

function kanbanHideColorTitle(value){
	showWait();
	saveDataToSession("kanbanHideColorTitle",value,true);
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		vKanbanColumnList[i].setHideColorTitle(value);
	}
	hideWait();
	refreshKanban();
}

function kanbanModeColorTitle(value){
	var vKanbanColumnList = kbn.getKanbanColumnList();
	var hideColorTitle = false;
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		vKanbanColumnList[i].setModeColorTitle(value);
		hideColorTitle = vKanbanColumnList[i].getHideColorTitle();
	}
	saveDataToSession("kanbanModeColorTitle",value,true,function(){
		hideWait();
		if(!hideColorTitle){
			refreshKanban();
		}
	});
}

function kanbanColorOnTitleOrFullTile(value){
	showWait();
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		vKanbanColumnList[i].setColorOnTitleOrFullTile(value);
	}
	saveDataToSession("kanbanColorOnTitleOrFullTile",value,true,function(){
		hideWait();
		refreshKanban();
	});
}
// ======================================= COMMON BACKLOG FUNCTION ======================================= //

function getJsonKanbanUrl (oldColumn, newColumn) {
  if(oldColumn == undefined)oldColumn=null;
  if(newColumn == undefined)newColumn=null;
  url="../tool/jsonKanban.php";
  if(oldColumn && newColumn){
	url += '?onlyRefresh=true&oldColumn='+oldColumn+'&newColumn='+newColumn+addTokenIndexToUrl();
  }
  return url;
}

function getJsonKanbanData (onlyName) {
  if(onlyName==undefined)onlyName=false;
  data=dojo.byId('kanbanJsonData');
  if(onlyName)data='kanbanJsonData';
  return data;
}

function refreshGlobalKanban(idKanban){
	if(idKanban){
		if(idKanban == '0')idKanban=null;
		saveDataToSession('kanbanIdKanban', idKanban, true);
	}
	var currentScreen=(dojo.byId('objectClassManual')) ? dojo.byId('objectClassManual').value : 'Kanban';
	var resultDiv = (currentScreen == 'LiveMeeting')?'divBottom':'centerDiv';
	loadContent('../view/kanbanViewMain.php',resultDiv,null);
}

function addKanbanFromKanban(){
	loadDialog('dialogKanbanUpdate', function(){kanbanFindTitle('addKanban');}, true, '&typeDynamic=addKanban', true, false);
}

function managedKanbanColumn(idKanban, type){
	manageKanbanColunm(type, idKanban);
}

function editKanbanColumn(idKanban, type, from){
	manageKanbanColunm(type, idKanban, from);
}

function addItemFromKanban(item){
	kanbanPendingColumnContext = null;
	var canCreate = (canCreateArray[item] == 'YES')?1:0;
	showDetail('refreshActionAddItemKanban', canCreate,item,false,null,true);
	newDetailItem(item, null, null);
}

var kanbanPendingColumnContext = null;

function addItemFromKanbanColumn(columnClass, columnTarget, columnType){
	if(!columnClass)return;
	var canCreate = (canCreateArray[columnClass] == 'YES')?1:0;
	if(!canCreate)return;
	showDetail('refreshActionAddItemKanban', canCreate, columnClass, false, null, true);
	newDetailItem(columnClass, null, null);
	kanbanPendingColumnContext = {columnTarget:columnTarget, columnType:columnType, objectClass:columnClass};
}

function openKanbanColumnContextMenu(evt, columnClass, columnTarget, columnType, columnName){
	if(evt){
		if(evt.target && (evt.target.closest && evt.target.closest('.backlogItem, .backlogItemFull, .columnOptionButton'))){
			return;
		}
		evt.preventDefault();
		if(evt.stopPropagation)evt.stopPropagation();
	}
	// Cancel any pending hide that could wipe our onClick handler
	if(typeof hideKanbanContextMenuTimeout != 'undefined' && hideKanbanContextMenuTimeout){
		clearTimeout(hideKanbanContextMenuTimeout);
		hideKanbanContextMenuTimeout = null;
	}
	var contextMenu = dijit.byId('kanbanContextMenu');
	var contextMenuDiv = dojo.byId('dialogKanbanContextMenu');
	if(!contextMenu || !contextMenuDiv)return;
	var item = (dojo.byId('typeKanban'))?dojo.byId('typeKanban').value:null;
	if(!item)return;
	var divKanbanContainer = dojo.byId('divKanbanContainer');
	var scrollX = (divKanbanContainer)?divKanbanContainer.scrollLeft:0;
	var mousePosition = {x: evt.clientX + scrollX, y: evt.clientY - 150};
	if(dojo.byId('isMenuLeftOpen') && dojo.byId('isMenuLeftOpen').value == 'true'){
		mousePosition.x -= 250;
	}
	dojo.query('.contextMenuClass').forEach(function(node){
		node.style.cssText='position:absolute;width:0px;height:0px;overflow:hidden;top:'+mousePosition.y+'px;left:'+mousePosition.x+'px';
	});
	// Hide all rows except the "Add" one
	var rowsToHide = ['editFromKanban','copyFromKanban','addCommentFromKanban','removeFromKanban','printFromKanban','printPdfFromKanban','mailFromKanban','searchFromKanban','gotoFromKanban'];
	rowsToHide.forEach(function(rowId){
		var row = dojo.byId(rowId);
		if(row){ row.style.display = 'none'; row.onclick = null; row.setAttribute('onClick',''); }
	});
	var addRow = dojo.byId('addFromKanban');
	if(addRow){
		addRow.style.display = '';
		var label = dojo.byId('addFromKanban_label');
		if(label){
			label.innerHTML = i18n('contextMenuButtonNew')+' ('+columnName+')';
		}
		addRow.setAttribute('onClick','');
		addRow.onclick = function(){
			addRow.onclick = null;
			hideKanbanContextMenu(0);
			addItemFromKanbanColumn(columnClass, columnTarget, columnType);
		};
	}
	contextMenu.openDropDown();
	contextMenuDiv.focus();
}

function refreshActionAddKanban(field){
	if(dijit.byId(field.id).get('value')!=-1){
		var idKanban = field.value;
		refreshGlobalKanban(idKanban);
		dijit.byId(field.id).set('value',-1);
	}
}

function refreshActionAddItemKanban(field){
	if(dijit.byId(field.id).get('value')!=-1){
		var newId = dijit.byId(field.id).get('value');
		if(kanbanPendingColumnContext && newId && parseInt(newId) > 0){
			var ctx = kanbanPendingColumnContext;
			kanbanPendingColumnContext = null;
			var idKanban = dojo.byId('idKanban').value;
			// Reset the field BEFORE async xhr so it does not fire again
			dijit.byId(field.id).set('value',-1);
			var url = "../tool/kanbanUpdate.php?objectId=" + newId
				+ "&objectClass=" + ctx.objectClass
				+ "&itemID=" + ctx.objectClass + newId
				+ "&oldColumn=" + ctx.columnTarget
				+ "&newColumn=" + ctx.columnTarget
				+ "&columnType=" + ctx.columnType
				+ "&idKanban=" + idKanban
				+ "&forceWorkflow=1" + addTokenIndexToUrl();
			dojo.xhrGet({
				url:url,
				load:function(data){
					if(data && data.indexOf('messageError/split/') != -1){
						showAlert(data.split('messageError/split/')[1], null);
						refreshKanban();
					}else if(data && data.indexOf('needGlobalRefresh') != -1){
						refreshGlobalKanban();
					}else if(data){
						// Required fields / result / resource needed : open the dialog
						var functionCallback = function(){ hideWait(); };
						if ((data.indexOf('needResult') != -1 && typeof dojo.byId("kanbanResultEditorType") != 'undefined')
							|| ((data.indexOf('kanbanDescription') != -1 || data.indexOf('description') != -1) && typeof dojo.byId("descriptionEditorType") != 'undefined')) {
							functionCallback = function(){
								var editorTypeResult = null;
								if (dojo.byId("kanbanResultEditorType") && typeof dojo.byId("kanbanResultEditorType") != 'undefined') editorTypeResult = dojo.byId("kanbanResultEditorType").value;
								if (editorTypeResult == "CK") {
									ckEditorReplaceEditor("kanbanResult", 999);
								} else if (dijit.byId("liveMeetingResult") && dijit.byId("kanbanResult")) {
									dijit.byId("kanbanResult").set("class", "input");
								}
								var editorTypeDescription = null;
								if (dojo.byId("descriptionEditorType") && typeof dojo.byId("descriptionEditorType") != 'undefined') editorTypeDescription = dojo.byId("descriptionEditorType").value;
								if (editorTypeDescription == "CK") {
									if (dojo.byId("kanbanDescription")) ckEditorReplaceEditor("kanbanDescription", 999);
									else ckEditorReplaceEditor("description", 999);
								} else if (dijit.byId("liveMeetingResult") && dijit.byId("kanbanDescription")) {
									dijit.byId("kanbanDescription").set("class", "input");
								} else if (dijit.byId("liveMeetingResult") && dijit.byId("description")) {
									dijit.byId("description").set("class", "input");
								}
							};
						}
						loadDialog('dialogKanbanUpdate', functionCallback, true, data + "&typeDynamic=update", true, false);
					}else{
						refreshKanban();
					}
				},
				error:function(){
					refreshKanban();
				}
			});
			return;
		}
		refreshKanban();
		dijit.byId(field.id).set('value',-1);
	}
}

function manageKanbanColunm(columnType, idKanban, idColumn){
	if(columnType == undefined)columnType='';
	if(idKanban == undefined)idKanban='';
	if(idColumn == undefined)idColumn='';
	var params = '&columnType='+columnType+'&idKanban='+idKanban+'&idColumn='+idColumn;
	loadDialog('dialogKanbanManageColumn',null,true,params,true,false);
}

function updateKanbanColumnManagment(source, target, nodes){
	var targetManagment = (target.id=='columnManagmentDndTarget')?target:source;
	if(target.id=='columnManagmentDndTarget'){
		nodes.forEach(function(node){
			dojo.removeClass(node, 'itemSource');
	   		dojo.addClass(node, 'itemTarget');
	     	dojo.query('.itemColumnHeaderTR', node).forEach(function(itemName){
	     		itemName.style.display = '';
	     	});
			dojo.query('.itemColumnContentSource', node).forEach(function(itemName){
	     		itemName.style.display = 'none';
	     	});
			dojo.query('.itemColumnContentTarget', node).forEach(function(itemName){
	     		itemName.style.display = 'flex';
	     	});
	   	});
	}else{
		nodes.forEach(function(node){
       		dojo.removeClass(node, 'itemTarget');
       		dojo.addClass(node, 'itemSource');
         	dojo.query('.itemColumnHeaderTR', node).forEach(function(itemName){
         		itemName.style.display = 'none';
         	});
         	dojo.query('.itemColumnContentSource', node).forEach(function(itemName){
         		itemName.style.display = 'flex';
         	});
         	dojo.query('.itemColumnContentTarget', node).forEach(function(itemName){
         		itemName.style.display = 'none';
         	});
       	});
	}
	setTimeout(function(){
		source.selectNone();
		target.selectNone();
		if(targetManagment.id=='columnManagmentDndTarget'){
			var allNodes = [];
		    targetManagment.getAllNodes().forEach(function(node){
		        var sortOrder = node.attributes.sortorder.value;
		        allNodes.push({
		            node: node,
		            sortOrder: parseInt(sortOrder)
		        });
		    });
			
			allNodes.sort(function(a, b) {
			    return a.sortOrder - b.sortOrder;
			});
			
			var typeData = dojo.byId('typeData').value;
			var jsonColumn = dojo.byId('jsonColumn');
			var json = '{"column":[';
				
			dojo.query('.columnManagmentItem.backlogColumn').forEach(function(node){
				var from = node.attributes.from.value;
				var namecolumn = dojo.byId('nameColumn_'+from).value;
				if(!namecolumn.trim()){
					var namecolumn = node.attributes.namecolumn.value;
				}
				json += '{"from":'+from+',"name":"'+namecolumn+'","cantDelete":1},';
			});
			
			allNodes.forEach(function(item){
				var node = item.node;
				var from = node.attributes.from.value;
				var namecolumn = dojo.byId('nameColumn_'+from).value;
				if(!namecolumn.trim()){
					var namecolumn = node.attributes.namecolumn.value;
				}
				json += '{"from":'+from+',"name":"'+namecolumn+'"},';
			});
			
			json = json.replace(/.$/,"],");
			json += '"typeData":"'+typeData+'"}';
			jsonColumn.value = json;
		}
		if(source != target){
			loadContent("../tool/refreshColumnManagmentTargetDiv.php","columnManagementTargetDiv","columnManagmentForm");
		}
	}, 1);
}

function updateColumnName(){
	var typeData = dojo.byId('typeData').value;
	var jsonColumn = dojo.byId('jsonColumn');
	var json = '{"column":[';
		
	dojo.query('.columnManagmentItem.backlogColumn').forEach(function(node){
		var from = node.attributes.from.value;
		var namecolumn = dojo.byId('nameColumn_'+from).value;
		if(!namecolumn.trim()){
			namecolumn = node.attributes.namecolumn.value;
		}
		json += '{"from":'+from+',"name":"'+namecolumn+'","cantDelete":1},';
	});
	
	columnManagmentDndTarget.getAllNodes().forEach(function(node){
		var from = node.attributes.from.value;
		var namecolumn = dojo.byId('nameColumn_'+from).value;
		if(!namecolumn.trim()){
			namecolumn = node.attributes.namecolumn.value;
		}
		json += '{"from":'+from+',"name":"'+namecolumn+'"},';
	});
	
	json = json.replace(/.$/,"],");
	json += '"typeData":"'+typeData+'"}';
	jsonColumn.value = json;
}

function saveKanbanColumnManagment(editMode){
	if(!editMode){
		var typeData = dojo.byId('typeData').value;
		var jsonColumn = dojo.byId('jsonColumn');
		var json = '{"column":[';
			
		dojo.query('.columnManagmentItem.backlogColumn').forEach(function(node){
			var from = node.attributes.from.value;
			var namecolumn = dojo.byId('nameColumn_'+from).value;
			if(!namecolumn.trim()){
				namecolumn = node.attributes.namecolumn.value;
			}
			json += '{"from":'+from+',"name":"'+namecolumn+'","cantDelete":1},';
		});
		
		columnManagmentDndTarget.getAllNodes().forEach(function(node){
			var from = node.attributes.from.value;
			var namecolumn = dojo.byId('nameColumn_'+from).value;
			if(!namecolumn.trim()){
				namecolumn = node.attributes.namecolumn.value;
			}
			json += '{"from":'+from+',"name":"'+namecolumn+'"},';
		});
		
		json = json.replace(/.$/,"],");
		json += '"typeData":"'+typeData+'"}';
		jsonColumn.value = json;
	}
	var callBack = function(){
		dijit.byId('dialogKanbanManageColumn').hide();
		refreshGlobalKanban();
	};
	loadContent("../tool/saveKanbanColumnManagment.php","resultDivMain","columnManagmentForm",false,null,null,null,callBack);
}

function hideKanbanColumn(idKanban, from, hide){
	hide = (hide)?1:0;
	saveDataToSession('kanbanHideColumn_'+idKanban+'_'+from, hide, true);
	refreshGlobalKanban();
}

function kanbanColumnHideStatus(idKanban, idStatus){
	var hide = dojo.byId('isColumnStatusHided_'+idStatus);
	saveDataToSession('kanbanColumnStatusHide_'+idKanban+'_'+idStatus, hide.value, true);
	var hideButton = dojo.byId('columnHideStatus_'+idStatus);
	var status = dojo.byId('columnStatus_'+idStatus);
	if(hide.value == '1'){
		dojo.query('.iconButtonNoView', hideButton).forEach(function(node){
			dojo.removeClass(node ,'iconButtonNoView');
			dojo.removeClass(node ,'iconButtonNoView16');
			dojo.addClass(node, 'iconButtonView');
			dojo.addClass(node, 'iconButtonView16');
	 	});
		hide.value = '0';
		dojo.style(status, 'opacity', '0.25');
	}else{
		dojo.query('.iconButtonView', hideButton).forEach(function(node){
			dojo.removeClass(node ,'iconButtonView');
			dojo.removeClass(node ,'iconButtonView16');
			dojo.addClass(node, 'iconButtonNoView');
			dojo.addClass(node, 'iconButtonNoView16');
	 	});
		hide.value = '1';
		dojo.style(status, 'opacity', '1');
	}
}

function filterItemName() {
	var input = (dojo.byId('searchByName'))?dojo.byId('searchByName').value.toLowerCase():null;
	var filter = input.value.toLowerCase();
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		var vKanbanItemList = vKanbanColumnList[i].getKanbanItemList();
		for(var j = 0; j < vKanbanItemList.length; j++) {
			var item = dojo.byId(vKanbanItemList[j].getID());
			var itemName = vKanbanItemList[j].getName().toLowerCase();
			if(itemName.indexOf(filter) > -1 || !filter.trim()){
				dojo.removeClass(item, 'backlogItemHide');
		    } else {
				dojo.addClass(item, 'backlogItemHide');
		    }
		}
	}
}

function filterItemResponsible() {
	var idResponsible = (dijit.byId('searchByResponsible'))?dijit.byId('searchByResponsible').get('value'):null;
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		var vKanbanItemList = vKanbanColumnList[i].getKanbanItemList();
		for(var j = 0; j < vKanbanItemList.length; j++) {
			var item = dojo.byId(vKanbanItemList[j].getID());
			var itemResponsible = vKanbanItemList[j].getIdResource();
			if(itemResponsible == idResponsible.trim() || !idResponsible.trim()){
				dojo.removeClass(item, 'backlogItemHide');
		    } else {
				dojo.addClass(item, 'backlogItemHide');
		    }
		}
	}
}

function filterItemStatus() {
	var idStatus = (dijit.byId('searchByStatus'))?dijit.byId('searchByStatus').get('value'):null;
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		var vKanbanItemList = vKanbanColumnList[i].getKanbanItemList();
		for(var j = 0; j < vKanbanItemList.length; j++) {
			var item = dojo.byId(vKanbanItemList[j].getID());
			var itemStatus = vKanbanItemList[j].getIdResource();
			if(itemStatus == idStatus.trim() || !idStatus.trim()){
				dojo.removeClass(item, 'backlogItemHide');
		    } else {
				dojo.addClass(item, 'backlogItemHide');
		    }
		}
	}
}

function filterItemVersion() {
	var idVersion = (dijit.byId('searchByTargetProductVersion'))?dijit.byId('searchByTargetProductVersion').get('value'):null;
	var vKanbanColumnList = kbn.getKanbanColumnList();
	for(var i = 0; i < vKanbanColumnList.length; i++) {
		var vKanbanItemList = vKanbanColumnList[i].getKanbanItemList();
		for(var j = 0; j < vKanbanItemList.length; j++) {
			var item = dojo.byId(vKanbanItemList[j].getID());
			var itemVersion = vKanbanItemList[j].getIdTargetProductVersion();
			if(itemVersion == idVersion.trim() || !idVersion.trim()){
				dojo.removeClass(item, 'backlogItemHide');
		    } else {
				dojo.addClass(item, 'backlogItemHide');
		    }
		}
	}
}

function filterKanban(refresh) {
	if(refresh==undefined)refresh=false;
	
    var nameFilter      = (dojo.byId('searchByName'))?dojo.byId('searchByName').value.toLowerCase():null;
    var idResponsible   = (dijit.byId('searchByResponsible'))?dijit.byId('searchByResponsible').get('value'):null;
	var idStatus        = (dijit.byId('searchByStatus'))?dijit.byId('searchByStatus').get('value'):null;
	var idVersion       = (dijit.byId('searchByTargetProductVersion'))?dijit.byId('searchByTargetProductVersion').get('value'):null;

    nameFilter    = nameFilter.trim();
    idResponsible = idResponsible ? idResponsible.toString().trim() : '';
	idStatus	  = idStatus ? idStatus.toString().trim() : '';
    idVersion     = idVersion ? idVersion.toString().trim() : '';

    var vKanbanColumnList = kbn.getKanbanColumnList();

    for (var i = 0; i < vKanbanColumnList.length; i++) {
        if (vKanbanColumnList[i].isHidden()) continue;
        var vKanbanItemList = vKanbanColumnList[i].getKanbanItemList();
        for (var j = 0; j < vKanbanItemList.length; j++) {
            var itemNode       = dojo.byId(vKanbanItemList[j].getID());
            var itemName       = vKanbanItemList[j].getName().toLowerCase();
            var itemResp       = vKanbanItemList[j].getIdResource();
            var itemItemVer    = vKanbanItemList[j].getIdTargetProductVersion();
			var itemStatus	   = vKanbanItemList[j].getIdStatus();

            var okName   = (!nameFilter)    || (itemName.indexOf(nameFilter) > -1);
            var okResp   = (!idResponsible) || (itemResp == idResponsible);
            var okVer    = (!idVersion)     || (itemItemVer == idVersion);
			var okStatus = (!idStatus) 		|| (itemStatus == idStatus);
            if (okName && okResp && okVer && okStatus) {
				vKanbanItemList[j].setIsHidden(false);
                dojo.removeClass(itemNode, 'backlogItemHide');
            } else {
				vKanbanItemList[j].setIsHidden(true);
                dojo.addClass(itemNode, 'backlogItemHide');
            }
        }
		kbn.setKanbanColumnItemCount(vKanbanColumnList[i].getID());
		if(dojo.byId(vKanbanColumnList[i].getColumnBadgeName())){
			dojo.byId(vKanbanColumnList[i].getColumnBadgeName()).innerHTML = vKanbanColumnList[i].getItemCount();
		}
		kbn.setKanbanColumnWorksValue(vKanbanColumnList[i].getID());
		if(dojo.byId(vKanbanColumnList[i].getColumnPlannedWorksName()) && dojo.byId(vKanbanColumnList[i].getColumnRealWorksName()) && dojo.byId(vKanbanColumnList[i].getColumnLeftWorksName())){
			dojo.byId(vKanbanColumnList[i].getColumnPlannedWorksName()).innerHTML = vKanbanColumnList[i].getPlannedWorks(true);
			dojo.byId(vKanbanColumnList[i].getColumnRealWorksName()).innerHTML = vKanbanColumnList[i].getRealWorks(true);
			dojo.byId(vKanbanColumnList[i].getColumnLeftWorksName()).innerHTML = vKanbanColumnList[i].getLeftWorks(true);
		}
    }
	if(refresh){
		refreshKanban();
	}
}


function activityStreamKanban(itemId, objectId,objectClass,placeholder) {
  var param="&itemId=" + itemId +"&objectId=" + objectId + "&objectClass=" + objectClass;
  var callBack=function(){
    dijit.byId("noteStreamKanban").set("placeholder", placeholder);
  };
  loadDialog('dialogKanbanGetObjectStream',callBack,true,param,true,true,'titleStream');
}

var saveNoteStreamKanbanTimeout=null;
function saveNoteStreamKanban(event) {
  var key=event.keyCode;
  if (key == 13 && !event.shiftKey) {
    var noteEditor=dijit.byId("noteStreamKanban");
    var noteEditorContent=noteEditor.get("value");
    if (noteEditorContent.trim() == "") {
      noteEditor.focus();
      return;
    }
    var callBack=function() {
	  dojo.byId('noteStreamKanban').value = null;
	  var itemId = dojo.byId('itemId').value;
	  var noteBadge = dojo.byId('noteBadge_'+itemId);
	  var countNoteBadge = dojo.byId('countNoteItem').value;
	  noteBadge.innerHTML = countNoteBadge;
	  var margin=(countNoteBadge>9)?'-10':'-7';
	  noteBadge.parentNode.style.marginLeft = margin+'px';
      dojo.byId("resultKanbanStreamDiv").style.display="block";
      if (saveNoteStreamKanbanTimeout) clearTimeout(saveNoteStreamKanbanTimeout);
      saveNoteStreamKanbanTimeout=setTimeout('dojo.byId("resultKanbanStreamDiv").style.display="none";',3000);
    };
    loadContent("../tool/saveNoteStreamKanban.php","activityStreamCenterKanban","noteFormStreamKanban",false,null,null,null,callBack);
    event.preventDefault();
  }
}

function sendChangeKanban(node, source, target) {
	var itemID = node.id;
	var objectId=node.attributes.refid.value;
	var objectClass=node.attributes.reftype.value;
	var columnType=source.columntype;
	var oldColumn=node.attributes.fromc.value;
	var newColumn=target.columntarget;
	var idKanban = dojo.byId('idKanban').value;
    showWait();
  	dojo.xhrGet({
	    url:"../tool/kanbanUpdate.php?objectId=" + objectId + "&objectClass=" + objectClass + "&itemID=" + itemID + "&oldColumn=" + oldColumn + "&newColumn=" + newColumn + "&columnType=" + columnType + "&idKanban=" + idKanban +addTokenIndexToUrl(),
	    load:function(data) {
      if (data.indexOf('messageError/split/') != -1) {
		refreshKanban(oldColumn, newColumn);
        showAlert(data.split('messageError/split/')[1],null);
      } else if (data.indexOf('needGlobalRefresh') != -1) {
	  	refreshGlobalKanban();
	  } else if(data){
        functionCallback=function() {
          hideWait();
        };
		if ((data.indexOf('needResult') != -1 && typeof dojo.byId("kanbanResultEditorType") != 'undefined')
            || ((data.indexOf('kanbanDescription') != -1 || data.indexOf('description') != -1) && typeof dojo.byId("descriptionEditorType") != 'undefined')) functionCallback=function() {
          var editorTypeResult=null;
          if (dojo.byId("kanbanResultEditorType") && typeof dojo.byId("kanbanResultEditorType") != 'undefined') editorTypeResult=dojo.byId("kanbanResultEditorType").value;
          if (editorTypeResult == "CK") { // CKeditor type
            ckEditorReplaceEditor("kanbanResult",999);
          } else if (dijit.byId("liveMeetingResult") && dijit.byId("kanbanResult")) { // Dojo
                                                                                      // type
                                                                                      // editor
            dijit.byId("kanbanResult").set("class","input");
          }
          var editorTypeDescription=null;
          if (dojo.byId("descriptionEditorType") && typeof dojo.byId("descriptionEditorType") != 'undefined') editorTypeDescription=dojo.byId("descriptionEditorType").value;
          if (editorTypeDescription == "CK") { // CKeditor type
            if (dojo.byId("kanbanDescription")) ckEditorReplaceEditor("kanbanDescription",999);
            else ckEditorReplaceEditor("description",999);
          } else if (dijit.byId("liveMeetingResult") && dijit.byId("kanbanDescription")) { // Dojo
                                                                                      // type
                                                                                      // editor
            dijit.byId("kanbanDescription").set("class","input");
          } else if (dijit.byId("liveMeetingResult") && dijit.byId("description")) { // Dojo
            // type
            // editor
          dijit.byId("description").set("class","input");
          }
        };
        loadDialog('dialogKanbanUpdate',functionCallback,true,data + "&typeDynamic=update",true,false);
      } else {
		refreshKanban(oldColumn, newColumn, itemID);
		var oldColumnObj = kbn.getKanbanColumnByID(oldColumn);
		kbn.setKanbanColumnItemCount(oldColumn);
		 if (dojo.byId(oldColumnObj.getColumnBadgeName())){
			dojo.byId(oldColumnObj.getColumnBadgeName()).innerHTML = oldColumnObj.getItemCount();
		 }
		 kbn.setKanbanColumnWorksValue(oldColumn);
		 if(dojo.byId(oldColumnObj.getColumnPlannedWorksName()) && dojo.byId(oldColumnObj.getColumnRealWorksName()) && dojo.byId(oldColumnObj.getColumnLeftWorksName())){
			dojo.byId(oldColumnObj.getColumnPlannedWorksName()).innerHTML = oldColumnObj.getPlannedWorks(true);
			dojo.byId(oldColumnObj.getColumnRealWorksName()).innerHTML = oldColumnObj.getRealWorks(true);
			dojo.byId(oldColumnObj.getColumnLeftWorksName()).innerHTML = oldColumnObj.getLeftWorks(true);
		 }
      }
    },
    error:function(data) {
		refreshKanban(oldColumn, newColumn);
	    showError(data);
	    hideWait();
    }
  });
}

function sendChangeKanbanMono(itemID, objectId, objectClass, oldColumn, newColumn) {
	var idKanban = dojo.byId('idKanban').value;
	var columnType = dojo.byId('typeKanban').value;
    showWait();
  	dojo.xhrGet({
	    url:"../tool/kanbanUpdate.php?objectId=" + objectId + "&objectClass=" + objectClass + "&itemID=" + itemID + "&oldColumn=" + oldColumn + "&newColumn=" + newColumn + "&columnType=" + columnType + "&idKanban=" + idKanban +addTokenIndexToUrl(),
	    load:function(data) {
      if (data.indexOf('messageError/split/') != -1) {
		refreshKanban(oldColumn, newColumn);
        showAlert(data.split('messageError/split/')[1],null);
      } else if (data.indexOf('needGlobalRefresh') != -1) {
	  	refreshGlobalKanban();
	  } else if(data){
        functionCallback=function() {
          hideWait();
        };
		if ((data.indexOf('needResult') != -1 && typeof dojo.byId("kanbanResultEditorType") != 'undefined')
            || ((data.indexOf('kanbanDescription') != -1 || data.indexOf('description') != -1) && typeof dojo.byId("descriptionEditorType") != 'undefined')) functionCallback=function() {
          var editorTypeResult=null;
          if (dojo.byId("kanbanResultEditorType") && typeof dojo.byId("kanbanResultEditorType") != 'undefined') editorTypeResult=dojo.byId("kanbanResultEditorType").value;
          if (editorTypeResult == "CK") { // CKeditor type
            ckEditorReplaceEditor("kanbanResult",999);
          } else if (dijit.byId("liveMeetingResult") && dijit.byId("kanbanResult")) { // Dojo
                                                                                      // type
                                                                                      // editor
            dijit.byId("kanbanResult").set("class","input");
          }
          var editorTypeDescription=null;
          if (dojo.byId("descriptionEditorType") && typeof dojo.byId("descriptionEditorType") != 'undefined') editorTypeDescription=dojo.byId("descriptionEditorType").value;
          if (editorTypeDescription == "CK") { // CKeditor type
            if (dojo.byId("kanbanDescription")) ckEditorReplaceEditor("kanbanDescription",999);
            else ckEditorReplaceEditor("description",999);
          } else if (dijit.byId("liveMeetingResult") && dijit.byId("kanbanDescription")) { // Dojo
                                                                                      // type
                                                                                      // editor
            dijit.byId("kanbanDescription").set("class","input");
          } else if (dijit.byId("liveMeetingResult") && dijit.byId("description")) { // Dojo
            // type
            // editor
          dijit.byId("description").set("class","input");
          }
        };
        loadDialog('dialogKanbanUpdate',functionCallback,true,data + "&typeDynamic=update",true,false);
      } else {
		refreshKanban(oldColumn, newColumn, itemID);
		var oldColumnObj = kbn.getKanbanColumnByID(oldColumn);
		kbn.setKanbanColumnItemCount(oldColumn);
		 if (dojo.byId(oldColumnObj.getColumnBadgeName())){
			dojo.byId(oldColumnObj.getColumnBadgeName()).innerHTML = oldColumnObj.getItemCount();
		 }
		 kbn.setKanbanColumnWorksValue(oldColumn);
		 if(dojo.byId(oldColumnObj.getColumnPlannedWorksName()) && dojo.byId(oldColumnObj.getColumnRealWorksName()) && dojo.byId(oldColumnObj.getColumnLeftWorksName())){
			dojo.byId(oldColumnObj.getColumnPlannedWorksName()).innerHTML = oldColumnObj.getPlannedWorks(true);
			dojo.byId(oldColumnObj.getColumnRealWorksName()).innerHTML = oldColumnObj.getRealWorks(true);
			dojo.byId(oldColumnObj.getColumnLeftWorksName()).innerHTML = oldColumnObj.getLeftWorks(true);
		 }
      }
    },
    error:function(data) {
		refreshKanban(oldColumn, newColumn);
	    showError(data);
	    hideWait();
    }
  });
}

function saveKanbanResult(oldColumn, newColumn, itemID, mandatoryNoteAlreadyChecked) {
  if (!mandatoryNoteAlreadyChecked && dojo.byId('columnType') && dojo.byId('columnType').value=='Status') {
    var objectClass=dojo.byId('objectClass').value;
    var objectId=dojo.byId('objectId').value;
    checkMandatoryNoteOnStatusChange(objectClass, objectId, newColumn, function() {
      openMandatoryNoteOnStatusChange(function() { saveKanbanResult(oldColumn, newColumn, itemID, true); });
    }, function() { saveKanbanResult(oldColumn, newColumn, itemID, true); });
    return;
  }
  showWait();
  tmpCkEditor='';
  if (typeof CKEDITOR.instances.kanbanResult != 'undefined') {
    CKEDITOR.instances.kanbanResult.updateElement();
    tmpCkEditor=CKEDITOR.instances.kanbanResult.document.getBody().getText();
  }
  tmpCkEditorKanbanDescription='';
  if (typeof CKEDITOR.instances.kanbanDescription != 'undefined') {
    CKEDITOR.instances.kanbanDescription.updateElement();
    tmpCkEditorKanbanDescription=CKEDITOR.instances.kanbanDescription.document.getBody().getText();
  }
  var extraRequired=dojo.byId('extraRequiredFields').value.split(',');
  var extraRequiredVal=true;
  if (extraRequired && extraRequired[0] != '') {
    extraRequired.forEach(function(item) {
      var field=dojo.byId(item);
      if (dijit.byId(item) == 'undefined') {
        extraRequiredVal=false;
      } else if (field && field.value.trim() == '') {
        extraRequiredVal=false;
      } else if (field && field.value == 0) {
        extraRequiredVal=false;
      }
    });
  }
  var idKanban = dojo.byId('idKanban').value;
  var form=dijit.byId('kanbanResultForm');
  if (!form.validate()) {
    showAlert(i18n("alertInvalidForm"));
  } else {
    if (extraRequiredVal
		&& ((typeof dijit.byId('kanbanResourceList') != 'undefined' && dijit.byId('kanbanResourceList').get('value').trim() != '') || typeof dijit.byId('kanbanResourceList') == 'undefined')
        && ((typeof CKEDITOR.instances.kanbanResult == 'undefined' || (typeof CKEDITOR.instances.kanbanResult != 'undefined' && tmpCkEditor.trim() != '')) && ((typeof dijit.byId('kanbanResult') != 'undefined' && dijit
            .byId('kanbanResult').get('value').trim() != '') || typeof dijit.byId('kanbanResult') == 'undefined'))
        && ((typeof CKEDITOR.instances.kanbanDescription == 'undefined' || (typeof CKEDITOR.instances.kanbanDescription != 'undefined' && tmpCkEditorKanbanDescription.trim() != '')) && ((typeof dijit
            .byId('kanbanDescription') != 'undefined' && dijit.byId('kanbanDescription').get('value').trim() != '') || typeof dijit.byId('kanbanDescription') == 'undefined'))
        && ((typeof dijit.byId('kanbanResolutionList') != 'undefined' && dijit.byId('kanbanResolutionList').get('value').trim() != '') || typeof dijit.byId('kanbanResolutionList') == 'undefined')) {
      dojo.xhrPost({
        url:"../tool/kanbanUpdate.php?idKanban=" + idKanban +addTokenIndexToUrl(),
        form:"kanbanResultForm",
        handleAs:"text",
        load:function(data,args) {
          formChangeInProgress=false;
          dijit.byId('dialogKanbanUpdate').hide();
          if (data.indexOf('messageError/split/') != -1) {
			 hideWait();
			 refreshKanban(oldColumn, newColumn);
	         showAlert(data.split('messageError/split/')[1],null);
          } else {
			 refreshKanban(oldColumn, newColumn, itemID);
			 hideWait();
          }
        },
        error:function() {
			refreshKanban(oldColumn, newColumn);
          	hideWait();
        }
      });
    } else {
      var finalMessage='';

	  if ((typeof dijit.byId('kanbanResourceList') != 'undefined' && dijit.byId('kanbanResourceList').get('value').trim() == '')) {
         finalMessage+=i18n('messageMandatory',[i18n('colMandatoryResourceOnHandled')]);
       }
       valCk='';
       if (typeof CKEDITOR.instances.kanbanResult != 'undefined') valCk=CKEDITOR.instances.kanbanResult.getData();
       if (!((typeof CKEDITOR.instances.kanbanResult == 'undefined' || (typeof CKEDITOR.instances.kanbanResult != 'undefined' && tmpCkEditor.trim() != '')) && ((typeof dijit.byId('kanbanResult') != 'undefined' && dijit
           .byId('kanbanResult').get('value').trim() != '') || typeof dijit.byId('kanbanResult') == 'undefined'))) {
         if (finalMessage != '') finalMessage+='<br/>';
         finalMessage+=i18n('messageMandatory',[i18n('colMandatoryResultOnDone')]);
       }
      valCk='';
	  if ((typeof dijit.byId('kanbanResolutionList') != 'undefined' && dijit.byId('kanbanResolutionList').get('value').trim() == '')) {
	      if (finalMessage != '') finalMessage+='<br/>';
	      finalMessage+=i18n('messageMandatory',[i18n('colIdResolution')]);
	    }
      if (!extraRequiredVal) {
        if (finalMessage != '') finalMessage+='<br/>';
        extraRequired.forEach(function(item) {
          var field=dojo.byId(item);
          if (field && (field.value.trim() == '' || field.value == 0)) {
            var name=item[0].toUpperCase() + item.substring(1);
            finalMessage+=i18n('messageMandatory',[i18n('col' + name)]);
            finalMessage+='<br/>';
          }
        });
      }
      if (finalMessage != ''){
		refreshKanban(oldColumn, newColumn);
		showAlert(finalMessage);
	  } 
      hideWait();
    }
  }
}

function delKanban(idKanban, i18nF, idFrom) {
  if (dojo.byId('objectClass')) {
    var currentScreen=(dojo.byId('objectClassManual')) ? dojo.byId('objectClassManual').value : 'Object';
  }
  if (typeof idFrom == 'undefined') idFrom='';
  showConfirm(i18nF,function() {
    showWait();
    addUrl='';
    if (idFrom != '') {
      addUrl='&idFrom=' + idFrom;
    }
    dojo.xhrGet({
      url:"../tool/kanbanDel.php?idKanban=" + idKanban + addUrl +addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data,args) {
        formChangeInProgress=false;
		  if(currentScreen == "LiveMeeting"){
			loadContent("../view/kanbanViewMain.php?idKanban=" + data,"divBottom");
		  }else{
          	loadContent("../view/kanbanViewMain.php?idKanban=" + data,"centerDiv");
		  }
      },
      error:function() {
        hideWait();
      }
    });
  });
}

function kanbanShared(idKanban) {
  if (dojo.byId('objectClass')) {
	var currentScreen=(dojo.byId('objectClassManual')) ? dojo.byId('objectClassManual').value : 'Object';
  }
  showWait();
  dojo.xhrGet({
    url:"../tool/kanbanShare.php?idKanban=" + idKanban +addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data,args) {
	  if( currentScreen == "LiveMeeting"){
        loadContent("../view/kanbanViewMain.php?idKanban=" + data,"divBottom");
	  }else{
		loadContent("../view/kanbanViewMain.php?idKanban=" + data,"centerDiv");
	  }
    },
    error:function() {
      hideWait();
    }
  });
}

function kanbanGoToKan(id) {
   if (dojo.byId('objectClass')) {
	var currentScreen=(dojo.byId('objectClassManual')) ? dojo.byId('objectClassManual').value : 'Object';
  }
  lastIdKanban=id;
  showWait();
  if(currentScreen == "LiveMeeting"){
  	loadContent("../view/kanbanViewMain.php?idKanban=" + lastIdKanban,"divBottom");
  }else{
	loadContent("../view/kanbanViewMain.php?idKanban=" + lastIdKanban,"centerDiv");
  }
}

function plgAddKanban() {
  var name=dijit.byId("kanbanName").get("value");
  var type=dijit.byId("kanbanTypeList").get("value");
  var shared=dijit.byId("kanbanShared").get("value");
  if (dojo.byId('objectClass')) {
    var currentScreen=(dojo.byId('objectClassManual')) ? dojo.byId('objectClassManual').value : 'Object';
  }
  
  if (name.trim() != '' && type != '') {
    showWait();
    dojo.xhrPost({
      url:"../tool/kanbanAdd.php?type=" + type + "&shared=" + shared +addTokenIndexToUrl(),
      form:"kanbanResultForm",
      handleAs:"text",
      load:function(data,args) {
        formChangeInProgress=false;
        if (data.indexOf('class="messageERROR"') > 0) {
          showError(data);
        } else {
		  if(currentScreen == "LiveMeeting"){
	        loadContent("../view/kanbanViewMain.php?idKanban=" + data,"divBottom");
		  }else{
			loadContent("../view/kanbanViewMain.php?idKanban=" + data,"centerDiv");
		  }
        }
        dijit.byId('dialogKanbanUpdate').hide();
      },
      error:function() {
        hideWait();
      }
    });
  } else {
    if (type == '' && name.trim() == '') {
      showAlert(i18n('messageMandatory',[i18n('Type')]) + '</br>' + i18n('messageMandatory',[i18n('colName')]));
    } else if (type == '') {
      showAlert(i18n('messageMandatory',[i18n('Type')]));
    } else if (name.trim() == '') {
      showAlert(i18n('messageMandatory',[i18n('colName')]));
    }
  }
}

function copyKanban(idKanban) {
  if (dojo.byId('objectClass')) {
	var currentScreen=(dojo.byId('objectClassManual')) ? dojo.byId('objectClassManual').value : 'Object';
  }
  showWait();
  dojo.xhrGet({
    url:"../tool/kanbanCopy.php?idKanban=" + idKanban +addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data,args) {
	  if( currentScreen == "LiveMeeting"){
        loadContent("../view/kanbanViewMain.php?idKanban=" + idKanban,"divBottom");
	  }else{
		loadContent("../view/kanbanViewMain.php?idKanban=" + idKanban,"centerDiv");
	  }
      // hideWait();
    },
    error:function() {
      hideWait();
    }
  });
}

function editKanban(idKanban) {
  loadDialog('dialogKanbanUpdate',function() {
    kanbanFindTitle('editKanban');
  },true,"&idKanban=" + idKanban + "&typeDynamic=editKanban",true,false);
}

function saveEditKanban(idKanban) {
  if (dojo.byId('objectClass')) {
    var currentScreen=(dojo.byId('objectClassManual')) ? dojo.byId('objectClassManual').value : 'Object';
  }
  var name="";
  if (typeof (dijit.byId("kanbanName")) != 'undefined') name=dijit.byId("kanbanName").get("value");
  if (name.trim() != '') {
    showWait();
    dojo.xhrPost({
      url:"../tool/kanbanEditName.php?idKanban=" + idKanban +addTokenIndexToUrl(),
      form:"kanbanResultForm",
      handleAs:"text",
      load:function(data,args) {
        formChangeInProgress=false;
		if( currentScreen == "LiveMeeting" ){
        	loadContent("../view/kanbanViewMain.php?idKanban=" + idKanban,"divBottom");
		}else{
			loadContent("../view/kanbanViewMain.php?idKanban=" + idKanban,"centerDiv");
		}
        dijit.byId('dialogKanbanUpdate').hide();
        // hideWait();
      },
      error:function() {
        hideWait();
      }
    });
  }
}

function kanbanFindTitle(type) {
  title=i18n('dialogKanbanUpdate');
  if (type == "addKanban") {
    title=i18n('kanbanAdd');
  } else if (type == "addColumnKanban") {
    title=i18n('kanbanAddColumn');
  } else if (type == "editColumnKanban") {
    title=i18n('kanbanColumnEdit');
  } else if (type == "update") {
    title=i18n('kanbanTicketEdit');
  } else if (type == "kanbanEdit") {
    title=i18n('kanbanEdit');
  }
  dijit.byId('dialogKanbanUpdate').set('title',title);
}

function kanbanRefreshListType(listType,destination,param) { // , paramVal,
                                                              // selected,
                                                              // required
  var urlList='../tool/kanbanJsonList.php?listType=' + listType;
  urlList+='&critField=' + param;
  var datastore=new dojo.data.ItemFileReadStore({
    url:urlList + addTokenIndexToUrl(urlList)
  });
  var store=new dojo.store.DataStore({
    store:datastore
  });

  var mySelect=dijit.byId('kanbanTypeList');

  mySelect.set({
    labelAttr:'name',
    store:store,
    sortByLabel:false
  });
  store.query({
    id:"*"
  });

}

function plgEditColumnKanban(idKanban,idFrom,isStatut,typeD) {

  require(["dojo/parser","dijit/form/CheckBox"]);

  var name="";
  if (typeof (dijit.byId("kanbanName")) != 'undefined') name=dijit.byId("kanbanName").get("value");
  var types=[];

  var allStats=document.querySelectorAll('input[name=checkboxKanbanColumn]');
  allStats.forEach(function(element) {
    if (element.checked) {
      types.push(element.value);
    }
  });
  sendTypes=types.join();

  dojo.xhrPost({
    url:"../tool/kanbanColumnEdit.php?name=" + name + "&types=" + sendTypes + "&idKanban=" + idKanban + '&idFrom=' + idFrom +addTokenIndexToUrl(),
    form:"kanbanResultForm",
    handleAs:"text",
    load:function(data,args) {
      formChangeInProgress=false;
      refreshGlobalKanban();
      dijit.byId('dialogKanbanUpdate').hide();
      hideWait();
    },
    error:function() {
      hideWait();
    }
  });

}

function restoreKanbanScroll() {
  if (!window.kanbanScrollToRestore) return;
  var data = window.kanbanScrollToRestore;

  // Scroll global horizontal
  var kanbanContainer = dojo.byId('divKanbanContainer');
  if (kanbanContainer && typeof data.horizontal === 'number') {
    kanbanContainer.scrollLeft = data.horizontal;
  }

  // Scroll vertical for each column
  for (var colId in data.verticals) {
    if (!data.verticals.hasOwnProperty(colId)) continue;
    var col = dojo.byId(colId);
    if (col && typeof data.verticals[colId] === 'number') {
      col.scrollTop = data.verticals[colId];
    }
  }
}

function kanbanRefreshSelection() {
  dojo.xhrGet({
    url:"../tool/kanbanRefreshSelection.php"+addTokenIndexToUrl('?'),
    handleAs:"text",
    load:function(data,args) {
      var idKanban = dojo.byId('idKanban').value;
      if(data == 'noKanban'){
        loadDialog('dialogKanbanUpdate', function(){kanbanFindTitle('addKanban');}, true, '&typeDynamic=addKanban', true, false);
      }else if(idKanban == -1){
        if(data.indexOf('mineKanban') != -1){
          idKanban = data.split('_')[1];
          kanbanGoToKan(idKanban);
        }else if(data.indexOf('sharedKanban') != -1){
          idKanban = data.split('_')[1];
          kanbanGoToKan(idKanban);
        }else if(data == 'allKanban'){
          if(dijit.byId('kanbanListSelect'))dijit.byId('kanbanListSelect').openDropDown();
        }
      }
	  if (window.needRestoreKanbanScroll) {
	    window.needRestoreKanbanScroll = false;
	    restoreKanbanScroll();
	  }
    },
    error:function() {
    }
  });
}

function kanbanSaveDataSession(type,value,idSearch) {
  // #2887
  saveDataToSession("kanban" + type,(idSearch == -1 ? value : idSearch));
  /*
   * dojo.xhrPost({ url :
   * "../tool/saveDataToSession.php?idData=kanban"+type+"&value=" +
   * (idSearch==-1 ? value : idSearch), handleAs : "text", load : function(data,
   * args) { } });
   */
}

//==================================================================
//Kanban ContextMenu
//==================================================================

function deleteOnKanbanFromContextMenu(refId, refType){
  fromContextMenu = true;
  if (refType=='Replan' || refType=='Construction' || refType=='Fixed') refType='Project';
  var action=function(){
    var resetContextMenuVariable=function(){
      if(!(dojo.byId('confirmControl') && dojo.byId('confirmControl').value=='delete')){
        fromContextMenu=false;
      }
      refreshKanban();
    }
    dojo.byId('objectClass').value = refType;
    dojo.byId('objectId').value = refId;
    loadContent('../tool/deleteObject.php?objectId=' + refId
        + '&objectClassName='+refType+'&fromContextMenu='+fromContextMenu, 'resultDivMain', 'objectForm', true, null, null, null, resetContextMenuVariable);
  };
  showConfirm(i18n('confirmDelete', new Array(refType, refId)) ,action);
}

var hideKanbanContextMenuTimeout = null;
function hideKanbanContextMenu(delay) {
  var contextMenu = dijit.byId('kanbanContextMenu');
  var contextMenuDiv = dojo.byId('dialogKanbanContextMenu');
  if (contextMenu) {
    var callback = function () {
      if (dojo.byId('addFromKanban')) dojo.byId('addFromKanban').setAttribute('onClick', '');
	  if (dojo.byId('editFromKanban')) dojo.byId('editFromKanban').setAttribute('onClick', '');
      if (dojo.byId('copyFromKanban')) dojo.byId('copyFromKanban').setAttribute('onClick', '');
      if (dojo.byId('removeFromKanban')) dojo.byId('removeFromKanban').setAttribute('onClick', '');
      if (dojo.byId('printFromKanban')) dojo.byId('printFromKanban').setAttribute('onClick', '');
      if (dojo.byId('printPdfFromKanban')) dojo.byId('printPdfFromKanban').setAttribute('onClick', '');
      if (dojo.byId('addCommentFromKanban')) dojo.byId('addCommentFromKanban').setAttribute('onClick', '');
      if (dojo.byId('mailFromKanban')) dojo.byId('mailFromKanban').setAttribute('onClick', '');
      if (dojo.byId('searchFromKanban')) dojo.byId('searchFromKanban').setAttribute('onClick', '');
      if (dojo.byId('GotoFromKanban')) dojo.byId('GotoFromKanban').setAttribute('onClick', '');
      contextMenu.closeDropDown();
      contextMenuDiv.blur();
    };
    hideKanbanContextMenuTimeout = setTimeout(callback, delay);
  }
}

function openKanbanContextMenu(vID, refId, refType, idProject, type){
  var contextMenu = dijit.byId('kanbanContextMenu');
  var contextMenuDiv = dojo.byId('dialogKanbanContextMenu');
  event.preventDefault();
  if(event.stopPropagation)event.stopPropagation();
  // Restore rows that may have been hidden by column context menu
  ['editFromKanban','copyFromKanban','addCommentFromKanban','removeFromKanban','printFromKanban','printPdfFromKanban','mailFromKanban','searchFromKanban','gotoFromKanban'].forEach(function(rowId){
    var row = dojo.byId(rowId);
    if(row) row.style.display = '';
  });
  var addLabel = dojo.byId('addFromKanban_label');
  if(addLabel) addLabel.innerHTML = i18n('contextMenuButtonNew');
  var divKanbanContainer = dojo.byId('divKanbanContainer');
  var scrollX = divKanbanContainer.scrollLeft;
  var mousePosition = {
      x: event.clientX + scrollX, 
      y: event.clientY -150
    };
  if(dojo.byId('isMenuLeftOpen').value == 'true'){
    mousePosition.x -= 250;
  }
  dojo.query('.contextMenuClass').forEach(function(node){
    node.style.cssText='position:absolute;width:0px;height:0px;overflow:hidden;top:'+mousePosition.y+'px;left:'+mousePosition.x+'px';
  });
  if (refType=='Replan' || refType=='Construction' || refType=='Fixed') refType='Project';
  if(dojo.byId('contextMenuRefId'))dojo.byId('contextMenuRefId').value = refId;
  if(dojo.byId('contextMenuRefType'))dojo.byId('contextMenuRefType').value = refType;
  if(dojo.byId('objectClassRow'))dojo.byId('objectClassRow').value = refType;
  if(dojo.byId('objectIdRow'))dojo.byId('objectIdRow').value = refId;
  
  var currentClass = null;
  var currentId = null;
  
  if(dojo.byId('addFromKanban')){
    dojo.byId('addFromKanban').style.display = '';
    dojo.byId('addFromKanban').setAttribute('onClick', 'addItemFromKanban(\''+refType+'\')');
  }
  if(dojo.byId('copyFromKanban')){
    dojo.byId('copyFromKanban').style.display = '';
    dojo.byId('copyFromKanban').setAttribute('onClick', 'copyObjectFromContextMenu(\''+refId+'\', \''+refType+'\', null, '+idProject+', true)');
  }
  if(dojo.byId('editFromKanban')){
    dojo.byId('editFromKanban').style.display = '';
    dojo.byId('editFromKanban').setAttribute('onClick', 'showDetail(\'refreshActionAddItemKanban\',1,\''+refType+'\',false,'+refId+')');
  }
  if(dojo.byId('addCommentFromKanban')){
    dojo.byId('addCommentFromKanban').style.display = '';
    dojo.byId('addCommentFromKanban').setAttribute('onClick', 'activityStreamKanban(\''+vID+'\', '+refId+', \''+refType+'\', \''+i18n('textareaEnterText')+'\');');
  }
  if(dojo.byId('removeFromKanban')){
    dojo.byId('removeFromKanban').style.display = '';
    dojo.byId('removeFromKanban').setAttribute('onClick', 'deleteOnKanbanFromContextMenu(\''+refId+'\', \''+refType+'\', true)');
  } 
  if(dojo.byId('printFromKanban')){
    dojo.byId('printFromKanban').style.display = '';
    dojo.byId('printFromKanban').setAttribute('onClick', 'showPrint(\'objectDetail.php\', \'contextMenu\', null, null, \'P\')');
  }   
  if(dojo.byId('printPdfFromKanban')){
    dojo.byId('printPdfFromKanban').style.display = '';
    dojo.byId('printPdfFromKanban').setAttribute('onClick', 'showPrint(\'objectDetail.php\', \'contextMenu\', null, \'pdf\', \'P\')');
  }
  if(dojo.byId('mailFromKanban')){
    dojo.byId('mailFromKanban').style.display = '';
    dojo.byId('mailFromKanban').setAttribute('onClick', 'showMailOptions()');
  }
  if(dojo.byId('searchFromKanban')){
    dojo.byId('searchFromKanban').style.display = '';
    dojo.byId('searchFromKanban').setAttribute('onClick', 'noRefresh=true;gotoElement(\''+refType+'\', \''+refId+'\' ,false, false,\'planning\',false)');
  }
  if(dojo.byId('gotoFromKanban')){
    dojo.byId('gotoFromKanban_label').innerHTML = i18n('kanbanGotoItem', new Array(refId,refId));
    dojo.byId('gotoFromKanban').style.display = '';
    dojo.byId('gotoFromKanban').setAttribute('onClick', 'gotoElement(\''+refType+'\','+refId+', true)');
  }
  
  contextMenu.openDropDown();
  contextMenuDiv.focus();
}


// =================== KANBAN TOOLTIP ======================================= //
var KanbanTooltip = (function () {
  var _cfg = {
    root: document,
    showDelay: 0,
    hideDelay: 200,
    offsetX: -5,
    offsetY: 8,
    zIndex: 99999
  };

  var _tooltipNode = null;
  var _hideTimer = null;
  var _showTimer = null;
  var _currentTrigger = null;

  function init(options) {
    if (options) {
      for (var k in options) _cfg[k] = options[k];
    }
    if (!_tooltipNode) _tooltipNode = _createTooltipNode();
    _installEvents();
  }

  function _installEvents() {
    var root = _cfg.root || document;
    root.addEventListener("mouseover", _onMouseOver, true);
    root.addEventListener("mouseout", _onMouseOut, true);
    window.addEventListener("scroll", function () { hide(0); }, true);
    window.addEventListener("resize", function () { hide(0); }, true);
  }

  function _onMouseOver(e) {
    var trigger = _closestTrigger(e.target);
    if (!trigger) return;
    if (_currentTrigger === trigger) return;
    _currentTrigger = trigger;
    clearTimeout(_showTimer);
    _showTimer = setTimeout(function () {
      show(trigger);
    }, _cfg.showDelay);
  }

  function _onMouseOut(e) {
    var trigger = _closestTrigger(e.target);
    if (!trigger) return;
    var related = e.relatedTarget;
    if (related && trigger.contains(related)) return;
    hide(_cfg.hideDelay);
    _currentTrigger = null;
  }

  function _closestTrigger(node) {
    while (node && node !== document) {
      if (node.getAttribute && node.getAttribute("data-ktip") === "1") {
        return node;
      }
      node = node.parentNode;
    }
    return null;
  }

  function show(trigger) {
    if (!_tooltipNode) _tooltipNode = _createTooltipNode();
    clearTimeout(_hideTimer);
    var pos = trigger.getAttribute("data-ktip-pos") || "bottom";
   _setContentFromTrigger(trigger);
    _tooltipNode.style.display = "block";
    _tooltipNode.style.zIndex = String(_cfg.zIndex);
    _position(trigger, pos);
  }

  function hide(delay) {
    clearTimeout(_showTimer);
    clearTimeout(_hideTimer);

    _hideTimer = setTimeout(function () {
      if (_tooltipNode) _tooltipNode.style.display = "none";
    }, delay || 0);
  }

  function _setContentFromTrigger(trigger) {
    var text = trigger.getAttribute("data-ktip-text") || "";
    var mode = trigger.getAttribute("data-ktip-mode") || "";
    var left = _tooltipNode.querySelector(".ktipLeft");
    var label = _tooltipNode.querySelector(".ktipText");

    left.innerHTML = "";
	var allowHtml = trigger.getAttribute("data-ktip-html") === "1";
	if (allowHtml) {
	  label.innerHTML = text;
	} else {
	  label.textContent = text;
	}
	
    if (mode === "user") {
      var userMode = trigger.getAttribute("data-ktip-user-mode");
      if (userMode === "img") {
        var src = trigger.getAttribute("data-ktip-user-src") || "";
        left.innerHTML =
          '<div class="ktipUserBox">' +
          '  <img class="ktipUserImg" src="'+src+'" />' +
          '</div>';
      } else {
        var initial = trigger.getAttribute("data-ktip-user-initial") || "";
        var bg = trigger.getAttribute("data-ktip-user-bg") || "#777";
        left.innerHTML =
          '<div class="ktipUserBox">' +
          '  <div class="ktipUserInitial" style="background:'+bg+'">'+
          (initial || "?") +
          '</div>' +
          '</div>';
      }
      return;
    }
	
    var iconClass = trigger.getAttribute("data-ktip-icon") || "";
    if (iconClass) {
      left.innerHTML = '<div class="ktipIcon '+iconClass+'"></div>';
    } else {
      left.innerHTML = '<div class="ktipIcon"></div>';
    }
  }

  function _position(trigger, pos) {
    var t = _tooltipNode;
    var r = trigger.getBoundingClientRect();

    var prevDisplay = t.style.display;
    var prevVis = t.style.visibility;

    t.style.display = "block";
    t.style.visibility = "hidden";

    var tw = t.offsetWidth;
    var th = t.offsetHeight;

    t.style.visibility = prevVis || "";
    t.style.display = prevDisplay || "block";

    var desired = (pos === "top") ? "top" : "bottom";

    // 2) Calculate a candidate position
    function computeCandidate(which) {
      var left = r.left + _cfg.offsetX;
      var top = (which === "top")
        ? (r.top - th - _cfg.offsetY)
        : (r.top + r.height + _cfg.offsetY);

      var minLeft = 8;
      var maxLeft = window.innerWidth - tw - 8;
      if (left < minLeft) left = minLeft;
      if (left > maxLeft) left = maxLeft;

      var overflowTop = Math.max(0, 8 - top);
      var overflowBottom = Math.max(0, (top + th + 8) - window.innerHeight);
      var overflow = overflowTop + overflowBottom;

      return { which: which, left: left, top: top, overflow: overflow };
    }

    // 3) We test both positions and choose the best one
    var candDesired = computeCandidate(desired);
    var candOther = computeCandidate(desired === "bottom" ? "top" : "bottom");

    var chosen = candDesired;
    if (candOther.overflow < candDesired.overflow) {
      chosen = candOther;
    }

    var finalTop = chosen.top;
    var minTop = 8;
    var maxTop = window.innerHeight - th - 8;
    if (finalTop < minTop) finalTop = minTop;
    if (finalTop > maxTop) finalTop = maxTop;

    t.style.left = chosen.left + "px";
    t.style.top = finalTop + "px";

    if (chosen.which === "top") {
      _setArrow("bottom"); // tooltip top -> arrow down
    } else {
      _setArrow("top");    // tooltip bottom -> arrow up
    }

    _alignArrowToTrigger(r, chosen.left);
  }
  
  function _alignArrowToTrigger(triggerRect, tooltipLeft) {
    var arrow = _tooltipNode.querySelector(".ktipArrow");
    if (!arrow) return;

    var triggerCenterX = triggerRect.left + (triggerRect.width / 2);
    var arrowX = triggerCenterX - tooltipLeft - 5; // 5 = mid arraow (10px)

    var minX = 10;
    var maxX = _tooltipNode.offsetWidth - 20;
    if (arrowX < minX) arrowX = minX;
    if (arrowX > maxX) arrowX = maxX;

    arrow.style.left = arrowX + "px";
  }

  function _setArrow(where) {
    var arrow = _tooltipNode.querySelector(".ktipArrow");
    if (!arrow) return;

    if (where === "top") {
      arrow.style.top = "-5px";
      arrow.style.bottom = "auto";
      arrow.style.transform = "rotate(45deg)";
    } else {
      arrow.style.bottom = "-5px";
      arrow.style.top = "auto";
      arrow.style.transform = "rotate(225deg)";
    }
  }

  function _createTooltipNode() {
    var node = document.createElement("div");
    node.id = "kanbanGlobalTooltip";
    node.className = "ktip dijitLikeTooltip";
    node.style.position = "fixed";
    node.style.display = "none";
    node.style.pointerEvents = "none";

	node.innerHTML =
	  '<div class="ktipArrow"></div>' +
	  '<div class="ktipRow">' +
	  '  <div class="ktipLeft"></div>' +
	  '  <div class="ktipText"></div>' +
	  '</div>';

    document.body.appendChild(node);
    return node;
  }

  return {
    init: init,
    show: show,
    hide: hide
  };
})();

//==================================================================
//Draw Kanban using jsKanban
//==================================================================

function drawKanban(onlyRefresh) {
showWait();
if (onlyRefresh==undefined) onlyRefresh=false;
var typeKanban = dojo.byId('typeKanban').value;
var classKanban = dojo.byId('classKanban').value;
// Only first display, refresh JSKanban object
if (!onlyRefresh) {
   kbn = new JSKanban.Kanban(typeKanban, classKanban);
}

jsonData = getJsonKanbanData();

//// Error in jsonData
if (jsonData.innerHTML.indexOf('{"identifier"') < 0 || jsonData.innerHTML.indexOf('{"identifier":"id", "items":[ ],"totalRows":"0"')>=0) {
   dojo.query('#divKanbanContainer .sectionBadge').forEach(function(node){
	node.innerHTML=0;
   });
   dojo.query('#divKanbanContainer .kanbanColumnBody').forEach(function(node){
   	node.innerHTML=null;
   });
   hideWait();
   return;
}

// Parse the jsonData and set Store values
  if (kbn && jsonData) {
   showWait();
   try {
     var store = eval('(' + jsonData.innerHTML + ')');
   } catch(e) {
     consoleTraceLog("ERROR Parsing jsonData in drawKanban()");
     consoleTraceLog(jsonData.innerHTML);
     hideWait();
     return;
   }
   kbn.clearRefreshKanbanColumn();
   var columns = store.items;
   // Treat all lines
   for (var i = 0; i < columns.length; i++) {
     var column = columns[i];
     var newKanbanColumn=new JSKanban.KanbanColumn(column);
	 if (dojo.byId(newKanbanColumn.getColumnName())){
		var colNode = dojo.byId(newKanbanColumn.getColumnName());
		if(newKanbanColumn.isHidden()){
			dojo.query('.dojoDndItem', colNode).forEach(function(n){
				if(n.parentNode) n.parentNode.removeChild(n);
			});
		}else{
			colNode.innerHTML = '';
		}
	 }
     if (onlyRefresh==true){
	   kbn.ReplaceKanbanColumn(newKanbanColumn);
       kbn.RefreshKanbanColumn(newKanbanColumn);
     }else{
       kbn.AddKanbanColumn(newKanbanColumn);
     }
	 kbn.setKanbanColumnItemCount(newKanbanColumn.getID());
	 if (dojo.byId(newKanbanColumn.getColumnBadgeName())){
		dojo.byId(newKanbanColumn.getColumnBadgeName()).innerHTML = newKanbanColumn.getItemCount();
	 }
	 kbn.setKanbanColumnWorksValue(newKanbanColumn.getID());
	 if(dojo.byId(newKanbanColumn.getColumnPlannedWorksName()) && dojo.byId(newKanbanColumn.getColumnRealWorksName()) && dojo.byId(newKanbanColumn.getColumnLeftWorksName())){
		dojo.byId(newKanbanColumn.getColumnPlannedWorksName()).innerHTML = newKanbanColumn.getPlannedWorks(true);
		dojo.byId(newKanbanColumn.getColumnRealWorksName()).innerHTML = newKanbanColumn.getRealWorks(true);
		dojo.byId(newKanbanColumn.getColumnLeftWorksName()).innerHTML = newKanbanColumn.getLeftWorks(true);
	 }
   }
   kbn.Draw(onlyRefresh);
   filterKanban();
  } else {
   return;
  }
}
