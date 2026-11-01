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

//=============================================================================
//= Product Composition
//=============================================================================

/**
 * Display a add link Box
 * 
 */
function addProductStructure(way) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;
  var param="&objectClass=" + objectClass + "&objectId=" + objectId + "&way=" + way;
  var callBackFunc=function() {
    if (dojo.byId('directAccessToList') && dojo.byId('directAccessToList').value == 'true') {
      var canCreate=0;
      if (dojo.byId('productStructureCanCreateComponent')) {
        canCreate=dojo.byId('productStructureCanCreateComponent').value;
      }
      showDetail('productStructureListId',canCreate,'Component',true);
    } else {
      dijit.byId('dialogProductStructure').show();
    }
  }
  dojo.xhrGet({
    url:"../tool/filterComponentType.php?" + param +addTokenIndexToUrl(),
  });
  loadDialog('dialogProductStructure',callBackFunc,false,param,true);
}

function editProductStructure(way,productStructureId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;

  var param="&objectClass=" + objectClass + "&objectId=" + objectId + "&way=" + way + "&structureId=" + productStructureId;
  loadDialog('dialogProductStructure',null,true,param,true);
}

function refreshProductStructureList(selected,newName) {
  var selectList=dojo.byId('productStructureListId');
  if (selected && selectList) {
    if (newName) {
      var option=document.createElement("option");
      option.text=newName;
      option.value=selected;
      selectList.add(option);
    }
    var ids=selected.split('_');
    for (j=0;j < selectList.options.length;j++) {
      var sel=selectList.options[j].value;
      if (ids.indexOf(sel) >= 0) { // Found in selected items
        selectList.options[j].selected='selected';
      }
    }
    selectList.focus()
    enableWidget('dialogProductStructureSubmit');
  }
}

function saveProductStructure() {
  if (dojo.byId("productStructureListId").value == "") return;
  loadContent("../tool/saveProductStructure.php","resultDivMain","productStructureForm",true,'ProductStructure');
  dijit.byId('dialogProductStructure').hide();
}

function removeProductStructure(ProductStructureId,refType,refId,refTypeName) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeProductStructure.php?id=" + ProductStructureId,"resultDivMain",null,true,'ProductStructure');
  };
  if (!refTypeName) {
    refTypeName=i18n(refType);
  }
  msg=i18n('confirmDeleteLink',new Array(refTypeName,refId));
  showConfirm(msg,actionOK);
}

// =============================================================================
// = BusinessFeatures
// =============================================================================

function addBusinessFeature() {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;
  var param="&objectClass=" + objectClass + "&objectId=" + objectId;
  loadDialog('dialogBusinessFeature',null,true,param,false);
}

function editBusinessFeature(businessFeatureId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;
  var param="&objectClass=" + objectClass + "&objectId=" + objectId + "&businessFeatureId=" + businessFeatureId;
  loadDialog('dialogBusinessFeature',null,true,param,false);
}

function saveBusinessFeature() {
  if (dojo.byId("businessFeatureName").value == "") return;
  loadContent("../tool/saveBusinessFeature.php","resultDivMain","businessFeatureForm",true,'BusinessFeature');
  dijit.byId('dialogBusinessFeature').hide();
}

function removeBusinessFeature(businessFeatureId,refType) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeBusinessFeature.php?businessFeatureId=" + businessFeatureId,"resultDivMain",null,true,'BusinessFeature');
  };
  msg=i18n('confirmDeleteBusinessFeature',new Array(refType,businessFeatureId));
  showConfirm(msg,actionOK);
}

// =============================================================================
// = Product/Component Language/Context
// =============================================================================

function addLanguage(scope) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;
  var param="&objectClass=" + objectClass + "&objectId=" + objectId;
  if (scope == "LocalizationTranslator") {
    loadDialog('dialogTranslatorLanguage',null,true,param,false);
  } else {
    loadDialog('dialogProductLanguage',null,true,param,false);
  }

}

function saveTranslationLanguage() {
  loadContent("../tool/saveTranslatorLanguage.php","resultDivMain","translatorLanguageForm",true,'LocalizationTranslatorLanguage');
  dijit.byId('dialogTranslatorLanguage').hide();
}

function saveProductLanguage() {
  loadContent("../tool/saveProductLanguage.php","resultDivMain","productLanguageForm",true,'ProductLanguage');
  dijit.byId('dialogProductLanguage').hide();
}

function editLanguage(typeLanguageId,scope) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;

  var param="&objectClass=" + objectClass + "&objectId=" + objectId + "&languageId=" + typeLanguageId;

  if (scope == "LocalizationTranslator") {
    loadDialog('dialogTranslatorLanguage',null,true,param,false);
  } else {
    loadDialog('dialogProductLanguage',null,true,param,true);
  }
}

function removeLanguage(typeLanguageId,refType) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  if (refType == 'LocalizationTranslator') {
    actionOK=function() {
      loadContent("../tool/removeTranslatorLanguage.php?refType=" + refType + "&translatorLanguageId=" + typeLanguageId,"resultDivMain",null,true,'LocalizationTranslatorLanguage');
    };
  } else {
    actionOK=function() {
      loadContent("../tool/removeProductLanguage.php?refType=" + refType + "&productLanguageId=" + typeLanguageId,"resultDivMain",null,true,'ProductLanguage');
    };
  }
  msg=i18n('confirmDeleteLanguage');
  showConfirm(msg,actionOK);
}

function addProductContext() {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;
  var param="&objectClass=" + objectClass + "&objectId=" + objectId;
  loadDialog('dialogProductContext',null,true,param,false);
}

function saveProductContext() {
  loadContent("../tool/saveProductContext.php","resultDivMain","productContextForm",true,'ProductContext');
  dijit.byId('dialogProductContext').hide();
}

function editProductContext(productContextId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;

  var param="&objectClass=" + objectClass + "&objectId=" + objectId + "&contextId=" + productContextId;
  loadDialog('dialogProductContext',null,true,param,true);
}

function removeProductContext(productContextId,refType) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeProductContext.php?refType=" + refType + "&productContextId=" + productContextId,"resultDivMain",null,true,'ProductContext');
  };
  msg=i18n('confirmDeleteProductContext');
  showConfirm(msg,actionOK);
}

// =============================================================================
// = Product Version Compatibility
// =============================================================================

function addVersionCompatibility() {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;
  var param="&objectClass=" + objectClass + "&objectId=" + objectId;
  var callBackFunc=function() {
    if (dojo.byId('directAccessToList') && dojo.byId('directAccessToList').value == 'true') {
      showDetail('versionCompatibilityListId',0,'ProductVersion',true);
      dijit.byId('dialogDetail').on('hide',function(evt) {
        dojo.xhrGet({
          url:"../tool/removeHiddenFilterDetail.php?objectClass=ProductVersion"+addTokenIndexToUrl()
        });
        dijit.byId('dialogDetail').on('hide',null);
        dijit.byId('dialogVersionCompatibility').hide();
      });
    } else {
      dijit.byId('dialogVersionCompatibility').show();
    }
  };
  loadDialog('dialogVersionCompatibility',callBackFunc,false,param,true);
}

function refreshVersionCompatibilityList(selected,newName) {
  var selectList=dojo.byId('versionCompatibilityListId');
  if (selected && selectList) {
    if (newName) {
      var option=document.createElement("option");
      option.text=newName;
      option.value=selected;
      selectList.add(option);
    }
    var ids=selected.split('_');
    for (j=0;j < selectList.options.length;j++) {
      var sel=selectList.options[j].value;
      if (ids.indexOf(sel) >= 0) { // Found in selected items
        selectList.options[j].selected='selected';
      }
    }
    selectList.focus();
    enableWidget('dialogVersionCompatibilitySubmit');
  }
}

function saveVersionCompatibility() {
  if (dojo.byId('versionCompatibilityListId').value == '') return;
  loadContent("../tool/saveVersionCompatibility.php","resultDivMain","versionCompatibilityForm",true,'VersionCompatibility');
  dijit.byId('dialogVersionCompatibility').hide();
}

function removeVersionCompatibility(versionCompatibilityId,refType,refId,refTypeName) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeVersionCompatibility.php?versionCompatibilityId=" + versionCompatibilityId,"resultDivMain",null,true,'VersionCompatibility');
  };
  if (!refTypeName) {
    refTypeName=i18n(refType);
  }
  msg=i18n('confirmDeleteVersionCompatibility',new Array(refType,versionCompatibilityId));
  showConfirm(msg,actionOK);
}

function addAssetComposition(id) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    dijit.byId("dialogAssetComposition").show();
  };
  var params="&idParent=" + id;
  params+="&mode=add";
  loadDialog('dialogAssetComposition',callBack,false,params);
}

function saveAssetComposition() {
  if (dojo.byId("idParent").value == "") return;
  loadContent("../tool/saveAssetComposition.php","resultDivMain","assetCompositionForm",true,'AssetComposition');
  dijit.byId('dialogAssetComposition').hide();
}

function removeAssetComposition(assetId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeAssetComposition.php?id=" + assetId,"resultDivMain",null,true,'AssetComposition');
  };
  refTypeName=i18n('Asset');
  msg=i18n('confirmDeleteLink',new Array(refTypeName,assetId));
  showConfirm(msg,actionOK);
}

// =============================================================================
// = Product Version Composition
// =============================================================================

function addProductVersionStructure(way) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;
  var param="&objectClass=" + objectClass + "&objectId=" + objectId + "&way=" + way;
  var callBackFunc=function() {
    if (dojo.byId('directAccessToList') && dojo.byId('directAccessToList').value == 'true') {
      showDetail('productVersionStructureListId',0,'ComponentVersion',true);
      handle=dijit.byId('dialogDetail').on('hide',function(evt) {
        dojo.xhrGet({
          url:"../tool/removeHiddenFilterDetail.php?objectClass=ComponentVersion"+addTokenIndexToUrl()
        });
        handle.remove();
      });
    } else {
      dijit.byId('dialogProductVersionStructure').show();
    }
  }
  loadDialog('dialogProductVersionStructure',callBackFunc,false,param,true);
}

function editProductVersionStructureAsset(productVersionStructureId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;
  var param="&objectClass=" + objectClass + "&objectId=" + objectId + "&structureId=" + productVersionStructureId;
  loadDialog('dialogProductVersionStructure',null,true,param,true);
}

function editProductVersionStructure(way,productVersionStructureId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;
  var param="&objectClass=" + objectClass + "&objectId=" + objectId + "&way=" + way + "&structureId=" + productVersionStructureId;
  loadDialog('dialogProductVersionStructure',null,true,param,true);
}

var upgradeProductVersionStructureId=null;
function upgradeProductVersionStructure(structureId,withoutConfirm) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  upgradeProductVersionStructureId=structureId;
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;
  var params="&objectClass=" + objectClass + "&objectId=" + objectId;
  if (structureId) params+="&structureId=" + structureId;
  if (withoutConfirm) {
    loadContent("../tool/upgradeProductVersionStructure.php?confirm=true" + params,"resultDivMain",null,true,'ProductVersionStructure');
  } else {
    dojo.xhrGet({
      url:"../tool/upgradeProductVersionStructure.php?confirm=false" + params +addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data) {
        actionOK=function() {
          var objectClass=dojo.byId('objectClass').value;
          var objectId=dojo.byId("objectId").value;
          var params="&objectClass=" + objectClass + "&objectId=" + objectId;
          if (upgradeProductVersionStructureId) params+="&structureId=" + upgradeProductVersionStructureId;
          loadContent("../tool/upgradeProductVersionStructure.php?confirm=true" + params,"resultDivMain",null,true,'ProductVersionStructure');
        };
        showConfirm(data,actionOK);
      }
    });
  }
}

function refreshProductVersionStructureList(selected,newName) {
  var selectList=dojo.byId('productVersionStructureListId');
  if (selected && selectList) {
    if (newName) {
      var option=document.createElement("option");
      option.text=newName;
      option.value=selected;
      selectList.add(option);
    }
    var ids=selected.split('_');
    for (var j=0;j < selectList.options.length;j++) {
      var sel=selectList.options[j].value;
      if (ids.indexOf(sel) >= 0) { // Found in selected items
        selectList.options[j].selected='selected';
      }
    }
    selectList.focus();
    enableWidget('dialogProductVersionStructureSubmit');
  }
}

function saveProductVersionStructure() {
  if (dojo.byId("productVersionStructureListId").value == "") return;
  loadContent("../tool/saveProductVersionStructure.php","resultDivMain","productVersionStructureForm",true,'ProductVersionStructure');
  dijit.byId('dialogProductVersionStructure').hide();
}

function saveProductVersionStructureAsset() {
  if (dojo.byId("productVersionStructureListId").value == "") return;
  loadContent("../tool/saveProductAsset.php","resultDivMain","productVersionStructureForm",true,'ProductVersionStructure');
  dijit.byId('dialogProductVersionStructure').hide();
}

function removeProductVersionStructure(ProductVersionStructureId,refType,refId,refTypeName) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeProductVersionStructure.php?id=" + ProductVersionStructureId,"resultDivMain",null,true,'ProductVersionStructure');
  };
  if (!refTypeName) {
    refTypeName=i18n(refType);
  }
  msg=i18n('confirmDeleteLink',new Array(refTypeName,refId));
  showConfirm(msg,actionOK);
}

function removeProductVersionStructureAsset(id,refType,refId,refTypeName) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeProductVersionStructureAsset.php?id=" + id,"resultDivMain",null,true,'ProductVersionStructure');
  };
  if (!refTypeName) {
    refTypeName=i18n(refType);
  }
  msg=i18n('confirmDeleteLink',new Array(refTypeName,refId));
  showConfirm(msg,actionOK);
}

function changeValueSecurityConstraint(value) {
  dojo.byId("securityConstraint").value=value;
  if (dojo.byId("addToFollowUp").checked || dijit.byId("securityConstraint1").checked) {
    dojo.query(".generalColClass.addPseudoUsersClass").style("display", "inline-block");
    dojo.byId("_lib_helpAddPseudoUsers").style.display = "contents"
  } else{
    dojo.query(".generalColClass.addPseudoUsersClass").style("display", "none");
    dojo.byId("_lib_helpAddPseudoUsers").style.display = "none";
  }
}

function changeValueActionMail(action, value) {
  dojo.byId(action).value=value;
}

// =============================================================================
// = OtherVersions
// =============================================================================

function addOtherVersion(versionType) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;
  dojo.byId("otherVersionRefType").value=objectClass;
  dojo.byId("otherVersionRefId").value=objectId;
  dojo.byId("otherVersionType").value=versionType;
  refreshOtherVersionList(null);
  dijit.byId("dialogOtherVersion").show();
  disableWidget('dialogOtherVersionSubmit');
}

function refreshOtherVersionList(selected) {
  disableWidget('dialogOtherVersionSubmit');
  var url='../tool/dynamicListOtherVersion.php';
  if (selected) {
    url+='?selected=' + selected;
  }
  if (!selected) {
    selectOtherVersionItem();
  }
  loadContent(url,'dialogOtherVersionList','otherVersionForm',false);
}

function selectOtherVersionItem() {
  var nbSelected=0;
  list=dojo.byId('otherVersionIdVersion');
  if (list.options) {
    for (var i=0;i < list.options.length;i++) {
      if (list.options[i].selected) {
        nbSelected++;
      }
    }
  }
  if (nbSelected > 0) {
    enableWidget('dialogOtherVersionSubmit');
  } else {
    disableWidget('dialogOtherVersionSubmit');
  }
}

function saveOtherVersion() {
  if (dojo.byId("otherVersionIdVersion").value == "") return;
  loadContent("../tool/saveOtherVersion.php","resultDivMain","otherVersionForm",true,'otherVersion');
  dijit.byId('dialogOtherVersion').hide();
}

function removeOtherVersion(id,name,type) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  dojo.byId("otherVersionId").value=id;
  actionOK=function() {
    loadContent("../tool/removeOtherVersion.php","resultDivMain","otherVersionForm",true,'otherVersion');
  };
  msg=i18n('confirmDeleteOtherVersion',new Array(name,i18n('colId' + type)));
  showConfirm(msg,actionOK);
}

function swicthOtherVersionToMain(id,name,type) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  dojo.byId("otherVersionId").value=id;
  loadContent("../tool/switchOtherVersion.php","resultDivMain","otherVersionForm",true,'otherVersion');
}

function showDetailOtherVersion() {
  var canCreate=0;
  if (canCreateArray['Version'] == "YES") {
    canCreate=1;
  }
  var versionType='Version';
  if (dojo.byId("otherVersionType")) {
    var typeValue=dojo.byId("otherVersionType").value;
    if (typeValue.substr(-16) == 'ComponentVersion') versionType='ComponentVersion';
    else if (typeValue.substr(-14) == 'ProductVersion') versionType='ProductVersion';
  }
  showDetail('otherVersionIdVersion',canCreate,versionType,true);
}

// =============================================================================
// = Version Project
// =============================================================================

function addVersionProject(idVersion,idProject) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  params="&idVersionProject=&idVersion=" + idVersion + "&idProject=" + idProject;
  loadDialog('dialogVersionProject',null,true,params,true);
}

function removeVersionProject(id) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeVersionProject.php?idVersionProject=" + id,"resultDivMain",null,true,'versionProject');
  };
  msg=i18n('confirmDeleteVersionProject');
  showConfirm(msg,actionOK);
}

function editVersionProject(id,idVersion,idProject) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  params="&idVersionProject=" + id + "&idVersion=" + idVersion + "&idProject=" + idProject;
  loadDialog('dialogVersionProject',null,true,params,true);
}

function saveVersionProject() {
  var formVar=dijit.byId('versionProjectForm');
  if (formVar.validate()) {
    loadContent("../tool/saveVersionProject.php","resultDivMain","versionProjectForm",true,'versionProject');
    dijit.byId('dialogVersionProject').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

// =============================================================================
// = Product Project
// =============================================================================

function addProductProject(idProduct,idProject) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  params="&idProductProject=&idProduct=" + idProduct + "&idProject=" + idProject;
  loadDialog('dialogProductProject',null,true,params,true);
}

function removeProductProject(id) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeProductProject.php?idProductProject=" + id,"resultDivMain",null,true,'productProject');
  };
  msg=i18n('confirmDeleteProductProject');
  showConfirm(msg,actionOK);
}

function editProductProject(id,idProduct,idProject) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  params="&idProductProject=" + id + "&idProduct=" + idProduct + "&idProject=" + idProject;
  loadDialog('dialogProductProject',null,true,params,true);
}

function saveProductProject() {
  var formVar=dijit.byId('productProjectForm');
  if (formVar.validate()) {
    loadContent("../tool/saveProductProject.php","resultDivMain","productProjectForm",true,'productProject');
    dijit.byId('dialogProductProject').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function setProductValueFromVersion(field,versionId) {
  dojo.xhrGet({
    url:"../tool/getProductValueFromVersion.php?idVersion=" + versionId +addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data,args) {
      prd=dijit.byId(field);
      if (prd) {
        prd.set("value",trim(data));
      }
    },
    error:function() {
    }
  });
}

// =============================================================================
// = OtherClients
// =============================================================================

var handle=null;
function addOtherClient(directAccess) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  if (directAccess==undefined) directAccess=false;
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;
  dojo.byId("otherClientRefType").value=objectClass;
  dojo.byId("otherClientRefId").value=objectId;
  if (directAccess) { // direct Access To List : always on
    dojo.byId('otherClientIdClient').value=null;
    showDetail('otherClientIdClient',0,'Client',true);
    handle=dijit.byId('dialogDetail').on('hide',function(evt) {
      saveOtherClient();
      handle.remove();
    });
  } else { // No real use, kept in case direct access to list will become
    // parametered
    refreshOtherClientList(null);
    dijit.byId("dialogOtherClient").show();
    disableWidget('dialogOtherClientSubmit');
  }
}

function refreshOtherClientList(selected) {
  disableWidget('dialogOtherClientSubmit');
  var url='../tool/dynamicListOtherClient.php';
  if (selected) {
    url+='?selected=' + selected;
  }
  if (!selected) {
    selectOtherClientItem();
  }
  loadContent(url,'dialogOtherClientList','otherClientForm',false);
}

function selectOtherClientItem() {
  var nbSelected=0;
  list=dojo.byId('otherClientIdClient');
  if (list.options) {
    for (var i=0;i < list.options.length;i++) {
      if (list.options[i].selected) {
        nbSelected++;
      }
    }
  }
  if (nbSelected > 0) {
    enableWidget('dialogOtherClientSubmit');
  } else {
    disableWidget('dialogOtherClientSubmit');
  }
}

function saveOtherClient() {
  if (dojo.byId("otherClientIdClient").value == "") return;
  loadContent("../tool/saveOtherClient.php","resultDivMain","otherClientForm",true,'otherClient');
  dijit.byId('dialogOtherClient').hide();
}

function removeOtherClient(id,name,type) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  dojo.byId("otherClientId").value=id;
  actionOK=function() {
    loadContent("../tool/removeOtherClient.php","resultDivMain","otherClientForm",true,'otherClient');
  };
  msg=i18n('confirmDeleteOtherClient',new Array(name,i18n('colId' + type)));
  showConfirm(msg,actionOK);
}

function swicthOtherClientToMain(id,name,type) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  dojo.byId("otherClientId").value=id;
  loadContent("../tool/switchOtherClient.php","resultDivMain","otherClientForm",true,'otherClient');
}

function showDetailOtherClient() {
  var canCreate=0;
  if (canCreateArray['Client'] == "YES") {
    canCreate=1;
  }
  showDetail('otherClientIdClient',canCreate,'Client',true);
}

function saveRestrictProductList() {
  loadContent("../tool/saveRestrictProductList.php","resultDivMain","dialogRestrictProductListForm",true);
  dijit.byId('dialogRestrictProductList').hide();
}

function displayVersionsPlanning(idProductVersions,objectVersion) {
  vGanttCurrentLine=-1;
  cleanContent("centerDiv");
  loadContent("versionsPlanningMain.php?productVersionsListId=" + idProductVersions + "&objectVersion=" + objectVersion,"centerDiv");
}
