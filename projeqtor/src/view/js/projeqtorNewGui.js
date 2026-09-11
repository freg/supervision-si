/*******************************************************************************
 * COPYRIGHT NOTICE *
 * 
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 * 
 * This file is part of ProjeQtOr.
 * 
 * ProjeQtOr is free software: you can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the Free Software
 * Foundation, either version 3 of the License, or (at your option) any later
 * version.
 * 
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
 * A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.
 * 
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 * 
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org
 * 
 * DO NOT REMOVE THIS NOTICE **
 ******************************************************************************/

// ============================================================================
// All specific ProjeQtOr functions and variables
// This file is included in the main.php page, to be reachable in every context
// ============================================================================
// =============================================================================
// = Variables (global)
// =============================================================================
//var i18nMessages = null; // array containing i18n messages
//var i18nMessagesCustom = null; // array containing i18n messages
//var currentLocale = null; // the locale, from browser or user set
//var browserLocale = null; // the locale, from browser
//var cancelRecursiveChange_OnGoingChange = false; // boolean to avoid
// recursive change trigger
//var formChangeInProgress = false; // boolean to avoid exit from form when
// changes are not saved
//var currentRow = null; // the row num of the current selected
// element in the main grid
//var currentFieldId = ''; // Id of the ciurrent form field (got
// via onFocus)
//var currentFieldValue = ''; // Value of the current form field (got
// via onFocus)
//var g; // Gant chart for JsGantt : must be
// named "g"
//var quitConfirmed = false;
//var noDisconnect = false;
//var forceRefreshMenu = false;
//var directAccessIndex = null;

//var debugPerf = new Array();

//var pluginMenuPage = new Array();
//
//var previousSelectedProject=null;
//var previousSelectedProjectName=null;
//
//var mustApplyFilter=false;
//
//var arraySelectedProject = new Array();
//
//var displayFilterVersionPlanning='0';
//var displayFilterComponentVersionPlanning='0';
//
//var contentPaneResizingInProgress={};
//
//var defaultMenu=null;

//=============================================================================
//function for close/open left Menu 
//
// ticket 4965 Florent
//=============================================================================

;( function(window) {
  function menuLeft(menu) {  
    this.el = menu;
    this._init();
  }

  menuLeft.prototype = {
    _init : function() {
      this.menuRight=dojo.byId('menuBarVisibleDiv');
      this.trigger = dojo.byId( 'hideStreamNewGui' );
      this.isMenuOpen =dojo.byId('isMenuLeftOpen').value; //replace to datatsession;
      //divButton
      this.hidStreamButtonTopBar= document.createElement('div');
      this.hidStreamButtonTopBar.className = 'hideStreamNewGuiTopBar';
      this.hidStreamButtonTopBar.setAttribute('id', 'hideStreamNewGuiTopBar');
      this.hidStreamButtonTopBar.setAttribute('style', ((this.isMenuOpen=='false')?'float:left;width:32px;display:block;':'display:none;'));
      
      //incon
      this.hidStreamButtonTopBarIcon = document.createElement('div');
      this.hidStreamButtonTopBarIcon.className = 'iconHideMenuRight iconSize32';
      //insert in menuBar
      this.menuRight.insertAdjacentElement('afterbegin', this.hidStreamButtonTopBar);
      this.hidStreamButtonTopBar.insertAdjacentElement('afterbegin',  this.hidStreamButtonTopBarIcon);
      
      this.triggerBar = dojo.byId( 'hideStreamNewGuiTopBar' );
      this.eventtype ='click';
      this.menuLinks = dojo.query('.menu__linkDirect');
      this.pinButton = dojo.byId('autoHideMenuIcon');
      this.autoHideMenu = (dojo.byId( 'modePin' ).value == 'true') ? true : false;
      this._initEvents();
    },
    
    _initEvents : function() {
      var self = this;
      this.isInit=false;
      
      if (this.autoHideMenu == true) {
        this.triggerBar.addEventListener( "mouseover", menuOpenEventMouseOver, true );
        this.triggerBar.addEventListener("mouseout", menuOpenEventMouseLeave, true);
      } else {
        this.triggerBar.addEventListener( "click", menuOpenEventMouseOver, true );
      }
      
      function menuOpenEventMouseOver( ev ) {
        ev.stopPropagation();
        ev.preventDefault();
        this.timeOutEvent = setTimeout(function () {
          if(self.isMenuOpen=='false' ) {
            self._openMenu();
            document.addEventListener( self.eventtype, self.bodyClickFn );
          }
        },200);        
      };
      
      function menuOpenEventMouseLeave( ev )   {
        ev.stopPropagation();
        ev.preventDefault();
        clearTimeout(this.timeOutEvent);
      };
      
      this.pinButton.addEventListener("click", function(ev) {
        if(self.autoHideMenu){
          self.pinButton.removeAttribute('class');
          self.pinButton.setAttribute('class', 'autoHideMenuOff iconSize16');
          self.autoHideMenu = false;
          self.triggerBar.removeEventListener( "mouseover", menuOpenEventMouseOver,true );
          self.triggerBar.removeEventListener("mouseout", menuOpenEventMouseLeave, true);
          self.hidStreamButtonTopBar.setAttribute('style', ((self.isMenuOpen=='false')?'float:left;width:32px;display:block;':'display:none;'));
          if (dojo.byId('globalTopCenterDiv').style.left == "0px"){
            self._setSize();  
          }
          saveDataToSession('pinMode',false,true);
        }else{
          self.pinButton.removeAttribute('class');
          self.pinButton.setAttribute('class', 'autoHideMenuOn iconSize16');
          self.autoHideMenu = true;
          self.triggerBar.addEventListener( "mouseover", menuOpenEventMouseOver, true );
          self.triggerBar.addEventListener("mouseout", menuOpenEventMouseLeave, true);
          saveDataToSession('pinMode',true,true);
        }
      });
      
      this.menuLinks.forEach(function(link, pos) {
        link.addEventListener( "click", function( ev ) {
          ev.stopPropagation();
          ev.preventDefault();
          if (self.autoHideMenu) {
            self._closeMenu();
            document.removeEventListener( self.eventtype, self.bodyClickFn );
          }
        });
      });
      
      this.trigger.addEventListener( this.eventtype, function( ev ) {
        ev.stopPropagation();
        ev.preventDefault();
        if( self.isMenuOpen=='true' ) {
          self._closeMenu();
          document.removeEventListener( self.eventtype, self.bodyClickFn );
        }
      } );
      this.triggerBar.addEventListener( this.eventtype, function( ev ) {
        ev.stopPropagation();
        ev.preventDefault();
        if(self.isMenuOpen=='false' ) {
          self._openMenu();
          document.addEventListener( self.eventtype, self.bodyClickFn );
        }
      } );
    },
    
    _openMenu : function() {
      if(this.isMenuOpen=='true') return;
      this.isMenuOpen = 'true'; //replace to datatsession;
      this._setSize();
      this._showHideButton();
      saveDataToSession('isMenuLeftOpen','true', true);
      setTimeout("kawaMsgShow();",1000);
    },
    
    _closeMenu : function() {
      if(this.isMenuOpen=='false') return;
      this.isMenuOpen = 'false';//replace to datatsession;
      this._setSize();
      this._showHideButton();
      saveDataToSession('isMenuLeftOpen','false', true);
	  setTimeout(function() {
	    document.querySelectorAll('canvas[id^="timeline-"]').forEach(function(canvas) {
	      const event = new Event('resize');
	      window.dispatchEvent(event);
	    });
	  }, 300); 
    },
    
    _showHideButton : function(){
      dojo.removeAttr('hideStreamNewGui','style');
      dojo.removeAttr('contentMenuBar','style');
      dojo.removeAttr('hideStreamNewGuiTopBar','style');
      if(this.isMenuOpen=='true'){
        dojo.byId('hideStreamNewGui').setAttribute('style','display:block;float:right;');
        if (this.autoHideMenu == false || !dojo.byId('mainDivContainer')) {
          dojo.byId('hideStreamNewGuiTopBar').setAttribute('style','display:none;');
        } else {
          dojo.byId('hideStreamNewGuiTopBar').setAttribute('style','float:left;width:32px;display:block;');
        }
        dojo.byId('hideMenuLeftMargin').style.display = 'none';
        dojo.byId('isMenuLeftOpen').value = 'true';
      }else{
        dojo.byId('hideStreamNewGui').setAttribute('style','display:none;');
        dojo.byId('hideStreamNewGuiTopBar').setAttribute('style','float:left;width:32px;display:block;');
        dojo.byId('hideMenuLeftMargin').style.display = '';
        dojo.byId('isMenuLeftOpen').value = 'false';
      }
      dojo.setAttr('contentMenuBar','style','top:1px; overflow:hidden; z-index:0');
    },
    
    _setSize :function(){
      // A Planning & Work Plan pane resize is emitted asynchronously after the
      // menu animation. Keep its detail-refresh handler disabled for the whole
      // animation cycle, not just while the dimensions are being changed.
      this.skipPlanningWorkPlanRefreshUntil=Date.now()+1200;
      if (dojo.byId('autoHideMenuIcon').className.includes('autoHideMenuOff') ) var globalWidth=(this.isMenuOpen=='true') ? dojo.byId('mainDiv').offsetWidth-250 : dojo.byId('mainDiv').offsetWidth;
      else var globalWidth=dojo.byId('mainDiv').offsetWidth;
      duration=this._resizeDiv (globalWidth);
      this._resizeGlobalContainer(duration);
     },
    
    _resizeDiv : function(globalWidth){
      var isObject=true;
      closeOpenLeftMenu=true;
      var hideDetail=false;
      if(dojo.byId('objectClass') && dojo.byId('mainDivContainer') && dojo.byId('contentDetailDiv')){
          var mainDivHeight= dojo.byId('mainDivContainer').offsetHeight;
          var detailHeight=dojo.byId("contentDetailDiv").offsetHeight;
          if(dojo.attr(dojo.byId("listDiv"),"region")=='top'){
           var listDivHeight=mainDivHeight - detailHeight-5;
           var listDivWidth=globalWidth-20;

           var detailWidth=dojo.byId("contentDetailDiv").offsetWidth;        
           if(detailWidth==0) hideDetail=true;
           if (this.autoHideMenu == "false") {
             var detailLeft=(this.isMenuOpen=='true')? dojo.byId("contentDetailDiv").offsetLeft-250 : dojo.byId("contentDetailDiv").offsetLeft+250;
           } else {
             var detailLeft= dojo.byId("mainDiv").offsetLeft;
           }
           var mainDivContainerWith=dojo.byId('mainDiv').offsetWidth+1;
           listDivWidth=mainDivContainerWith-1;
           detailWidth=mainDivContainerWith;
          }else {
            if (this.autoHideMenu===false || dojo.byId("globalTopCenterDiv").offsetLeft==250) {
              var detailWidth=dojo.byId("contentDetailDiv").offsetWidth;
              if(detailWidth==0)hideDetail=true;
              if(dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value == 'PlanningWorkPlan')detailWidth=0;
              var detailLeft=(this.isMenuOpen=='true')? dojo.byId("contentDetailDiv").offsetLeft-250 : dojo.byId("contentDetailDiv").offsetLeft+250;
              var listDivWidth=(this.isMenuOpen=='true')? (dojo.byId('mainDivContainer').offsetWidth-250) - detailWidth -5: (dojo.byId('mainDivContainer').offsetWidth+250) - detailWidth-5;
              var listDivHeight=mainDivHeight;
              var mainDivContainerWith=listDivWidth+detailWidth+5;
              if(dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value == 'PlanningWorkPlan')detailWidth=dojo.byId("contentDetailDiv").offsetWidth;;
              if(hideDetail)listDivWidth+=5;
            }
          }
        var currentScreen=(dojo.byId('objectClassManual'))?dojo.byId('objectClassManual').value:'Object';
        if(tabPlanView.includes(currentScreen)){
          isObject=false;
          if(coverListAction!='CLOSE' && (detailWidth==0 || detailHeight==0 ))setActionCoverListNonObj('CLOSE',false);
        }
        
      }
      var contentPaneNode=(document.querySelector('[id^="dijit_layout_ContentPane_"'))?document.querySelector('[id^="dijit_layout_ContentPane_"'):document.querySelector('[id^="dijit_layout_BorderContainer_"');
      var duration=200;
      if(dojo.byId('objectClass')&& dojo.byId('mainDivContainer') && dojo.byId("contentDetailDiv")){
          dojox.fx.combine([ dojox.fx.animateProperty({
            node : "menuTop",
            properties : {
              width : globalWidth,
            },
            duration : duration
          }), dojox.fx.animateProperty({
            node : "leftMenu",
            properties : {
              width : { start:(this.isMenuOpen=='true')? 0 : 250 ,
                        end:(this.isMenuOpen=='true')? 250 : 0}
            },
            duration : duration
          }), dojox.fx.animateProperty({
            node : "leftDiv",
            properties : {
              width : { start:(this.isMenuOpen=='true')? 0 : 250 ,
                        end:(this.isMenuOpen=='true')? 250 : 0}
            },
            duration : duration
          }),dojox.fx.animateProperty({
            node : "menuLeftBarContaineur",
            properties : {
              width :{ start:(this.isMenuOpen=='true')?  0 : 250,
                       end:(this.isMenuOpen=='true')? 250 :0 }
            },
            duration : duration
          })
          , dojox.fx.animateProperty({
            node : "globalTopCenterDiv",
            properties : {
              width : globalWidth,
              left: { start:(this.isMenuOpen=='true' || dojo.byId('autoHideMenuIcon').className.includes('autoHideMenuOn') )? 0 : 250 ,
                      end:(this.isMenuOpen=='true' && dojo.byId('autoHideMenuIcon').className.includes('autoHideMenuOff') )? 250 : 0}
            },
            duration : duration
          })
          ,dojox.fx.animateProperty({
            node : "statusBarDiv",
            properties : {
              width : globalWidth,
            },
            duration : duration
          })
          , dojox.fx.animateProperty({
            node : "centerDiv",
            properties : {
              width : globalWidth,
              left:0
            },
            duration : duration
          })
          , dojox.fx.animateProperty({
            node : "listDiv_splitter",
            properties : {
              left : (hideDetail)?detailLeft:detailLeft-5,
            },
            duration : duration
          })
          ,  dojox.fx.animateProperty({
            node : "statusBarDivBottom",
            properties : {
              width : globalWidth,
            },
            duration : duration
          })
          , dojox.fx.animateProperty({
          node : "mainDivContainer",
          properties : {
            width :mainDivContainerWith ,
          },
          duration : duration
        })
        , dojox.fx.animateProperty({
          node : contentPaneNode,
          properties : {
            width :mainDivContainerWith,
          },
          duration : duration
        })
        , dojox.fx.animateProperty({
          node :  document.querySelector('[id^="dijit_layout_BorderContainer_"'),
          properties : {
            width :mainDivContainerWith,
          },
          duration : duration
        })
          , dojox.fx.animateProperty({
            node : "listDiv",
            properties : {
              width :listDivWidth ,
              height :listDivHeight,
            },
            duration : duration
          })
          ,dojox.fx.animateProperty({
            node : "contentDetailDiv",
            properties : {
              width : detailWidth,
              height :detailHeight,
              left : detailLeft
            },
            duration : duration
          })
          ,dojox.fx.animateProperty({
            node : "globalContainer",
            properties : {
              width :(this.isMenuOpen=='true')? globalWidth+250 : globalWidth ,
            },
            duration : duration
          })
          
        ]).play();
        setTimeout("if (dojo.byId('detailDiv').offsetWidth<dojo.byId('contentDetailDiv').offsetWidth-20) dijit.byId('contentDetailDiv').resize();",duration+50);

      }else{
          dojox.fx.combine([ dojox.fx.animateProperty({
            node : "menuTop",
            properties : {
              width : globalWidth,
            },
            duration : duration
          }), dojox.fx.animateProperty({
            node : "leftMenu",
            properties : {
              width : { start:(this.isMenuOpen=='true')? 0 : 250 ,end:(this.isMenuOpen=='true')? 250 : 0}
            },
            duration : duration
          }), dojox.fx.animateProperty({
            node : "leftDiv",
            properties : {
              width : { start:(this.isMenuOpen=='true')? 0 : 250 ,end:(this.isMenuOpen=='true')? 250 : 0}
            },
            duration : duration
          }), dojox.fx.animateProperty({
            node : "globalTopCenterDiv",
            properties : {
              width : globalWidth,
              left: { start:(this.isMenuOpen=='true' || dojo.byId('autoHideMenuIcon').className.includes('autoHideMenuOn') )? 0 : 250 ,end:(this.isMenuOpen=='true' &&  dojo.byId('autoHideMenuIcon').className.includes('autoHideMenuOff') )? 250 : 0}
            },
            duration : duration
          }), dojox.fx.animateProperty({
            node : "centerDiv",
            properties : {
              width : globalWidth,
              left: { start:(this.isMenuOpen=='true' || dojo.byId('autoHideMenuIcon').className.includes('autoHideMenuOn')  )? 0 : -250 ,end:(this.isMenuOpen=='true'  &&  dojo.byId('autoHideMenuIcon').className.includes('autoHideMenuOff') )? 0 : 0}
            },
            duration : duration
          }),dojox.fx.animateProperty({
            node : "menuLeftBarContaineur",
            properties : {
              width :{ start:(this.isMenuOpen=='true')?  0 : 250,end:(this.isMenuOpen=='true')? 250 :0 }
            },
            duration : duration
          }), dojox.fx.animateProperty({
            node : "statusBarDiv",
            properties : {
              width : globalWidth,
            },
            duration : duration
          }),  dojox.fx.animateProperty({
            node : "statusBarDivBottom",
            properties : {
              width : globalWidth,
//              left: { start:(this.isMenuOpen=='true'  || dojo.byId('autoHideMenuIcon').className.includes('autoHideMenuOn') )? 0 : 250 ,end:(this.isMenuOpen=='true'  &&  dojo.byId('autoHideMenuIcon').className.includes('autoHideMenuOff') )? 250 : 0}
            },
            duration : duration
          })
        ]).play();
      } 
        
      if(dojo.byId('todayClassicView') && dojo.byId('todayActStream')){
        var todayActStreamWidth=(dojo.byId('todayActStreamIsActive').value=='true')? 0 : parseInt(dojo.byId('defaultTodayActStreamWidth').value);
        var todayClassicViwWidth=(globalWidth-20)-todayActStreamWidth;
        if(todayActStreamWidth==0){
            dojox.fx.combine([ dojox.fx.animateProperty({
            node : "todayClassicView",
            properties : {
              width : todayClassicViwWidth,
              left: { start:(this.isMenuOpen=='true')? 0 : 250 ,end:(this.isMenuOpen=='true')? 250 : 0}
            },
            duration : duration
          }), dojox.fx.animateProperty({
            node : "todayActStream",
            properties : {
              width : todayActStreamWidth,
              left: { start:(this.isMenuOpen=='true')? 0 : 250 ,end:(this.isMenuOpen=='true')? 250 : 0}
            },
            duration : duration
          })]).play();
        }
      }
      return duration;
    },
    
    _resizeGlobalContainer: function (duration){
      if (dojo.byId('mainDivContainer') && dojo.byId('contentDetailDiv')) {
  			if (dojo.byId('autoHideMenuIcon').className.includes('autoHideMenuOn') ) {
          //setTimeout('dojo.byId("globalTopCenterDiv").offsetWidth=dojo.byId("toolBarDiv").offsetWidth+250;dijit.byId("globalContainer").resize();dojo.byId("globalTopCenterDiv").style.left = 0;', duration+50);
  			  setTimeout('dijit.byId("listDiv").resize();dijit.byId("leftDiv").resize();', duration+50);
        } else {
          //var toolBarDivWidth=+dojo.byId("toolBarDiv").offsetWidth;
          setTimeout('dijit.byId("globalContainer").resize();', duration+50);
          if(dojo.byId('contentDetailDiv').style.width == '0px'){
            setTimeout('refreshTimeline();', duration+50);
          }
        }
      } else {
        if (dojo.byId('autoHideMenuIcon').className.includes('autoHideMenuOn') ) {
          //setTimeout('dojo.byId("globalTopCenterDiv").offsetWidth=dojo.byId("toolBarDiv").offsetWidth+250;dijit.byId("globalContainer").resize();dojo.byId("globalTopCenterDiv").style.left = 0;', duration+50);
          setTimeout('dijit.byId("centerDiv").resize();dijit.byId("leftDiv").resize();', duration+50);
        } else {
          //var toolBarDivWidth=+dojo.byId("toolBarDiv").offsetWidth;
          setTimeout('dijit.byId("globalContainer").resize();', duration+50);
        }
      }
			if(dojo.byId('dndListToday')) setTimeout(resizeTodayLayoutWidgets, duration+50);
			setTimeout('closeOpenLeftMenu=false',duration+400) ;
    }
  };
  
  window.menuLeft = menuLeft;

} )(window);


//=============================================================================
//add remove favoris 
//=============================================================================
function addRemoveFavMenuLeft (id,name,mode,type,idRow){
  var items=dojo.byId('ml-menu').querySelectorAll('#'+id);
  items.forEach(function(el){
  el.removeAttribute('class');
  el.removeAttribute('onclick');
  });
  if(mode=='add'){
     var isReport=(type=="reportDirect")?'true':'false';
      var func= "addRemoveFavMenuLeft('"+id+"','"+name+"','remove','"+type+"')";
      var menuName=(isReport=='true')?name:name.substr(4);
      var param="?operation=add&class="+menuName+"&isReport="+isReport;
      dojo.xhrGet({
        url : "../tool/saveCustomMenu.php"+param+addTokenIndexToUrl(),
        handleAs : "text",
        load : function(data, args) {
        	menuNewGuiFilter('menuBarCustom', null);
        },
      });
      items.forEach(function(el){
        el.setAttribute('onclick',func);
        el.setAttribute('class','menu__as__Fav');
      });
  }else{
  var isReport=(type=="reportDirect")?'true':'false';
  var func= "addRemoveFavMenuLeft('"+id+"','"+name+"','add','"+type+"')";
  var menuName=(isReport=='true')?name:name.substr(4);
  var param="?operation=remove&class="+menuName+"&isReport="+isReport+"&idRow="+idRow;
  dojo.xhrGet({
    url : "../tool/saveCustomMenu.php"+param+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
    	menuNewGuiFilter('menuBarCustom', null);
    },
  });
  items.forEach(function(el){
    el.setAttribute('onclick',func);
    el.setAttribute('class','menu__add__Fav');
  
  });
  }
}

//=============================================================================
//show icons on menu left 
//=============================================================================
function showIconLeftMenu(){
  var leftMenu=dojo.byId('ml-menu');
  var divMenuSearch=leftMenu.querySelector('.menu__searchMenuDiv ');
  var mode=dojo.byId('displayModeLeftMenu').value;
  display=(mode=='ICONTXT')?'none':'block';
  style=(mode=='ICONTXT')?"float:left;max-width:180px;":"float:left;max-width:155px;";
  style2=(mode=='ICONTXT')?"float:left;max-width:200px;":"float:left;max-width:165px;";
  leftMenu.menus = [].slice.call(leftMenu.querySelectorAll('.menu__level'));
  leftMenu.menus.forEach(function(menuEl, pos) {
    var items = menuEl.querySelectorAll('.menu__item');
    items.forEach(function(itemEl) {
      var iconDiv = itemEl.querySelector('.iconSize16');
      iconDiv.style.display=display;
      
      var posDiv = itemEl.querySelector('.divPosName');
      posDiv.style=(itemEl.querySelector('.menuPluginToInstall'))?style2:style;
    });
  });
  if(dojo.byId('menuSearchDiv').value.trim()!=''){
    var menus=divMenuSearch.querySelectorAll('.menu__item');
    menus.forEach(function(menuCopyEl, pos) {
        var iconDivCopy = menuCopyEl.querySelector('.iconSize16');
        iconDivCopy.style.display=display;
        var posDivCopy = menuCopyEl.querySelector('.divPosName');
        posDivCopy.style=(menuCopyEl.querySelector('.menuPluginToInstall'))?style2:style;
    });
  }

  if(dojo.byId('selectedViewMenu').value=='Parameter'){
    if(dojo.byId('parameterMenu')){
      var menuParam=dojo.byId('parameterMenu').querySelectorAll('.menu__item');
      menuParam.forEach(function(e){
       var icon=e.querySelector('.iconSize16');
       icon.style.display=display;
      });
    }
  }
  mode=(display=='block')?'ICONTXT':'TXT';
  dojo.setAttr('displayModeLeftMenu','value',mode);
  saveDataToSession('menuLeftDisplayMode',mode,true);
}

//=============================================================================
//show bottom content on menu left 
//=============================================================================
function showBottomContent (menu){
  if(menu==dojo.byId('selectedViewMenu').value)return;
  menuAcces=dojo.byId('menuPersonalAcces');
  var asSelect=menuAcces.querySelector('.iconBreadSrumbSelect');
  if(asSelect){
    classie.remove(asSelect,'iconBreadSrumbSelect');
  }
  classie.add(dojo.byId('button'+menu),'iconBreadSrumbSelect');
  saveDataToSession('bottomMenuDivItemSelect',menu,true);
  if(menu!='Console'){
    dojo.byId('messageDivNewGui').style.display='none';
    dojo.byId('loadDivBarBottom').style.display='block';
  }
  if(menu!='Kawa'){
    dojo.byId('kawaDivNewGui').style.display='none';
  }
  var items=dojo.byId('loadDivBarBottom');
  var alldiv=items.querySelectorAll('.menuBottomDiv');
  alldiv.forEach(function(el){
    el.style.display='none';
  });
  dojo.setAttr('selectedViewMenu','value',menu);
  switch(menu){
    case 'Parameter':
        var menuLeftTop=dojo.byId('ml-menu');
        var menuSelected=menuLeftTop.querySelector('.menu__link--current');
        if(menuSelected!=null){
          var onclick=menuSelected.getAttribute('onclick');
          var isObject=(onclick.includes('loadMenuBarItem'))?'false':'true';
          var id=(menuSelected.id.indexOf('report')!=-1)?'Report':menuSelected.id.substr(4);
          showMenuBottomParam(id,isObject);
        }
        dojo.byId('parameterDiv').style.display='block';
      break;
    case 'Link':
      dojo.byId('projectLinkDiv').style.display='block';
      break;
    case 'Document':
      dojo.byId('documentsDiv').style.display='block';
      dojo.byId('documentDirectoryTree').style.height="auto";
      dojo.byId('documentDirectoryTree').style.width="auto";
      dijit.byId('documentsDiv').resize();
      break;
    case 'Notification':
      dojo.byId('notificationBottom').style.display='block';
      dijit.byId('notificationBottom').resize();
      break;
    case 'Console':
      items.style.display='none';
      dojo.byId('messageDivNewGui').style.display='block';
      break;
    case 'Kawa':
      items.style.display='none';
      if (!isHosted) dojo.byId('kawaDivNewGui').style.display='block';
      break;
  }
  
}

//=============================================================================
//load reports  
//=============================================================================
function loadMenuReportDirect(cate,idReport,lstRepId,file){
 
  if (checkFormChangeInProgress()) {
    return false;
  }
  setActionCoverListNonObj('CLOSE',false); 
  item="Reports";
  cleanContent("detailDiv");
  hideResultDivs();
  formChangeInProgress=false;
  var currentScreen=item;
  var objectExist='false';
  var repList=(lstRepId!='')?'&lstRepId='+lstRepId:'';
  var nameCat=(file!='')?'&nameSubCat='+file:'';
  loadContent("reportsMain.php?idCategory="+cate+repList+nameCat, "centerDiv");
  loadDiv("menuUserScreenOrganization.php?currentScreen="+currentScreen+'&objectExist='+objectExist,"mainDivMenu");
  stockHistory(item,null,currentScreen);
  if(defaultMenu == 'menuBarRecent'){
    menuNewGuiFilter(defaultMenu, item);
  }
  editFavoriteRow(true);
  selectIconMenuBar(item);
  setTimeout('reportSelectReport('+idReport+')',500);
  return true;
}
  

//=============================================================================
//show menu prameter on bottom left menu  
//=============================================================================
function showMenuBottomParam(item,isObject){
  if(dojo.byId('selectedViewMenu') && dojo.byId('selectedViewMenu').value=='Parameter'){
    var execute=true;
    if(dojo.byId('menuParamDisplay')){
      execute=(dojo.byId('menuParamDisplay').value!=menuSelect)?true:false;
    }
    var menuSelect = dojo.byId('selectedScreen').value;
    if(item!=menuSelect && execute==true ){
      loadContent("../tool/drawBottomParameterMenu.php?currentScreen="+item+'&isObject='+isObject,"parameterDiv");
    }
    dojo.setAttr('selectedScreen','value',item);
  }
}

//=============================================================================
//refresh selected menu on Menu left 
//=============================================================================
function refreshSelectedMenuLeft(menuName){
  var menuLeftTop=dojo.byId('ml-menu');
  var divMenuSearch=leftMenu.querySelector('.menu__searchMenuDiv ');
  if(dojo.byId('parameterMenu'))var menuLeftBottom=dojo.byId('parameterMenu');
  
  var curents=menuLeftTop.querySelectorAll('.menu__link--current');
  curents.forEach(function(el){
    classie.remove(el,'menu__link--current');
  });
  var newCurrents=menuLeftTop.querySelectorAll('#'+menuName);
  newCurrents.forEach(function(e){
    classie.add(e,'menu__link--current');
  });
  if(dojo.byId('parameterMenu')){
    var bootomMenuSelcet=menuLeftBottom.querySelector('.menu__link--current');
    if(bootomMenuSelcet!=null){
      classie.remove(bootomMenuSelcet, 'menu__link--current');
    }
    var newMenuBottomSelect=menuLeftBottom.querySelector('#'+menuName+'Param');
    if(newMenuBottomSelect!=null) classie.add(newMenuBottomSelect,'menu__link--current');
  }
  if(dojo.byId('menuSearchDiv').value.trim()!=''){
    var searchMenuSelcet=divMenuSearch.querySelector('.menu__link--current');
    if(searchMenuSelcet!=null){
      classie.remove(searchMenuSelcet, 'menu__link--current');
    }
    var newSearchMenuSelect=divMenuSearch.querySelector('#'+menuName);
    if(newSearchMenuSelect!=null) classie.add(newSearchMenuSelect,'menu__link--current');
  }
}
//=============================================================================
//load plugin page for not intaled plugins 
//=============================================================================
function loadPluginView(id){
  setActionCoverListNonObj('CLOSE',false); 
  loadContent("pluginShopView.php?objectId="+id,"centerDiv");
}

function directionExternalPage (page){
  window.open(page, '_blank');
}
//=============================================================================


//=============================================================================
//load plugin page for not intaled plugins 
//=============================================================================
//=============================================================================
function changePasswordType(old){
  if(!old){
    var newPw=dojo.byId('dojox_form__NewPWBox_0'),
    veryPw=dojo.byId('dojox_form__VerifyPWBox_0');
    if(newPw.getAttribute('type')=='password' && veryPw.getAttribute('type')=='password'){
      newPw.setAttribute('type','text');
      veryPw.setAttribute('type','text');
    }else{
      newPw.setAttribute('type','password');
      veryPw.setAttribute('type','password');
    }
  }else{
    var oldPw=dojo.byId('oldPwd');
    if(oldPw.getAttribute('type')=='password'){
      oldPw.setAttribute('type','text');
    }else{
      oldPw.setAttribute('type','password');
    }
  }
}

//=============================================================================
//search menu 
//=============================================================================
function searchMenuToDisplay(val){
  val=val.toUpperCaseWithoutAccent();
  var menuExist= new Array();
  var menuReportExist= new Array();
  var arrayMenuName=new Array();
  var menuLeftTop=dojo.byId('ml-menu');
  var currentDivMenu=menuLeftTop.querySelector('.menu__wrap');
  var menuSearchMenu=menuLeftTop.querySelector('.menu__searchMenuDiv ');
  var clearSearch=dojo.byId('clearSearchMenu');
  
  if(currentDivMenu.style.display!='none' && val.trim()!=''){
    currentDivMenu.setAttribute('style','display:none;');
  }else if(currentDivMenu.style.display=='none' && val.trim()==''){
    currentDivMenu.setAttribute('style','display:block;');
  }
  var testasChild=menuSearchMenu.hasChildNodes();
  if(menuSearchMenu.style.display=='none' && val.trim()!='' && !testasChild){
    menuSearchMenu.setAttribute('style','display:block;');
  }else if(menuSearchMenu.style.display=='block' && val.trim()==''){
    menuSearchMenu.setAttribute('style','display:none;');
  }else if((val.trim()!='' && testasChild )){
    menuSearchMenu.remove();
    var menuSearchMenu=document.createElement('div');
    menuSearchMenu.className='menu__searchMenuDiv ';
    menuSearchMenu.setAttribute('style','display:block');
    menuLeftTop.insertAdjacentElement('beforeEnd',menuSearchMenu );
  }
  if(val.trim()==''){
    clearSearch.style.display='none';
    return;
  }
  if(clearSearch.style.display=='none')clearSearch.style.display='block';
  var menus=menuLeftTop.querySelectorAll('.divPosName');
  var c=0;
  menus.forEach(function(el){
    c++;
    var text=el.innerHTML.toLowerCase();
    text=text.replace('<span style="display:none">','');
    text=text.replace('</span>','');
    menuName="'"+text+"'";
    if(!arrayMenuName.includes(menuName)){
      if(menuName.includes(val.toLowerCase())){
        if(el.parentNode.className=='menu__linkDirect' || el.parentNode.className=='menu__linkDirect menu__link--current'){
          arrayMenuName.push(menuName);
          if(el.parentNode.parentNode.querySelector('#reportFileMenu')){
            var report=el.parentNode.parentNode.cloneNode(true);
            report.setAttribute('onClick','refreshSelectedMenuLeft("'+el.parentNode.id+'")');
            menuReportExist.push(report);
          }else{
            var menu=el.parentNode.parentNode.cloneNode(true);
            menu.setAttribute('onClick','refreshSelectedMenuLeft("'+el.parentNode.id+'")');
            menuExist.push(menu);
          }
        }
      }
    }
  });
  
  menuExist.forEach(function(e){
    menuSearchMenu.insertAdjacentElement('beforeEnd',e);
    e.addEventListener( "click", function( ev ) {
      ev.stopPropagation();
      ev.preventDefault();
      if (dojo.byId('autoHideMenuIcon').className.includes('autoHideMenuOn')) {
        menuLeft.prototype._closeMenu();
        dojo.byId( 'hideStreamNewGuiTopBar' ).addEventListener( "mouseover", function() {
          ev.stopPropagation();
          ev.preventDefault();
          this.timeOutEvent = setTimeout(function () {
            if(menuLeft.prototype.isMenuOpen=='false' ) {
              menuLeft.prototype._openMenu();
              document.addEventListener( self.eventtype, self.bodyClickFn );
            }
          },200); 
        }, true );
        document.removeEventListener( menuLeft.prototype.eventtype, menuLeft.prototype.bodyClickFn );
      }
    });
  });
  
  if(menuReportExist.length!==0){
    if(menuExist.length!==0){
      var reportDiv=document.createElement('div');
      reportDiv.className='sectionReportMenuSearch';
      reportDiv.innerHTML=i18n('menuReports');
      menuSearchMenu.insertAdjacentElement('beforeEnd',reportDiv );
    }

    menuReportExist.forEach(function(e){
      menuSearchMenu.insertAdjacentElement('beforeEnd',e);
    });
  }
}

//=============================================================================
//clear search
//=============================================================================

function clearSearchInputMenuLeft(){
  dojo.byId('menuSearchDiv').value='';
  dojo.byId('clearSearchMenu').style.display='none';
  var menuLeftTop=dojo.byId('ml-menu');
  var currentDivMenu=menuLeftTop.querySelector('.menu__wrap');
  var menuSearchMenu=menuLeftTop.querySelector('.menu__searchMenuDiv ');
  menuSearchMenu.remove();
  var newMenuSearchMenu=document.createElement('div');
  newMenuSearchMenu.className='menu__searchMenuDiv ';
  newMenuSearchMenu.setAttribute('style','display:none');
  menuLeftTop.insertAdjacentElement('beforeEnd',newMenuSearchMenu );
  currentDivMenu.setAttribute('style','display:block;');
}

function clearSearchInputSelectorProject (){
  dojo.byId('projectFilterInput').value = "";
  dojo.byId('projectFilterInput').focus();
  dojo.byId('clearSearchSelectorProject').style.display = 'none';
  filterProjects();
}
//=============================================================================


function helpDisplayIconIsRead (val){
  if(val=='yes'){
    saveUserParameter('helpDisplayIconMesagediv',val);
    dojo.byId('helpDisplayIcon').style.display='none';
  }
}

var menuBarListDivData=null;
var anotherBarContainerData=null;
var menuBarListDivCallback=null;
var anotherBarContainerCallback=null;
var menuNewGuiFilterInProgress=false;
function menuNewGuiFilter(filter, item) {
  if (menuNewGuiFilterInProgress==true) {
    return;
  }
  menuNewGuiFilterInProgress=true;
  saveUserParameter('defaultMenu', filter);
  if(!item)item=dojo.byId('itemSelected').value;
	var historyBar = new Array();
	historyTable.forEach(function(element){
		historyBar.push('menu'+element[0]);
	});
	var callback = function(){
	  //refreshSelectedItem(item, filter);
		if(filter != 'menuBarCustom'){
			dojo.byId('favoriteSwitch').style.display = 'none';
			dojo.addClass('recentButton','imageColorNewGuiSelected');
			dojo.removeClass('favoriteButton','imageColorNewGuiSelected');
		}else{
			dojo.byId('favoriteSwitch').style.display = 'block';
			dojo.addClass('favoriteButton','imageColorNewGuiSelected');
			dojo.removeClass('recentButton','imageColorNewGuiSelected');
		}
    dojo.query('.anotherBarDiv').forEach(function(el){
    	var source = new dojo.dnd.Source(el.id, { accept:["menuBar" ],horizontal:true});
    });
	};
	var hide = function(){
		if(filter == 'menuBarRecent')editFavoriteRow(true);
	};
	var isMenuLeftOpen = dojo.byId('isMenuLeftOpen').value;
	//cleanContent("menuBarListDiv");
	menuBarListDivData=null;
	anotherBarContainerData=null;
	saveUserParameter('defaultMenu', filter);
	defaultMenu=filter;
	loadContent('../view/refreshMenuBarList.php?menuFilter='+filter+'&historyTable='+historyBar, 'menuBarListDiv', null, null, null, null, null, callback, true);
	//cleanContent("anotherBarContainer");
	loadContent('../view/refreshMenuAnotherBarList.php?menuFilter='+filter+'&isMenuLeftOpen='+isMenuLeftOpen, 'anotherBarContainer', null, null, null, null, null, hide, true);
	refreshSelectedItem(item, filter);
	//saveUserParameter('defaultMenu', filter);
	//defaultMenu=filter;
}

function refreshSelectedItem(item, filter){
	dojo.byId('itemSelected').value = item;
	var refreshItem = function(){
		if(item)selectIconMenuBar(item);
	};
	loadDiv('../view/refreshMenuBarButtonFavorite.php?item='+item+'&menuFilter='+filter, 'menuBarFavoriteButton', null, refreshItem);
}

function switchFavoriteRow(idRow, direction, maxRow){
	var nextRow=idRow;
	if(direction=='up'){
		do{
			nextRow -= 1;
			if(nextRow < 1)nextRow=maxRow;
		}while(dojo.byId('menuBarDndSource'+nextRow) && dojo.byId('menuBarDndSource'+nextRow).querySelectorAll('.dojoDndItem').length == 0);
	}else if(direction=='down'){
		do{
			nextRow += 1;
			if(nextRow > maxRow)nextRow=1;
		}while(dojo.byId('menuBarDndSource'+nextRow) && dojo.byId('menuBarDndSource'+nextRow).querySelectorAll('.dojoDndItem').length == 0);
	}else{
		
	}
	var callback = function(){
		saveUserParameter('idFavoriteRow', nextRow);
		menuNewGuiFilter('menuBarCustom', null);
	};
	if(nextRow != idRow){
		loadDiv('../view/refreshMenuBarFavoriteCount.php?idFavoriteRow='+nextRow+'&defaultMenu='+defaultMenu, 'favoriteSwitch', null, callback);
	}else{
		return;
	}
}

function gotoFavoriteRow(idRow, nextRow){
	var row = nextRow;
	//TICKET #10275 - Give the possibilty to select an empty bar of favorite menus
//	if(dojo.byId('menuBarDndSource'+nextRow).querySelectorAll('.dojoDndItem').length == 0){
//		row=idRow;
//	}
	var callback = function(){
		saveUserParameter('idFavoriteRow', nextRow);
		menuNewGuiFilter('menuBarCustom', null);
	};
	if(row != idRow){
		loadDiv('../view/refreshMenuBarFavoriteCount.php?idFavoriteRow='+nextRow+'&defaultMenu='+defaultMenu, 'favoriteSwitch', null, callback);
	}else{
		return;
	}
}

function wheelFavoriteRow(idRow, evt, maxRow){
	if(defaultMenu == 'menuBarRecent')return;
	var nextRow=idRow;
	if(evt.deltaY < 0){
		do{
			nextRow -= 1;
			if(nextRow < 1)nextRow=maxRow;
		}while(dojo.byId('menuBarDndSource'+nextRow) && dojo.byId('menuBarDndSource'+nextRow).querySelectorAll('.dojoDndItem').length == 0);
	}else if(evt.deltaY > 0){
		do{
			nextRow += 1;
			if(nextRow > maxRow)nextRow=1;
		}while(dojo.byId('menuBarDndSource'+nextRow) && dojo.byId('menuBarDndSource'+nextRow).querySelectorAll('.dojoDndItem').length == 0);
	}
	var callback = function(){
		saveUserParameter('idFavoriteRow', nextRow);
		menuNewGuiFilter('menuBarCustom', null);
	};
	if(nextRow != idRow){
		loadDiv('../view/refreshMenuBarFavoriteCount.php?idFavoriteRow='+nextRow+'&defaultMenu='+defaultMenu, 'favoriteSwitch', null, callback);
	}else{
		return;
	}
}


function checkClassForDisplay(el,id,mode){
  element=el.querySelector('#'+id);
  if(mode=='leave'){
    element.setAttribute('style','display:none;');
  }else{
    element.setAttribute('style','display:block;');
  }
}

function editFavoriteRow(hide){
	if(defaultMenu == 'menuBarRecent')return;
	if(dojo.byId('isEditFavorite').value == 'true' || hide){
		dojo.byId('menuBarListDiv').setAttribute('style', 'overflow:hidden;width: 100%;height: 43px;border-left: 1px solid var(--color-dark);');
		dojo.byId('isEditFavorite').value = 'false';
		dojo.byId('anotherBarContainer').style.display = 'none';
	}else{
		dojo.byId('menuBarListDiv').setAttribute('style', 'overflow:hidden;width: 100%;height: 43px;border-radius: 5px;border-left: 1px solid var(--color-dark);');
		dojo.byId('isEditFavorite').value = 'true';
		dojo.byId('anotherBarContainer').style.display = 'block';
	}
}

function resetTodayDiv(){
  var param="?reset=1";
  dojo.xhrGet({
    url : "../tool/saveCustomTodayMenuOrder.php"+param+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
      loadMenuBarItem('Today','Today','bar');
      dijit.byId('dialogNewTodayParameters').hide();
    },
  });
}

function resizeTodayLayoutWidgets(){
  var todayGrid = dojo.byId('dndListToday');
  if (!todayGrid || !dijit.registry) return;

  var widgets = dijit.registry.toArray().filter(function(widget) {
    return widget && widget.domNode
        && typeof widget.resize === 'function'
        && dojo.isDescendant(widget.domNode, todayGrid);
  });

  widgets.sort(function(widgetA, widgetB) {
    var depthA = 0;
    var depthB = 0;
    var node = widgetA.domNode;
    while (node && node !== todayGrid) {
      depthA++;
      node = node.parentNode;
    }
    node = widgetB.domNode;
    while (node && node !== todayGrid) {
      depthB++;
      node = node.parentNode;
    }
    return depthA - depthB;
  });

  var projectsDiv = dojo.byId('Projects');
  var expandedProjectTabHeight = (projectsDiv && projectsDiv.getAttribute('data-expanded') === 'true')
      ? parseInt(projectsDiv.getAttribute('data-expanded-tabH'))
      : 0;

  widgets.forEach(function(widget) {
    if (widget.domNode.offsetWidth === 0 || widget.domNode.offsetHeight === 0) return;

    try {
      var parentNode = widget.domNode.parentNode;
      var parentWidth = parentNode ? dojo.contentBox(parentNode).w : 0;
      if (parentWidth > 0) {
        var resizeBox = {w: parentWidth};
        if (widget.domNode.id === 'todayTab' && expandedProjectTabHeight > 0) {
          resizeBox.h = expandedProjectTabHeight;
        }
        widget.resize(resizeBox);
      } else {
        widget.resize();
      }
    } catch (e) {
      // A widget may disappear while a Today block is being refreshed.
    }
  });
}

function moveTodayDiv(source, target, selection){
  var customArray = new Array();
  var pos = 1;
  dojo.byId(target).querySelectorAll('.dojoDndItem').forEach(function(node){
    var name = node.id;
    if(name.indexOf('dojoUnique') == -1){
      customArray[pos] = name;
      pos++;
    }
  });

  // Moving any block can change the width of several rows in the flex layout.
  setTimeout(resizeTodayLayoutWidgets, 0);
  
  var param="?customArray="+customArray;
  dojo.xhrGet({
    url : "../tool/saveCustomTodayMenuOrder.php"+param+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
      
    },
  });
  
}

function moveMenuBarItem(source, target, selection, copy){
	if(dojo.byId('isEditFavorite').value != 'true')dojo.byId('anotherBarContainer').style.display = 'none';
	dojo.byId('removeMenuDiv').style.visibility = 'hidden';
	var idRow = null;
	var idRowSource = null;
	if(target != 'menuBarDndSource'){
		idRow = target.substr(-1);
	}else{
		idRow = dojo.byId('idFavoriteRow').value;
	}
	if(source != 'menuBarDndSource'){
		idRowSource = source.substr(-1);
	}else{
		idRowSource = dojo.byId('idFavoriteRow').value;
	}
	var customArray = new Array();
	var pos = 1;
	dojo.byId(target).querySelectorAll('.dojoDndItem').forEach(function(node){
		var idItem = node.id;
		var name = idItem.substr(7);
		if(idItem.indexOf('dojoUnique') == -1){
			name = name.split('_')[0];
			customArray[pos] = name;
			pos++;
		}
	});
	if(copy == 'true'){
		var selectedItems = selection.split(',');
		customArray = new Array();
		selectedItems.forEach(function(idItem){
			var name = idItem.substr(7);
			name = name.split('_')[0];
			customArray[pos] = name;
			pos++;
		});
	}
	  var param="?idSourceFrom="+source+"&idSourceTo="+target+"&idRow="+idRow+"&customArray="+customArray+'&defaultMenu='+defaultMenu+'&copy='+copy+'&idRowSource='+idRowSource;
	  dojo.xhrGet({
	    url : "../tool/saveCustomMenuOrder.php"+param+addTokenIndexToUrl(),
	    handleAs : "text",
	    load : function(data, args) {
	    	menuNewGuiFilter('menuBarCustom', null);
	    },
	  });
}

function getSourceSelectedItem(nodes){
	var selectedItem = new Array();
	nodes.forEach(function(item, id, map){
		selectedItem[id]=item.id;
	});
	return selectedItem.toString();
}

function removeMenuBarItem(target, idNode){
	dojo.byId('removeMenuDiv').style.visibility = 'hidden';
	dojo.byId('removeMenuDiv').querySelectorAll('.dojoDndItem').forEach(function(node){
		var name = node.id.substr(7);
		var idName = name.split('_');
		name = idName[0];
		var idRow = idName[1];
		var type = (name.substr(4) == 'menu')?'menu':'reportDirect';
		var id = (type=='menu')?'div'+name.charAt(0).toUpperCase()+name.slice(1):'div'+name;
		addRemoveFavMenuLeft (id, name, 'remove', type, idRow);
	});
}

function showFavoriteTooltip(menuClass,idFavoriteRow) {
  editFavoriteRow(true);
  clearTimeout(closeFavoriteTimeout);
  clearTimeout(openFavoriteTimeout);
  openFavoriteTimeout=setTimeout("dijit.byId('addFavorite"+menuClass+"_"+idFavoriteRow+"').openDropDown();",100);
  customMenuAddRemoveClass=menuClass;
}

function hideFavoriteTooltip(delay, menuClass, idFavoriteRow) {
  if (!dijit.byId("addFavorite"+menuClass+"_"+idFavoriteRow)) return;
  clearTimeout(closeFavoriteTimeout);
  clearTimeout(openFavoriteTimeout);
  closeFavoriteTimeout=setTimeout("dijit.byId('addFavorite"+menuClass+"_"+idFavoriteRow+"').closeDropDown();",delay);
  customMenuAddRemoveClass=menuClass;
}

function addNewGuiItem(item){
	if (checkFormChangeInProgress()) {
	    return false;
	}
    var currentScreen=null;
    if(dojo.byId('objectClass'))currentScreen=dojo.byId('objectClass').value;
    var classManual=null;
    if(dojo.byId('objectClassManual'))classManual=dojo.byId('objectClassManual').value;
    var param = dojo.byId('newItemAccessMode').value;
    if(classManual == 'Kanban' && item==currentScreen){
    	showDetail('refreshActionAdd'+item,1,item,false,'new');
    	return;
    }
	if(param == 'direct'){
		var callbackPlanning = function(){
			loadDiv("menuUserScreenOrganization.php?currentScreen=Planning&objectExist="+objectExist,"mainDivMenu");
			stockHistory('Planning',null,'Planning');
			if(defaultMenu == 'menuBarRecent'){
			  menuNewGuiFilter(defaultMenu, 'Planning');
			}
			selectIconMenuBar('Planning');
			addNewItem(item);
		};
		var callbackItem = function(){
			loadDiv("menuUserScreenOrganization.php?currentScreen="+item+"&objectExist="+objectExist,"mainDivMenu");
			stockHistory(item,null,'Object');
			if(defaultMenu == 'menuBarRecent'){
			  menuNewGuiFilter(defaultMenu, item);
			}
			selectIconMenuBar(item);
			addNewItem(item);
		};
		if(item != 'Resource' && item != 'Ticket' && canAccessPlanning=='1'){
			var currentMenu=null;
		    if(dojo.byId('objectClassManual'))currentMenu=dojo.byId('objectClassManual').value;
		    if(currentMenu != 'Planning'){
		    	vGanttCurrentLine=-1;
			    cleanContent("centerDiv");
			    notShowDetailAfterReplan=false;
				loadContent("planningMain.php", "centerDiv",null,null,null,null,null,callbackPlanning);
		    }else{
		    	addNewItem(item);
		    }
		}else{
			if(currentScreen != item){
				cleanContent("detailDiv");
				loadContent("objectMain.php?objectClass=" + item, "centerDiv",null,null,null,null,null,callbackItem);
			}else{
				addNewItem(item);
			}
		}
	}else{
	  var currentClass='';
	  if (dojo.byId('objectClassManual')) currentClass=dojo.byId('objectClassManual').value;
	  else if (dojo.byId('objectClass')) currentClass=dojo.byId('objectClass').value;
	  if (currentClass==item || currentClass.substr(0,8)=="Planning") fromContextMenu=true;
		actionSelectAdd(item, null, null);
	}
}

function clearGlobalQuickSearchDialog() {
  var field=dijit.byId('globalQuickSearchValue');
  if (!field) return;
  field.set('value','');
  field.focus();
}

function applyGlobalQuickSearchValue(value) {
  var quickField=dijit.byId('quickSearchValueQuick');
  var listField=dijit.byId('listQuickSearchFilter');
  if (!quickField || !listField) return;
  quickField.set('value',value);
  synchronizeQuickSearchQuickFilter(value);
  if (value==='') {
    quickSearchCloseQuick('list');
  } else {
    quickSearchExecuteQuick('quick');
  }
}

function executeGlobalQuickSearchDialog() {
  var field=dijit.byId('globalQuickSearchValue');
  if (!field) return;
  var value=field.get('value').trim();
  var currentClass=(dojo.byId('objectClassList'))
    ? dojo.byId('objectClassList').value
    : '';
  if (value==='' && currentClass!=='GlobalView') return;
  if (currentClass==='GlobalView') {
    applyGlobalQuickSearchValue(value);
    return;
  }
  loadMenuBarObject('GlobalView',i18n('menuGlobalView'),'bar',false,function() {
    applyGlobalQuickSearchValue(value);
  });
}

function setArchiveMode(){
	var callBack = function(){
	    refreshProjectSelectorList(false);
	    if (dojo.byId('objectClass') ) {
	      refreshGrid(true);
	    }
	  };
  saveDataToSession('projectSelectorShowIdle', 0,false,callBack);
  dijit.byId('dialogProjectSelectorParameters').hide();
  dojo.byId('archiveOn').style.display='none';
  dojo.byId('archiveOnSeparator').style.display='none';
  dojo.byId('archiveOnDiv').style.display='none';
}

function displayFullScreenCK(field) {
  displayFullScreenCKfield = field;
  displayFullScreenCKopening = true;
  alreadyExist = false;  
  if (typeof CKEDITOR.instances['textFullScreenCK'] == 'undefined') {
    ckEditorReplaceEditor("textFullScreenCK", 996);
  } else {
    if (CKEDITOR.instances['textFullScreenCK'].getCommand('maximize').state == CKEDITOR.TRISTATE_OFF) {
      CKEDITOR.instances['textFullScreenCK'].execCommand('maximize');
    }
  }  
  if (typeof CKEDITOR.instances['textFullScreenCK'] != 'undefined' && typeof CKEDITOR.instances[field] != 'undefined') {
    var ckSetDataAndFocus = function() {
      var editorFS = CKEDITOR.instances['textFullScreenCK'];
      var editorSource = CKEDITOR.instances[field];      
      // IMPORTANT: Disable undo BEFORE setData
      if (editorFS.undoManager) {
        editorFS.undoManager.lock();
      }      
      editorFS.setData(editorSource.getData(), function(){
        editorFS.focus();       
        // Re-enable undo AFTER setData
        if (editorFS.undoManager) {
          editorFS.undoManager.unlock();
        }
        disableBrowserZoom();
        setupTabDetachHandling(editorFS);
      });
      editorFS.readOnly = editorSource.readOnly;
    };
    setTimeout(ckSetDataAndFocus, 100);
  } else {
    setTimeout(function() {
      disableBrowserZoom();
      if (typeof CKEDITOR.instances['textFullScreenCK'] != 'undefined') {
        setupTabDetachHandling(CKEDITOR.instances['textFullScreenCK']);
      }
    }, 200);
  }  
  whichFullScreen = 996; 
  setTimeout(function() {
    displayFullScreenCKopening = false;
  }, 500);
}

// Enhanced function to handle tab detach movement
function setupTabDetachHandling(editor) {
  var undoLocked = false; 
  // Save data before tab is moved
  var saveBeforeDetach = function() {
    try {
      if (editor && editor.checkDirty && editor.checkDirty()) {
        // Lock undo before saving
        if (editor.undoManager && !undoLocked) {
          editor.undoManager.lock();
          undoLocked = true;
        }
        
        // Force data save without using getSelection
        var data = editor.getData();
        if (displayFullScreenCKfield && CKEDITOR.instances[displayFullScreenCKfield]) {
          var targetEditor = CKEDITOR.instances[displayFullScreenCKfield];
          if (targetEditor.undoManager) {
            targetEditor.undoManager.lock();
          }
          targetEditor.setData(data);
          if (targetEditor.undoManager) {
            targetEditor.undoManager.unlock();
          }
        }
      }
    } catch(e) {}
  };
  
  // Temporarily disable undo during movement
  var disableUndoTemporarily = function() {
    try {
      if (editor.undoManager && !undoLocked) {
        editor.undoManager.lock();
        undoLocked = true;
      }
    } catch(e) {}
  };
  
  var enableUndoAgain = function() {
    try {
      if (editor.undoManager && undoLocked) {
        editor.undoManager.unlock();
        undoLocked = false;
      }
    } catch(e) {}
  };
  
  // Listen for page visibility change events
  var visibilityHandler = function() {
    if (document.hidden) {
      disableUndoTemporarily();
      saveBeforeDetach();
    } else {
      setTimeout(enableUndoAgain, 100);
    }
  };
  document.addEventListener('visibilitychange', visibilityHandler);
  
  // Listen for window blur (losing focus)
  var blurHandler = function() {
    disableUndoTemporarily();
  };
  window.addEventListener('blur', blurHandler);
  
  var focusHandler = function() {
    setTimeout(enableUndoAgain, 100);
  };
  window.addEventListener('focus', focusHandler);
  
  // Wrapper to catch getSelection errors
  if (editor.on) {
    editor.on('blur', function() {
      disableUndoTemporarily();
    });
    
    editor.on('focus', function() {
      setTimeout(enableUndoAgain, 100);
    });
  }
  
  // Clean up event listeners when the editor is destroyed
  editor.on('destroy', function() {
    document.removeEventListener('visibilitychange', visibilityHandler);
    window.removeEventListener('blur', blurHandler);
    window.removeEventListener('focus', focusHandler);
  });
}

function displayFullScreenCK_close() {
  if (displayFullScreenCKopening) return;   
  displayFullScreenCKopening = true;  
  // Re-enable zoom IMMEDIATELY
  enableBrowserZoom();  
  if (typeof CKEDITOR.instances['textFullScreenCK'] != 'undefined' && typeof CKEDITOR.instances[displayFullScreenCKfield] != 'undefined') {
    var editorFS = CKEDITOR.instances['textFullScreenCK'];
    var editor = CKEDITOR.instances[displayFullScreenCKfield];   
    if (! editor.readOnly ) {
      // Lock both editors during the transfer
      if (editorFS.undoManager) {
        editorFS.undoManager.lock();
      }
      if (editor.undoManager) {
        editor.undoManager.lock();
      }
      
      try {
        var data = editorFS.getData();
        editor.setData(data, function(){
          // Unlock after transfer
          if (editorFS.undoManager) {
            editorFS.undoManager.unlock();
          }
          if (editor.undoManager) {
            editor.undoManager.unlock();
          }
          
          editor.focus();
        });
      } catch(e) {
        // In case of error, unlock anyway
        if (editorFS.undoManager) {
          editorFS.undoManager.unlock();
        }
        if (editor.undoManager) {
          editor.undoManager.unlock();
        }
      }
    }
  }  
  displayFullScreenCKfield = null; 
  setTimeout(function() {
    displayFullScreenCKopening = false;
  }, 500);
  whichFullScreen = -1;
}


var zoomPreventionActive = false;

// Function to disable zoom
function disableBrowserZoom() {
  if (zoomPreventionActive) return; 
  // Block on document AND window to be sure
  document.addEventListener('wheel', preventZoom, { passive: false, capture: true });
  window.addEventListener('wheel', preventZoom, { passive: false, capture: true });  
  document.addEventListener('keydown', preventZoomKeys, { passive: false, capture: true });
  window.addEventListener('keydown', preventZoomKeys, { passive: false, capture: true });  
  document.addEventListener('touchmove', preventTouchZoom, { passive: false, capture: true });
  window.addEventListener('touchmove', preventTouchZoom, { passive: false, capture: true });  
  document.addEventListener('gesturestart', preventGesture, { passive: false, capture: true });
  window.addEventListener('gesturestart', preventGesture, { passive: false, capture: true });  
  // Also add on CKEditor iframe if it exists
  setTimeout(function() {
    var ckeditorIframes = document.querySelectorAll('.cke_wysiwyg_frame');
    ckeditorIframes.forEach(function(iframe) {
      try {
        var iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        iframeDoc.addEventListener('wheel', preventZoom, { passive: false, capture: true });
        iframeDoc.addEventListener('keydown', preventZoomKeys, { passive: false, capture: true });
      } catch(e) {}
    });
  }, 300);
  
  zoomPreventionActive = true;
}

// Function to re-enable zoom
function enableBrowserZoom() {
  if (!zoomPreventionActive) return;
  document.removeEventListener('wheel', preventZoom, { capture: true });
  window.removeEventListener('wheel', preventZoom, { capture: true });  
  document.removeEventListener('keydown', preventZoomKeys, { capture: true });
  window.removeEventListener('keydown', preventZoomKeys, { capture: true });  
  document.removeEventListener('touchmove', preventTouchZoom, { capture: true });
  window.removeEventListener('touchmove', preventTouchZoom, { capture: true });  
  document.removeEventListener('gesturestart', preventGesture, { capture: true });
  window.removeEventListener('gesturestart', preventGesture, { capture: true });  
  var ckeditorIframes = document.querySelectorAll('.cke_wysiwyg_frame');
  ckeditorIframes.forEach(function(iframe) {
    try {
      var iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
      iframeDoc.removeEventListener('wheel', preventZoom, { capture: true });
      iframeDoc.removeEventListener('keydown', preventZoomKeys, { capture: true });
    } catch(e) {}
  });
  
  zoomPreventionActive = false;
}

// Prevent zoom with mouse wheel + Ctrl/Cmd
function preventZoom(e) {
  if (e.ctrlKey || e.metaKey) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    return false;
  }
}

// Prevent zoom with keyboard shortcuts
function preventZoomKeys(e) {
  var isZoomKey = (e.ctrlKey || e.metaKey) && 
                  (e.keyCode === 61 || e.keyCode === 107 || // + (numpad and normal)
                   e.keyCode === 173 || e.keyCode === 109 || // - (numpad and normal)
                   e.keyCode === 187 || e.keyCode === 189 || // +/- (other keyboards)
                   e.keyCode === 48 || // 0 (reset zoom)
                   e.key === '+' || e.key === '-' || e.key === '=' || e.key === '0');
  
  if (isZoomKey) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    return false;
  }
}

// Prevent pinch-to-zoom on mobile/trackpad
function preventTouchZoom(e) {
  if (e.touches && e.touches.length > 1) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    return false;
  }
}

// Prevent zoom gestures
function preventGesture(e) {
  e.preventDefault();
  e.stopPropagation();
  e.stopImmediatePropagation();
  return false;
}

function addRemoveFavProject (id,mode, skipRefreshProjectSelector){
	var div = dojo.byId('divFavProject_'+id);
	if(!div)return;
	dojo.removeAttr(div, 'class');
	dojo.removeAttr(div, 'onclick');
	
  if(mode=='add'){
	  var func= "event.stopPropagation();addRemoveFavProject('"+id+"','remove')";
	  dojo.setAttr(div, 'onclick',func);
	  dojo.setAttr(div, 'class', 'menu__as__Fav');
	  dojo.byId('labelProject_'+id).style.color = 'var(--color-secondary)';
	  if(favoriteProjectsArray.length > 0){
		  favoriteProjectsArray += ','+id;
	  }else{
		  favoriteProjectsArray = id;
	  }
	  saveDataToSession('favoriteProjectsArray', favoriteProjectsArray, true);
    if(selectedFavoriteProject == '' && favoriteProjectsArray.length > 0){
      dojo.byId('saveFavoriteListButtonDiv').style.display = '';
      dojo.byId('favoriteProjectListName').style.display = 'flex';
      dojo.byId('resetFavoriteListButtonDiv').style.display = '';
    }
  }else{
	  var func= "event.stopPropagation();addRemoveFavProject('"+id+"','add')";
	  dojo.setAttr(div, 'onclick',func);
	  dojo.setAttr(div, 'class', 'menu__add__Fav');
	  dojo.byId('labelProject_'+id).style.color = '';
	  if(favoriteProjectsArray.length > 0){
		  if(favoriteProjectsArray.indexOf(','+id) != -1){
			  favoriteProjectsArray = favoriteProjectsArray.replace(','+id,'');
		  }else{
			  favoriteProjectsArray = favoriteProjectsArray.replace(id,'');
		  }
	  }
	  if(favoriteProjectsArray.substr(0, 1) == ','){
		  favoriteProjectsArray = favoriteProjectsArray.substr(1);
	  }
	  saveDataToSession('favoriteProjectsArray', favoriteProjectsArray, true);
    if(selectedFavoriteProject == '' && favoriteProjectsArray.length > 0){
      dojo.byId('saveFavoriteListButtonDiv').style.display = '';
      dojo.byId('favoriteProjectListName').style.display = 'flex';
      dojo.byId('resetFavoriteListButtonDiv').style.display = '';
    }
    
	  var isFavoriteSelected = dojo.byId('isFavoriteSelected').value;
	  if(isFavoriteSelected == '1' && skipRefreshProjectSelector!==true){
		  refreshProjectSelectorList(skipRefreshProjectSelector);
	  }
  }
}

function saveFavoriteProjectList(isEdit,projectChecked) {
  if(isEdit == undefined || isEdit == null)isEdit = false;
  if (projectChecked == undefined || projectChecked == null) projectChecked='';
  if(!isEdit){
    if (dijit.byId('favoriteProjectListName')) {
      if (dijit.byId('favoriteProjectListName').get('value') == "") {
        showAlert(i18n("messageMandatory", new Array(i18n("colFavoriteName"))));
        return;
      }
      if(favoriteProjectsArray.length <= 0){
      showAlert(i18n("noFavoriteProjectItem"));
      return;
      }
      dojo.byId('favoriteProjectName').value=dijit.byId('favoriteProjectListName').get(
          'value');
      var callback = function(){
        clearDivDelayed('saveFavoriteProjectResult');
        if(dojo.byId('idSelectedFavoriteProject'))selectedFavoriteProject=dojo.byId('idSelectedFavoriteProject').value;
        setTimeout('selectFavoriteProjectList(\'\', \''+selectedFavoriteProject+'\', false, false, false);', 100);
        setTimeout('dijit.byId("dialogProjectSelectorParameters").hide();', 110);
      };
      loadContent("../tool/saveFavoriteProjectList.php", "listStoredFavoriteProjectList", "favoriteProjectListForm", false,null,null,null,callback);
    }
  }else{
    if (dojo.byId('favoriteProjectListName')) {
      var favoriteProjectName = dojo.byId('favoriteProjectListName').value;
      var favoriteTitlePane = dijit.byId('projectSelectorFavoriteTitlePane');
      if(!favoriteTitlePane.get('open')){
        favoriteTitlePane.toggle();
      }
      dojo.byId('favoriteProjectListName').focus();
      if (favoriteProjectName == "") {
        dojo.byId('saveFavoriteMessage').innerHTML = i18n("messageMandatory", new Array(i18n("colFavoriteName")));
        dojo.byId('saveFavoriteProjectResult').style.display='flex';
        return;
      }
      if(favoriteProjectsArray.length <= 0){
        dojo.byId('saveFavoriteMessage').innerHTML = i18n("noFavoriteProjectItem");
        dojo.byId('saveFavoriteProjectResult').style.display='flex';
        return;
      }
      var url='../tool/saveFavoriteProjectList.php?mode=fromProjectSelector';
      dojo.xhrPost({
        url : url+addTokenIndexToUrl(),
        form : "favoriteProjectListForm",
        handleAs : "text",
        load : function(data, args) {
          if(data)selectedFavoriteProject=data;
          selectFavoriteProjectList(projectChecked, selectedFavoriteProject, false, false, true);
        }
      });
    }
  }
}

function removeFavoriteProjectList(favoriteFlatList ,id){
	var callback = function(){
		clearDivDelayed('saveFavoriteProjectResult');
		if(selectedFavoriteProject == id){
			saveDataToSession('idFavoriteProjectList', '');
			refreshProjectSelectorList(false, fromProjectSelector);
		}
		if(favoriteFlatList.length > 0){
		  if(favoriteFlatList.indexOf(','+id) != -1){
			  favoriteFlatList = favoriteFlatList.replace(','+id,'');
		  }else{
			  favoriteFlatList = favoriteFlatList.replace(id,'');
		  }
		  if(favoriteFlatList.length <= 0 || favoriteFlatList == ''){
			  refreshProjectSelectorList(false, fromProjectSelector);
		  }
		}else{
			refreshProjectSelectorList(false, fromProjectSelector);
		}
	};
	loadContent("../tool/saveFavoriteProjectList.php?idFavoriteList="+id, "listStoredFavoriteProjectList",
		      "favoriteProjectListForm", false,null,null,null,callback);
}

function removeFavoriteProjectListFromSelector(id, idFilter){
  if(idFilter == undefined)idFilter=null;
  if(idFilter){
	saveFilterToFavoriteProjectList(idFilter,'remove', true);
	if(selectedFavoriteProject == id){
      selectFavoriteProjectList('', '', false,true,true);
    }
  }else{
	var url='../tool/saveFavoriteProjectList.php?idFavoriteList='+id;
	  dojo.xhrPost({
	    url : url+addTokenIndexToUrl(),
	    handleAs : "text",
	    load : function(data, args) {
	      if(selectedFavoriteProject == id){
	        selectFavoriteProjectList('', '', false,true,true);
	      }else{
	        refreshProjectSelectorList(false, true);
	      }
	    }
	  });
  }  
}

function confirmRemoveFavoriteProjectList(id, nameFavorite, idFilter) {
  if(idFilter == undefined)idFilter=false;
  var msg = i18n('confirmDeleteFavorite', new Array(nameFavorite));
  var selectedProject = dijit.byId('selectedProject');
  var actionOK = function() {
      if (selectedProject && selectedProject.dropDown.isShowingNow) {
        selectedProject.closeDropDown();
      }
      removeFavoriteProjectListFromSelector(id, idFilter);
      setTimeout(function() {
        selectedProject.openDropDown();
      }, 50);
    };

  var actionNO = function() {
	selectedProject.closeDropDown();
	selectedProject.openDropDown();  
  };

  showQuestion(msg, actionOK,actionNO);
}



function changedSelectedProjectToFavorite(isEdit){
  if(isEdit == undefined)isEdit=false;
  var projectChecked = '';
  projectChecked = pqProjectCheckList().join(',');
  if(projectChecked.length > 0){
    favoriteProjectsArray = projectChecked;
    saveDataToSession('favoriteProjectsArray', projectChecked, true);
    saveFavoriteProjectList(isEdit,projectChecked);
  }else{
    showAlert(i18n("noFavoriteProjectItem"));
  }
}

function selectFavoriteProjectList(favoriteProjectlist, idFavoriteList, isEdit, hideParam, openDropDown){
  if(isEdit==undefined || isEdit == null)isEdit=false;
  if (hideParam==null || hideParam==undefined)hideParam=true;
  if (openDropDown==null || openDropDown==undefined)openDropDown=false;
	var favoriteProjectName = '';
	if(isEdit && idFavoriteList){
	  if(document.getElementById('favoriteProjectName_'+idFavoriteList)){
	    favoriteProjectName = document.getElementById('favoriteProjectName_'+idFavoriteList).innerHTML;
	  }
	}
	favoriteProjectsArray = favoriteProjectlist;
	saveDataToSession('favoriteProjectsArray', favoriteProjectlist, true);
	if(favoriteProjectName)saveDataToSession('favoriteProjectListName', favoriteProjectName, true);
	var isFavoriteListSelected = dojo.byId('isFavoriteListSelected');
	selectedFavoriteProject = idFavoriteList;
	arraySelectedProject.splice(0);
	if(!isEdit){
	  saveDataToSession('editFavoriteProject', '');
	  saveDataToSession('idFavoriteProjectList', idFavoriteList, true);
	  if(dijit.byId('favoriteProjectListName'))dijit.byId('favoriteProjectListName').set('value', '');
	  if(idFavoriteList == ''){
	    if(isFavoriteListSelected)isFavoriteListSelected.value = 0;
	    saveDataToSession('favoriteProjectsArray', '');
	  }else{
	    var row = dojo.byId('favoriteList'+idFavoriteList);
	    if(row)dojo.setAttr(row, 'class', 'dojoDndItemAnchor');
	    isFavoriteListSelected.value = idFavoriteList;
	  }
	}else{
	  saveDataToSession('editFavoriteProject', idFavoriteList);
	  saveDataToSession('idFavoriteProjectList', '', true);
	  if(isFavoriteListSelected)isFavoriteListSelected.value = 0;
	  openDropDown=true;
	}
	saveDataToSession('project', '*', true);
	saveDataToSession('projectSelected',' ', true);
	// A replan triggered outside the plan dialog reads this hidden field, and
	// nothing else refreshes it : a blank means every project
	var planScope=(!isEdit && idFavoriteList && favoriteProjectlist) ? favoriteProjectlist : ' ';
	if (dojo.byId('planSelectedProjects')) dojo.byId('planSelectedProjects').value=planScope;
	refreshProjectSelectorList(false, openDropDown, hideParam);
  if (hideParam && dijit.byId('dialogProjectSelectorParameters')) {
    dijit.byId('dialogProjectSelectorParameters').hide();
  }
	if (dojo.byId("GanttChartDIV")) {
		if (dojo.byId("resourcePlanning")) {
	      loadContent("resourcePlanningList.php", "listDiv", 'listForm');
	    } else if (dojo.byId("portfolioPlanning")) {
	      loadContent("portfolioPlanningList.php", "listDiv", 'listForm');
	    } else if (dojo.byId("globalPlanning")) {
	      loadContent("globalPlanningList.php", "listDiv", 'listForm');
	    } else if (dojo.byId("workPlan")) {
        loadContent("workPlanList.php", "listDiv", 'listForm');
      } else if (dojo.byId("planningWorkPlan")) {
        loadContent("planningWorkPlanList.php", "listDiv", 'listForm');
      } else if (dojo.byId('objectClassManual')
              && dojo.byId('objectClassManual').value == 'DocumentExplorer'
              && typeof documentExplorerReloadScreen == 'function') {
        /* L'explorateur documentaire a lui aussi un GanttChartDIV : sans cette
           branche il tombait dans le repli ci-dessous et se faisait remplacer par
           le planning, en laissant son panneau de detail ouvert par-dessus. */
        documentExplorerReloadScreen();
      } else {
	      loadContent("planningList.php", "listDiv", 'listForm');
	    }
	}else if(dojo.byId('objectClass')){
		if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value =='ProjectDashboard') refreshDashboard();
		else if (dojo.byId('objectClassManual') && (dojo.byId('objectClassManual').value == 'ProductBacklog' || dojo.byId('objectClassManual').value == 'SprintBacklog'))refreshGlobalBacklog();
		else if(dojo.byId('objectClassManual') && (dojo.byId('objectClassManual').value == 'Kanban'))refreshGlobalKanban();
		else{
		  var objclass = dojo.byId('objectClass').value;
		  refreshJsonList(objclass);
		}
	}else{
		refreshGrid();
	}
}

function hasProjectSelectorSelectionChanged(currentSelection, validatedSelection){
  var currentList = (currentSelection || []).map(function(id){
    return String(id);
  }).filter(function(id){
    return id !== '';
  }).sort();
  var validatedList = String(validatedSelection || '').split(',').filter(function(id){
    return id !== '';
  }).sort();
  return currentList.join(',') !== validatedList.join(',');
}

function validateProjectSelectionOnClose(){
  var checkedProjects = pqProjectCheckList();
  var validatedSelectionNode = dojo.byId('projectSelectorValidatedSelection');
  var validatedSelection = validatedSelectionNode ? validatedSelectionNode.value : arraySelectedProject.join(',');
  if(hasProjectSelectorSelectionChanged(checkedProjects, validatedSelection))selectedMultiProject();
}

function checkProjectToSelect(){
  var checkedProjects = pqProjectCheckList();
  var showFavoriteButton = 'none';
  var showFavoriteName = 'none';
  if(checkedProjects.length > 0){
    showFavoriteButton = '';
    showFavoriteName = 'flex';
  }
  // A search can check hundreds of projects at once, so show how many
  var countNode = dojo.byId('multiProjectSelectCount');
  if(countNode) countNode.innerHTML = (checkedProjects.length > 1)?'&nbsp;('+checkedProjects.length+')':'';
  var validatedSelectionNode = dojo.byId('projectSelectorValidatedSelection');
  var validatedSelection = validatedSelectionNode ? validatedSelectionNode.value : arraySelectedProject.join(',');
  var showOKButton = hasProjectSelectorSelectionChanged(checkedProjects, validatedSelection) ? '' : 'none';
  dojo.byId('multiProjectSelectButtonDiv').style.display = showOKButton;
  if(dojo.byId('saveFavoriteListButtonDiv').style.display == 'none')dojo.byId('saveNewFavoriteListButtonDiv').style.display = showFavoriteButton;
  dojo.byId('favoriteProjectListName').style.display = showFavoriteName;
  var FavoriteTitlePan = dijit.byId('projectSelectorFavoriteTitlePane');
  var isOpen=FavoriteTitlePan.get('open');
  if(isOpen){
	resizeTitlePanProjectSelector(isOpen);
  }
}

function highlightFavoriteProject(id, mode){
  var div = dojo.byId('divFavProject_'+id);
  if(!div)return;
  var isSelected = false;
  if(dojo.hasClass(div, 'menu__as__Fav')){
    div.style.display='';
    isSelected = true;
  }else if(dojo.hasClass(div, 'menu__add__Fav')){
    div.style.display='none';
  }
  if(mode == 'mouseover' && !isSelected){
    dojo.byId('divFavProject_'+id).style.display='';
  }else if(mode == 'mouseout' && !isSelected){
    dojo.byId('divFavProject_'+id).style.display='none';
  }
}
