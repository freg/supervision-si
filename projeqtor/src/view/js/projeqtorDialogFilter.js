///*******************************************************************************
// * COPYRIGHT NOTICE *
// * 
// * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org Contributors : -
// * 
// * This file is part of ProjeQtOr.
// * 
// * ProjeQtOr is free software: you can redistribute it and/or modify it under
// * the terms of the GNU Affero General Public License as published by the Free Software
// * Foundation, either version 3 of the License, or (at your option) any later
// * version.
// * 
// * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
// * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
// * A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.
// * 
// * You should have received a copy of the GNU Affero General Public License along with
// * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
// * 
// * You can get complete code of ProjeQtOr, other resource, help and information
// * about contributors at http://www.projeqtor.org
// * 
// * DO NOT REMOVE THIS NOTICE **
// ******************************************************************************/
//
//// ============================================================================
//// All specific ProjeQtOr functions and variables for Dialog Purpose
//// This file is included in the main.php page, to be reachable in every context
//// ============================================================================

// =============================================================================
// = Filter
// =============================================================================

var filterStartInput=false;
var filterFromDetail=false;
function getFilterAttributeObjectClass(objectClass) {
  if (objectClass == 'Planning' || objectClass == 'PlanningWorkPlan') return 'PlanningElement';
  if (objectClass == 'VersionsPlanning' || objectClass == 'ResourcePlanning') return 'Activity';
  return objectClass;
}
function getFilterAttributeField(attribute) {
  if (!attribute) return attribute;
  if (attribute.substr(0, 15) == 'PlanningObject_') return attribute.substr(15);
  if (attribute.substr(0, 16) == 'PlanningElement_') return attribute.substr(16);
  return attribute;
}
function showFilterDialog(idFilterFromFavoriteProject) {
  if(idFilterFromFavoriteProject == undefined) idFilterFromFavoriteProject=null;
  function callBack() {
    filterStartInput=false;
    window.top.filterFromDetail=false;
    if (dojo.byId('filterInsertPosition')) dojo.byId('filterInsertPosition').value='';
    if (dojo.byId("isGroup")) dojo.byId("isGroup").value="0";
    if (dojo.byId("indentLevel")) dojo.byId("indentLevel").value="0";
    setPendingFilterOpenGroup(false);

    dojo.style(dijit.byId('idFilterOperator').domNode,{
      visibility:'hidden'
    });
    dojo.style(dijit.byId('filterValue').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterValueList').domNode,{
      display:'none'
    });
    if (isNewGui) dojo.byId("filterDynamicParameterPane").style.left="200px";
    if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
    dojo.style(dijit.byId('showDetailInFilter').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterValueCheckbox').domNode,{
      display:'none'
    });
    if (dijit.byId('filterValueCheckboxSwitch')) {
      dojo.style(dijit.byId('filterValueCheckboxSwitch').domNode,{
        display:'none'
      });
    }
    dojo.style(dijit.byId('filterValueDate').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('FilterCompareAttribute').domNode,{
      display:'none'
    });
	hideCompareValueInput();
    dojo.byId('filterDynamicParameterPane').style.display='none';
    dojo.byId('filterCompareParameterPane').style.display='none';
    
    if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
    dijit.byId('idFilterAttribute').reset();
	if(idFilterFromFavoriteProject) dojo.byId('filterObjectClass').value='Project';
    else if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) dojo.byId('filterObjectClass').value=dojo.byId('objectClassList').value;
    else if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value) dojo.byId('filterObjectClass').value=dojo.byId('objectClassManual').value;
    else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) dojo.byId('filterObjectClass').value=dojo.byId('objectClass').value;
    else dojo.byId('filterObjectClass').value=null;
    filterType="";
    var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
    dojo.xhrPost({
      url:"../tool/backupFilter.php?filterObjectClass=" + dojo.byId('filterObjectClass').value + compUrl +addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data,args) {
      }
    });
    compUrl=(window.top.dijit.byId("dialogDetail").open) ? '?comboDetail=true' : '';
    loadContent("../tool/displayFilterClause.php" + compUrl,"listFilterClauses","dialogFilterForm",false,null,null,null,function() {
      updateFilterGroupButtons();
    });
    loadContent("../tool/refreshFilterNameLayout.php" + compUrl,"filterNameLayoutDiv","dialogFilterForm",false, null, null, null);
    loadContent("../tool/displayFilterList.php" + compUrl,"listStoredFilters","dialogFilterForm",false);
    loadContent("../tool/displayFilterSharedList.php" + compUrl,"listSharedFilters","dialogFilterForm",false);
	if(idFilterFromFavoriteProject){
		selectStoredFilter(idFilterFromFavoriteProject,'','','favoriteProjectList','');
	}
// else{
//		const filterData = document.querySelectorAll('td[id^="filterData_"]');
//	    filterData.forEach(function(td) {
//	      if (td.dataset.selected === 'isSelected') {
//	        const idsPart = td.id.replace('filterData_', '');
//	        const [filterId, idLayout] = idsPart.split('#');
//	        selectStoredFilter(filterId,idLayout,'','','');
//	      }
//	    });
//	}
	var objectClass='';
	if(idFilterFromFavoriteProject) objectClass='Project';
    else if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) objectClass=dojo.byId('objectClassList').value;
    else if (dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) objectClass=getFilterAttributeObjectClass(dojo.byId("objectClassManual").value);
    else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) objectClass=dojo.byId('objectClass').value;
    if (objectClass.substr(0,7) == 'Report_') objectClass=objectClass.substr(7);
    refreshListSpecific('object','idFilterAttribute','objectClass',objectClass);
    dijit.byId("dialogFilter").show();
	setTimeout(function() {
	  displayOrOperator();
	}, 300);
  }
  var params = (idFilterFromFavoriteProject)?'&idFilterFromFavoriteProject='+idFilterFromFavoriteProject:'';
  loadDialog('dialogFilter',callBack,true,params,true);
}

function displayOrOperator() {
  if (dojo.byId('nbFilterCriteria') && dojo.byId('nbFilterCriteria').value != "0") {
    dojo.byId('filterLogicalOperator').style.display='block';
  }
  updateFilterGroupButtons();
}
var samefilteroperator = null;
function filterSelectAtribute(value) {
  if (value) {
    filterStartInput=true;
    if (dijit.byId('filterCompareParameterSwitch')) dijit.byId('filterCompareParameterSwitch').set('value','off');
    if (dijit.byId('filterDynamicParameterSwitch')) dijit.byId('filterDynamicParameterSwitch').set('value','off');
    if (editFilterValueDynamic!==null && editFilterValueDynamic==1){
      dijit.byId("filterDynamicParameterSwitch").set("value",'on');
    }
    var dataTypeEdit=null;
    dijit.byId('idFilterAttribute').store.store.fetchItemByIdentity({
      identity:value,
      onItem:function(item) {
        var dataType=dijit.byId('idFilterAttribute').store.store.getValue(item,"dataType","inconnu");
        if (value == "refTypeIncome" || value == "refTypeExpense") {
          dataType="list";
        }
        var datastoreOperator=new dojo.data.ItemFileReadStore({
          url:'../tool/jsonList.php?listType=operator&dataType=' + dataType + ''+addTokenIndexToUrl()
        });
        var storeOperator=new dojo.store.DataStore({
          store:datastoreOperator
        });
        storeOperator.query({
          id:"*"
        });
        dijit.byId('idFilterOperator').set('store',storeOperator);
        datastoreOperator.fetch({
          query:{
            id:"*"
          },
          count:1,
          onItem:function(item) {
            var filteroperator = (editFilterOperator )? editFilterOperator : item.id;
            if (editFilterOperator!==null){
              if (editFilterOperator=='BETWEEN'){
                filteroperator = '=';
              }else if(editFilterOperator=='NOT BETWEEN'){
                filteroperator = '<>';
              }else if(editFilterOperator=='is null'){
                filteroperator = 'isEmpty';
              }else if(editFilterOperator=='is not null'){
                filteroperator = 'isNotEmpty';
              }else if(editFilterOperator=='LIKE' && !editFilterValue.startsWith("'%")){
                filteroperator = 'startBy'; 
              }else if(editFilterOperator=='<='){
                if (editFilterValue.toUpperCase().includes('DAY')){
                  filteroperator = '<=now+';
                }
              }else if(editFilterOperator=='>='){
                if (editFilterValue.toUpperCase().includes('DAY')){
                  filteroperator = '>=now+';
                }
              } else if(editFilterOperator == ' exists ' && value=='dependencies'){
				if (editFilterValue.includes('predecessorRefType')){
				  filteroperator = 'hasSuccessors';
				} else if(editFilterValue.includes('successorRefType')){
					filteroperator = 'hasPredecessors';
				}
			  } else if(editFilterOperator == ' exists ' && (value=='assignedResource__idResourceAll' || value=='assignedResourceLeftWork__idResourceAll')){
			    if (/\bNOT\s+IN\s*\(/i.test(editFilterValue)) {
			      filteroperator = 'NOT IN';
			    } else if (/\bIN\s*\(/i.test(editFilterValue)) {
			      filteroperator = 'IN';
			    } else {
			      filteroperator = 'isNotEmpty';
			    }
			  }	else if(editFilterOperator == ' not exists ' && (value=='assignedResource__idResourceAll' || value=='assignedResourceLeftWork__idResourceAll') ){
			    filteroperator = 'isEmpty';
			  }else if(editFilterOperator == ' not exists '){
				filteroperator = 'isEmpty';
			  }else if(editFilterOperator=='ILIKE'){
				filteroperator = 'LIKE';
			  }else if(editFilterOperator=='NOT ILIKE'){
				filteroperator = 'NOT LIKE';
			  }
              if (samefilteroperator==filteroperator) filterSelectOperator(filteroperator); 
                samefilteroperator = filteroperator; 
            }
            dijit.byId('idFilterOperator').set("value",filteroperator);
          },
          onError:function(err) {
            console.info(err.message);
          }
        });
        dojo.style(dijit.byId('idFilterOperator').domNode,{
          visibility:'visible'
        });
        var datastoreCompare=new dojo.data.ItemFileReadStore({
          url:'../tool/jsonList.php?listType=empty&attribute='+value+'&dataType=' + dataType + ''+addTokenIndexToUrl()
        });
        var storeCompare=new dojo.store.DataStore({
          store:datastoreCompare
        });
        storeCompare.query({
          id:"*"
        });
        dijit.byId('FilterCompareAttribute').set('store',storeCompare);
        datastoreCompare.fetch({
          query:{
            id:"*"
          },
          count:1,
          onItem:function(item) {
            dijit.byId('FilterCompareAttribute').set("value",item.id);
          },
          onError:function(err) {
            console.info(err.message);
          }
        });
        dojo.style(dijit.byId('FilterCompareAttribute').domNode,{
          visibility:'visible'
        });
        // ADD qCazelles - Dynamic filter - Ticket #78
        if (editFilterValueCompare) {
          dojo.byId('filterDynamicParameterPane').style.display = 'none';
        }
        else dojo.byId('filterDynamicParameterPane').style.display='block';
        dojo.byId('filterCompareParameterPane').style.display='none';
		dijit.byId("filterCompareParameter").set("checked",false);
		
        if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
        // END ADD qCazelles - Dynamic filter - Ticket #78
        dojo.byId('filterDataType').value=dataType;
        if (dataType == "bool") {
          dataTypeEdit="bool";
          dijit.byId("filterCompareParameter").set("checked",false);
          dojo.byId('filterCompareParameterPane').style.display='none';
          filterType="bool";
          dojo.style(dijit.byId('filterValue').domNode,{
            display:'none'
          });
          dojo.style(dijit.byId('filterValueList').domNode,{
            display:'none'
          });
          if (isNewGui) dojo.byId("filterDynamicParameterPane").style.left="200px";
          if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
          if (dijit.byId('filterValueCheckboxSwitch')) {
            dojo.style(dijit.byId('filterValueCheckboxSwitch').domNode,{
              display:'block'
            });

            if (isNewGui) dojo.byId("filterValueCheckboxSwitch").style.top="10px";
            dijit.byId('filterValueCheckbox').set('value','off');
          } else {
            dojo.style(dijit.byId('filterValueCheckbox').domNode,{
              display:'block'
            });
            dijit.byId('filterValueCheckbox').set('checked','');
          }
          dojo.style(dijit.byId('filterValueDate').domNode,{
            display:'none'
          });
          dojo.style(dijit.byId('showDetailInFilter').domNode,{
            display:'none'
          });
		  dojo.style(dijit.byId('filterValueHatch').domNode,{
		  		display:'none'
		  });
        } else if (dataType == "list") {
          dataTypeEdit='list';
          dijit.byId("filterCompareParameter").set("checked",false);
          dojo.byId('filterCompareParameterPane').style.display='none';
          filterType="list";
          var extraUrl="";
          value=getFilterAttributeField(value);
          if (value == 'idTargetVersion' || value == 'idTargetProductVersion' || value == 'idOriginalProductVersion') {
            value='idProductVersion';
            if (dojo.byId('archiveOn') && dojo.byId('archiveOn').style.display=='none'){
              extraUrl='&critField=idle&critValue=0'; 
            }else{
              extraUrl='&critField=idle&critValue=all';
            }
          } else if (value == 'idTargetComponentVersion' || value == 'idOriginalComponentVersion') {
            value='idComponentVersion';
            if (dojo.byId('archiveOn') && dojo.byId('archiveOn').style.display=='none'){
              extraUrl='&critField=idle&critValue=0'; 
            }else{
              extraUrl='&critField=idle&critValue=all';
            }
          } else if (value == 'idResourceSelect' || (value == 'idResource' && dojo.byId('filterObjectClass') && dojo.byId('filterObjectClass').value=='Assignment' )) {
            value='idResourceAllNoMaterial';
          }
          var urlListFilter='../tool/jsonList.php?required=true&listType=list&dataType=' + value + ''+addTokenIndexToUrl();

          // CHANGE qCazelles - Ticket 165 //Empty lists on filter in
          // comboDetail
          // Old
          // if (currentSelectedProject && currentSelectedProject!='' &&
          // currentSelectedProject!='*') {
          // New
          if (typeof currentSelectedProject != 'undefined' && currentSelectedProject != '' && currentSelectedProject != '*') {
            // END CHANGE qCazelles - Ticket 165
            if (value == 'idActivity') {
              urlListFilter+='&critField=idProjectSub&critValue=' + currentSelectedProject;
            }
            if (value.substr(0,2)=='id' && value.substr(-4)=='Type') {
              // noting              
            } else if (value == 'idComponent') {
              // noting
            } else if (value=='idProject') {
              urlListFilter+='&critField=id&critValue=' + currentSelectedProject;
            } else {
              urlListFilter+='&critField=idProject&critValue=' + currentSelectedProject;
            }
            if (extraUrl == '&critField=idle&critValue=all') {
              extraUrl == '&critField1=idle&critValue1=all';
            }
          }
          if (extraUrl != "") {
            urlListFilter+=extraUrl;
          }
          var tmpStore=new dojo.data.ItemFileReadStore({
            url:urlListFilter + addTokenIndexToUrl(urlListFilter)
          });
          var mySelect=dojo.byId("filterValueList");
          mySelect.options.length=0;
          var nbVal=0;
          // ADD aGaye - Ticket 196
          if (dijit.byId('idFilterAttribute').getValue() == "idBusinessFeature") {
            var listId="";
            tmpStore.fetch({
              query:{
                id:"*"
              },
              onItem:function(item) {
                listId+=(listId != "") ? '_' : '';
                listId+=parseInt(tmpStore.getValue(item,"id",""),10) + '';
                nbVal++;
              },
              onError:function(err) {
                console.info(err.message);
              },
              onComplete:function() {
                dojo.xhrGet({
                  url:'../tool/getProductNameFromBusinessFeature.php?listId=' + listId + ''+addTokenIndexToUrl(),
                  handleAs:"text",
                  load:function(data) {
                    var listName=JSON.parse(data);
                    tmpStore.fetch({
                      query:{
                        id:"*"
                      },
                      onItem:function(item) {
                        mySelect.options[mySelect.length]=new Option(tmpStore.getValue(item,"name","") + " (" + listName[tmpStore.getValue(item,"id","")] + ")",tmpStore.getValue(item,"id",""));
                      },
                      onError:function(err) {
                        console.info(err.message);
                      }
                    });
                  }
                });
              }
            });
          } else {
			valueSelect=[];
			if (editFilterValue!==null) {
			  var idMatch = editFilterValue.match(/idResource\s+(?:NOT\s+)?IN\s*\(([^)]+)\)/i);
			  var rawValue = idMatch ? idMatch[1] : editFilterValue.replace(/\(|\)|\s/g,'');
			  valueSelect = rawValue.replace(/\s/g,'').split(',');
			}
            tmpStore.fetch({
              query:{
                id:"*"
              },
              onItem:function(item) {
                selected=(valueSelect.indexOf(item.id[0])!=-1)?true:false;
                mySelect.options[mySelect.length]=new Option(tmpStore.getValue(item,"name",""),tmpStore.getValue(item,"id",""),selected,selected);
                nbVal++;
              },
              onError:function(err) {
                console.info(err.message);
              }
            });
          }
          // END aGaye - Ticket 196
          mySelect.size=(nbVal > 10) ? 10 : nbVal;
          dojo.style(dijit.byId('filterValue').domNode,{
            display:'none'
          });
          dojo.style(dijit.byId('filterValueList').domNode,{
            display:'block'
          });
            if (isNewGui) dojo.byId("filterDynamicParameterPane").style.left="8px";
            if (isNewGui) dojo.byId("filterValueListHideTop").style.display="block";
            dojo.xhrGet({
            url : "../tool/checkAccessForScreen.php?listType="+value+addTokenIndexToUrl(),
            handleAs : "text",
            load : function(data) {
              if(data && data=="YES"){          
                dojo.style(dijit.byId('showDetailInFilter').domNode, {display : 'block'}); 
              } else {
                dojo.style(dijit.byId('showDetailInFilter').domNode, {display : 'none'});
              }
            }
          });
          dijit.byId('showDetailInFilter').set('value',item.id);
          dijit.byId('filterValueList').reset();
          dojo.style(dijit.byId('filterValueCheckbox').domNode,{
            display:'none'
          });
          if (dijit.byId('filterValueCheckboxSwitch')) {
            dojo.style(dijit.byId('filterValueCheckboxSwitch').domNode,{
              display:'none'
            });
          }
          dojo.style(dijit.byId('filterValueDate').domNode,{
            display:'none'
          });
		  dojo.style(dijit.byId('filterValueHatch').domNode,{
		  	display:'none'
		  });
        } else if (dataType == "hatchPattern") {
		   dataTypeEdit='hatchPattern';
		   dojo.style(dijit.byId('filterValueHatch').domNode,{
		   		display:'block'
		   });
		   
		   dijit.byId('filterValue').reset();
		   dojo.style(dijit.byId('filterValueList').domNode,{
		      display:'none'
		   });
		   dojo.byId('filterDynamicParameterPane').style.display='none';
		   if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
		   dojo.style(dijit.byId('showDetailInFilter').domNode,{
		     display:'none'
		   });
		   dojo.style(dijit.byId('filterValueCheckbox').domNode,{
		     display:'none'
		   });
		   if (dijit.byId('filterValueCheckboxSwitch')) {
		     dojo.style(dijit.byId('filterValueCheckboxSwitch').domNode,{
		       display:'none'
		      });
		    }
		    dojo.style(dijit.byId('filterValueDate').domNode,{
		      display:'none'
		    });
			
			dijit.byId("filterCompareParameter").set("checked", false);
			dojo.byId('filterCompareParameterPane').style.display = 'none';
			hideCompareValueInput();
		}else if (dataType == "date") {
          dataTypeEdit='date';
          filterType="date";
          dojo.byId('filterCompareParameterPane').style.display='block';
          dojo.style(dijit.byId('filterValue').domNode,{
            display:'none'
          });
          dojo.style(dijit.byId('filterValueList').domNode,{
            display:'none'
          });
          if (isNewGui) dojo.byId("filterDynamicParameterPane").style.left="200px";
          if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
          dojo.style(dijit.byId('showDetailInFilter').domNode,{
            display:'none'
          });
          dojo.style(dijit.byId('filterValueCheckbox').domNode,{
            display:'none'
          });
          if (dijit.byId('filterValueCheckboxSwitch')) {
            dojo.style(dijit.byId('filterValueCheckboxSwitch').domNode,{
              display:'none'
            });
          }
          dojo.style(dijit.byId('filterValueDate').domNode,{
            display:'block'
          });
          dijit.byId('filterValueDate').reset();
		  dojo.style(dijit.byId('filterValueHatch').domNode,{
		  	display:'none'
		  });
        } else {
      	  if (dataType=='decimal') {
      		dataTypeEdit='decimal';
      		if (isNewGui) dojo.byId("filterCompareParameterPane").style.left="200px";
      	    if (isNewGui) dojo.byId("filterCompareParameterPane").style.top="30px";
      	    if (isNewGui) dojo.byId('filterCompareParameterPane').style.display='block';
      	  } else {
        		dataTypeEdit='varchar';
        		dojo.byId('filterCompareParameterPane').style.display='none';
        		dijit.byId("filterCompareParameter").set("checked",false);
      	  }
          filterType="text";
          dojo.style(dijit.byId('filterValue').domNode,{
            display:'block'
          });
          dijit.byId('filterValue').reset();
          dojo.style(dijit.byId('filterValueList').domNode,{
            display:'none'
          });
          if (isNewGui) dojo.byId("filterDynamicParameterPane").style.left="200px";
          if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
          dojo.style(dijit.byId('showDetailInFilter').domNode,{
            display:'none'
          });
          dojo.style(dijit.byId('filterValueCheckbox').domNode,{
            display:'none'
          });
          if (dijit.byId('filterValueCheckboxSwitch')) {
            dojo.style(dijit.byId('filterValueCheckboxSwitch').domNode,{
              display:'none'
            });
          }
          dojo.style(dijit.byId('filterValueDate').domNode,{
            display:'none'
          });
		  if (dataType == "varchar" || dataType == 'refObject'){
			dojo.byId("filterCompareParameterPane").style.left="200px";
			dojo.byId("filterCompareParameterPane").style.top="30px";
		  	dojo.byId('filterCompareParameterPane').style.display='none';
		  }
		  dojo.style(dijit.byId('filterValueHatch').domNode,{
		  		display:'none'
		  });
        }
      },
      onError:function(err) {
        dojo.style(dijit.byId('idFilterOperator').domNode,{
          visibility:'hidden'
        });
        dojo.style(dijit.byId('filterValue').domNode,{
          display:'none'
        });
        dojo.style(dijit.byId('filterValueList').domNode,{
          display:'none'
        });
        if (isNewGui) dojo.byId("filterDynamicParameterPane").style.left="200px";
        if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
        dojo.style(dijit.byId('showDetailInFilter').domNode,{
          display:'none'
        });
        dojo.style(dijit.byId('filterValueCheckbox').domNode,{
          display:'none'
        });
        if (dijit.byId('filterValueCheckboxSwitch')) {
          dojo.style(dijit.byId('filterValueCheckboxSwitch').domNode,{
            display:'none'
          });
        }
        dojo.style(dijit.byId('filterValueDate').domNode,{
          display:'none'
        });
        // hideWait();
      }
    });
    dijit.byId('filterValue').reset();
    dijit.byId('filterValueList').reset();
    dijit.byId('filterValueCheckbox').reset();
    if (dijit.byId('filterValueCheckboxSwitch')) {
      dijit.byId('filterValueCheckboxSwitch').reset();
    }
    dijit.byId('filterValueDate').reset();
    dojo.byId('buttonSaveFieldEdition').style.display=(editFilterValue!==null || editFilterValueDynamic!==null)?'block':'none';
    updateFilterGroupButtons();
    
    if (editFilterValue!==null) {
      if (dataTypeEdit == "bool" && editFilterValue==1){
        dijit.byId('filterValueCheckboxSwitch').set('value','on');
      }else if (dataTypeEdit == "date"){
        var dateFilter = editFilterValue.match(/(\d{4}-\d{2}-\d{2})/);
        if (dateFilter) dijit.byId('filterValueDate').set('value', new Date(dateFilter[1]));
        if (editFilterOperator=='<=' || editFilterOperator=='>=' || editFilterOperator == '=month+' || editFilterOperator == '=year+' ){
          var valueFilter = editFilterValueDisp.match(/(\d+)/);
          if (valueFilter) {
			dijit.byId("filterValue").set("value",valueFilter[1]);
			window.isEditingFilter = true;
		  }
        } 
      } else if (dataTypeEdit == "hatchPattern"){
  		var hatchValue = editFilterValueDisp.replace(/^'|'$/g, '');
		dijit.byId('filterValueHatch').set('value', hatchValue);
		dojo.byId('filterDynamicParameterPane').style.display='none';
		dojo.style(dijit.byId('filterValue').domNode,{
		  display:'none'
		});
		window.isEditingFilter = true;
	  }else if (dataTypeEdit!='list'){
        valueFilter = editFilterValue;
        if (editFilterOperator=='LIKE' || editFilterOperator=='NOT LIKE' || editFilterOperator=='ILIKE' || editFilterOperator=='NOT ILIKE'){
          valueFilter =  editFilterValueDisp.replace(/^'|'$/g, '');
        }
		window.isEditingFilter = true;
        dijit.byId("filterValue").set("value",valueFilter);
      }
      if (editFilterOperator!='NOT IN' && editFilterOperator!='IN' ){
        dojo.byId('showDetailInFilter').style.display='none'; 
      }else{
        dojo.byId('showDetailInFilter').style.display='block';
      }
    }
    //#6012
    var objectClass='';
    if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) objectClass=dojo.byId('objectClassList').value;
    else if (dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) objectClass=getFilterAttributeObjectClass(dojo.byId("objectClassManual").value);
    else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) objectClass=dojo.byId('objectClass').value;
    if (objectClass.substr(0,7) == 'Report_') objectClass=objectClass.substr(7);
    if (dijit.byId('filterCompareParameter').get('checked')) {
      dojo.style(dijit.byId('FilterCompareAttribute').domNode,{
        display:'block'
      });
      if (isNewGui) dojo.byId("filterCompareParameterPane").style.left="200px";
      if (isNewGui) dojo.byId("filterCompareParameterPane").style.top=(dojo.byId("filterDynamicParameterPane").style.display=='none')?"9px":"30px";
      dojo.style(dijit.byId('filterValue').domNode,{
        display:'none'
      });
      dojo.style(dijit.byId('filterValueList').domNode,{
        display:'none'
      });
      dojo.style(dijit.byId('filterValueCheckbox').domNode,{
        display:'none'
      });
      dojo.style(dijit.byId('filterValueDate').domNode,{
        display:'none'
      });
      dojo.style(dijit.byId('filterSortValueList').domNode,{
        display:'none'
      });
      dijit.byId('FilterCompareAttribute').set('value', null);
      refreshListSpecific('object','FilterCompareAttribute','objectClass',objectClass, null, false, 'field', value);
    }else{
      dojo.style(dijit.byId('FilterCompareAttribute').domNode,{
        display:'none'
      }); 
    }    //#6012
  } else {
    dojo.style(dijit.byId('idFilterOperator').domNode,{
      visibility:'hidden'
    });
    dojo.style(dijit.byId('filterValue').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterValueList').domNode,{
      display:'none'
    });
    if (isNewGui) dojo.byId("filterDynamicParameterPane").style.left="200px";
    if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
    dojo.style(dijit.byId('showDetailInFilter').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterValueCheckbox').domNode,{
      display:'none'
    });
    if (dijit.byId('filterValueCheckboxSwitch')) {
      dojo.style(dijit.byId('filterValueCheckboxSwitch').domNode,{
        display:'none'
      });
    }
    dojo.style(dijit.byId('filterValueDate').domNode,{
      display:'none'
    });
  }
}

function filterActiveCompareField() {
  var valueFilterAttribute = dijit.byId('idFilterAttribute').get('value');
  var valueFilterOperator = dijit.byId('idFilterOperator').get('value');
  var dataType = dojo.byId('filterDataType').value;
  var objectClass='';
  if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) objectClass=dojo.byId('objectClassList').value;
  else if (dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) objectClass=getFilterAttributeObjectClass(dojo.byId("objectClassManual").value);
  else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) objectClass=dojo.byId('objectClass').value;
  if (objectClass.substr(0,7) == 'Report_') objectClass=objectClass.substr(7);
  if (dijit.byId('filterCompareParameter').get('checked')) {
    dojo.style(dijit.byId('FilterCompareAttribute').domNode,{
      display:'block'
    });
    if (isNewGui) dojo.byId("filterCompareParameterPane").style.left="200px";
    if (isNewGui) dojo.byId("filterCompareParameterPane").style.top=(dojo.byId("filterDynamicParameterPane").style.display=='none')?"9px":"30px";
    dojo.style(dijit.byId('filterValue').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterValueList').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterValueCheckbox').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterValueDate').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterSortValueList').domNode,{
      display:'none'
    });
    dijit.byId('FilterCompareAttribute').set('value', null);
    refreshListSpecific('object','FilterCompareAttribute','objectClass',objectClass, null, false, 'field', valueFilterAttribute);
	var attributeType = '';
	if (dataType == 'date'){
	  attributeType = 'date';
	}else if (dataType == 'decimal'){
	  if (valueFilterAttribute.toLowerCase().endsWith('cost') || valueFilterAttribute.toLowerCase().endsWith('amount') || valueFilterAttribute.toLowerCase().endsWith('revenue')){
		attributeType = 'cost';
	  } else if (valueFilterAttribute.toLowerCase().endsWith('work')){
		if (valueFilterAttribute == 'ProjectPlanningElement_realWork') attributeType = 'workUnit';
		else attributeType = 'work';
	  }
	}
	showCompareValueInput(attributeType);
	if (editFilterValue !== null) {
	  var compareAttribute = '';
	  var compareOperator = 'plus';
	  var compareValue = '';
	  editFilterValue = editFilterValue.replace(/\[|\]/g, '');
	  
	  var matchPlusPattern = editFilterValue.match(/^([A-Za-z0-9_]+)\s*\+\s*(\d+(?:\.\d+)?)$/);
	  var matchMinusPattern = editFilterValue.match(/^([A-Za-z0-9_]+)\s*\-\s*(\d+(?:\.\d+)?)$/);
	  var matchMultiPattern = editFilterValue.match(/^([A-Za-z0-9_]+)\s*x\s*(\d+(?:\.\d+)?)$/);
	  if (matchPlusPattern) {
	    compareAttribute = matchPlusPattern[1].trim();
	    compareOperator = 'plus';
		compareValue = editFilterValueDisp.split('+').pop().trim();
	  } else if (matchMinusPattern) {
	    compareAttribute = matchMinusPattern[1].trim();
	    compareOperator = 'minus';
		compareValue = editFilterValueDisp.split('-').pop().trim();
	  } else if (matchMultiPattern) {
	    compareAttribute = matchMultiPattern[1].trim();
	    compareOperator = 'multi';
		compareValue = editFilterValueDisp.split('x').pop().trim();
	  } else {
	    compareAttribute = editFilterValue;
	  }	
	  setTimeout(function() {
	    if (compareAttribute) {
	      dijit.byId('FilterCompareAttribute').set('value', compareAttribute);
	    }
	    if (compareOperator && dijit.byId('operatorCompare')) {
	      dijit.byId('operatorCompare').set('value', compareOperator);
	    }
	    if (compareValue && dijit.byId('filterCompareValue')) {
	      dijit.byId('filterCompareValue').set('value', parseFloat(compareValue) || 0);
	    }
		window.isEditingFilterCompareValue = true;
	  }, 500);
	}
//    if (editFilterValue!==null) {
//     editFilterValue=editFilterValue.replace(/\[|\]/g, '');
//     dijit.byId('FilterCompareAttribute').set('value',editFilterValue);
//    }
  }else{
    dojo.style(dijit.byId('FilterCompareAttribute').domNode,{
      display:'none'
    }); 
    if(dataType == 'List'){
      dojo.style(dijit.byId('filterValueList').domNode,{
        display:'block'
      });
    } else if (dataType == 'date'){
      if(valueFilterOperator == '<=now+'){
        dojo.style(dijit.byId('filterValueDate').domNode,{
          display:'none'
        });
      }else{
        dojo.style(dijit.byId('filterValueDate').domNode,{
          display:'block'
        });
      }
    }else if(dataType == 'bool'){
      dojo.style(dijit.byId('filterValueCheckbox').domNode,{
        display:'block'
      });
    }else{
      dojo.style(dijit.byId('filterValue').domNode,{
        display:'block'
      });
    }
	hideCompareValueInput();
  }    //#6012
}

function showCompareValueInput(attributeType) {
  const inputDiv = dojo.byId('filterCompareValueInput');
  const unitSpan = dojo.byId('compareUnit');
  if (inputDiv) {
	updateOperatorOptions(attributeType);
    inputDiv.style.display = 'block';
    if (attributeType === 'date') {
      unitSpan.textContent = i18n('daysCalendar');
    } else if (attributeType === 'work') {
	  var paramImputationUnit=window.top.paramImputationUnit;
      if (paramImputationUnit == 'hours') unitSpan.textContent = i18n('hours');
	  else unitSpan.textContent = i18n('daysCalendar');
    } else if (attributeType === 'workUnit'){
	  var paramUnit=window.top.paramWorkUnit;
	  if (paramUnit == 'hours') unitSpan.textContent = i18n('hours');
	  else unitSpan.textContent = i18n('daysCalendar');
	} else {
      unitSpan.textContent = '';
    }
  }
}
var attributeTypeStore = null;
function updateOperatorOptions(attributeType) {
  const operatorWidget = dijit.byId('operatorCompare');
  if (!operatorWidget) return;
  var data = operatorWidget.store.data.filter(opt => opt.value !== 'multi');
  if (attributeType === 'cost' || attributeType === 'work' || attributeType === 'workUnit') {
    data.push({ id: 'multi', value: 'multi', name: '×' });
  }
  operatorWidget.set('store', new dojo.store.Memory({ data: data }));
  operatorWidget.set('value', 'plus');
  attributeTypeStore = attributeType;
}

function handleOperatorChange(value) {
  const unitSpan = dojo.byId('compareUnit');
  if (!unitSpan) return;
  if (value === 'multi') {
    unitSpan.textContent = '';
  } else if (attributeTypeStore && attributeTypeStore =='work'){
	var paramImputationUnit=window.top.paramImputationUnit;
	if (paramImputationUnit == 'hours') unitSpan.textContent = i18n('hours');
    else unitSpan.textContent = i18n('daysCalendar');
  } else if(attributeTypeStore && attributeTypeStore =='workUnit'){
	var paramUnit=window.top.paramWorkUnit;
	if (paramUnit == 'hours') unitSpan.textContent = i18n('hours');
	else unitSpan.textContent = i18n('daysCalendar');
  }
}

function hideCompareValueInput() {
  const inputDiv = dojo.byId('filterCompareValueInput');
  if (inputDiv) {
    inputDiv.style.display = 'none';
  }
}

function filterSelectOperator(operator) {
  filterStartInput=true;
  const operatorFilteTypeNull = ['isEmpty', 'isNotEmpty', 'hasSome','hasNotes', 'hasAttachments', 'hasLinks', 'hasPredecessors', 'hasSuccessors'];  
     filterType="null";
  if (dijit.byId('filterCompareParameterSwitch')){
	dijit.byId('filterCompareParameterSwitch').set('value','off');
	if (!window.isEditingFilter) dijit.byId('filterValue').set('value', '');
	if (!window.isEditingFilterCompareValue) dijit.byId('filterCompareValue').set('value','');
	window.isEditingFilter = false;
	window.isEditingFilterCompareValue = false;
  }  
  dojo.byId('filterCompareParameterPane').style.display='block';
  dataType=dojo.byId('filterDataType').value;
  if (operator == "SORT") {
    filterType="SORT";
    dojo.style(dijit.byId('filterValue').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterValueList').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('FilterCompareAttribute').domNode,{
      display:'none'
    })
    dojo.byId('filterCompareParameterPane').style.display='none';
    dijit.byId("filterCompareParameter").set("checked",false);
    if (isNewGui) dojo.byId("filterDynamicParameterPane").style.left="200px";
    if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
    dojo.style(dijit.byId('showDetailInFilter').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterValueCheckbox').domNode,{
      display:'none'
    });
    if (dijit.byId('filterValueCheckboxSwitch')) {
      dojo.style(dijit.byId('filterValueCheckboxSwitch').domNode,{
        display:'none'
      });
    }
    dojo.style(dijit.byId('filterValueDate').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterSortValueList').domNode,{
      display:'block'
    });
    dojo.style(dijit.byId('FilterCompareAttribute').domNode,{
      display:'none'
    });
    dijit.byId('filterDynamicParameter').set('checked','');
    if (dijit.byId('filterDynamicParameterSwitch')) dijit.byId('filterDynamicParameterSwitch').set('value','off');
    dojo.byId('filterDynamicParameterPane').style.display='none';
    if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
    if (dijit.byId('filterCompareParameterSwitch')) dijit.byId('filterCompareParameterSwitch').set('value','off');
    
  }	else if (dataType == "hatchPattern") {
	dataTypeEdit='hatchPattern';
	if (operatorFilteTypeNull.includes(operator)) {
	  // isEmpty / isNotEmpty
	  dojo.style(dijit.byId('filterValueHatch').domNode, { display:'none' });
	  dojo.style(dijit.byId('filterValue').domNode, { display:'none' });
	} else {
	  dojo.style(dijit.byId('filterValueHatch').domNode, { display:'block' });
	  dijit.byId('filterValue').reset();
	}
			   
	dijit.byId('filterValue').reset();
	dojo.style(dijit.byId('filterValueList').domNode,{
	  display:'none'
	});
	dojo.byId('filterDynamicParameterPane').style.display='none';
	if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
	dojo.style(dijit.byId('showDetailInFilter').domNode,{
	  display:'none'
	});
	dojo.style(dijit.byId('filterValueCheckbox').domNode,{
	  display:'none'
	});
	if (dijit.byId('filterValueCheckboxSwitch')) {
		dojo.style(dijit.byId('filterValueCheckboxSwitch').domNode,{
	  	  display:'none'
		});
	}
	dojo.style(dijit.byId('filterValueDate').domNode,{
	   display:'none'
	});
	dojo.style(dijit.byId('FilterCompareAttribute').domNode,{
	  display:'none'
	});
	dojo.style(dijit.byId('filterSortValueList').domNode,{
	  display:'none'
	});
	
	dijit.byId("filterCompareParameter").set("checked", false);
	dojo.byId('filterCompareParameterPane').style.display = 'none';
	hideCompareValueInput();
  } else if (operator == "<=now+" || operator == ">=now+" || operator == "=month+" || operator == "=year+" ) {
    if (dijit.byId('filterCompareParameter').get('checked')) {
      dojo.style(dijit.byId('FilterCompareAttribute').domNode,{
        display:'block'
      });
      if (isNewGui) dojo.byId("filterCompareParameterPane").style.left="200px";
      if (isNewGui) dojo.byId("filterCompareParameterPane").style.top=(dojo.byId("filterDynamicParameterPane").style.display=='none')?"9px":"30px";
      dojo.style(dijit.byId('filterValue').domNode,{
        display:'none'
      });
      
    } else {
    filterType="text";
    dojo.style(dijit.byId('filterValue').domNode,{
      display:'block'
    });
    dojo.style(dijit.byId('filterValueList').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterValueDate').domNode,{
      display:'none'
    });
    if (isNewGui) dojo.byId("filterDynamicParameterPane").style.left="200px";
    if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
    dojo.style(dijit.byId('showDetailInFilter').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterValueCheckbox').domNode,{
      display:'none'
    });
    if (dijit.byId('filterValueCheckboxSwitch')) {
      dojo.style(dijit.byId('filterValueCheckboxSwitch').domNode,{
        display:'none'
      });
    }
    dojo.style(dijit.byId('filterSortValueList').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('FilterCompareAttribute').domNode,{
      display:'none'
    });
    }
	if (dijit.byId('filterCompareParameterSwitch')) dijit.byId('filterCompareParameterSwitch').set('value','off');
	dojo.byId('filterCompareParameterPane').style.display='none';
  } else if (operatorFilteTypeNull.includes(operator)){
    dojo.style(dijit.byId('filterValue').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterValueList').domNode,{
      display:'none'
    });
    if (isNewGui) dojo.byId("filterDynamicParameterPane").style.left="200px";
    if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
    dojo.style(dijit.byId('showDetailInFilter').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterValueCheckbox').domNode,{
      display:'none'
    });
    if (dijit.byId('filterValueCheckboxSwitch')) {
      dojo.style(dijit.byId('filterValueCheckboxSwitch').domNode,{
        display:'none'
      });
    }
    dojo.style(dijit.byId('filterValueDate').domNode,{
      display:'none'
    });
    dojo.style(dijit.byId('filterSortValueList').domNode,{
      display:'none'
    });
    dijit.byId('filterDynamicParameter').set('checked','');
    if (dijit.byId('filterDynamicParameterSwitch')) dijit.byId('filterDynamicParameterSwitch').set('value','off');
    dojo.byId('filterDynamicParameterPane').style.display='none';
    if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
    if (dijit.byId('filterCompareParameterSwitch')) dijit.byId('filterCompareParameterSwitch').set('value','off');
    dojo.byId('filterCompareParameterPane').style.display='none';
    if (dijit.byId('filterCompareParameter').get('checked')) {
      dojo.style(dijit.byId('FilterCompareAttribute').domNode,{
        display:'none'
      });
      dojo.style(dijit.byId('filterCompareParameter').domNode,{
        display:'none'
      });
    }
  } else {
    dojo.style(dijit.byId('filterValue').domNode,{
      display:'none'
    });
    dataType=dojo.byId('filterDataType').value;
    dojo.style(dijit.byId('filterSortValueList').domNode,{
      display:'none'
    });
    if (dataType == "bool") {
      dojo.byId('filterCompareParameterPane').style.display='none';
      filterType="bool";
      if (dijit.byId('filterValueCheckboxSwitch')) {
        dojo.style(dijit.byId('filterValueCheckboxSwitch').domNode,{
          display:'block'
        });
      } else {
        dojo.style(dijit.byId('filterValueCheckbox').domNode,{
          display:'block'
        });
      }
    } else if (dataType == "list") {
      filterType="list";
      dijit.byId("filterCompareParameter").set("checked",false);
      dojo.byId('filterCompareParameterPane').style.display='none';
	  
	  // --- #11774 : Dynamic parameter is no longer visible
	  dijit.byId('filterDynamicParameter').set('checked','');
	  if (dijit.byId('filterDynamicParameterSwitch')) dijit.byId('filterDynamicParameterSwitch').set('value','off');
	  if (editFilterValueCompare) dojo.byId('filterDynamicParameterPane').style.display = 'none';
	  else dojo.byId('filterDynamicParameterPane').style.display='block';
	  // ---------------------------------------------------
	  
//      if(dijit.byId('filterCompareParameter').get('checked')) {
//        dojo.style(dijit.byId('filterValueList').domNode,{
//          display:'none'
//        });
//        dojo.style(dijit.byId('FilterCompareAttribute').domNode,{
//          display:'block' 
//        });
//        dojo.style(dijit.byId('showDetailInFilter').domNode,{
//          display:'block'
//        });
//        dijit.byId('filterDynamicParameter').set('checked','');
//        if (dijit.byId('filterDynamicParameterSwitch')) dijit.byId('filterDynamicParameterSwitch').set('value','off');
//        dojo.byId('filterDynamicParameterPane').style.display='block';
//        if (isNewGui) dojo.byId("filterDynamicParameterPane").style.left="200px";
//        //if (isNewGui) dojo.byId("filterCompareParameterPane").style.left="200px";
//        //if (isNewGui) dojo.byId("filterCompareParameterPane").style.top="30px";
//        if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
//      }else{
        if (isNewGui) dojo.byId("filterDynamicParameterPane").style.left="8px";
        if (isNewGui) dojo.byId("filterValueListHideTop").style.display="block";
        //if (isNewGui) dojo.byId("filterCompareParameterPane").style.left="180px";
        //if (isNewGui) dojo.byId("filterCompareParameterPane").style.top="9px";
        //if(!dijit.byId('filterCompareParameter').get('checked')) {
        //  dojo.byId('filterCompareParameterPane').style.display='none';
        //}
 //     }
    } else if (dataType == "date") {
      filterType="date";
      dojo.style(dijit.byId('filterValueDate').domNode,{
        display:'block'
      });
      dijit.byId('filterDynamicParameter').set('checked','');
      if (dijit.byId('filterDynamicParameterSwitch')) dijit.byId('filterDynamicParameterSwitch').set('value','off');
      if (editFilterValueCompare) dojo.byId('filterDynamicParameterPane').style.display = 'none';
      else dojo.byId('filterDynamicParameterPane').style.display='block';
      if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
    } else {
      filterType="text";
      dojo.style(dijit.byId('filterValue').domNode,{
        display:'block'
      });
      dijit.byId('filterDynamicParameter').set('checked','');
      if (dijit.byId('filterDynamicParameterSwitch')) dijit.byId('filterDynamicParameterSwitch').set('value','off');
      if (editFilterValueCompare) dojo.byId('filterDynamicParameterPane').style.display = 'none';
      else dojo.byId('filterDynamicParameterPane').style.display='block';
      if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none"; 
	  if (dataType == "varchar" || dataType == 'refObject'){
		dojo.byId("filterCompareParameterPane").style.left="200px";
		dojo.byId("filterCompareParameterPane").style.top="30px";
		dojo.byId('filterCompareParameterPane').style.display='none';
	  }
    } 
    //#6012
    var objectClass='';
    if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) objectClass=dojo.byId('objectClassList').value;
    else if (dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) objectClass=getFilterAttributeObjectClass(dojo.byId("objectClassManual").value);
    else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) objectClass=dojo.byId('objectClass').value;
    if (objectClass.substr(0,7) == 'Report_') objectClass=objectClass.substr(7);
    if (dijit.byId('filterCompareParameter').get('checked')) {
      dojo.style(dijit.byId('FilterCompareAttribute').domNode,{
        display:'block'
      });
      if (isNewGui) dojo.byId("filterCompareParameterPane").style.left="200px";
      if (isNewGui) dojo.byId("filterCompareParameterPane").style.top=(dojo.byId("filterDynamicParameterPane").style.display=='none')?"9px":"30px";
      dojo.style(dijit.byId('filterValue').domNode,{
        display:'none'
      });
      dojo.style(dijit.byId('filterValueList').domNode,{
        display:'none'
      });
      dojo.style(dijit.byId('filterValueCheckbox').domNode,{
        display:'none'
      });
      dojo.style(dijit.byId('filterValueDate').domNode,{
        display:'none'
      });
      dojo.style(dijit.byId('filterSortValueList').domNode,{
        display:'none'
      });
      //refreshListSpecific('object','FilterCompareAttribute','objectClass',objectClass, null, false, 'field', value);
    }else{
      dojo.style(dijit.byId('FilterCompareAttribute').domNode,{
        display:'none'
      }); 
    }    //#6012
  }
  if (editFilterValueCompare && dijit.byId('filterCompareParameterSwitch')){
    dijit.byId('filterCompareParameterSwitch').set('value','on');
    dojo.byId('filterDynamicParameterPane').style.display = 'none';
  }else{
    dijit.byId('filterCompareParameterSwitch').set('value','off');
  }
  if (editFilterValueDynamic !== null && editFilterValueDynamic == 1 && dijit.byId('filterCompareParameterSwitch')){
    dijit.byId('filterDynamicParameterSwitch').set('value','on');
  }else{
    dijit.byId('filterDynamicParameterSwitch').set('value','off');
  }
  // PBER #11112 - Button was always hidden
  //if (editFilterOperator!='NOT IN' && editFilterOperator!='IN' ){
  if (operator && operator!='NOT IN' && operator!='IN' ){
   // dojo.byId('showDetailInFilter').style.display='none'; 
   dojo.style(dijit.byId('filterValueList').domNode,{display:'none'});
   if (isNewGui) dojo.byId("filterValueListHideTop").style.display="none";
   dojo.style(dijit.byId('showDetailInFilter').domNode, {display : 'none'});
  }else{
    //dojo.byId('showDetailInFilter').style.display='block';
    dojo.style(dijit.byId('filterValueList').domNode,{display:'block'});
    if (isNewGui) dojo.byId("filterDynamicParameterPane").style.left="8px";
    if (isNewGui) dojo.byId("filterValueListHideTop").style.display="block";
    dojo.style(dijit.byId('showDetailInFilter').domNode, {display : 'block'});
  }
}

function getFilterCriteriaScrollPosition() {
  var container=dojo.byId('listFilterClauses');
  if (!container) return null;
  return {
    top:container.scrollTop,
    atBottom:(container.scrollHeight-container.clientHeight-container.scrollTop)<=2
  };
}

function restoreFilterCriteriaScrollPosition(position) {
  if (!position) return;
  var restorePosition=function() {
    var container=dojo.byId('listFilterClauses');
    if (!container) return;
    container.scrollTop=position.atBottom ? container.scrollHeight-container.clientHeight : position.top;
  };
  restorePosition();
  setTimeout(restorePosition, 0);
}

function addfilterClause(silent,updateFilter,replaceIdFilterClause) {
  filterStartInput=false;
  var scrollPosition=getFilterCriteriaScrollPosition();
  var isGroup = dojo.byId('isGroup');
  var indentLevel = dojo.byId('indentLevel');
  var selectedCursorBeforeAdd=dojo.byId("cursorFilter");
  var selectedOnLastLine=selectedCursorBeforeAdd && selectedCursorBeforeAdd.getAttribute("data-filter-entry")=="0";
  var selectedConditionOrder=selectedCursorBeforeAdd ? selectedCursorBeforeAdd.getAttribute("data-condition-order") : null;

  if (isGroup && isGroup.value=="1" && getPendingFilterOpenError(true)=="maximumLevel") {
    if (!silent) showAlert(i18n("filterGroupLevelMax"));
    return;
  }
  
  if (dijit.byId('filterNameDisplay')) {
    dojo.byId('filterName').value=dijit.byId('filterNameDisplay').get('value');
  }
  if (filterType == "") {
    if (!silent) showAlert(i18n('attributeNotSelected'));
    return;
  }
  if (trim(dijit.byId('idFilterOperator').get('value')) == '') {
    if (!silent) showAlert(i18n('operatorNotSelected'));
    return;
  }

  if ( dijit.byId('idFilterOperator') && (dijit.byId('idFilterOperator').get('value')=='=month+' || dijit.byId('idFilterOperator').get('value')=='=year+')){
	if (!dijit.byId('filterValue').get('value')) dijit.byId('filterValue').set('value', '0');
  }
  if (!dijit.byId('filterDynamicParameter').get('checked')) {
    if (!dijit.byId('filterCompareParameter').get('checked')) {
      if (filterType == "list" && trim(dijit.byId('filterValueList').get('value')) == '') {
        if (!silent) showAlert(i18n('valueNotSelected'));
        return;
      }
    }
    if (!dijit.byId('filterCompareParameter').get('checked')) {
      if (filterType == "date" && !dijit.byId('filterValueDate').get('value')) {
        if (!silent) showAlert(i18n('valueNotSelected'));
        return;
      }
    }
    if (!dijit.byId('filterCompareParameter').get('checked')) {
      if (filterType == "text" && !dijit.byId('filterValue').get('value')) {
        if (!silent) showAlert(i18n('valueNotSelected'));
        return;
      }
    }else{
      if (filterType == "text" && !dijit.byId('FilterCompareAttribute').get('value')) {
        if (!silent) showAlert(i18n('valueNotSelected'));
        return;
      } else {
		dijit.byId('filterValueDate').set('value', null);
		dijit.byId('filterValue').set('value', '');
	  }
    }
	
    if (dijit.byId('idFilterAttribute').get('value') == 'idle' && dijit.byId('idFilterOperator').get('value') == '=' && dijit.byId('filterValueCheckbox').get('checked')) {
      dijit.byId('listShowIdle').set('checked',true);
    }
  }else{
	if(dojo.byId('idFilterFromFavoriteProject') && dojo.byId('idFilterFromFavoriteProject').value != ''){
		showAlert(i18n('cantBeDynamicFilter'));
		return;
	}
  }
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '?comboDetail=true' : '';
  compUrl += (compUrl ? "&" : "?") + "updateFilter=" + (updateFilter ? "true" : "false");
  compUrl += "&replaceFilterClause=" +(replaceIdFilterClause != undefined ? replaceIdFilterClause : '');
  if (updateFilter && dojo.byId('filterInsertPosition')) dojo.byId('filterInsertPosition').value='';
  dojo.byId('filterEditId').value=(updateFilter)?editFilterIndex:null;
  loadContent("../tool/addFilterClause.php" + compUrl,"listFilterClauses","dialogFilterForm",false,null,null,null,function() {
    clearDivDelayed('saveFilterResult');
    isGroup.value = "0";
    indentLevel.value = "0";
    if (selectedOnLastLine) {
      var lastCursor=document.querySelector('.filterInsertCursor[data-filter-entry="0"]');
      if (lastCursor) {
        selectFilterInsertPosition(lastCursor.getAttribute("data-insert-position"), lastCursor);
      }
    } else if (updateFilter && selectedConditionOrder!==null) {
      var updatedCursor=document.querySelector('.filterInsertCursor[data-condition-order="' + selectedConditionOrder + '"]');
      if (updatedCursor) {
        selectFilterInsertPosition(updatedCursor.getAttribute("data-insert-position"), updatedCursor);
      }
    } else if (!selectedCursorBeforeAdd) {
      var defaultLastCursor=document.querySelector('.filterInsertCursor[data-filter-entry="0"]');
      if (defaultLastCursor) {
        selectFilterInsertPosition(defaultLastCursor.getAttribute("data-insert-position"), defaultLastCursor);
      }
    } else if (dojo.byId('filterInsertPosition') && dojo.byId('filterInsertPosition').value!=='') {
      selectFilterInsertPosition(dojo.byId('filterInsertPosition').value);
    }
    restoreFilterCriteriaScrollPosition(scrollPosition);
  });
  if (dojo.byId('filterLogicalOperator') && dojo.byId('filterLogicalOperator').style.display == 'none') {
    dojo.byId('filterLogicalOperator').style.display='block';
  }
  dojo.byId('buttonSaveFieldEdition').style.display='none';
}

function selectFilterInsertPosition(position, selectedCursor) {
  if (!dojo.byId('filterInsertPosition')) return;
  dojo.byId('filterInsertPosition').value=position;
  var cursors=document.querySelectorAll('.filterInsertCursor');
  for (var i=0;i<cursors.length;i++) {
    cursors[i].style.opacity='0.25';
    cursors[i].removeAttribute('id');
    if (cursors[i].parentNode) {
      dojo.removeClass(cursors[i].parentNode,'imageColorNewGui');
      dojo.addClass(cursors[i].parentNode,'imageColorNewGuiNoSelection');
    }
  }
  var cursor=selectedCursor ? selectedCursor : document.querySelector('.filterInsertCursor[data-insert-position="' + position + '"]');
  if (cursor) {
    cursor.style.opacity='1';
    cursor.id='cursorFilter';
    if (cursor.parentNode) {
      dojo.removeClass(cursor.parentNode,'imageColorNewGuiNoSelection');
      dojo.addClass(cursor.parentNode,'imageColorNewGui');
    }
  }
  updateFilterGroupButtons();
}

function removefilterClause(id) {
  var scrollPosition=getFilterCriteriaScrollPosition();
  if (dojo.byId('filterInsertPosition')) dojo.byId('filterInsertPosition').value='';
  if (dijit.byId('filterNameDisplay')) {
    dojo.byId('filterName').value=dijit.byId('filterNameDisplay').get('value');
  }
  if (dijit.byId('idLayout')) {
    dojo.byId('filterLayout').value=dijit.byId('idLayout').get('value');
  }
  dojo.byId("filterClauseId").value=id;
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '?comboDetail=true' : '';
  loadContent("../tool/removeFilterClause.php" + compUrl ,"listFilterClauses","dialogFilterForm",false,null,null,null,function() {
    updateFilterGroupButtons();
    restoreFilterCriteriaScrollPosition(scrollPosition);
  });
  if (id == 'all' || dojo.byId('nbFilterCriteria').value == "1") { // Value is
    // not set
    // to 0
    // already
    // but is
    // going to
    dojo.byId('filterLogicalOperator').style.display='none';
  } else if (dojo.byId('nbFilterCriteria').value == "2") { // Value is going to
    // be set at 1
    loadContent("../tool/displayFilterClause.php" + compUrl,"listFilterClauses","dialogFilterForm",false,null,null,null,function() {
      clearDivDelayed('saveFilterResult');
      restoreFilterCriteriaScrollPosition(scrollPosition);
    });
  }
}

function removeFilterGroup(markerReference, event) {
  if (event) dojo.stopEvent(event);
  var scrollPosition=getFilterCriteriaScrollPosition();
  var selectedCursor=dojo.byId("cursorFilter");
  var selectedOnLastLine=selectedCursor && selectedCursor.getAttribute("data-filter-entry")=="0";
  var selectedOrder=selectedCursor ? selectedCursor.getAttribute("data-condition-order") : null;
  if (dijit.byId('filterNameDisplay')) {
    dojo.byId('filterName').value=dijit.byId('filterNameDisplay').get('value');
  }
  if (dijit.byId('idLayout')) {
    dojo.byId('filterLayout').value=dijit.byId('idLayout').get('value');
  }
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '?comboDetail=true' : '';
  compUrl+=(compUrl ? '&' : '?') + 'filterGroupMarkerReference=' + encodeURIComponent(markerReference);
  loadContent("../tool/removeFilterGroup.php" + compUrl, "listFilterClauses", "dialogFilterForm", false, null, null, null, function() {
    var cursor=null;
    if (selectedOnLastLine) {
      cursor=document.querySelector('.filterInsertCursor[data-filter-entry="0"]');
    } else if (selectedOrder!==null) {
      cursor=document.querySelector('.filterInsertCursor[data-condition-order="' + selectedOrder + '"]');
    }
    if (cursor) {
      selectFilterInsertPosition(cursor.getAttribute("data-insert-position"), cursor);
    } else {
      updateFilterGroupButtons();
    }
    restoreFilterCriteriaScrollPosition(scrollPosition);
  });
}

function selectFilter(skipRefresh,fromSave) {
  if (skipRefresh==null || skipRefresh==undefined) skipRefresh=false;
  if (fromSave==null || fromSave==undefined) fromSave=false;
  if (!validateFilterParentheses()) {
    return false;
  }
  if (filterStartInput) {
	if (editFilterIndex !== null && editFilterIndex !== undefined) {
	  addfilterClause(true, true, editFilterIndex);
	} else {
	  addfilterClause(true);
	}
    setTimeout("selectFilterContinue("+((skipRefresh)?'true':'false')+");",1000);
  } else {
    selectFilterContinue(skipRefresh,fromSave);
  }
}

var timeoutSetCheck1=null;
var timeoutSetCheck2=null;
function selectFilterContinue(skipRefresh,fromSave) {
  if (skipRefresh==null || skipRefresh==undefined) skipRefresh=false;
  if (fromSave==null || fromSave==undefined) fromSave=false;
  if (window.top.dijit.byId('dialogDetail').open) {
    var doc=window.top.frames['comboDetailFrame'];
  } else {
    var doc=window.top;
  }
  if (dijit.byId('filterNameDisplay')) {
    dojo.byId('filterName').value=dijit.byId('filterNameDisplay').get('value');
  }
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
  dojo.xhrPost({
    url:"../tool/backupFilter.php?valid=true" + compUrl +addTokenIndexToUrl(),
    form:'dialogFilterForm',
    handleAs:"text",
    load:function(data,args) {
    }
  });
  if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) {
    objectClass=dojo.byId('objectClassList').value;
  } else if (!window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) {
    objectClass=dojo.byId("objectClassManual").value;
  } else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) {
    objectClass=dojo.byId('objectClass').value;
  }
  var currentScreen = (!window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) ? dojo.byId("objectClassManual").value : objectClass;
  if (currentScreen) compUrl += '&currentscreen=' + currentScreen;
  if (dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value == 'Kanban') {
    compUrl+='&context=directFilterList';
    compUrl+='&contentLoad=../tool/jsonKanban.php';
    compUrl+='&container=kanbanJsonData';
  }
  doc.loadContent("../tool/displayFilterList.php?displayQuickFilter=true&context=directFilterList&filterObjectClass=" + objectClass + compUrl,
                  "directFilterList",null,false,'returnFromFilter'+((skipRefresh)?'SkipRefresh':''),false);
  /*
   * florent Ticket #4010 When adding filter (not stored), icon has not the "on"
   * flag
   */
  var setCheckFilter=null;
  if (dojo.byId("nbFilterCriteria").value > 0 && !dijit.byId('filterDynamicParameter').get("checked") && dojo.byId('nbDynamicFilterCriteria').value == 0) {
    setCheckFilter=function() {
      dijit.byId('listFilterFilter').set('iconClass', 'dijitButtonIcon iconActiveFilter');
    }
  } else {
    setCheckFilter=function() {
      dijit.byId('listFilterFilter').set('iconClass', 'dijitButtonIcon iconFilter');
    }
  }
  setTimeout(setCheckFilter,500);
  if (timeoutSetCheck1) clearTimeout(timeoutSetCheck1);
  if (timeoutSetCheck2) clearTimeout(timeoutSetCheck2);
  timeoutSetCheck1=setTimeout(setCheckFilter,1000);
  timeoutSetCheck2=setTimeout(setCheckFilter,2000);
  if (skipRefresh) {
	if(!fromSave){
		dijit.byId("dialogFilter").hide();
	}
	filterStartInput=false;
	return;
  }
  if (!window.top.dijit.byId('dialogDetail').open && dojo.byId('objectClassManual') && (dojo.byId('objectClassManual').value == 'Kanban' || dojo.byId('objectClassManual').value == 'LiveMeeting')) {
    refreshKanban();
  } else if (!dijit.byId('filterDynamicParameter').get("checked")) {
    if (dojo.byId("objectClassManual") && (dojo.byId("objectClassManual").value == 'Planning' || dojo.byId("objectClassManual").value == 'PlanningWorkPlan') && !window.top.dijit.byId('dialogDetail').open) {
      refreshJsonPlanning();
    } else if (dojo.byId("objectClassManual") && (dojo.byId("objectClassManual").value == 'VersionsPlanning' || dojo.byId("objectClassManual").value == 'ResourcePlanning')
        && !window.top.dijit.byId('dialogDetail').open) {
      if (dojo.byId("objectClassManual").value == 'VersionsPlanning') {
        refreshJsonPlanning('version');
      } else {
        refreshJsonPlanning('resource');
      }
    } else if (dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value == 'Report') {
      dojo.byId('outMode').value='';
      runReport();
    } else {
      doc.refreshJsonList(objectClass);
    }
  }
  if(!fromSave){
  	dijit.byId("dialogFilter").hide();
  }
  filterStartInput=false;
}

function cancelFilter() {
  filterStartInput=true;
  resetOpenCloseGroup();
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
  dojo.xhrPost({
    url:"../tool/backupFilter.php?cancel=true" + compUrl +addTokenIndexToUrl(),
    form:'dialogFilterForm',
    handleAs:"text",
    load:function(data,args) {
    }
  });
  dijit.byId('dialogFilter').hide();
}

function clearFilter() {
  if (dijit.byId('filterNameDisplay')) {
    dijit.byId('filterNameDisplay').reset();
  }
  if (dijit.byId('idLayout')) {
    dijit.byId('idLayout').reset();
  }
  dojo.byId('filterName').value="";
  dojo.byId('filterLayout').value="";
  removefilterClause('all');
  // setTimeout("selectFilter();dijit.byId('listFilterFilter').set('iconClass','dijitButtonIcon
  // iconFilter');",100);
  if (timeoutSetCheck1) clearTimeout(timeoutSetCheck1);
  if (timeoutSetCheck2) clearTimeout(timeoutSetCheck2);
  dijit.byId('listFilterFilter').set('iconClass','dijitButtonIcon iconFilter');
  dijit.byId('filterNameDisplay').set('value',null);
  dojo.byId('filterName').value=null;
  dijit.byId('idLayout').set('value',null);
  dojo.byId('filterLayout').value=null;
  resetOpenCloseGroup();
}

function defaultFilter(removeDefaultFilter,filterName) {
  if (!removeDefaultFilter) removeDefaultFilter=false; 
  if (!filterName) filterName=null;
  if (dijit.byId('filterNameDisplay') && !removeDefaultFilter && filterName==null) {
    dojo.byId('filterName').value=dijit.byId('filterNameDisplay').get('value');
  }else if (filterName){
    dojo.byId('filterName').value=filterName;
  }
  var removeParam = (compUrl ? "&" : "?") + "removeDefaultFilter=" + (removeDefaultFilter ? "1" : "0");
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '?comboDetail=true' : '';
  loadContent("../tool/defaultFilter.php" + compUrl + removeParam,"listStoredFilters","dialogFilterForm",false,null,null,null,function() {
    clearDivDelayed('saveFilterResult');
  });
}

function saveFilterToFavoriteProjectList(idFilter, mode, fromFavoriteProjectList) {
  if(fromFavoriteProjectList == undefined)fromFavoriteProjectList=false;
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '?comboDetail=true' : '';
  var idFilter = (compUrl ? '&' : '?') + 'idFilter=' + idFilter;
  var mode = "&mode="+mode;
  if(fromFavoriteProjectList){
	dojo.xhrGet({
	    url:"../tool/saveFilterToFavoriteProjectList.php"+ compUrl + idFilter + mode + addTokenIndexToUrl(),
	    handleAs:"text",
	    load:function(data,args) {
	    },
	    error:function() {
	    }
	  });
  }else{
	loadContent("../tool/saveFilterToFavoriteProjectList.php" + compUrl + idFilter + mode,"listStoredFilters","dialogFilterForm",false,null,null,null,function() {
		refreshProjectSelectorList();
	    clearDivDelayed('saveFilterResult');
	  });
  }
}

function copyFilterShared(idFilter){
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '?comboDetail=true' : '';
  var idFilter = (compUrl ? '&' : '?') + 'idFilter=' + idFilter;
  loadContent("../tool/saveFilterShared.php" + compUrl + idFilter ,"listStoredFilters",null,false,null,null,null,function() {
    clearDivDelayed('saveFilterResult');
  });
}

function saveFilter() {
  if (dijit.byId('filterNameDisplay')) {
    if (dijit.byId('filterNameDisplay').get('value') == "") {
      showAlert(i18n("messageMandatory",new Array(i18n("filterName"))));
      return;
    }
    dojo.byId('filterName').value=dijit.byId('filterNameDisplay').get('value');
  }
  if (!validateFilterParentheses()) {
    return false;
  }
  resetOpenCloseGroup();
  
  var nbFilter=dojo.byId('nbFilterCriteria');
  if (nbFilter && nbFilter.value == 0) {
    showAlert(i18n("cantSaveFilterWithNoClause"));
    return;
  }
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '?comboDetail=true' : '';
  loadContent("../tool/saveFilter.php" + compUrl,"listStoredFilters","dialogFilterForm",false,null,null,null,function() {
	refreshProjectSelectorList();
	selectFilter(true,true);
    clearDivDelayed('saveFilterResult');
  });
}

editFilterOperator=null;
editFilterOperatorDisp=null;
editFilterValue=null;
editFilterValueDisp=null;
editFilterValueDynamic=null;
editFilterValueCompare=null;
editFilterIndex=null;
function editFilterClause(id){
  if (dojo.byId("isGroup") && dojo.byId("isGroup").value=="1") {
    resetOpenCloseGroup();
  }
  var filterRow=dojo.byId('idFilterTr_'+id);
  var lineCursor=filterRow ? filterRow.querySelector('.filterInsertCursor') : null;
  if (lineCursor) {
    selectFilterInsertPosition(lineCursor.getAttribute('data-insert-position'), lineCursor);
  }
	if (dojo.byId('filterObjectClass') && dojo.byId('filterObjectClass').value)objectFilterClass = dojo.byId('filterObjectClass').value;
	else if (!dojo.byId('objectClass').value && dojo.byId('objectClassManual').value) objectFilterClass=dojo.byId('objectClassManual').value;
	else objectFilterClass = dojo.byId('objectClass').value;
  dojo.xhrPost({
    url:"../tool/getFilterClause.php?objectClass="+objectFilterClass+"&filterClause=" + id + addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data,args) {
      var res=JSON.parse(data);
      currentAttribute=dijit.byId('idFilterAttribute').value;
      editFilterOperator=res.sql.operator;
      editFilterOperatorDisp=res.disp.operator;
      editFilterValue=res.sql.value;
      editFilterValueDisp=res.disp.value;
      editFilterIndex=id;
	  var sqlAttribute = res.sql.attribute;
      if (lineCursor && lineCursor.getAttribute('data-condition-order')=='0' && dojo.byId('filterLogicalOperator')){
		dojo.byId('filterLogicalOperator').style.display='none';
	  }else{
		dojo.byId('filterLogicalOperator').style.display='block';
	  }
      editFilterValueCompare=(editFilterValue && editFilterValue[0]=='[')?true:false; 
      editFilterValueDynamic=res.isDynamic;
      dijit.byId('orOperator').set('value',res.orOperator);
      dijit.byId('idFilterAttribute').set('value',sqlAttribute);
      if (currentAttribute==sqlAttribute) filterSelectAtribute(currentAttribute);
      setTimeout("editFilterOperator=null;editFilterValue=null;editFilterValueDynamic=null;editFilterValueCompare=null;editFilterOperatorDisp=null;editFilterValue=null;",2000);     
    }
  });
}

function getSelectedFilterGroupCursor(action) {
  var selectedCursor=dojo.byId("cursorFilter");
  if (!selectedCursor) return null;
  if (selectedCursor.getAttribute("data-filter-condition")=="1") {
    return selectedCursor;
  }
  if (action=="close" && selectedCursor.getAttribute("data-filter-entry")=="0") {
    var conditionCursors=document.querySelectorAll('.filterInsertCursor[data-filter-condition="1"]');
    if (conditionCursors.length>0) {
      return conditionCursors[conditionCursors.length-1];
    }
  }
  return null;
}

function getFilterGroupRowsError(cursors, selectedOrder, action, replaceSelectedOpen) {
  var level=0;
  var groupConditionCounts=[];
  for (var i=0;i<cursors.length;i++) {
    var openCount=parseInt(cursors[i].getAttribute("data-group-open-count") || "0", 10);
    var closeCount=parseInt(cursors[i].getAttribute("data-group-close-count") || "0", 10);
    if (i==selectedOrder && action=="open") openCount++;
    if (i==selectedOrder && action=="close") closeCount++;
    if (i==selectedOrder && replaceSelectedOpen) openCount--;
    for (var openId=0;openId<openCount;openId++) {
      level++;
      if (level>3) return "maximumLevel";
      groupConditionCounts.push(0);
    }
    for (var groupId=0;groupId<groupConditionCounts.length;groupId++) {
      groupConditionCounts[groupId]++;
    }
    for (var closeId=0;closeId<closeCount;closeId++) {
      if (level==0) return "missingOpenGroup";
      if (groupConditionCounts[groupConditionCounts.length-1]<2) {
        return "notEnoughGroupContent";
      }
      groupConditionCounts.pop();
      level--;
    }
  }
  return "";
}

function isPendingFilterOpenContext(action) {
  if (action!="open") return false;
  var editButton=dojo.byId("buttonSaveFieldEdition");
  if (editButton && editButton.style.display!="none") return false;
  var conditionCursors=document.querySelectorAll('.filterInsertCursor[data-filter-condition="1"]');
  var nbFilter=dojo.byId("nbFilterCriteria");
  if (conditionCursors.length==0 && nbFilter && nbFilter.value=="0") {
    return true;
  }
  var selectedCursor=dojo.byId("cursorFilter");
  if (!selectedCursor) return filterStartInput;
  return selectedCursor.getAttribute("data-filter-entry")=="0" || filterStartInput;
}

function getPendingFilterOpenError(ignorePendingGroup) {
  var isGroup=dojo.byId("isGroup");
  if (!ignorePendingGroup && isGroup && isGroup.value=="1") {
    return "alreadyOpen";
  }
  var conditionCursors=document.querySelectorAll('.filterInsertCursor[data-filter-condition="1"]');
  if (conditionCursors.length==0) return "";
  var selectedCursor=dojo.byId("cursorFilter");
  if (!selectedCursor) {
    selectedCursor=document.querySelector('.filterInsertCursor[data-filter-entry="0"]');
  }
  if (!selectedCursor) return "noLine";
  var level=0;
  for (var i=0;i<conditionCursors.length;i++) {
    if (conditionCursors[i]===selectedCursor) break;
    level+=parseInt(conditionCursors[i].getAttribute("data-group-open-count") || "0", 10);
    level-=parseInt(conditionCursors[i].getAttribute("data-group-close-count") || "0", 10);
  }
  return (level>=3) ? "maximumLevel" : "";
}

function getFilterGroupChangeError(action) {
  if (isPendingFilterOpenContext(action)) {
    return getPendingFilterOpenError(false);
  }
  var selectedCursor=getSelectedFilterGroupCursor(action);
  if (!selectedCursor || !dojo.byId('filterInsertPosition')) return "noLine";
  var selectedOrder=parseInt(selectedCursor.getAttribute("data-condition-order"), 10);
  if (isNaN(selectedOrder)) return "noLine";
  var selectedOpenCount=parseInt(selectedCursor.getAttribute("data-group-open-count") || "0", 10);
  if (action=="open" && selectedOpenCount>0) {
    return "alreadyOpen";
  }
  var cursors=document.querySelectorAll('.filterInsertCursor[data-filter-condition="1"]');
  var error=getFilterGroupRowsError(cursors, selectedOrder, action, false);
  if (action=="close" && error=="notEnoughGroupContent" && selectedOpenCount>0) {
    error=getFilterGroupRowsError(cursors, selectedOrder, action, true);
  }
  return error;
}

function updateFilterGroupButtons() {
  var openButton=dijit.byId("dialogFilterOpenGroup");
  var closeButton=dijit.byId("dialogFilterCloseGroup");
  if (!openButton || !closeButton) return;
  var isGroup=dojo.byId("isGroup");
  var pendingOpen=isGroup && isGroup.value=="1";
  setPendingFilterOpenGroup(pendingOpen);
  openButton.set("disabled", getFilterGroupChangeError("open")!="");
  closeButton.set("disabled", pendingOpen || getFilterGroupChangeError("close")!="");
}

function changeFilterGroup(action) {
  var error=getFilterGroupChangeError(action);
  if (error=="maximumLevel") {
    showAlert(i18n("filterGroupLevelMax"));
    return;
  }
  if (error=="missingOpenGroup") {
    showAlert(i18n("groupNotOpen"));
    return;
  }
  if (error=="emptyGroup") {
    showAlert(i18n("filterGroupEmpty"));
    return;
  }
  if (error=="notEnoughGroupContent") {
    showAlert(i18n("filterGroupNeedsTwoCriteria"));
    return;
  }
  if (error!="") return;
  if (isPendingFilterOpenContext(action)) {
    if (dojo.byId("isGroup")) dojo.byId("isGroup").value="1";
    if (dojo.byId("indentLevel")) dojo.byId("indentLevel").value="0";
    updateFilterGroupButtons();
    return;
  }
  var scrollPosition=getFilterCriteriaScrollPosition();
  var selectedLineCursor=dojo.byId("cursorFilter");
  var selectedCursor=getSelectedFilterGroupCursor(action);
  if (!selectedLineCursor || !selectedCursor) return;
  var selectedOnLastLine=(selectedLineCursor.getAttribute("data-filter-entry")=="0");
  if (dijit.byId('filterNameDisplay')) {
    dojo.byId('filterName').value=dijit.byId('filterNameDisplay').get('value');
  }
  if (dijit.byId('idLayout')) {
    dojo.byId('filterLayout').value=dijit.byId('idLayout').get('value');
  }
  var selectedOrder=selectedCursor.getAttribute("data-condition-order");
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '?comboDetail=true' : '';
  compUrl+=(compUrl ? '&' : '?') + 'filterGroupAction=' + action;
  compUrl+='&filterGroupConditionPosition=' + selectedCursor.getAttribute("data-condition-position");
  compUrl+='&filterGroupConditionOrder=' + selectedOrder;
  loadContent("../tool/updateFilterGroup.php" + compUrl, "listFilterClauses", "dialogFilterForm", false, null, null, null, function() {
    var updateError=dojo.byId("filterGroupUpdateError");
    if (updateError && updateError.value=="maximumLevel") {
      showAlert(i18n("filterGroupLevelMax"));
    } else if (updateError && updateError.value=="missingOpenGroup") {
      showAlert(i18n("groupNotOpen"));
    } else if (updateError && updateError.value=="emptyGroup") {
      showAlert(i18n("filterGroupEmpty"));
    } else if (updateError && updateError.value=="notEnoughGroupContent") {
      showAlert(i18n("filterGroupNeedsTwoCriteria"));
    }
    var nextOrder=dojo.byId("filterGroupNextConditionOrder");
    var cursor=null;
    if (selectedOnLastLine) {
      cursor=document.querySelector('.filterInsertCursor[data-filter-entry="0"]');
    } else {
      cursor=document.querySelector('.filterInsertCursor[data-condition-order="' + (nextOrder ? nextOrder.value : selectedOrder) + '"]');
    }
    if (cursor) selectFilterInsertPosition(cursor.getAttribute("data-insert-position"), cursor);
    restoreFilterCriteriaScrollPosition(scrollPosition);
  });
}

function setPendingFilterOpenGroup(display) {
  var markers=document.querySelectorAll(".pendingFilterOpenGroupMarker");
  for (var i=0;i<markers.length;i++) {
    markers[i].style.display="none";
  }
  var operators=document.querySelectorAll(".pendingFilterLogicalOperator");
  for (var operatorId=0;operatorId<operators.length;operatorId++) {
    operators[operatorId].style.display="none";
  }
  var emptyCursor=dojo.byId("cursorFilterNoFilterClause");
  if (emptyCursor) emptyCursor.style.display="none";
  if (!display) return;
  var selectedCursor=dojo.byId("cursorFilter");
  if (!selectedCursor) {
    selectedCursor=document.querySelector('.filterInsertCursor[data-filter-entry="0"]');
  }
  if (selectedCursor) {
    var parent=selectedCursor.parentNode;
    while (parent && parent.tagName!="TD") {
      parent=parent.parentNode;
    }
    var selectedMarker=parent ? parent.querySelector(".pendingFilterOpenGroupMarker") : null;
    if (selectedMarker) selectedMarker.style.display="flex";
  } else {
    var emptyMarker=dojo.byId("pendingFilterOpenGroup");
    if (emptyCursor) emptyCursor.style.display="block";
    if (emptyMarker) emptyMarker.style.display="flex";
  }
  updatePendingFilterLogicalOperator();
}

function updatePendingFilterLogicalOperator() {
  var operators=document.querySelectorAll(".pendingFilterLogicalOperator");
  for (var i=0;i<operators.length;i++) {
    operators[i].style.display="none";
  }
  var isGroup=dojo.byId("isGroup");
  if (!isGroup || isGroup.value!="1") return;
  var conditionCursors=document.querySelectorAll('.filterInsertCursor[data-filter-condition="1"]');
  var selectedCursor=dojo.byId("cursorFilter");
  if (!selectedCursor) {
    selectedCursor=document.querySelector('.filterInsertCursor[data-filter-entry="0"]');
  }
  var isFirstCondition=conditionCursors.length==0;
  if (selectedCursor && selectedCursor.getAttribute("data-filter-condition")=="1"
      && selectedCursor.getAttribute("data-condition-order")=="0") {
    isFirstCondition=true;
  }
  if (isFirstCondition || !selectedCursor) return;
  var parent=selectedCursor.parentNode;
  while (parent && parent.tagName!="TD") {
    parent=parent.parentNode;
  }
  var selectedOperator=parent ? parent.querySelector(".pendingFilterLogicalOperator") : null;
  var logicalOperator=dijit.byId("orOperator");
  if (!selectedOperator || !logicalOperator) return;
  var isOr=logicalOperator.get("value")=="1";
  selectedOperator.innerHTML=isOr ? i18n("OR") : i18n("AND");
  selectedOperator.style.backgroundColor=isOr ? "#e97c2d" : "#10c621";
  selectedOperator.style.display="flex";
}

function resetOpenCloseGroup(){
  if (dojo.byId("isGroup")) dojo.byId("isGroup").value="0";
  if (dojo.byId("indentLevel")) dojo.byId("indentLevel").value="0";
  setPendingFilterOpenGroup(false);
  updateFilterGroupButtons();
}

function validateFilterParentheses() {
  var cursors=document.querySelectorAll('.filterInsertCursor[data-filter-condition="1"]');
  var level=0;
  var groupConditionCounts=[];
  for (var i=0;i<cursors.length;i++) {
    var openCount=parseInt(cursors[i].getAttribute("data-group-open-count") || "0", 10);
    var closeCount=parseInt(cursors[i].getAttribute("data-group-close-count") || "0", 10);
    for (var openId=0;openId<openCount;openId++) {
      level++;
      if (level>3) {
        showAlert(i18n("filterGroupLevelMax"));
        return false;
      }
      groupConditionCounts.push(0);
    }
    for (var groupId=0;groupId<groupConditionCounts.length;groupId++) {
      groupConditionCounts[groupId]++;
    }
    for (var closeId=0;closeId<closeCount;closeId++) {
      if (level==0) {
        showAlert(i18n("groupNotOpen"));
        return false;
      }
      if (groupConditionCounts[groupConditionCounts.length-1]<2) {
        showAlert(i18n("filterGroupNeedsTwoCriteria"));
        return false;
      }
      groupConditionCounts.pop();
      level--;
    }
  }
  if (level>0) {
    showAlert(i18n("groupNotClose"));
    return false;
  }
  return true;
}



/**
 * Select a stored filter in the list and fetch criteria
 * 
 */
var globalSelectFilterContentLoad=null;
var globalSelectFilterContainer=null;
function selectStoredFilter(idFilter,idLayout,context,contentLoad,container) {
  if (dojo.byId('filterInsertPosition')) dojo.byId('filterInsertPosition').value='';
  if (dojo.byId('buttonSaveFieldEdition')) dojo.byId('buttonSaveFieldEdition').style.display='none';
  resetOpenCloseGroup();
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
  globalSelectFilterContentLoad=null;
  globalSelectFilterContainer=null;
  var callBack= function(){
    validateLayoutListColumn();
    updateFilterGroupButtons();
  };
  if (context == 'directFilterList') {
    if (dojo.byId('noFilterSelected')) {
      if (idFilter == '0') {
        dojo.byId('noFilterSelected').value='true';
      } else {
        dojo.byId('noFilterSelected').value='false';
      }
    } else if (window.top.dojo.byId('noFilterSelected')) {
      if (idFilter == '0') {
        window.top.dojo.byId('noFilterSelected').value='true';
      } else {
        window.top.dojo.byId('noFilterSelected').value='false';
      }
    }
    if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) objectClass=dojo.byId('objectClassList').value;
    else if (dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) objectClass=dojo.byId("objectClassManual").value;
    else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) objectClass=dojo.byId('objectClass').value;
    if (objectClass=="PlanningWorkPlan") objectClass="Planning";
	var list= "listSort_" + objectClass;
	saveDataToSession(list, "reset", false, function(data) {
	  if (resetResponse === '1') {
	    var idObj = document.querySelector('.dojoxGridRowSelected') ? parseInt(dojo.byId('objectId').value) : null;
	    hideExtraButtons('extraButtonsList');
	    loadContent("objectMain.php?objectClass=" + objectClass, "centerDiv", null, false, false, idObj, false);
	  }
	});

    var validationType=(idFilter==0 || ! idLayout)?null:'skipRefresh';
    var currentScreen = (dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value)?dojo.byId("objectClassManual").value:null;
    if (dojo.byId('dynamicFilterId' + idFilter)) {
      var param="&idFilter=" + idFilter + "&filterObjectClass=" + objectClass;
      loadDialog('dialogDynamicFilter',null,true,param,true);
      globalSelectFilterContentLoad=contentLoad;
      globalSelectFilterContainer=container;
      validationType='selectFilter'; // will avoid immediate refresh
    }
    if (typeof contentLoad != 'undefined' && typeof container != 'undefined') {
      if(idLayout !=0){
        loadContent("../tool/selectStoredFilter.php?currentscreen="+currentScreen+"&idFilter=" + idFilter + "&context=" + context + "&contentLoad=" + contentLoad + "&container=" + container + "&filterObjectClass=" + objectClass
            + compUrl,"directFilterList",null,false,validationType, null, null, callBack); 
      }else{
        loadContent("../tool/selectStoredFilter.php?currentscreen="+currentScreen+"&idFilter=" + idFilter + "&context=" + context + "&contentLoad=" + contentLoad + "&container=" + container + "&filterObjectClass=" + objectClass
            + compUrl,"directFilterList",null,false,validationType); 
      }
      if (!dojo.byId('dynamicFilterId' + idFilter)) loadContent(contentLoad,container);
    } else {
      if(idLayout !=0){
        loadContent("../tool/selectStoredFilter.php?currentscreen="+currentScreen+"&idFilter=" + idFilter + "&context=" + context + "&filterObjectClass=" + objectClass + compUrl,"directFilterList",null,false,validationType, null, null, callBack);
      } else {
        loadContent("../tool/selectStoredFilter.php?currentscreen="+currentScreen+"&idFilter=" + idFilter + "&context=" + context + "&filterObjectClass=" + objectClass + compUrl,"directFilterList",null,false,validationType);
      }
      if (dojo.byId("objectClassList") && dojo.byId("objectClassList").value.substr(0,7) == 'Report_') {
        dojo.byId('outMode').value='';
        runReport();
      }
    }
    if (isNewGui) {
      dijit.byId('listFilterFilter').closeDropDown();
    }
  } else if(context == 'favoriteProjectList'){
	var param="&idFilter=" + idFilter + "&filterObjectClass=Project";
    loadDialog('dialogDynamicFilter',null,true,param,true);
  } else {
    var filters = document.querySelectorAll("tr[id^='filter']");
    for (var m = 0; m < filters.length; m++){
      var filterID = filters[m].id.charAt(0).toUpperCase() + filters[m].id.slice(1);
      if (filters[m].id == 'filter' + idFilter) {
        dojo.byId('filter' + idFilter).style.cssText = "color: var(--color-darker); background-color: var(--color-medium-secondary);";
        if (dojo.byId('img'+filterID)) dojo.byId('img'+filterID).style.cssText = "filter:brightness(0) invert(var(--color-toolbar-invert));float:left;width:10px;";
      } else {
        dojo.byId(filters[m].id).style.cssText = "cursor: pointer;";
        if (dojo.byId('img'+filterID)) dojo.byId('img'+filterID).style.cssText = "float:left;width:10px";
      }
    }
    if (dojo.byId('filterLogicalOperator') && dojo.byId('filterLogicalOperator').style.display == 'none') {
      dojo.byId('filterLogicalOperator').style.display='block';
    }   
    loadContent("../tool/selectStoredFilter.php?idFilter=" + idFilter + compUrl,"listFilterClauses","dialogFilterForm",false, null, null, null);
    loadContent("../tool/refreshFilterNameLayout.php?idFilter=" + idFilter + '&idLayout=' + idLayout + compUrl,"filterNameLayoutDiv","dialogFilterForm",false, null, null, null);
  }
}

function removeStoredFilter(idFilter,nameFilter) {
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
  var action=function() {
    var callBack=function() {
	  refreshProjectSelectorList();
      clearDivDelayed('saveFilterResult');
    };
    loadContent("../tool/removeFilter.php?idFilter=" + idFilter + compUrl,"listStoredFilters","dialogFilterForm",false,null,null,null,callBack);
  };
  window.top.showConfirm(i18n("confirmRemoveFilter",new Array(nameFilter)),action);
}

function shareStoredFilter(idFilter,nameFilter) {
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
  loadContent("../tool/shareFilter.php?idFilter=" + idFilter + compUrl,"listStoredFilters","dialogFilterForm",false);
}

function createCommonFilter(idFilter) {
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
  loadContent("../tool/commonFilter.php?idFilter=" + idFilter + compUrl,"listStoredFilters","dialogFilterForm",false);
}


function selectDynamicFilter() {
  for (var i=0;i < dojo.byId('nbDynamicFilterClauses').value;i++) {
    if (dijit.byId('filterValueList' + i)) {
      if (dijit.byId('filterValueList' + i).get("value") == "") {
        showAlert(i18n('valueNotSelected'));
        return;
      }
    } else if (dijit.byId('filterValue' + i)) {
      if (dijit.byId('filterValue' + i).get("value") == "") {
        showAlert(i18n('valueNotSelected'));
        return;
      }
    } else if (dijit.byId('filterValueDate' + i)) {
      if (dijit.byId('filterValueDate' + i).get("value") == "") {
        showAlert(i18n('valueNotSelected'));
        return;
      }
    }
  }

  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '?comboDetail=true' : '';
  var callBack=function() {
    selectDynamicFilterContinue();
  }
  loadContent("../tool/addDynamicFilterClause.php" + compUrl,"listDynamicFilterClauses","dialogDynamicFilterForm",false,null,null,null,callBack);
}

function selectDynamicFilterContinue() {
  if (window.top.dijit.byId('dialogDetail').open) {
    var doc=window.top.frames['comboDetailFrame'];
  } else {
    var doc=top;
  }
  if (dijit.byId('filterNameDisplay')) {
    dojo.byId('filterName').value=dijit.byId('filterNameDisplay').get('value');
  }
  doc.dijit.byId("listFilterFilter").set("iconClass","dijitButtonIcon iconActiveFilter");
  if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) objectClass=dojo.byId('objectClassList').value;
  else if (dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) objectClass=dojo.byId("objectClassManual").value;
  else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) objectClass=dojo.byId('objectClass').value;
  var compUrl='';
  if (dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value == 'Kanban') {
    compUrl+='&context=directFilterList';
    compUrl+='&contentLoad=../tool/jsonKanban.php';
    compUrl+='&container=kanbanJsonData';
  }
  doc.loadContent("../tool/displayFilterList.php?context=directFilterList&displayQuickFilter=true&displayQuickFilter=true&filterObjectClass=" + objectClass + compUrl,"directFilterList",null,false,
      'returnFromFilter',false);

  if (dojo.byId("objectClassManual") && (dojo.byId("objectClassManual").value == 'Planning' || dojo.byId("objectClassManual").value == 'PlanningWorkPlan') && !window.top.dijit.byId('dialogDetail').open) {
    refreshJsonPlanning();
  } else if (dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value == 'Report') {
    dojo.byId('outMode').value='';
    runReport();
  } else if (doc.dojo.byId('objectClassList')) {
    doc.refreshJsonList(doc.dojo.byId('objectClassList').value);
  } else {
    doc.refreshJsonList(doc.dojo.byId('objectClass').value);
  }
  dijit.byId("dialogDynamicFilter").hide();
}

function updateShowTagState(tag, id){
  if(dojo.hasClass(tag, 'docLineTag')){
    dojo.removeClass(tag, 'docLineTag');
    dojo.addClass(tag, 'docLineTagNew');
    dijit.byId('showTags'+id).set('checked', true);
  }else if(dojo.hasClass(tag, 'docLineTagNew')){
    dojo.removeClass(tag, 'docLineTagNew');
    dojo.addClass(tag, 'docLineTag');
    dijit.byId('showTags'+id).set('checked', false);
  }
}

function updateShowStatusState(Status, id, color){
  if(dojo.hasClass(Status, 'docLineTag')){
    dojo.removeClass(Status, 'docLineTag');
    dojo.addClass(Status, 'docLineTagNew');
    Status.style.background = color;
    Status.style.color = getForeColor(color);
    dijit.byId('showStatus'+id).set('checked', true);
  }else if(dojo.hasClass(Status, 'docLineTagNew')){
    dojo.removeClass(Status, 'docLineTagNew');
    Status.style.background = null;
    Status.style.color = null;
    dojo.addClass(Status, 'docLineTag');
    dijit.byId('showStatus'+id).set('checked', false);
  }
}

/*
 * Ticket #3988 - Object list : boutton reset parameters florent
 */
function resetFilter(lstStat, lstTags) {
  var grid=dijit.byId("objectGrid");
  var notDef;
  var i=0;
  for (var i=1;i <= lstStat;i++) {
    if (dijit.byId('showStatus' + i)) {
      dijit.byId('showStatus' + i).set('checked',false);
    }
  }
  dojo.query('#barFilterByStatus .docLineTagNew').forEach(function(node,index,nodelist) {
    dojo.removeClass(node, 'docLineTagNew');
    node.style.background = null;
    node.style.color = null;
    dojo.addClass(node, 'docLineTag');
  });
  i=0;
  for (var i=1;i <= lstTags;i++) {
    if (dijit.byId('showTags' + i)) {
      dijit.byId('showTags' + i).set('checked',false);
    }
  }
  dojo.query('#barFilterByTags .docLineTagNew').forEach(function(node,index,nodelist) {
    dojo.removeClass(node, 'docLineTagNew');
    dojo.addClass(node, 'docLineTag');
  });

  if (dijit.byId("listFilterFilter").iconClass == "dijitButtonIcon iconActiveFilter") {
    selectStoredFilter('0','0','directFilterList',notDef,notDef);
  }
  if (grid) {
    if (dijit.byId('listTypeFilter')) {
      dijit.byId('listTypeFilter').set('value','');
    }
    if (dijit.byId('listClientFilter')) {
      dijit.byId('listClientFilter').set('value','');
    }
    if (dijit.byId('listItemSelector')) {
      dijit.byId('listItemSelector').set('value','');
    }
    if (dijit.byId('showAllProjects')) {
      dijit.byId('showAllProjects').set('value','');
    }
    if (dijit.byId('ListPredefinedActions')) {
      dijit.byId('ListPredefinedActions').set('value','');
    }
    if (dijit.byId('ListBudgetParentFilter')) {
      dijit.byId('ListBudgetParentFilter').set('value','');
    }
    if (dijit.byId('ListBudgetParentFilter')) {
      dijit.byId('ListBudgetParentFilter').set('value','');
    }
    if (dijit.byId('ListShowIdle')) {
      dijit.byId('ListShowIdle').set('value','');
    }
    if (dijit.byId('hideInService')) {
      dijit.byId('hideInService').set('value','');
    }
    if (dojo.byId("listQuickSearchValueFilter")){
      dijit.byId('listQuickSearchFilter').set('value','');
    }
    if (dijit.byId('listIdFilter') || dijit.byId('listNameFilter') || dijit.byId('listNameFilter') && dijit.byId('listIdFilter')) {
      dijit.byId('listIdFilter').set('value','');
      dijit.byId('listNameFilter').set('value','');
      filter={};
      grid.query=filter;
      grid._refresh();
    }
  }

}

function resetFilterQuick(lstStat, lstTags) {
  var grid=dijit.byId("objectGrid");
  var notDef;
  var i=0;
  for (var i=1;i <= lstStat;i++) {
    if (dijit.byId('showStatus' + i)) {
      dijit.byId('showStatus' + i).set('checked',false);
    }
  }
  if (lstStat != null ){
    dojo.query('#barFilterByStatus .docLineTagNew').forEach(function(node,index,nodelist) {
      dojo.removeClass(node, 'docLineTagNew');
      node.style.background = null;
      node.style.color = null;
      dojo.addClass(node, 'docLineTag');
    });
  } 
  i=0;
  for (var i=1;i <= lstTags;i++) {
    if (dijit.byId('showTags' + i)) {
      dijit.byId('showTags' + i).set('checked',false);
    }
  }
  if (lstTags != null ){
    dojo.query('#barFilterByTags .docLineTagNew').forEach(function(node,index,nodelist) {
      dojo.removeClass(node, 'docLineTagNew');
      dojo.addClass(node, 'docLineTag');
    }); 
  }

  if (dijit.byId("listFilterFilter").iconClass == "dijitButtonIcon iconActiveFilter") {
    selectStoredFilter('0','0','directFilterList',notDef,notDef);
  }
  if (grid) {
    if (dijit.byId('listTypeFilter')) {
      dijit.byId('listTypeFilter').set('value','');
    }
    if (dijit.byId('listClientFilter')) {
      dijit.byId('listClientFilter').set('value','');
    }
    if (dijit.byId('listItemSelector')) {
      dijit.byId('listItemSelector').set('value','');
    }
    if (dijit.byId('showAllProjects')) {
      dijit.byId('showAllProjects').set('value','');
    }
    if (dijit.byId('ListPredefinedActions')) {
      dijit.byId('ListPredefinedActions').set('value','');
    }
    if (dijit.byId('ListBudgetParentFilter')) {
      dijit.byId('ListBudgetParentFilter').set('value','');
    }
    if (dijit.byId('ListShowIdle')) {
      dijit.byId('ListShowIdle').set('value','');
    }
    if (dijit.byId('hideInService')) {
      dijit.byId('hideInService').set('value','');
    }
    if (dijit.byId('listIdFilter')) {
      dijit.byId('listIdFilter').set('value','');
    }
    if (dijit.byId('listNameFilter')) {
      dijit.byId('listNameFilter').set('value','');
    }
    if (dojo.byId("listQuickSearchValueFilter")){
      dijit.byId('listQuickSearchFilter').set('value','');
    }
    if (dijit.byId('listIdFilter') || dijit.byId('listNameFilter')) {
      filter={};
      grid.query=filter;
      grid._refresh();
    }
  }

  if (dijit.byId('listIdFilterQuick')) {
    dijit.byId('listIdFilterQuick').set('value','');
    if (dijit.byId('listIdFilterQuickSw').get('value') == 'off') {
      dojo.byId('filterDivsSpan').style.display="none";
      dijit.byId('listIdFilter').domNode.style.display='none';
    }
  }
  if (dijit.byId('listNameFilterQuick')) {
    dijit.byId('listNameFilterQuick').set('value','');
    if (dijit.byId('listNameFilterQuickSw').get('value') == 'off') {
      dojo.byId('listNameFilterSpan').style.display="none";
      dijit.byId('listNameFilter').domNode.style.display='none';
    }
  }
  if (dijit.byId('listTypeFilterQuick')) {
    dijit.byId('listTypeFilterQuick').set('value','');    
    if (dijit.byId('listTypeFilterQuickSw').get('value') == 'off') {
      dojo.byId('listTypeFilterSpan').style.display="none";
      dijit.byId('listTypeFilter').domNode.style.display='none';
    }
  }
  if (dijit.byId('listClientFilterQuick')) {
    dijit.byId('listClientFilterQuick').set('value','');
    if (dijit.byId('listClientFilterQuickSw').get('value') == 'off') {
      dojo.byId('listClientFilterSpan').style.display="none";
      dijit.byId('listClientFilter').domNode.style.display='none';
    }
  }
  if (dijit.byId('listBudgetParentFilterQuick')) {
    dijit.byId('listBudgetParentFilterQuick').set('value','');
    if (dijit.byId('listBudgetParentFilterQuickSw').get('value') == 'off') {
      dojo.byId('listBudgetParentFilterSpan').style.display="none";
      dijit.byId('listBudgetParentFilter').domNode.style.display='none';
    }
  }

  if (dijit.byId('quickSearchValueQuick')) {
    dijit.byId('quickSearchValueQuick').set('value','');
    quickSearchClose();
    if (dijit.byId('quickSearchValueQuickSw').get('value') == 'off') {
      dojo.byId('listQuickSearchFilterSpan').style.display="none";
      dijit.byId('listQuickSearchFilter').domNode.style.display = "none";
      dojo.byId('listQuickSearchFilterBtnSearch').style.display = "none";
      dojo.byId('listQuickSearchFilterBtnClose').style.display = "none";
    }
  }
}
