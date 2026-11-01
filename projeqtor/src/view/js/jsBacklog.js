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
/* BACKLOG OBJECT FUNCTION */
/* =============================================================================== */

var JSBacklog; if (!JSBacklog) JSBacklog = {};

JSBacklog.Backlog = function(pBacklogType){
	var vBacklogType	= pBacklogType;
	var vBacklogColumnList     = new Array();
	var vRefreshBacklogColumnList = new Array();
	var vBacklogContainer = 'productBacklogContainer';
	
	this.getBacklogType = function() { return vBacklogType; };
	this.setBacklogType = function(pBacklogType) { vBacklogType = pBacklogType; };
	this.getBacklogContainer = function(){
		if(vBacklogType == 'Status'){
			vBacklogContainer = 'sprintBacklogContainer';
		}
		return vBacklogContainer;
	};
	
	this.setBacklogColumnItemCount = function(vColumnID){
		var vColumnList = this.getBacklogColumnList();
	    for(var i = 0; i < vColumnList.length; i++) {
			if(vColumnList[i].getID() == vColumnID){
				var vItemList = vColumnList[i].getBacklogItemList();
				var itemCount = 0;
				for(var j = 0; j < vItemList.length; j++){
					if(!vItemList[j].getIsHidden())itemCount++;
				}
				vColumnList[i].setItemCount(itemCount);
			}
	    }
	}
	
	this.setBacklogColumnStoryPointAndBusinessValue = function(vColumnID){
		var vColumnList = this.getBacklogColumnList();
	    for(var i = 0; i < vColumnList.length; i++) {
			if(vColumnList[i].getID() == vColumnID){
				var vItemList = vColumnList[i].getBacklogItemList();
				var vStoryPoints = 0;
				var vBusinessValues = 0;
				for(var j = 0; j < vItemList.length; j++){
					if(!vItemList[j].getIsHidden() && vItemList[j].getClass() != 'Epic'){
						vStoryPoints += vItemList[j].getStoryPoints();
						vBusinessValues += vItemList[j].getBusinessValue();
					}
				}
				vColumnList[i].setStoryPoints(vStoryPoints);
				vColumnList[i].setBusinessValues(vBusinessValues);
			}
	    }
	}
	
	this.highlightItemFromEpic = function(ItemID, idEpic){
		if(!idEpic)return;
		if(vBacklogType == 'Status')return;
		var itemEpic = dojo.byId(ItemID);
		dojo.addClass(itemEpic, 'backlogHighlightItemFromEpic');
		var vColumnList = this.getBacklogColumnList();
	    for(var i = 0; i < vColumnList.length; i++) {
			var vItemList = vColumnList[i].getBacklogItemList();
			for(var j = 0; j < vItemList.length; j++){
				if(vItemList[j].getIdEpic() && vItemList[j].getIdEpic() == idEpic){
					var item = dojo.byId(vItemList[j].getID());
					dojo.addClass(item, 'backlogHighlightItemFromEpic');
				}	
			}
		}
	};
	
	this.highlightEpicFromItem = function(ItemID, idEpic){
		if(!idEpic)return;
		if(vBacklogType == 'Status')return;
		var epicItem = dojo.byId(ItemID);
		dojo.addClass(epicItem, 'backlogHighlightEpicFromItem');
		var vColumnList = this.getBacklogColumnList();
	    for(var i = 0; i < vColumnList.length; i++) {
			var vItemList = vColumnList[i].getBacklogItemList();
			for(var j = 0; j < vItemList.length; j++){
				if(vItemList[j].getClass() == 'Epic' && vItemList[j].getId() == idEpic){
					var item = dojo.byId(vItemList[j].getID());
					dojo.addClass(item, 'backlogHighlightEpicFromItem');
				}	
			}
		}
	};
	
	this.clearHighlightItemFromEpic = function(){
		dojo.query('.backlogHighlightItemFromEpic').forEach(function(node){
			dojo.removeClass(node, 'backlogHighlightItemFromEpic');
		});
	};
	
	this.clearHighlightEpicFromItem = function(){
		dojo.query('.backlogHighlightEpicFromItem').forEach(function(node){
			dojo.removeClass(node, 'backlogHighlightEpicFromItem');
		});
	};
	
	this.AddBacklogColumn = function(value) {
		vBacklogColumnList.push(value);
	};
	
	this.ReplaceBacklogColumn = function(value) {
	    var pId=value.getID();
	    var vList = this.getBacklogColumnList();
	    for(var i = 0; i < vList.length; i++) {
	      if(vList[i].getID()==pId){
	        vList[i]=value;
	        break;
	      }
	    }
	};
	
	this.RefreshBacklogColumn = function(value) {
	    vRefreshBacklogColumnList.push(value);
	};
	
	this.deleteItemFromBacklogColumn = function(pID){
		var vColumnList = this.getBacklogColumnList();
	    for(var i = 0; i < vColumnList.length; i++) {
			vColumnList[i].deleteBacklogItemFromList(pID);
	    }
	};
	
	this.getBacklogColumnList   = function(onlyRefresh) { 
		if(onlyRefresh==undefined)onlyRefresh=false;
		return (onlyRefresh)?vRefreshBacklogColumnList:vBacklogColumnList; 
	};
	
	this.clearRefreshBacklogColumn = function(){
		vRefreshBacklogColumnList = new Array();
	};
	
	this.getBacklogColumnArrayLocationByID = function(pId)  {
	    var vList = this.getBacklogColumnList();
	    for(var i = 0; i < vList.length; i++) {
	      if(vList[i].getID()==pId) {
	        return i;
	      }
	    }
	    return null;
	  };
	  this.getBacklogColumnByID = function(pId)  {
	    var vList = this.getBacklogColumnList();
	    for(var i = 0; i < vList.length; i++) {
	      if(vList[i].getID()==pId) {
	        return vList[i];
	      }
	    }
	    return null;
	  };
	  
	  this.getBacklogItemByIDFromColumn = function(pID){
		var vColumnList = this.getBacklogColumnList();
	    for(var i = 0; i < vColumnList.length; i++) {
			var item = vColumnList[i].getItemByID(pID);
			if(item)return item;
	    }
	    return null;
	  }
		
	  this.Draw = function(onlyRefresh){
		if(onlyRefresh==undefined)onlyRefresh=false;
		window.top.showWait();
		var vColumnList = this.getBacklogColumnList(onlyRefresh);
		if(vColumnList.length > 0){
			for(var i = 0; i < vColumnList.length; i++) {
				var columnHtmlItem = '';
				var itemList = vColumnList[i].getBacklogItemList();
				var hideStatus = (vColumnList[i].getHideStatus())?'display:none':'';
				var hideEpic = (vColumnList[i].getHideEpic())?'display:none':'';
				var hideSprint = (vColumnList[i].getHideSprint())?'display:none':'';
				var hideProduct = (vColumnList[i].getHideProduct())?'display:none':'';
				var hideType = (vColumnList[i].getHideType())?'display:none':'';
				var hideResponsible = (vColumnList[i].getHideResponsible())?'display:none':'';
				var hideScrumPriority = (vColumnList[i].getHideScrumPriority())?'display:none':'';
				var hideStoryPointsAndBusiness = (vColumnList[i].getHideStoryPointsAndBusiness())?'display:none':'';
				var fullWidthElement = vColumnList[i].getFullWidthElement();
				var hideResponsibleName = (!fullWidthElement)?'display:none':'';
				hideResponsibleName = (hideResponsible)?hideResponsible:hideResponsibleName;
				var hideProjectName = (vColumnList[i].getHideProjectName())?'display:none':'';
				hideProjectName = (!fullWidthElement)?'display:none':hideProjectName;
				var backlogItemStyle = (fullWidthElement)?'ticketKanBanStyleFull':'ticketKanBanStyle';
				var backlogItemClass = (fullWidthElement)?'backlogItemFull':'backlogItem';
				var backlogDescriptionClass = (fullWidthElement)?'backlogItemDescriptionFull':'backlogItemDescription';
				var backlogStatusClass = (fullWidthElement)?'backlogItemStatusFull':'backlogItemStatus';
				for(var j = 0; j < itemList.length; j++) {
					if(!itemList[j].hasResponsible()){
						hideResponsible = 'display:none';
					}else{
						hideResponsible = (vColumnList[i].getHideResponsible())?'display:none':'';
					}
					if(!itemList[j].hasScrumPriority()){
						hideScrumPriority = 'display:none';
					}else{
						hideScrumPriority = (vColumnList[i].getHideScrumPriority())?'display:none':'';
					}
					var epicClass = (itemList[j].getClass() == 'Epic')?'backlogEpicItem':'';
					var onmouseenter = (itemList[j].getClass() == 'Epic')?'highlightItemFromEpic(\''+itemList[j].getID()+'\', '+itemList[j].getId()+')':'highlightEpicFromItem(\''+itemList[j].getID()+'\', '+itemList[j].getIdEpic()+')';
					var onmouseleave = (itemList[j].getClass() == 'Epic')?'clearHighlightItemFromEpic()':'clearHighlightEpicFromItem()';
					columnHtmlItem += '<div class="dojoDndItem dojoDndHandle '+backlogItemStyle+' ticketKanBanColor '+backlogItemClass+' '+epicClass+'" dndtype="'+itemList[j].getDndType()+'"';
					columnHtmlItem += '  oncontextmenu="openBacklogContextMenu(\''+itemList[j].getID()+'\', '+itemList[j].getId()+', \''+itemList[j].getClass()+'\', '+itemList[j].getProjectId()+', \'object\');" ';
					columnHtmlItem += '  fromc="'+vColumnList[i].getID()+'" id="'+itemList[j].getID()+'" reftype="'+itemList[j].getClass()+'" refid="'+itemList[j].getId()+'" onmouseenter="'+onmouseenter+'" onmouseleave="'+onmouseleave+'">';
					columnHtmlItem += '	 <div style="position: relative;background: #FFFFFF;border-radius: 8px;cursor:move;">';
					columnHtmlItem += '		<div class="backlogItemHeader">';
					columnHtmlItem += '			<table style="width:100%"><tr title="'+i18n(itemList[j].getClass())+' #'+itemList[j].getId()+' '+i18n('Project')+' #'+itemList[j].getProjectId()+' - '+itemList[j].getProjectName()+'">';
					columnHtmlItem += '				<td style="font-size:10px;font-family:arial;width:75%">';
					columnHtmlItem += '					<div class="backlogItemProjectColorThumb">'+itemList[j].drawProjectColorThumb()+'</div>';
					columnHtmlItem += '					<div class="backlogItemId">#'+itemList[j].getId()+'</div>';
					columnHtmlItem += '					<div class="backlogItemTypeName" style="'+hideType+'">'+itemList[j].getTypeName()+'</div>';
					columnHtmlItem += '				</td>';
					columnHtmlItem += '				<td style="font-size:10px;font-family:arial;width:25%">';
					columnHtmlItem += '					<div class="backlogItemEpic" style="'+hideEpic+'">'+itemList[j].drawEpicThumb()+'</div>';
					columnHtmlItem += '				</td>';
					columnHtmlItem += '			</tr></table>';
					columnHtmlItem += '		</div>';
					columnHtmlItem += '		<div class="backlogItemTitle">'+itemList[j].drawTitle()+'</div>';
					columnHtmlItem += '		<div style="position: relative;cursor:move;display: flex;gap: 10px;">';
					columnHtmlItem += '			<div class="'+backlogStatusClass+'" style="'+hideStatus+'">'+itemList[j].drawStatusColorThumb()+'</div>';
					columnHtmlItem += '			<div class="backlogItemProjectName" style="'+hideProjectName+'">'+itemList[j].drawProjectName()+'</div>';
					columnHtmlItem += '		</div>';
					columnHtmlItem += '		<div class="'+backlogDescriptionClass+'">'+itemList[j].drawDescription()+'</div>';
					columnHtmlItem += '		<div class="backlogItemProduct" style="'+hideProduct+'">'+itemList[j].drawTargetProductVersion()+'</div>';
					columnHtmlItem += '		<div class="backlogItemSprint" style="'+hideSprint+'">'+itemList[j].drawSprintName()+'</div>';
					columnHtmlItem += '		<div class="backlogItemStoryPointAndBusiness" style="'+hideStoryPointsAndBusiness+'">'+itemList[j].drawStoryPointsAndBusiness()+'</div>';
					columnHtmlItem += '		<div class="backlogItemFooter">';
					columnHtmlItem += '			<div class="backlogItemUserThumb" style="'+hideResponsible+'">'+itemList[j].drawUserThumb()+'</div>';
					columnHtmlItem += '			<div style="'+hideResponsibleName+';float: left;padding: 5px 3px 5px 3px;">'+itemList[j].drawResponsibleName()+'</div>';
					columnHtmlItem += '			<div class="backlogItemScrumPriorityThumb" style="'+hideScrumPriority+'">'+itemList[j].drawScrumPriorityColorThumb()+'</div>';
					columnHtmlItem += '			<div class="backlogItemTableButton">'+itemList[j].drawTableButton()+'</div>';
					columnHtmlItem += '		</div>';
					columnHtmlItem += '	 </div>';
					columnHtmlItem += '</div>';
				}
				if(dojo.byId(vColumnList[i].getColumnName())){
					dojo.byId(vColumnList[i].getColumnName()).innerHTML = columnHtmlItem;
				}
			}
			if (!this._tooltipInited) {
			  BacklogTooltip.init({
			    root: dojo.byId(blg.getBacklogContainer()) || document
			  });
			  this._tooltipInited = true;
			}
		}
		window.top.hideWait();
	  };
};

JSBacklog.BacklogColumn = function(pColumn){
  var vID = pColumn.id;
  var vColumnName = 'backlogColumn'+vID;
  var vColumnBadgeName = 'badgeColumnItem'+vID;
  var vColumnStoryPointsName = 'storyPointsColumn'+vID;
  var vColumnBusinessValuesName = 'businessValuesColumn'+vID;
  var vItemCount = 0;
  var vStoryPoints = 0;
  var vBusinessValues = 0;
  var vItemList = pColumn.itemlist
  var vBacklogItemList = new Array();
  var vColumnType = pColumn.type;
  var vFullWidthElement = pColumn.fullwidthelement;
  var vHideStatus = pColumn.hidestatus;
  var vHideSprint = pColumn.hidesprint;
  var vHideEpic = pColumn.hideepic;
  var vHideProduct = pColumn.hideproduct;
  var vHideResponsible = pColumn.hideresponsible;
  var vHideStoryPointsAndBusiness = pColumn.hidestorypointsandbusiness;
  var vHideType = pColumn.hidetype;
  var vHideProjectName = pColumn.hideprojectname;
  var vHideScrumPriority = pColumn.hidescrumpriority;
  var vHideEpicItem = pColumn.hideepicitem;
  
  this.getID			  		= function(){ return vID; };
  this.getColumn      	  		= function(){ return pColumn; };
  this.getColumnName  	  		= function(){ return vColumnName; };
  this.getColumnType  	  		= function(){ return vColumnType; };
  this.getColumnBadgeName 		= function(){ return vColumnBadgeName; };
  this.getColumnStoryPointsName = function(){ return vColumnStoryPointsName; };
  this.getColumnBusinessValuesName = function(){ return vColumnBusinessValuesName; };
  this.getItemCount  	  		= function(){ return vItemCount; };
  this.getStoryPoints  	  		= function(){ return vStoryPoints; };
  this.getBusinessValues  	    = function(){ return vBusinessValues; };
  this.getFullWidthElement      = function(){ return (vFullWidthElement == 'on' || vFullWidthElement == '1')?true:false; };
  this.getHideStatus 			= function(){ return (vHideStatus == 'off' || vHideStatus == '0')?true:false; };
  this.getHideSprint 			= function(){ return (vHideSprint == 'off' || vHideSprint == '0')?true:false; };
  this.getHideEpic 				= function(){ return (vHideEpic == 'off' || vHideEpic == '0')?true:false; };
  this.getHideProduct 			= function(){ return (vHideProduct == 'off' || vHideProduct == '0')?true:false; };
  this.getHideResponsible 		= function(){ return (vHideResponsible == 'off' || vHideResponsible == '0')?true:false; };
  this.getHideStoryPointsAndBusiness = function(){ return (vHideStoryPointsAndBusiness == 'off' || vHideStoryPointsAndBusiness == '0')?true:false; };
  this.getHideType 				= function(){ return (vHideType == 'off' || vHideType == '0')?true:false; };
  this.getHideProjectName 		= function(){ return (vHideProjectName == 'off' || vHideProjectName == '0')?true:false; };
  this.getHideScrumPriority		= function(){ return (vHideScrumPriority == 'off' || vHideScrumPriority == '0')?true:false; };
  this.getHideEpicItem			= function(){ return (vHideEpicItem == 'off' || vHideEpicItem == '0')?true:false; };
  this.setFullWidthElement  	= function(pFullWidthElement){ vFullWidthElement = pFullWidthElement; };
  this.setHideStatus 			= function(pHideStatus){ vHideStatus = pHideStatus; };
  this.setHideSprint 			= function(pHideSprint){ vHideSprint = pHideSprint; };
  this.setHideEpic 				= function(pHideEpic){ vHideEpic = pHideEpic; };
  this.setHideProduct 			= function(pHideProduct){ vHideProduct = pHideProduct; };
  this.setHideResponsible 		= function(pHideResponsible){ vHideResponsible = pHideResponsible; };
  this.setHideStoryPointsAndBusiness = function(pHideStoryPointsAndBusiness){ vHideStoryPointsAndBusiness = pHideStoryPointsAndBusiness; };
  this.setHideType 			    = function(pHideType){ vHideType = pHideType; };
  this.setHideProjectName 		= function(pHideProjectName){ vHideProjectName = pHideProjectName; };
  this.setHideScrumPriority 	= function(pHideScrumPriority){ vHideScrumPriority = pHideScrumPriority; };
  this.setItemCount 			= function(pItemCount){ vItemCount = pItemCount; };
  this.setStoryPoints 			= function(pStoryPoints){ vStoryPoints = pStoryPoints; };
  this.setBusinessValues 		= function(pBusinessValues){ vBusinessValues = pBusinessValues; };
  this.setHideEpicItem			= function(pHideEpicItem){ vHideEpicItem = pHideEpicItem; };
  
  this.AddBacklogItem = function(value) {
	vBacklogItemList.push(value);
  };
  
  this.ReplaceBacklogItem = function(value) {
    var pId=value.getID();
    var vList = this.getBacklogItemList();
    for(var i = 0; i < vList.length; i++) {
      if(vList[i].getID()==pId){
        vList[i]=value;
        break;
      }
    }
  };
  
  for (var i = 0; i < vItemList.length; i++) {
    var item = vItemList[i];
    var newBacklogItem=new JSBacklog.BacklogItems(item);
  	vBacklogItemList.push(newBacklogItem);
  }
  
  this.deleteBacklogItemFromList = function(pID){
	var vItemList = this.getBacklogItemList();
	for(var i = 0; i < vItemList.length; i++) {
        if(vItemList[i].getID()==pID) {
        	vBacklogItemList.splice(i, 1);
        }
	}
  }
  
  this.getItemArrayLocationByID = function(pId)  {
    var vList = this.getBacklogItemList();
    for(var i = 0; i < vList.length; i++) {
      if(vList[i].getID()==pId) {
        return i;
      }
    }
    return null;
  };
  this.getItemByID = function(pId)  {
    var vList = this.getBacklogItemList();
    for(var i = 0; i < vList.length; i++) {
      if(vList[i].getID()==pId) {
        return vList[i];
      }
    }
    return null;
  };
  
  this.getBacklogItemList   = function() { return vBacklogItemList; };
};

JSBacklog.BacklogItems = function(pItem){
  var vID = pItem.id;
  var vName = htmlDecode(pItem.name);
  var vId = pItem.refid;
  var vClass = pItem.reftype;
  var vIdType = pItem.idtype;
  var vTypeName = htmlDecode(pItem.typename);
  var vIdStatus = pItem.idstatus;
  var vStatusName = htmlDecode(pItem.statusname);
  var vStatusColor = pItem.statuscolor;
  var vIdScrumPriority = pItem.idscrumpriority;
  var vScrumPriorityName = htmlDecode(pItem.scrumpriorityname);
  var vScrumPriorityColor = pItem.scrumprioritycolor;
  var vIdProject = pItem.idproject;
  var vProjectColor = pItem.projectcolor;
  var vProjectName = htmlDecode(pItem.projectname);
  var vIdResource = pItem.idresource;
  var vIconClass = pItem.iconclass;
  var vDndType = pItem.dndtype;
  var vResponsible = pItem.responsible;
  var vStoryPoints = pItem.storypoints;
  var vBusinessValue = pItem.businessvalue;
  var vIdTargetProductVersion = pItem.idtargetproductversion;
  var vTargetProductVersionName = pItem.targetproductversionname;
  var vIdEpic = pItem.idepic;
  var vEpicName = pItem.epicname;
  var vIdSprint = pItem.idsprint;
  var vSprintName = pItem.sprintname;
  var vDescription = htmlDecode(pItem.description);
  var vNoteBadge = pItem.notebadge;
  var vIsHidden = false;
  
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
  this.getIdType       				= function(){ return vIdType; };
  this.getTypeName     				= function(){ return vTypeName; };
  this.getIdStatus     				= function(){ return vIdStatus; };
  this.getStatusName   				= function(){ return vStatusName; };
  this.getStatusColor  				= function(){ return vStatusColor; };
  this.getIdScrumPriority     		= function(){ return vIdScrumPriority; };
  this.getScrumPriorityName   		= function(){ return vScrumPriorityName; };
  this.getScrumPriorityColor  		= function(){ return vScrumPriorityColor; };
  this.getProjectId    				= function(){ return vIdProject;}
  this.getProjectName  				= function(){ return vProjectName;}
  this.getProjectColor 				= function(){ return vProjectColor; };
  this.getIdResource   				= function(){ return vIdResource; };
  this.getClass        				= function(){ return vClass; };
  this.getStoryPoints   			= function(){ return vStoryPoints; };
  this.getBusinessValue  			= function(){ return vBusinessValue; };
  this.getIdTargetProductVersion    = function(){ return vIdTargetProductVersion; };
  this.getTargetProductVersionName  = function(){ return vTargetProductVersionName; };
  this.getIdSprint    				= function(){ return vIdSprint; };
  this.getSprintName  				= function(){ return vSprintName; };
  this.getIdEpic    				= function(){ return vIdEpic; };
  this.getEpicName  				= function(){ return vEpicName; };
  this.getDescription				= function(){ return htmlDecode(vDescription); };
  this.getNoteBadge      			= function(){ return vNoteBadge; };
  this.getIsHidden      			= function(){ return vIsHidden; };
  this.setIsHidden					= function(pIsHidden){ vIsHidden = pIsHidden; };
  this.hasResponsible				= function(){ if(vResponsible){return true;}else{return false;}}
  this.hasScrumPriority					= function(){ if(vIdScrumPriority){return true;}else{return false;}}
  this.getIconClass    				= function(){ 
    if(!vIconClass){
      vIconClass=this.getClass();
    }
    return vIconClass;
  };
  
  this.drawProjectColorThumb = function(){
	var projectColorThumb = '';
	projectColorThumb += '<div style="color:#FFFFFF;background:'+vProjectColor+';width:12px;height:12px;float:left;border-radius:3px" title="">&nbsp;</div>';
	return projectColorThumb;
  };
  
  this.drawEpicThumb = function(){
	var epicThumb = '';
	if(vIdEpic){
		epicThumb += '<div class="backlogItemEpicThumb" title="'+i18n('belongsEpic', new Array(vIdEpic,vEpicName))+'">';
		epicThumb += '	<div class="imageColorNewGuiNoSelection iconEpic16 iconEpic iconSize16" style="width:16px;height:16px;float:left"></div>';
		epicThumb += '</div>';
		epicThumb += '<div class="backlogItemEpicId" title="'+i18n('belongsEpic', new Array(vIdEpic,vEpicName))+'">#'+vIdEpic+'</div>';
	}
	return epicThumb;
  };
  
  this.drawTitle = function(){
	var title = '';
	title += '<div style="font-size:13px;" class="backlogItemTitle kanbanTitleTicket kanbanTitleSmallTiles">';
	title += '	<div class="imageColorNewGuiNoSelection icon'+vIconClass+'16 icon'+vIconClass+' iconSize16" style="width:16px;height:16px;float:left"></div>';
	title += '	&nbsp'+vName;
	title += '</div>';
	return title;
  };
  
  this.drawStoryPointsAndBusiness = function(){
	var storyPointsAndBusiness = '';
	storyPointsAndBusiness += '<table style="background-color:#eeeeee;cursor:move;width:100%;"><tr>';
	storyPointsAndBusiness += '	 <td class="" title="'+i18n('colStoryPoints')+'" style="width:33%;text-align:center;padding:0px 3px 3px 3px;font-size:90%;">';
	storyPointsAndBusiness += '		<span style="font-size:100%;color:var(--color-medium);">'+i18n('colStoryPoints')+'</span><br>'+vStoryPoints+'</td>';
	storyPointsAndBusiness += '			<td class="" title="'+i18n('colBusinessValue')+'" style="width:33%;text-align:center;padding:0px 3px 3px 3px;font-size:90%;">';
	storyPointsAndBusiness += '			<span style="font-size:100%;color:var(--color-medium);">'+i18n('colBusinessValue')+'</span><br>'+vBusinessValue+'</td>';
	storyPointsAndBusiness += '</tr></table>';
	return storyPointsAndBusiness;
  };
  
  this.drawDescription = function(){
	var description = '';
	description += htmlDecode(vDescription);
	return description;
  };
  
  this.drawStatusColorThumb = function(){
	var statusColorThumb = '';
	var isWhiteColor = (vStatusColor.toLowerCase() == '#ffffff')?true:false;
	var color = (isWhiteColor)?'#000000':'#ffffff';
	statusColorThumb += '<div style="padding:5px;width: 100%;text-align: center;">';
	statusColorThumb += '	<div style="color:'+color+';background:'+vStatusColor+';font-size:7pt;padding:'+((isWhiteColor)?'2px 8px 2px 8px':'3px 8px 3px 8px')+';border-radius:8px;'+((isWhiteColor)?'border:1px solid black;':'')+'" title="">'+vStatusName+'</div>';
	statusColorThumb += '</div>';
	return statusColorThumb;
  };
  
  this.drawScrumPriorityColorThumb = function(){
	  var scrumPriorityColorThumb = '';
	  if(vIdScrumPriority){
		scrumPriorityColorThumb += ''
		+ '<div style="float:left;margin:5px 0 5px 5px;position:relative">'
		+ '  <div class="backlogTooltipTrigger"'
		+ '       style="background:'+vScrumPriorityColor+';width:20px;height:20px;float:left;border-radius:5px;cursor:default;"'
		+ '       data-ktip="1"'
		+ '       data-ktip-text="'+htmlDecode(vScrumPriorityName)+'"'
		+ '       data-ktip-icon="imageColorNewGui iconPriority20 iconPriority iconSize20"'
		+ '       data-ktip-pos="bottom">'
		+ '    <div class="whiteIcon iconPriority16 iconPriorityFull iconSize16"'
		+ '         style="z-index:2;width:16px;height:16px;margin:2px;pointer-events:none;">&nbsp;</div>'
		+ '  </div>'
		+ '</div>';
	  }
	  return scrumPriorityColorThumb;
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
	      + ' class="backlogTooltipTrigger"'
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
	      + ' class="backlogTooltipTrigger"'
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
		responsibleName += '<div class="backlogResponsibleName" style="background-color:'+bgColor+';" onmouseenter="showToolTip(\'tooltipUserThumb_'+vID+'\');" onmouseleave="hideToolTip(\'tooltipUserThumb_'+vID+'\', 200);">';
		responsibleName +=		htmlDecode(vResponsible.name);
		responsibleName += '</div>';
	}
	return responsibleName;
  };
  
  this.drawSprintName = function(){
	var sprintId = '';
	sprintId += '<div style="height:20px;padding:0px 10px 0px 5px;overflow:hidden;white-space:nowrap;">';
	if(vSprintName){
		sprintId += '	<table style="margin: 2px;"><tr>';
		sprintId += '		<td title="'+i18n('Sprint')+' #'+vIdSprint+' '+vSprintName+'">';
		sprintId += '			<div class="imageColorNewGuiNoSelection iconSprint16 iconSprint iconSize16" style="width:16px;height:16px;float:left"></div>';
		sprintId += '		</td>';
		sprintId += '		<td title="'+i18n('Sprint')+' #'+vIdSprint+' '+vSprintName+'" id="vSprintName'+vID+'"  style="float:left;overflow:hidden;margin-left:2px;color:var(--color-medium);">'+vSprintName+'</td>';
		sprintId += '	</tr></table>';
	}
	sprintId += '</div>';
	return sprintId;
  };
  
  this.drawTargetProductVersion = function(){
	var targetProductVersion = '';
	targetProductVersion += '<div style="height:20px;padding:0px 10px 0px 5px;overflow:hidden;white-space:nowrap;">';
	if(vTargetProductVersionName){
		targetProductVersion += '	<table style="margin: 2px;"><tr>';
		targetProductVersion += '		<td title="'+i18n('colIdTargetProductVersion')+'">';
		targetProductVersion += '			<div class="imageColorNewGuiNoSelection iconProductVersion16 iconProductVersion iconSize16" style="width:16px;height:16px;float:left"></div>';
		targetProductVersion += '		</td>';
		targetProductVersion += '		<td title="'+vTargetProductVersionName+'" id="targetProductVersion'+vID+'"  style="float:left;overflow:hidden;margin-left:2px;color:var(--color-medium);">'+vTargetProductVersionName+'</td>';
		targetProductVersion += '	</tr></table>';
	}
	targetProductVersion += '</div>';
	return targetProductVersion;
  };
  
  this.drawTableButton = function(){
	var tableButton = '';
	var margin=(vNoteBadge>9)?'-10':'-7';
	tableButton += '<table style="float:right;margin:5px 0px;"><tr>';
	tableButton += '	<td><div class="roundedButtonSmall" style="width:16px;height:16px;cursor:pointer;vertical-align:text-bottom;margin-right:6px;float:left;padding-top: 2px;" onclick="showDetail(\'refreshActionAddItemBacklog\',1,\''+vClass+'\',false,'+vId+');" title="'+i18n('kanbanEditItem', new Array(vId, vId))+'">';
	tableButton += '		<span class="roundedButtonSmall" style="top:0px;display:inline-block;width:16px;height:16px;"><div class="iconButtonEdit16 iconButtonEdit iconSize16" style="">&nbsp;</div></span>';
	tableButton += '	</div></td>';
	if(vClass != 'Epic'){
		tableButton += '	<td><div style="position:relative">';
		tableButton += '		<div onclick="activityStreamBacklog(\''+vID+'\', '+vId+', \''+vClass+'\', \''+i18n('textareaEnterText')+'\');" style="margin-right:5px;margin-top: 3px;" title="'+i18n('commentImputationAdd')+'">';
		tableButton += '			<span class="roundedButtonSmall" style="top:0px;display:inline-block;width:16px;height:16px;"><div class="iconButtonAddComment16 iconButtonAddComment iconSize16" style="">&nbsp;</div></span>';
		tableButton += '			<div style="pointer-events: none;position:absolute;bottom:-3px;margin-left:'+margin+'px;width:5px;"><div id="noteBadge_'+vID+'" class="kanbanBadge" style="">'+vNoteBadge+'</div></div>';
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


// ======================================= SPRINT BACKLOG FUNCTION ======================================= //

function refreshSprintBacklog(oldColumn, newColumn, itemID) {
	showWait();
	if(oldColumn == undefined)oldColumn=null;
	if(newColumn == undefined)newColumn=null;
	if(itemID == undefined)itemID=null;
	if(!oldColumn && !newColumn && !itemID){
		var vBacklogColumnList = blg.getBacklogColumnList();
		for(var i = 0; i < vBacklogColumnList.length; i++) {
			var columnNode = dojo.byId(vBacklogColumnList[i].getColumnName());
			var widgets = dijit.registry.findWidgets(columnNode);
		    dojo.forEach(widgets, function(w) {
		        w.destroyRecursive(false);
		    });
		}
	}
	if(itemID){
		blg.deleteItemFromBacklogColumn(itemID);
		var widgets = dijit.registry.findWidgets(dojo.byId(itemID));
		dojo.forEach(widgets, function(w) {
	        w.destroyRecursive(false);
	    });
		oldColumn = newColumn;
	}
	var url = getJsonBacklogUrl('Status', oldColumn, newColumn);
	var jsonDiv = getJsonBacklogData('Status', true);
	loadContent(url,jsonDiv);
}

function sprintBacklogHideBacklog(value){
	showWait();
	saveDataToSession("sprintBacklogHideBacklog",value,true);
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
	if(!hide)refreshSprintBacklog('backlog', 'backlog');
	hideWait();
}

function sprintBacklogHideClosed(value){
	showWait();
	saveDataToSession("sprintBacklogHideClosed",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.isClosedColumn').forEach(function(node){
		node.style.display = display;
		if(hide){
			var widgets = dijit.registry.findWidgets(node);
		    dojo.forEach(widgets, function(w) {
		        w.destroyRecursive(false);
		    });
		}
	});
	if(!hide)refreshSprintBacklog('closed', 'closed');
	hideWait();
}

function sprintBacklogShowIdle(value){
	saveDataToSession("sprintBacklogShowIdle",value,true);
	refreshSprintBacklog();
}

function sprintBacklogFullWidthElement(value){
	saveDataToSession("sprintBacklogFullWidthElement",value,true);
//	var vFullWidthElement = (value == 'on' || value == '1')?true:false;
	var vBacklogColumnList = blg.getBacklogColumnList();
	showWait();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setFullWidthElement(value);
//		var hideProjectName = (vBacklogColumnList[i].getHideProjectName())?'display:none':'';
//		var vBacklogItemList = vBacklogColumnList[i].getBacklogItemList();
//		for(var j = 0; j < vBacklogItemList.length; j++) {
//			var item = dojo.byId(vBacklogItemList[j].getID());
//			if(vFullWidthElement){
//				dojo.removeClass(item, 'backlogItem');
//				dojo.addClass(item, 'backlogItemFull');
//				dojo.query('.backlogItemDescription').forEach(function(node){
//					dojo.addClass(node, 'backlogItemDescriptionFull');
//					dojo.removeClass(node, 'backlogItemDescription');
//				});
//				dojo.query('.backlogItemStatus').forEach(function(node){
//					dojo.addClass(node, 'backlogItemStatusFull');
//					dojo.removeClass(node, 'backlogItemStatus');
//				});
//				dojo.query('.backlogItemProjectName').forEach(function(node){
//					node.style.display = hideProjectName;
//				});
//				dojo.query('.backlogResponsibleName').forEach(function(node){
//					node.style.display = '';
//				});
//		    } else {
//				dojo.removeClass(item, 'backlogItemFull');
//				dojo.addClass(item, 'backlogItem');
//				dojo.query('.backlogItemDescriptionFull').forEach(function(node){
//					dojo.addClass(node, 'backlogItemDescription');
//					dojo.removeClass(node, 'backlogItemDescriptionFull');
//				});
//				dojo.query('.backlogItemStatusFull').forEach(function(node){
//					dojo.addClass(node, 'backlogItemStatus');
//					dojo.removeClass(node, 'backlogItemStatusFull');
//				});
//				dojo.query('.backlogItemProjectName').forEach(function(node){
//					node.style.display = 'none';
//				});
//				dojo.query('.backlogResponsibleName').forEach(function(node){
//					node.style.display = 'none';
//				});
//		    }
//		}
	}
	refreshSprintBacklog();
	hideWait();
}

function sprintBacklogHideStatus(value){
	showWait();
	saveDataToSession("sprintBacklogHideStatus",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemStatus').forEach(function(node){
		node.style.display = display;
	});
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideStatus(value);
	}
	hideWait();
}

function sprintBacklogHideEpic(value){
	showWait();
	saveDataToSession("sprintBacklogHideEpic",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemEpic').forEach(function(node){
		node.style.display = display;
	});
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideEpic(value);
	}
	hideWait();
}

function sprintBacklogHideSprint(value){
	showWait();
	saveDataToSession("sprintBacklogHideSprint",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemSprint').forEach(function(node){
		node.style.display = display;
	});
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideSprint(value);
	}
	hideWait();
}

function sprintBacklogHideProduct(value){
	showWait();
	saveDataToSession("sprintBacklogHideProduct",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemProduct').forEach(function(node){
		node.style.display = display;
	});
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideProduct(value);
	}
	hideWait();
}

function sprintBacklogHideResponsible(value){
	showWait();
	saveDataToSession("sprintBacklogHideResponsible",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemUserThumb').forEach(function(node){
		node.style.display = display;
	});
	var vBacklogColumnList = blg.getBacklogColumnList();
	var vFullWidthElement = false;
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideResponsible(value);
		vFullWidthElement = vBacklogColumnList[i].getFullWidthElement();
	}
	dojo.query('.backlogResponsibleName').forEach(function(node){
		node.style.display = (!vFullWidthElement)?'none':display;
	});
	hideWait();
}

function sprintBacklogHideScrumPriority(value){
	showWait();
	saveDataToSession("sprintBacklogHideScrumPriority",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemScrumPriorityThumb').forEach(function(node){
		node.style.display = display;
	});
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideScrumPriority(value);
	}
	hideWait();
}

function sprintBacklogHideStoryPointsAndBusiness(value){
	showWait();
	saveDataToSession("sprintBacklogHideStoryPointsAndBusiness",value,true);
//	var hide = (value == 'off' || value == '0')?true:false;
//	var display = (hide)?'none':'';
//	dojo.query('.backlogItemStoryPointAndBusiness').forEach(function(node){
//		node.style.display = display;
//	});
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideStoryPointsAndBusiness(value);
//		var node = dojo.byId(vBacklogColumnList[i].getColumnName());
	}
	refreshGlobalBacklog(null, 'Status');
	hideWait();
}

function sprintBacklogHideType(value){
	showWait();
	saveDataToSession("sprintBacklogHideType",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemTypeName').forEach(function(node){
		node.style.display = display;
	});
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideType(value);
	}
	hideWait();
}

function sprintBacklogHideProjectName(value){
	showWait();
	saveDataToSession("sprintBacklogHideProjectName",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideProjectName(value);
		display = (!vBacklogColumnList[i].getFullWidthElement())?'display:none':display;
	}
	dojo.query('.backlogItemProjectName').forEach(function(node){
		node.style.display = display;
	});
	hideWait();
}

// ======================================= PRODUCT BACKLOG FUNCTION ======================================= //

function refreshProductBacklog(oldColumn, newColumn, itemID) {
	showWait();
	if(oldColumn == undefined)oldColumn=null;
    if(newColumn == undefined)newColumn=null;
	if(itemID == undefined)itemID=null;
	if(!oldColumn && !newColumn && !itemID){
		var vBacklogColumnList = blg.getBacklogColumnList();
		for(var i = 0; i < vBacklogColumnList.length; i++) {
			var columnNode = dojo.byId(vBacklogColumnList[i].getColumnName());
			var widgets = dijit.registry.findWidgets(columnNode);
		    dojo.forEach(widgets, function(w) {
		        w.destroyRecursive(false);
		    });
		}
	}
	if(itemID){
		var item = blg.getBacklogItemByIDFromColumn(itemID);
		var itemClass = item.getClass();
		blg.deleteItemFromBacklogColumn(itemID);
		var widgets = dijit.registry.findWidgets(dojo.byId(itemID));
		dojo.forEach(widgets, function(w) {
	        w.destroyRecursive(false);
	    });
		if(itemClass != 'Epic')oldColumn = newColumn;
	}
	var url = getJsonBacklogUrl('Sprint', oldColumn, newColumn);
	var jsonDiv = getJsonBacklogData('Sprint', true);
	loadContent(url,jsonDiv);
	hideWait();
}

function productBacklogHideBacklog(value){
	showWait();
	saveDataToSession("productBacklogHideBacklog",value,true);
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
	if(!hide)refreshProductBacklog('backlog', 'backlog');
	hideWait();
}

function productBacklogShowIdle(value){
	saveDataToSession("productBacklogShowIdle",value,true);
	refreshProductBacklog();
}

function productBacklogFullWidthElement(value){
	showWait();
	saveDataToSession("productBacklogFullWidthElement",value,true);
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setFullWidthElement(value);
	}
	refreshProductBacklog();
	hideWait();
}

function productBacklogHideEpicItem(value){
	showWait();
	saveDataToSession("productBacklogHideEpicItem",value,true);
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideEpicItem(value);
	}
	refreshProductBacklog();
	hideWait();
}

function productBacklogHideStatus(value){
	showWait();
	saveDataToSession("productBacklogHideStatus",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemStatus').forEach(function(node){
		node.style.display = display;
	});
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideStatus(value);
	}
	hideWait();
}

function productBacklogHideEpic(value){
	showWait();
	saveDataToSession("productBacklogHideEpic",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemEpic').forEach(function(node){
		node.style.display = display;
	});
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideEpic(value);
	}
	hideWait();
}

function productBacklogHideSprint(value){
	showWait();
	saveDataToSession("productBacklogHideSprint",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemSprint').forEach(function(node){
		node.style.display = display;
	});
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideSprint(value);
	}
	hideWait();
}

function productBacklogHideProduct(value){
	showWait();
	saveDataToSession("productBacklogHideProduct",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemProduct').forEach(function(node){
		node.style.display = display;
	});
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideProduct(value);
	}
	hideWait();
}

function productBacklogHideResponsible(value){
	showWait();
	saveDataToSession("productBacklogHideResponsible",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemUserThumb').forEach(function(node){
		node.style.display = display;
	});
	var vBacklogColumnList = blg.getBacklogColumnList();
	var vFullWidthElement = false;
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideResponsible(value);
		vFullWidthElement = vBacklogColumnList[i].getFullWidthElement();
	}
	dojo.query('.backlogResponsibleName').forEach(function(node){
		node.style.display = (!vFullWidthElement)?'none':display;
	});
	hideWait();
}

function productBacklogHideScrumPriority(value){
	showWait();
	saveDataToSession("productBacklogHideScrumPriority",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemScrumPriorityThumb').forEach(function(node){
		node.style.display = display;
	});
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideScrumPriority(value);
	}
	hideWait();
}

function productBacklogHideStoryPointsAndBusiness(value){
	showWait();
	saveDataToSession("productBacklogHideStoryPointsAndBusiness",value,true);
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideStoryPointsAndBusiness(value);
	}
	refreshGlobalBacklog(null, 'Sprint');
	hideWait();
}

function productBacklogHideType(value){
	showWait();
	saveDataToSession("productBacklogHideType",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	dojo.query('.backlogItemTypeName').forEach(function(node){
		node.style.display = display;
	});
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideType(value);
	}
	hideWait();
}

function productBacklogHideProjectName(value){
	showWait();
	saveDataToSession("productBacklogHideProjectName",value,true);
	var hide = (value == 'off' || value == '0')?true:false;
	var display = (hide)?'none':'';
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		vBacklogColumnList[i].setHideProjectName(value);
		display = (!vBacklogColumnList[i].getFullWidthElement())?'display:none':display;
	}
	dojo.query('.backlogItemProjectName').forEach(function(node){
		node.style.display = display;
	});
	hideWait();
}

// ======================================= COMMON BACKLOG FUNCTION ======================================= //

function getJsonBacklogUrl (typeBacklog, oldColumn, newColumn) {
  if(oldColumn == undefined)oldColumn=null;
  if(newColumn == undefined)newColumn=null;
  if (typeBacklog == 'Status') {
    url="../tool/jsonSprintBacklog.php";
  } else if (typeBacklog == 'Sprint') {
    url="../tool/jsonProductBacklog.php";
  } else {
    return null;
  }
  if(oldColumn && newColumn){
	url += '?onlyRefresh=true&oldColumn='+oldColumn+'&newColumn='+newColumn+addTokenIndexToUrl();
  }
  return url;
}

function getJsonBacklogData (typeBacklog, onlyName) {
  if(onlyName==undefined)onlyName=false;
  if (typeBacklog == 'Status') {
    data=dojo.byId('sprintBacklogJsonData');
	if(onlyName)data='sprintBacklogJsonData';
  } else if (typeBacklog == 'Sprint') {
    data=dojo.byId('productBacklogJsonData');
	if(onlyName)data='productBacklogJsonData';
  } else {
    return null;
  }
  return data;
}

function refreshBacklog(oldColumn, newColumn, itemID){
	var columnType = blg.getBacklogType();
	if(columnType == 'Status'){
		refreshSprintBacklog(oldColumn, newColumn, itemID);
	}else{
		refreshProductBacklog(oldColumn, newColumn, itemID);
	}
}

function refreshGlobalBacklog(idSprint, backlogType){
	if(idSprint){
		if(idSprint == '0')$idSprint=null;
		saveDataToSession('sprintBacklogIdSprint', idSprint, true);
	}
	var columnType = (backlogType)?backlogType:blg.getBacklogType();
	if(columnType == 'Status'){
		loadContent('../view/sprintBacklogMain.php','centerDiv',null);
	}else{
		loadContent('../view/productBacklogMain.php?NoRefreshColumnOrder=true','centerDiv',null);
	}
}

function addSprintFromBacklog(){
	var canCreate = (canCreateArray['Sprint'] == 'YES')?1:0;
	showDetail('refreshActionAddSprintBacklog',canCreate,'Sprint',false,'new');
}

function addEpicFromBacklog(){
	backlogPendingColumnContext = null;
	var idSprint = (dijit.byId('listIdSprintBacklog'))?dijit.byId('listIdSprintBacklog').get('value'):null;
	var canCreate = (canCreateArray['Epic'] == 'YES')?1:0;
	showDetail('refreshActionAddItemBacklog', canCreate,'Epic',false,null,true);
	if(idSprint){
		newDetailItem('Epic', 'idSprint', idSprint);
	}else{
		newDetailItem('Epic', null, null);
	}
}

function addUserStoryFromBacklog(){
	backlogPendingColumnContext = null;
	var idSprint = (dijit.byId('listIdSprintBacklog'))?dijit.byId('listIdSprintBacklog').get('value'):null;
	var canCreate = (canCreateArray['UserStory'] == 'YES')?1:0;
	showDetail('refreshActionAddItemBacklog', canCreate,'UserStory',false,null,true);
	if(idSprint){
		newDetailItem('UserStory', 'idSprint', idSprint);
	}else{
		newDetailItem('UserStory', null, null);
	}
}

var backlogPendingColumnContext = null;

function addItemFromBacklogColumn(columnClass, columnTarget, columnType){
	if(!columnClass)return;
	var canCreate = (canCreateArray[columnClass] == 'YES')?1:0;
	if(!canCreate)return;
	showDetail('refreshActionAddItemBacklog', canCreate, columnClass, false, null, true);
	// Pre-set the column field on the new form when possible.
	// For Product Backlog (Sprint columns), force the target sprint.
	// For Sprint Backlog (Status columns), inherit the currently selected sprint from the page selector if any.
	if(columnType == 'Sprint'){
		newDetailItem(columnClass, 'idSprint', columnTarget);
	}else{
		var idSprint = (dijit.byId('listIdSprintBacklog'))?dijit.byId('listIdSprintBacklog').get('value'):null;
		if(idSprint && idSprint != '0' && idSprint != '-1'){
			newDetailItem(columnClass, 'idSprint', idSprint);
		}else{
			newDetailItem(columnClass, null, null);
		}
	}
	backlogPendingColumnContext = {columnTarget:columnTarget, columnType:columnType, objectClass:columnClass};
}

function openBacklogColumnContextMenu(evt, columnTarget, columnType, columnName){
	if(evt){
		if(evt.target && evt.target.closest && evt.target.closest('.backlogItem, .backlogItemFull, .columnOptionButton')){
			return;
		}
		evt.preventDefault();
		if(evt.stopPropagation)evt.stopPropagation();
	}
	if(typeof hideBacklogContextMenuTimeout != 'undefined' && hideBacklogContextMenuTimeout){
		clearTimeout(hideBacklogContextMenuTimeout);
		hideBacklogContextMenuTimeout = null;
	}
	var contextMenu = dijit.byId('backlogContextMenu');
	var contextMenuDiv = dojo.byId('dialogBacklogContextMenu');
	if(!contextMenu || !contextMenuDiv)return;
	var divBacklogContainer = dojo.byId('divBacklogContainer');
	var scrollX = (divBacklogContainer)?divBacklogContainer.scrollLeft:0;
	var mousePosition = {x: evt.clientX + scrollX, y: evt.clientY - 150};
	if(dojo.byId('isMenuLeftOpen') && dojo.byId('isMenuLeftOpen').value == 'true'){
		mousePosition.x -= 250;
	}
	dojo.query('.contextMenuClass').forEach(function(node){
		node.style.cssText='position:absolute;width:0px;height:0px;overflow:hidden;top:'+mousePosition.y+'px;left:'+mousePosition.x+'px';
	});
	// Hide all non-relevant rows
	var rowsToHide = ['copyFromBacklog','editFromBacklog','addCommentFromBacklog','removeFromBacklog','printFromBacklog','printPdfFromBacklog','gotoFromBacklog','gotoSprintListFromBacklog','gotoSprintBacklogFromBacklog','addSprintFromBacklog'];
	rowsToHide.forEach(function(rowId){
		var row = dojo.byId(rowId);
		if(row){ row.style.display = 'none'; row.onclick = null; row.setAttribute('onClick',''); }
	});
	// Show Add UserStory + Add Epic rows targeting this column.
	// Epic is only relevant on Product Backlog (columnType=Sprint) -
	// Sprint Backlog (columnType=Status) only displays UserStories.
	var usRow = dojo.byId('addUserStoryFromBacklog');
	if(usRow){
		usRow.style.display = '';
		var usLabel = dojo.byId('addUserStoryFromBacklog_label');
		if(usLabel) usLabel.innerHTML = i18n('addUserStoryBacklog')+' ('+columnName+')';
		usRow.setAttribute('onClick','');
		usRow.onclick = function(){
			usRow.onclick = null;
			hideBacklogContextMenu(0);
			addItemFromBacklogColumn('UserStory', columnTarget, columnType);
		};
	}
	var epRow = dojo.byId('addEpicFromBacklog');
	if(epRow){
		if(columnType == 'Sprint'){
			epRow.style.display = '';
			var epLabel = dojo.byId('addEpicFromBacklog_label');
			if(epLabel) epLabel.innerHTML = i18n('addEpicBacklog')+' ('+columnName+')';
			epRow.setAttribute('onClick','');
			epRow.onclick = function(){
				epRow.onclick = null;
				hideBacklogContextMenu(0);
				addItemFromBacklogColumn('Epic', columnTarget, columnType);
			};
		}else{
			epRow.style.display = 'none';
			epRow.onclick = null;
			epRow.setAttribute('onClick','');
		}
	}
	contextMenu.openDropDown();
	contextMenuDiv.focus();
}

function refreshActionAddSprintBacklog(field){
	if(dijit.byId(field.id).get('value')!=-1){
		var idSprint = field.value;
		refreshGlobalBacklog(idSprint);
		dijit.byId(field.id).set('value',-1);
	}
}

function refreshActionAddItemBacklog(field){
	if(dijit.byId(field.id).get('value')!=-1){
		var newId = dijit.byId(field.id).get('value');
		// For Sprint column type (Product Backlog), the form already pre-filled idSprint via
		// paramField/paramVal - the item is already in the right column. Skip the post-save
		// call entirely to avoid the "no change to save" error.
		if(backlogPendingColumnContext && backlogPendingColumnContext.columnType == 'Sprint'){
			backlogPendingColumnContext = null;
			dijit.byId(field.id).set('value',-1);
			_doBacklogRefreshAfterAdd();
			return;
		}
		if(backlogPendingColumnContext && newId && parseInt(newId) > 0){
			var ctx = backlogPendingColumnContext;
			backlogPendingColumnContext = null;
			dijit.byId(field.id).set('value',-1);
			var url = "../tool/backlogCheckRequiredField.php?objectId=" + newId
				+ "&objectClass=" + ctx.objectClass
				+ "&itemID=" + ctx.objectClass + newId
				+ "&oldColumn=" + ctx.columnTarget
				+ "&newColumn=" + ctx.columnTarget
				+ "&columnType=" + ctx.columnType
				+ "&forceWorkflow=1" + addTokenIndexToUrl();
			dojo.xhrGet({
				url:url,
				load:function(data){
					if(data && data.indexOf('messageError/split/') != -1){
						showAlert(data.split('messageError/split/')[1], null);
						_doBacklogRefreshAfterAdd();
					}else if(data && data.indexOf('needGlobalRefresh') != -1){
						refreshGlobalBacklog();
					}else if(data){
						// Required fields missing : open the dialog like a drag-drop
						var functionCallback = function(){ hideWait(); };
						if ((data.indexOf('needResult') != -1 && typeof dojo.byId("backlogResultEditorType") != 'undefined')
							|| ((data.indexOf('backlogDescription') != -1 || data.indexOf('description') != -1) && typeof dojo.byId("descriptionEditorType") != 'undefined')) {
							functionCallback = function(){
								var editorTypeResult = null;
								if (dojo.byId("backlogResultEditorType") && typeof dojo.byId("backlogResultEditorType") != 'undefined') editorTypeResult = dojo.byId("backlogResultEditorType").value;
								if (editorTypeResult == "CK") {
									ckEditorReplaceEditor("backlogResult", 999);
								} else if (dijit.byId("liveMeetingResult") && dijit.byId("backlogResult")) {
									dijit.byId("backlogResult").set("class", "input");
								}
								var editorTypeDescription = null;
								if (dojo.byId("descriptionEditorType") && typeof dojo.byId("descriptionEditorType") != 'undefined') editorTypeDescription = dojo.byId("descriptionEditorType").value;
								if (editorTypeDescription == "CK") {
									if (dojo.byId("backlogDescription")) ckEditorReplaceEditor("backlogDescription", 999);
									else ckEditorReplaceEditor("description", 999);
								} else if (dijit.byId("liveMeetingResult") && dijit.byId("backlogDescription")) {
									dijit.byId("backlogDescription").set("class", "input");
								}
							};
						}
						loadDialog('dialogBacklogUpdate', functionCallback, true, data, true, false);
					}else{
						_doBacklogRefreshAfterAdd();
					}
				},
				error:function(){
					_doBacklogRefreshAfterAdd();
				}
			});
			return;
		}
		if(blg.getBacklogType() == "Sprint"){
			refreshGlobalBacklog();
		}else{
			refreshBacklog();
			dijit.byId(field.id).set('value',-1);
		}
	}
}

function _doBacklogRefreshAfterAdd(){
	if(blg.getBacklogType() == "Sprint"){
		refreshGlobalBacklog();
	}else{
		refreshBacklog();
	}
}

function manageBacklogColunm(columnType){
	var params = '&columnType='+columnType;
	loadDialog('dialogBacklogManageColumn',null,true,params,true,false);
}

function filterItemName() {
	var input = dojo.byId('searchByName');
	var filter = input.value.toLowerCase();
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		var vBacklogItemList = vBacklogColumnList[i].getBacklogItemList();
		for(var j = 0; j < vBacklogItemList.length; j++) {
			var item = dojo.byId(vBacklogItemList[j].getID());
			var itemName = vBacklogItemList[j].getName().toLowerCase();
			if(itemName.indexOf(filter) > -1 || !filter.trim()){
				dojo.removeClass(item, 'backlogItemHide');
		    } else {
				dojo.addClass(item, 'backlogItemHide');
		    }
		}
	}
}

function filterItemResponsible() {
	var idResponsible = dijit.byId('searchByResponsible').get('value');
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		var vBacklogItemList = vBacklogColumnList[i].getBacklogItemList();
		for(var j = 0; j < vBacklogItemList.length; j++) {
			var item = dojo.byId(vBacklogItemList[j].getID());
			var itemResponsible = vBacklogItemList[j].getIdResource();
			if(itemResponsible == idResponsible.trim() || !idResponsible.trim()){
				dojo.removeClass(item, 'backlogItemHide');
		    } else {
				dojo.addClass(item, 'backlogItemHide');
		    }
		}
	}
}

function filterItemVersion() {
	var idVersion = dijit.byId('searchByTargetProductVersion').get('value');
	var vBacklogColumnList = blg.getBacklogColumnList();
	for(var i = 0; i < vBacklogColumnList.length; i++) {
		var vBacklogItemList = vBacklogColumnList[i].getBacklogItemList();
		for(var j = 0; j < vBacklogItemList.length; j++) {
			var item = dojo.byId(vBacklogItemList[j].getID());
			var itemVersion = vBacklogItemList[j].getIdTargetProductVersion();
			if(itemVersion == idVersion.trim() || !idVersion.trim()){
				dojo.removeClass(item, 'backlogItemHide');
		    } else {
				dojo.addClass(item, 'backlogItemHide');
		    }
		}
	}
}

function filterBacklog(refresh) {
	if(refresh==undefined)refresh=false;
	if(refresh){
		refreshGlobalBacklog();
		return;
	}
    var nameFilter      = dojo.byId('searchByName').value.toLowerCase();
    var idResponsible   = dijit.byId('searchByResponsible').get('value');
    var idVersion       = dijit.byId('searchByTargetProductVersion').get('value');

    nameFilter    = nameFilter.trim();
    idResponsible = idResponsible ? idResponsible.toString().trim() : '';
    idVersion     = idVersion ? idVersion.toString().trim() : '';

    var vBacklogColumnList = blg.getBacklogColumnList();

    for (var i = 0; i < vBacklogColumnList.length; i++) {
        var vBacklogItemList = vBacklogColumnList[i].getBacklogItemList();
        for (var j = 0; j < vBacklogItemList.length; j++) {

            var itemNode       = dojo.byId(vBacklogItemList[j].getID());
            var itemName       = vBacklogItemList[j].getName().toLowerCase();
            var itemResp       = vBacklogItemList[j].getIdResource();
            var itemItemVer    = vBacklogItemList[j].getIdTargetProductVersion();

            var okName   = (!nameFilter)    || (itemName.indexOf(nameFilter) > -1);
            var okResp   = (!idResponsible) || (itemResp == idResponsible);
            var okVer    = (!idVersion)     || (itemItemVer == idVersion);

            if (okName && okResp && okVer) {
				vBacklogItemList[j].setIsHidden(false);
                dojo.removeClass(itemNode, 'backlogItemHide');
            } else {
				vBacklogItemList[j].setIsHidden(true);
                dojo.addClass(itemNode, 'backlogItemHide');
            }
        }
		blg.setBacklogColumnItemCount(vBacklogColumnList[i].getID());
		if(dojo.byId(vBacklogColumnList[i].getColumnBadgeName())){
			dojo.byId(vBacklogColumnList[i].getColumnBadgeName()).innerHTML = vBacklogColumnList[i].getItemCount();
		}
		blg.setBacklogColumnStoryPointAndBusinessValue(vBacklogColumnList[i].getID());
		if(dojo.byId(vBacklogColumnList[i].getColumnStoryPointsName()) && dojo.byId(vBacklogColumnList[i].getColumnBusinessValuesName())){
			dojo.byId(vBacklogColumnList[i].getColumnStoryPointsName()).innerHTML = vBacklogColumnList[i].getStoryPoints();
			dojo.byId(vBacklogColumnList[i].getColumnBusinessValuesName()).innerHTML = vBacklogColumnList[i].getBusinessValues();
		}
    }
}


function activityStreamBacklog(itemId, objectId,objectClass,placeholder) {
  var param="&itemId=" + itemId +"&objectId=" + objectId + "&objectClass=" + objectClass;
  var callBack=function(){
    dijit.byId("noteStreamBacklog").set("placeholder", placeholder);
  };
  loadDialog('dialogBacklogGetObjectStream',callBack,true,param,true,true,'titleStream');
}

var saveNoteStreamBacklogTimeout=null;
function saveNoteStreamBacklog(event) {
  var key=event.keyCode;
  if (key == 13 && !event.shiftKey) {
    var noteEditor=dijit.byId("noteStreamBacklog");
    var noteEditorContent=noteEditor.get("value");
    if (noteEditorContent.trim() == "") {
      noteEditor.focus();
      return;
    }
    var callBack=function() {
	  dojo.byId('noteStreamBacklog').value = null;
	  var itemId = dojo.byId('itemId').value;
	  var noteBadge = dojo.byId('noteBadge_'+itemId);
	  var countNoteBadge = dojo.byId('countNoteItem').value;
	  noteBadge.innerHTML = countNoteBadge;
	  var margin=(countNoteBadge>9)?'-10':'-7';
	  noteBadge.parentNode.style.marginLeft = margin+'px';
      dojo.byId("resultBacklogStreamDiv").style.display="block";
      if (saveNoteStreamBacklogTimeout) clearTimeout(saveNoteStreamBacklogTimeout);
      saveNoteStreamBacklogTimeout=setTimeout('dojo.byId("resultBacklogStreamDiv").style.display="none";',3000);
    };
    loadContent("../tool/saveNoteStreamBacklog.php","activityStreamCenterBacklog","noteFormStreamBacklog",false,null,null,null,callBack);
    event.preventDefault();
  }
}

function sendChangeBacklog(node, source, target) {
	var itemID = node.id;
	var objectId=node.attributes.refid.value;
	var objectClass=node.attributes.reftype.value;
	var columnType=source.columntype;
	var oldColumn=node.attributes.fromc.value;
	var newColumn=target.columntarget;
    showWait();
  	dojo.xhrGet({
	    url:"../tool/backlogCheckRequiredField.php?objectId=" + objectId + "&objectClass=" + objectClass + "&itemID=" + itemID +"&oldColumn="+oldColumn+"&newColumn=" + newColumn + "&columnType=" + columnType +addTokenIndexToUrl(),
	    load:function(data) {
      if (data.indexOf('messageError/split/') != -1) {
		refreshBacklog(oldColumn, newColumn);
        showAlert(data.split('messageError/split/')[1],null);
      } else if (data.indexOf('needGlobalRefresh') != -1) {
	  	refreshGlobalBacklog();
	  } else if(data){
        functionCallback=function() {
          hideWait();
        };
        if ((data.indexOf('needResult') != -1 && typeof dojo.byId("backlogResultEditorType") != 'undefined')
            || ((data.indexOf('backlogDescription') != -1 || data.indexOf('description') != -1) && typeof dojo.byId("descriptionEditorType") != 'undefined')) functionCallback=function() {
          var editorTypeResult=null;
          if (dojo.byId("backlogResultEditorType") && typeof dojo.byId("backlogResultEditorType") != 'undefined') editorTypeResult=dojo.byId("backlogResultEditorType").value;
          if (editorTypeResult == "CK") { // CKeditor type
            ckEditorReplaceEditor("backlogResult",999);
          } else if (dijit.byId("liveMeetingResult") && dijit.byId("backlogResult")) { // Dojo
                                                                                      // type
                                                                                      // editor
            dijit.byId("backlogResult").set("class","input");
          }
          var editorTypeDescription=null;
          if (dojo.byId("descriptionEditorType") && typeof dojo.byId("descriptionEditorType") != 'undefined') editorTypeDescription=dojo.byId("descriptionEditorType").value;
          if (editorTypeDescription == "CK") { // CKeditor type
            if (dojo.byId("backlogDescription")) ckEditorReplaceEditor("backlogDescription",999);
            else ckEditorReplaceEditor("description",999);
          } else if (dijit.byId("liveMeetingResult") && dijit.byId("backlogDescription")) { // Dojo
                                                                                      // type
                                                                                      // editor
            dijit.byId("backlogDescription").set("class","input");
          }
        };
        loadDialog('dialogBacklogUpdate',functionCallback,true,data,true,false);
      } else {
		refreshBacklog(oldColumn, newColumn, itemID);
		var oldColumnObj = blg.getBacklogColumnByID(oldColumn);
		blg.setBacklogColumnItemCount(oldColumn);
		 if (dojo.byId(oldColumnObj.getColumnBadgeName())){
			dojo.byId(oldColumnObj.getColumnBadgeName()).innerHTML = oldColumnObj.getItemCount();
		 }
		 blg.setBacklogColumnStoryPointAndBusinessValue(oldColumn);
		 if(dojo.byId(oldColumnObj.getColumnStoryPointsName()) && dojo.byId(oldColumnObj.getColumnBusinessValuesName())){
			dojo.byId(oldColumnObj.getColumnStoryPointsName()).innerHTML = oldColumnObj.getStoryPoints();
			dojo.byId(oldColumnObj.getColumnBusinessValuesName()).innerHTML = oldColumnObj.getBusinessValues();
		 }
      }
    },
    error:function(data) {
		refreshBacklog(oldColumn, newColumn);
	    showError(data);
	    hideWait();
    }
  });
}

function saveBacklogResult(oldColumn, newColumn, itemID) {
  showWait();
  tmpCkEditor='';
  if (typeof CKEDITOR.instances.backlogResult != 'undefined') {
    CKEDITOR.instances.backlogResult.updateElement();
    tmpCkEditor=CKEDITOR.instances.backlogResult.document.getBody().getText();
  }
  tmpCkEditorBacklogDescription='';
  if (typeof CKEDITOR.instances.backlogDescription != 'undefined') {
    CKEDITOR.instances.backlogDescription.updateElement();
    tmpCkEditorBacklogDescription=CKEDITOR.instances.backlogDescription.document.getBody().getText();
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
  var form=dijit.byId('backlogResultForm');
  if (!form.validate()) {
    showAlert(i18n("alertInvalidForm"));
  } else {
    if (extraRequiredVal
        && ((typeof dijit.byId('backlogResourceList') != 'undefined' && dijit.byId('backlogResourceList').get('value').trim() != '') || typeof dijit.byId('backlogResourceList') == 'undefined')
        && ((typeof CKEDITOR.instances.backlogResult == 'undefined' || (typeof CKEDITOR.instances.backlogResult != 'undefined' && tmpCkEditor.trim() != '')) && ((typeof dijit.byId('backlogResult') != 'undefined' && dijit
            .byId('backlogResult').get('value').trim() != '') || typeof dijit.byId('backlogResult') == 'undefined'))
        && ((typeof CKEDITOR.instances.backlogDescription == 'undefined' || (typeof CKEDITOR.instances.backlogDescription != 'undefined' && tmpCkEditorBacklogDescription.trim() != '')) && ((typeof dijit
            .byId('backlogDescription') != 'undefined' && dijit.byId('backlogDescription').get('value').trim() != '') || typeof dijit.byId('backlogDescription') == 'undefined'))) {
      dojo.xhrPost({
        url:"../tool/backlogCheckRequiredField.php?"+addTokenIndexToUrl(),
        form:"backlogResultForm",
        handleAs:"text",
        load:function(data,args) {
          formChangeInProgress=false;
          dijit.byId('dialogBacklogUpdate').hide();
          if (data.indexOf('messageError/split/') != -1) {
			 hideWait();
			 refreshBacklog(oldColumn, newColumn);
			 showAlert(data.split('messageError/split/')[1],null);
          } else {
			 refreshBacklog(oldColumn, newColumn, itemID);
			 hideWait();
          }
        },
        error:function() {
			refreshBacklog(oldColumn, newColumn);
          	hideWait();
        }
      });
    } else {
      var finalMessage='';

      if ((typeof dijit.byId('backlogResourceList') != 'undefined' && dijit.byId('backlogResourceList').get('value').trim() == '')) {
        finalMessage+=i18n('messageMandatory',[i18n('colMandatoryResourceOnHandled')]);
      }
      valCk='';
      if (typeof CKEDITOR.instances.backlogResult != 'undefined') valCk=CKEDITOR.instances.backlogResult.getData();
      if (!((typeof CKEDITOR.instances.backlogResult == 'undefined' || (typeof CKEDITOR.instances.backlogResult != 'undefined' && tmpCkEditor.trim() != '')) && ((typeof dijit.byId('backlogResult') != 'undefined' && dijit
          .byId('backlogResult').get('value').trim() != '') || typeof dijit.byId('backlogResult') == 'undefined'))) {
        if (finalMessage != '') finalMessage+='<br/>';
        finalMessage+=i18n('messageMandatory',[i18n('colMandatoryResultOnDone')]);
      }
	  if (typeof CKEDITOR.instances.backlogDescription != 'undefined') valCk=CKEDITOR.instances.backlogDescription.getData();
	      if (!((typeof CKEDITOR.instances.backlogDescription == 'undefined' || (typeof CKEDITOR.instances.backlogDescription != 'undefined' && tmpCkEditor.trim() != '')) && ((typeof dijit.byId('backlogDescription') != 'undefined' && dijit
	        .byId('backlogDescription').get('value').trim() != '') || typeof dijit.byId('backlogDescription') == 'undefined'))) {
	      if (finalMessage != '') finalMessage+='<br/>';
	      finalMessage+=i18n('messageMandatory',[i18n('colMandatoryDescription')]);
	  }
      valCk='';
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
		refreshBacklog(oldColumn, newColumn);
		showAlert(finalMessage);
	  } 
      hideWait();
    }
  }
}

function updateBacklogColumnManagment(source, target, nodes){
	var targetManagment = (target.id=='columnManagmentDndTarget')?target:source;
   	nodes.forEach(function(node){
     	dojo.query('.itemSourceName', node).forEach(function(itemName){
     		itemName.style.display = 'flex';
     	});
   	});
	setTimeout(function(){
		source.selectNone();
		target.selectNone();
		var order = 1;
		targetManagment.getAllNodes().forEach(function(node){
			dojo.query('.itemSourceOrder', node).forEach(function(item){
				item.innerHTML = 'N°'+order;
			});
			order++;
		});
	}, 1);
}

function gotoSprintBacklog(idSprint){
	if(!idSprint)return;
	saveDataToSession('sprintBacklogIdSprint', idSprint, true);
	loadMenuBarItem('SprintBacklog',i18n('menuSprintBacklog'),'bar');
	refreshSelectedMenuLeft('menuSprintBacklog');
	showMenuBottomParam('SprintBacklog','false');
}

function highlightItemFromEpic(ItemID, idEpic){
	blg.highlightItemFromEpic(ItemID, idEpic);
}

function highlightEpicFromItem(ItemID, idEpic){
	blg.highlightEpicFromItem(ItemID, idEpic);
}

function clearHighlightItemFromEpic(){
	blg.clearHighlightItemFromEpic();
}

function clearHighlightEpicFromItem(){
	blg.clearHighlightEpicFromItem();
}

//==================================================================
//Backlog ContextMenu
//==================================================================

function deleteOnBacklogFromContextMenu(refId, refType){
  fromContextMenu = true;
  if (refType=='Replan' || refType=='Construction' || refType=='Fixed') refType='Project';
  var action=function(){
    var resetContextMenuVariable=function(){
      if(!(dojo.byId('confirmControl') && dojo.byId('confirmControl').value=='delete')){
        fromContextMenu=false;
      }
      refreshBacklog();
    }
    dojo.byId('objectClass').value = refType;
    dojo.byId('objectId').value = refId;
    loadContent('../tool/deleteObject.php?objectId=' + refId
        + '&objectClassName='+refType+'&fromContextMenu='+fromContextMenu, 'resultDivMain', 'objectForm', true, null, null, null, resetContextMenuVariable);
  };
  showConfirm(i18n('confirmDelete', new Array(refType, refId)) ,action);
}

var hideBacklogContextMenuTimeout = null;
function hideBacklogContextMenu(delay) {
  var contextMenu = dijit.byId('backlogContextMenu');
  var contextMenuDiv = dojo.byId('dialogBacklogContextMenu');
  if (contextMenu) {
    var callback = function () {
      if (dojo.byId('addUserStoryFromBacklog')) dojo.byId('addUserStoryFromBacklog').setAttribute('onClick', '');
	  if (dojo.byId('addEpicFromBacklog')) dojo.byId('addEpicFromBacklog').setAttribute('onClick', '');
	  if (dojo.byId('addSprintFromBacklog')) dojo.byId('addSprintFromBacklog').setAttribute('onClick', '');
	  if (dojo.byId('editFromBacklog')) dojo.byId('editFromBacklog').setAttribute('onClick', '');
      if (dojo.byId('copyFromBacklog')) dojo.byId('copyFromBacklog').setAttribute('onClick', '');
      if (dojo.byId('removeFromBacklog')) dojo.byId('removeFromBacklog').setAttribute('onClick', '');
      if (dojo.byId('printFromBacklog')) dojo.byId('printFromBacklog').setAttribute('onClick', '');
      if (dojo.byId('printPdfFromBacklog')) dojo.byId('printPdfFromBacklog').setAttribute('onClick', '');
      if (dojo.byId('addCommentFromBacklog')) dojo.byId('addCommentFromBacklog').setAttribute('onClick', '');
      if (dojo.byId('gotoFromBacklog')) dojo.byId('gotoFromBacklog').setAttribute('onClick', '');
	  if (dojo.byId('gotoSprintListFromBacklog')) dojo.byId('gotoSprintListFromBacklog').setAttribute('onClick', '');
	  if (dojo.byId('gotoSprintBacklogFromBacklog')) dojo.byId('gotoSprintBacklogFromBacklog').setAttribute('onClick', '');
      contextMenu.closeDropDown();
      contextMenuDiv.blur();
    };
    hideBacklogContextMenuTimeout = setTimeout(callback, delay);
  }
}

function openBacklogContextMenu(vID, refId, refType, idProject, type){
  var contextMenu = dijit.byId('backlogContextMenu');
  var contextMenuDiv = dojo.byId('dialogBacklogContextMenu');
  event.preventDefault();
  if(event.stopPropagation)event.stopPropagation();
  // Restore labels that may have been altered by the column context menu
  var usLabel = dojo.byId('addUserStoryFromBacklog_label');
  if(usLabel) usLabel.innerHTML = i18n('addUserStoryBacklog');
  var epLabel = dojo.byId('addEpicFromBacklog_label');
  if(epLabel) epLabel.innerHTML = i18n('addEpicBacklog');
  var divBacklogContainer = dojo.byId('divBacklogContainer');
  var scrollX = divBacklogContainer.scrollLeft;
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
  
  if(type == 'object'){
	  if(refType == 'UserStory' && dojo.byId('addUserStoryFromBacklog')){
	    dojo.byId('addUserStoryFromBacklog').style.display = '';
	    dojo.byId('addUserStoryFromBacklog').setAttribute('onClick', 'addUserStoryFromBacklog();');
		if(dojo.byId('addEpicFromBacklog')){
		  dojo.byId('addEpicFromBacklog').style.display = 'none';
		  dojo.byId('addEpicFromBacklog').setAttribute('onClick', '');
		}
		if(dojo.byId('addSprintFromBacklog')){
		  dojo.byId('addSprintFromBacklog').style.display = 'none';
		  dojo.byId('addSprintFromBacklog').setAttribute('onClick', '');
		}
	  }
	  if(refType == 'Epic' && dojo.byId('addEpicFromBacklog')){
	    dojo.byId('addEpicFromBacklog').style.display = '';
	    dojo.byId('addEpicFromBacklog').setAttribute('onClick', 'addEpicFromBacklog();');
		if(dojo.byId('addUserStoryFromBacklog')){
		  dojo.byId('addUserStoryFromBacklog').style.display = 'none';
		  dojo.byId('addUserStoryFromBacklog').setAttribute('onClick', '');
		}
		if(dojo.byId('addSprintFromBacklog')){
		  dojo.byId('addSprintFromBacklog').style.display = 'none';
		  dojo.byId('addSprintFromBacklog').setAttribute('onClick', '');
		}
	  }
	  if(dojo.byId('copyFromBacklog')){
	    dojo.byId('copyFromBacklog').style.display = '';
	    dojo.byId('copyFromBacklog').setAttribute('onClick', 'copyObjectFromContextMenu(\''+refId+'\', \''+refType+'\', null, '+idProject+', true);');
	  }
	  if(dojo.byId('editFromBacklog')){
	    dojo.byId('editFromBacklog').style.display = '';
		var refreshAction = (refType == 'Sprint')?'refreshActionAddSprintBacklog':'refreshActionAddItemBacklog';
	    dojo.byId('editFromBacklog').setAttribute('onClick', 'showDetail(\''+refreshAction+'\',1,\''+refType+'\',false,'+refId+');');
	  }
	  if(dojo.byId('addCommentFromBacklog')){
	    dojo.byId('addCommentFromBacklog').style.display = '';
	    dojo.byId('addCommentFromBacklog').setAttribute('onClick', 'activityStreamBacklog(\''+vID+'\', '+refId+', \''+refType+'\', \''+i18n('textareaEnterText')+'\');');
	  }
	  if(dojo.byId('removeFromBacklog')){
	    dojo.byId('removeFromBacklog').style.display = '';
	    dojo.byId('removeFromBacklog').setAttribute('onClick', 'deleteOnBacklogFromContextMenu(\''+refId+'\', \''+refType+'\', true);');
	  } 
	  if(dojo.byId('printFromBacklog')){
	    dojo.byId('printFromBacklog').style.display = '';
	    dojo.byId('printFromBacklog').setAttribute('onClick', 'showPrint(\'objectDetail.php\', \'contextMenu\', null, null, \'P\');');
	  }   
	  if(dojo.byId('printPdfFromBacklog')){
	    dojo.byId('printPdfFromBacklog').style.display = '';
	    dojo.byId('printPdfFromBacklog').setAttribute('onClick', 'showPrint(\'objectDetail.php\', \'contextMenu\', null, \'pdf\', \'P\');');
	  }
	  if(dojo.byId('gotoFromBacklog')){
	    dojo.byId('gotoFromBacklog_label').innerHTML = i18n('diaryGotoItem', new Array(refType,refId));
	    dojo.byId('gotoFromBacklog').style.display = '';
	    dojo.byId('gotoFromBacklog').setAttribute('onClick', 'gotoElement(\''+refType+'\','+refId+', true);');
	  }
	  if(dojo.byId('gotoSprintListFromBacklog')){
  	  	dojo.byId('gotoSprintListFromBacklog').style.display = 'none';
		dojo.byId('gotoSprintListFromBacklog').setAttribute('onClick', '');
  	  }
  	  if(dojo.byId('gotoSprintBacklogFromBacklog')){
  		dojo.byId('gotoSprintBacklogFromBacklog').style.display = 'none';
		dojo.byId('gotoSprintBacklogFromBacklog').setAttribute('onClick', '');
  	  }
  }else{
	  if(dojo.byId('addUserStoryFromBacklog')){
	    dojo.byId('addUserStoryFromBacklog').style.display = 'none';
	    dojo.byId('addUserStoryFromBacklog').setAttribute('onClick', '');
	  }
	  if(dojo.byId('addEpicFromBacklog')){
	    dojo.byId('addEpicFromBacklog').style.display = 'none';
	    dojo.byId('addEpicFromBacklog').setAttribute('onClick', '');
	  }
	  if(dojo.byId('addSprintFromBacklog')){
	    dojo.byId('addSprintFromBacklog').style.display = 'none';
	    dojo.byId('addSprintFromBacklog').setAttribute('onClick', '');
	  }
	  if(dojo.byId('copyFromBacklog')){
	    dojo.byId('copyFromBacklog').style.display = 'none';
	    dojo.byId('copyFromBacklog').setAttribute('onClick', '');
	  }
	  if(dojo.byId('editFromBacklog')){
	    dojo.byId('editFromBacklog').style.display = 'none';
	    dojo.byId('editFromBacklog').setAttribute('onClick', '');
	  }
	  if(dojo.byId('addCommentFromBacklog')){
	    dojo.byId('addCommentFromBacklog').style.display = 'none';
	    dojo.byId('addCommentFromBacklog').setAttribute('onClick', '');
	  }
	  if(dojo.byId('removeFromBacklog')){
	    dojo.byId('removeFromBacklog').style.display = 'none';
	    dojo.byId('removeFromBacklog').setAttribute('onClick', '');
	  } 
	  if(dojo.byId('printFromBacklog')){
	    dojo.byId('printFromBacklog').style.display = 'none';
	    dojo.byId('printFromBacklog').setAttribute('onClick', '');
	  }   
	  if(dojo.byId('printPdfFromBacklog')){
	    dojo.byId('printPdfFromBacklog').style.display = 'none';
	    dojo.byId('printPdfFromBacklog').setAttribute('onClick', '');
	  }
	  if(dojo.byId('gotoFromBacklog')){
	    dojo.byId('gotoFromBacklog_label').innerHTML = '';
	    dojo.byId('gotoFromBacklog').style.display = 'none';
	    dojo.byId('gotoFromBacklog').setAttribute('onClick', '');
	  }
	  if(refType == 'Sprint' && dojo.byId('addSprintFromBacklog')){
  	    dojo.byId('addSprintFromBacklog').style.display = '';
  	    dojo.byId('addSprintFromBacklog').setAttribute('onClick', 'addSprintFromBacklog();');
  		if(dojo.byId('addEpicFromBacklog')){
  		  dojo.byId('addEpicFromBacklog').style.display = 'none';
  		  dojo.byId('addEpicFromBacklog').setAttribute('onClick', '');
  		}
  		if(dojo.byId('addUserStoryFromBacklog')){
  		  dojo.byId('addUserStoryFromBacklog').style.display = 'none';
  		  dojo.byId('addUserStoryFromBacklog').setAttribute('onClick', '');
  		}
  	  }
	  if(dojo.byId('gotoSprintListFromBacklog')){
	  	dojo.byId('gotoSprintListFromBacklog').style.display = '';
		dojo.byId('gotoSprintListFromBacklog_label').innerHTML = i18n('diaryGotoItem', new Array(refType,refId));
	  	dojo.byId('gotoSprintListFromBacklog').setAttribute('onClick', 'gotoElement(\''+refType+'\','+refId+', true);');
	  }
	  if(dojo.byId('gotoSprintBacklogFromBacklog')){
		dojo.byId('gotoSprintBacklogFromBacklog').style.display = '';
		dojo.byId('gotoSprintBacklogFromBacklog').setAttribute('onClick', 'gotoSprintBacklog('+refId+');');
	  }
  }
  
  contextMenu.openDropDown();
  contextMenuDiv.focus();
}

//==================================================================
//Backlog ContextMenu
//==================================================================
var BacklogTooltip = (function () {
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
    node.id = "backlogGlobalTooltip";
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
//Draw Backlog using jsBacklog
//==================================================================

function drawAgileBacklog(typeBacklog, onlyRefresh) {
if (onlyRefresh==undefined) onlyRefresh=false;

// Only first display, refresh JSBacklog object
if (!onlyRefresh) {
   blg = new JSBacklog.Backlog(typeBacklog);
}

jsonData = getJsonBacklogData(typeBacklog);

//// Error in jsonData
if (jsonData.innerHTML.indexOf('{"identifier"') < 0 || jsonData.innerHTML.indexOf('{"identifier":"id", "items":[ ],"totalRows":"0"')>=0) {
   dojo.query('#divBacklogContainer .sectionBadge').forEach(function(node){
	node.innerHTML=0;
   });
   dojo.query('#divBacklogContainer .backlogColumnBody').forEach(function(node){
   	node.innerHTML=null;
   });
   hideWait();
   return;
}

// Parse the jsonData and set Store values
  if (blg && jsonData) {
   try {
     var store = eval('(' + jsonData.innerHTML + ')');
   } catch(e) {
     consoleTraceLog("ERROR Parsing jsonData in drawAgileBacklog()");
     consoleTraceLog(jsonData.innerHTML);
     hideWait();
     return;
   }
   blg.clearRefreshBacklogColumn();
   var columns = store.items;
   // Treat all lines
   for (var i = 0; i < columns.length; i++) {
     var column = columns[i];
     var newBacklogColumn=new JSBacklog.BacklogColumn(column);
	 if (dojo.byId(newBacklogColumn.getColumnName())){
		var colNode = dojo.byId(newBacklogColumn.getColumnName());
		colNode.innerHTML = '';
	 }
     if (onlyRefresh==true){
	   blg.ReplaceBacklogColumn(newBacklogColumn);
       blg.RefreshBacklogColumn(newBacklogColumn);
     }else{
       blg.AddBacklogColumn(newBacklogColumn);
     }
	 blg.setBacklogColumnItemCount(newBacklogColumn.getID());
	 if (dojo.byId(newBacklogColumn.getColumnBadgeName())){
		dojo.byId(newBacklogColumn.getColumnBadgeName()).innerHTML = newBacklogColumn.getItemCount();
	 }
	 blg.setBacklogColumnStoryPointAndBusinessValue(newBacklogColumn.getID());
	 if(dojo.byId(newBacklogColumn.getColumnStoryPointsName()) && dojo.byId(newBacklogColumn.getColumnBusinessValuesName())){
		dojo.byId(newBacklogColumn.getColumnStoryPointsName()).innerHTML = newBacklogColumn.getStoryPoints();
		dojo.byId(newBacklogColumn.getColumnBusinessValuesName()).innerHTML = newBacklogColumn.getBusinessValues();
	 }
   }
   blg.Draw(onlyRefresh);
   filterBacklog();
  } else {
   return;
  }
}