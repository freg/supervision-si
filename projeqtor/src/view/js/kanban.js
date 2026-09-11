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
/* Extra JavaScript for custom screen management */
/* =============================================================================== */

//function sendChangeKanBan(id,type,newStatut,target,oldStatut) {
//  targetLast=target;
//  dojo.style(dojo.byId('itemRow' + id + '-' + type),'display',"block");
//  if (dojo.byId('plannedWorkC' + newStatut) != null) {
//    plannedTicket=parseFloat(dojo.byId('plannedWork' + id).getAttribute("valueWork"));
//
//    realTicket=parseFloat(dojo.byId('realWork' + id).getAttribute("valueWork"));
//    leftTicket=parseFloat(dojo.byId('leftWork' + id).getAttribute("valueWork"));
//
//    dojo.byId('plannedWorkC' + newStatut).setAttribute("valueWork",(parseFloat(dojo.byId('plannedWorkC' + newStatut).getAttribute("valueWork")) + plannedTicket));
//    dojo.byId('plannedWorkC' + newStatut).innerHTML=workFormatter(dojo.byId('plannedWorkC' + newStatut).getAttribute("valueWork"));
//
//    dojo.byId('realWorkC' + newStatut).setAttribute("valueWork",(parseFloat(dojo.byId('realWorkC' + newStatut).getAttribute("valueWork")) + realTicket));
//    dojo.byId('realWorkC' + newStatut).innerHTML=workFormatter(dojo.byId('realWorkC' + newStatut).getAttribute("valueWork"));
//
//    dojo.byId('leftWorkC' + newStatut).setAttribute("valueWork",(parseFloat(dojo.byId('leftWorkC' + newStatut).getAttribute("valueWork")) + leftTicket));
//    dojo.byId('leftWorkC' + newStatut).innerHTML=workFormatter(dojo.byId('leftWorkC' + newStatut).getAttribute("valueWork"));
//
//    dojo.byId('plannedWorkC' + oldStatut).setAttribute("valueWork",(parseFloat(dojo.byId('plannedWorkC' + oldStatut).getAttribute("valueWork")) - plannedTicket));
//    dojo.byId('plannedWorkC' + oldStatut).innerHTML=workFormatter(dojo.byId('plannedWorkC' + oldStatut).getAttribute("valueWork"));
//
//    dojo.byId('realWorkC' + oldStatut).setAttribute("valueWork",(parseFloat(dojo.byId('realWorkC' + oldStatut).getAttribute("valueWork")) - realTicket));
//    dojo.byId('realWorkC' + oldStatut).innerHTML=workFormatter(dojo.byId('realWorkC' + oldStatut).getAttribute("valueWork"));
//
//    dojo.byId('leftWorkC' + oldStatut).setAttribute("valueWork",(parseFloat(dojo.byId('leftWorkC' + oldStatut).getAttribute("valueWork")) - leftTicket));
//    dojo.byId('leftWorkC' + oldStatut).innerHTML=workFormatter(dojo.byId('leftWorkC' + oldStatut).getAttribute("valueWork"));
//  }
//
//  if(target){
//    dojo.byId('numberTickets' + newStatut).innerHTML=parseFloat(dojo.byId('numberTickets' + newStatut).innerHTML) + 1;
//    dojo.byId('numberTickets' + oldStatut).innerHTML=parseFloat(dojo.byId('numberTickets' + oldStatut).innerHTML) - 1;
//  }
//
//  var nodeTicket=dojo.byId('itemRow' + id + '-' + type);
//  dojo.removeClass(dojo.byId('itemRow' + id + '-' + type),'dojoDndHandle');
//  var oldColor=dojo.style(nodeTicket,"background-color");
//  dojo.style(nodeTicket,"background-color",'#999');
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanUpdate.php?idTicket=" + id + "&type=" + type + "&newStatut=" + newStatut + "&idKanban=" + dojo.byId('idKanban').value +addTokenIndexToUrl(),
//    load:function(data) {
//      if (dojo.byId("liveMeetingResultEditorType") && data.indexOf('newStatusName') != -1 && data.indexOf('&idTicket=') == -1){
//        splitData=data.split('&');
//        regex =/=(.*)$/;
//        newStatusName=splitData[splitData.length-2].match(regex);
//        type=splitData[splitData.length-1].match(regex);
//        array = [type[1], id, newStatusName[1]];
//        text = i18n('meetingChangeStatus', array);
//        liveMeetingAddToEditor(text, true); 
//      }
//      if (data.indexOf('messageError/split/') != -1) {
//        // hideWait();
//        loadContent("../view/kanbanView.php?idKanban=" + dojo.byId('idKanban').value,"divKanbanContainer");
//        showAlert(data.split('messageError/split/')[1],null);
//      } else if (data.indexOf('&idTicket=') != -1) {
//        functionCallback=function() {
//          kanbanFindTitle('update');
//          hideWait();
//        };
//        if ((data.indexOf('needResult') != -1 && typeof dojo.byId("kanbanResultEditorType") != 'undefined')
//            || ((data.indexOf('kanbanDescription') != -1 || data.indexOf('description') != -1) && typeof dojo.byId("descriptionEditorType") != 'undefined')) functionCallback=function() {
//          var editorTypeResult=null;
//          if (dojo.byId("kanbanResultEditorType") && typeof dojo.byId("kanbanResultEditorType") != 'undefined') editorTypeResult=dojo.byId("kanbanResultEditorType").value;
//          if (editorTypeResult == "CK") { // CKeditor type
//            ckEditorReplaceEditor("kanbanResult",999);
//          } else if (dijit.byId("liveMeetingResult") && dijit.byId("kanbanResult")) { // Dojo
//                                                                                      // type
//                                                                                      // editor
//            dijit.byId("kanbanResult").set("class","input");
//          }
//          var editorTypeDescription=null;
//          if (dojo.byId("descriptionEditorType") && typeof dojo.byId("descriptionEditorType") != 'undefined') editorTypeDescription=dojo.byId("descriptionEditorType").value;
//          if (editorTypeDescription == "CK") { // CKeditor type
//            if (dojo.byId("kanbanDescription")) ckEditorReplaceEditor("kanbanDescription",999);
//            else ckEditorReplaceEditor("description",999);
//          } else if (dijit.byId("liveMeetingResult") && dijit.byId("kanbanDescription")) { // Dojo
//                                                                                      // type
//                                                                                      // editor
//            dijit.byId("kanbanDescription").set("class","input");
//          } else if (dijit.byId("liveMeetingResult") && dijit.byId("description")) { // Dojo
//            // type
//            // editor
//          dijit.byId("description").set("class","input");
//          }
//          kanbanFindTitle('update');
//        };
//        loadDialog('dialogKanbanUpdate',functionCallback,true,data + "&typeDynamic=update",true,false);
//        dojo.style(nodeTicket,"background-color",oldColor);
//        dojo.addClass(nodeTicket,'dojoDndHandle');
//      } else {
//        dataUserThumb=data.split('[splitcustom2]')[1];
//        idKanban=dojo.byId("idKanban").value;
//        splitData=data.split('[splitcustom]');
//        id=splitData[0].split('-')[0];
//        type=splitData[0].split('-')[1];
//        newStatut=splitData[0].split('-')[2];
//        newVersionName=splitData[0].split('-')[3];
//        className=splitData[0].split('-')[4];
//        
//        if (!newVersionName) newVersionName = i18n('undefinedValue');
//        array = [i18n(className), id, newVersionName];
//        text = i18n('meetingChangeStatus', array);
//        if (dojo.byId("liveMeetingResultEditorType")) liveMeetingAddToEditor(text, true);
//        
//        var oldAt=dojo.byId('itemRow' + id + '-' + type).getAttribute("dndType");
//        var addTo='';
//        if (oldAt.indexOf('-') != -1) addTo+=oldAt.split(oldAt.split('-')[0])[1];
//        if (type == 'Status' && target) target.getItem('itemRow' + id + '-' + type).type[0]="typeRow" + newStatut + addTo;
//        if(dojo.byId('itemRow' + id + '-' + type))dojo.byId('itemRow' + id + '-' + type).setAttribute('fromC',newStatut);
//        if(dojo.byId('divPrincItem' + id))dojo.byId('divPrincItem' + id).innerHTML=splitData[1].split('[splitcustom2]')[0];
//        var callback=function() {
//          nodeTicket=dojo.byId('itemRow' + id + '-' + type);
//          dojo.addClass(nodeTicket,'dojoDndItemAnchor');
//          dojo.style(nodeTicket,"background-color",oldColor);
//          dojo.addClass(nodeTicket,'dojoDndHandle');
//          dijit.byId("descr_" + id).value="truncated";
//          if(dojo.byId('userThumbTicket' + id))dojo.byId('userThumbTicket' + id).innerHTML=dataUserThumb.split('[splitcustom3]')[0];
//          hideWait();
//          if(target == null){
//            loadContent("../view/kanbanView.php","divKanbanContainer");
//          }
//        };
//        loadDiv('../tool/kanbanRefreshTicket.php?id=' + id + '&type=' + type + '&idKanban=' + idKanban + '&from=' + newStatut,'itemRow' + id + '-' + type,null,callback);
//      }
//    },
//    error:function(data) {
//      showError(data);
//      hideWait();
//    }
//  });
//}
////
//function saveKanbanResult(id,type,newStatut) {
//  showWait();
//  tmpCkEditor='';
//  if (typeof CKEDITOR.instances.kanbanResult != 'undefined') {
//    CKEDITOR.instances.kanbanResult.updateElement();
//    tmpCkEditor=CKEDITOR.instances.kanbanResult.document.getBody().getText();
//  }
//  tmpCkEditorKanbanDescription='';
//  if (typeof CKEDITOR.instances.kanbanDescription != 'undefined') {
//    CKEDITOR.instances.kanbanDescription.updateElement();
//    tmpCkEditorKanbanDescription=CKEDITOR.instances.kanbanDescription.document.getBody().getText();
//  }
//  var extraRequired=dojo.byId('extraRequiredFields').value.split(',');
//  var extraRequiredVal=true;
//  if (extraRequired && extraRequired[0] != '') {
//    extraRequired.forEach(function(item) {
//      var field=dojo.byId(item);
//      if (dijit.byId(item) == 'undefined') {
//        extraRequiredVal=false;
//      } else if (field && field.value.trim() == '') {
//        extraRequiredVal=false;
//      } else if (field && field.value == 0) {
//        extraRequiredVal=false;
//      }
//    });
//  }
//  var form=dijit.byId('kanbanResultForm');
//  if (!form.validate()) {
//    showAlert(i18n("alertInvalidForm"));
//  } else {
//    if (extraRequiredVal
//        && ((typeof dijit.byId('kanbanResourceList') != 'undefined' && dijit.byId('kanbanResourceList').get('value').trim() != '') || typeof dijit.byId('kanbanResourceList') == 'undefined')
//        && ((typeof CKEDITOR.instances.kanbanResult == 'undefined' || (typeof CKEDITOR.instances.kanbanResult != 'undefined' && tmpCkEditor.trim() != '')) && ((typeof dijit.byId('kanbanResult') != 'undefined' && dijit
//            .byId('kanbanResult').get('value').trim() != '') || typeof dijit.byId('kanbanResult') == 'undefined'))
//        && ((typeof CKEDITOR.instances.kanbanDescription == 'undefined' || (typeof CKEDITOR.instances.kanbanDescription != 'undefined' && tmpCkEditorKanbanDescription.trim() != '')) && ((typeof dijit
//            .byId('kanbanDescription') != 'undefined' && dijit.byId('kanbanDescription').get('value').trim() != '') || typeof dijit.byId('kanbanDescription') == 'undefined'))
//        && ((typeof dijit.byId('kanbanResolutionList') != 'undefined' && dijit.byId('kanbanResolutionList').get('value').trim() != '') || typeof dijit.byId('kanbanResolutionList') == 'undefined')) {
//      dojo.xhrPost({
//        url:"../tool/kanbanUpdate.php?idTicket=" + id + "&type=" + type + "&newStatut=" + newStatut + "&needIdKanban=kanbanResult&idKanban=" + dojo.byId('idKanban').value +addTokenIndexToUrl(),
//        form:"kanbanResultForm",
//        handleAs:"text",
//        load:function(data,args) {
//          if (dojo.byId("liveMeetingResultEditorType") && data.indexOf('newStatusName') != -1 && data.indexOf('&idTicket=') == -1){
//            splitData=data.split('&');
//            regex =/=(.*)$/;
//            newStatusName=splitData[splitData.length-2].match(regex);
//            type=splitData[splitData.length-1].match(regex);
//            array = [type[1], id, newStatusName[1]];
//            text = i18n('meetingChangeStatus', array);
//            liveMeetingAddToEditor(text, true); 
//          }
//          formChangeInProgress=false;
//          dijit.byId('dialogKanbanUpdate').hide();
//          if (data.indexOf('messageError/split/') != -1) {
//            // hideWait();
//            loadContent("../view/kanbanView.php?idKanban=" + dojo.byId('idKanban').value,"divKanbanContainer");
//            showAlert(data.split('messageError/split/')[1],null);
//          } else {
//            dataUserThumb=data.split('[splitcustom2]')[1];
//            splitData=data.split('[splitcustom]');
//            descrData=data.split('[splitcustom3]')[1];
//            newStatut=splitData[0].split('-')[2];
//            var oldAt=dojo.byId('itemRow' + id + '-' + type).getAttribute("dndType");
//            var addTo='';
//            if (oldAt.indexOf('-') != -1) addTo+=oldAt.split(oldAt.split('-')[0])[1];
//            if (type == 'Status') targetLast.getItem('itemRow' + id + '-' + type).type[0]="typeRow" + newStatut + addTo;
//            if(dojo.byId('itemRow' + id + '-' + type))dojo.byId('itemRow' + id + '-' + type).setAttribute('fromC',newStatut);
//            if(dojo.byId('divPrincItem' + id))dojo.byId('divPrincItem' + id).innerHTML=splitData[1].split('[splitcustom2]')[0];
//            if(dojo.byId('userThumbTicket' + id))dojo.byId('userThumbTicket' + id).innerHTML=dataUserThumb.split('[splitcustom3]')[0];
//            if(dojo.byId('objectDescr' + id))dojo.byId('objectDescr' + id).innerHTML=descrData;
//            hideWait();
//          }
//        },
//        error:function() {
//          hideWait();
//        }
//      });
//    } else {
//      var finalMessage='';
//
//      if ((typeof dijit.byId('kanbanResourceList') != 'undefined' && dijit.byId('kanbanResourceList').get('value').trim() == '')) {
//        finalMessage+=i18n('messageMandatory',[i18n('colMandatoryResourceOnHandled')]);
//      }
//      valCk='';
//      if (typeof CKEDITOR.instances.kanbanResult != 'undefined') valCk=CKEDITOR.instances.kanbanResult.getData();
//      if (!((typeof CKEDITOR.instances.kanbanResult == 'undefined' || (typeof CKEDITOR.instances.kanbanResult != 'undefined' && tmpCkEditor.trim() != '')) && ((typeof dijit.byId('kanbanResult') != 'undefined' && dijit
//          .byId('kanbanResult').get('value').trim() != '') || typeof dijit.byId('kanbanResult') == 'undefined'))) {
//        if (finalMessage != '') finalMessage+='<br/>';
//        finalMessage+=i18n('messageMandatory',[i18n('colMandatoryResultOnDone')]);
//      }
//
//      valCk='';
//      // PBER : No use, is tested with extraRequiredFields
//      // if(typeof CKEDITOR.instances.kanbanDescription
//      // !='undefined')valCk=CKEDITOR.instances.kanbanDescription.getData();
//      // if(!( (typeof CKEDITOR.instances.kanbanDescription == 'undefined' || (typeof
//      // CKEDITOR.instances.kanbanDescription != 'undefined' &&
//      // tmpCkEditorKanbanDescription.trim()!='')) && ((typeof
//      // dijit.byId('kanbanDescription') != 'undefined' &&
//      // dijit.byId('kanbanDescription').get('value').trim()!='') || typeof
//      // dijit.byId('kanbanDescription') == 'undefined')))
//      // {
//      // if(finalMessage!='')finalMessage+='<br/>';
//      // finalMessage+=i18n('messageMandatory',[i18n('colDescription')]);
//      // }
//
//      if ((typeof dijit.byId('kanbanResolutionList') != 'undefined' && dijit.byId('kanbanResolutionList').get('value').trim() == '')) {
//        if (finalMessage != '') finalMessage+='<br/>';
//        finalMessage+=i18n('messageMandatory',[i18n('colIdResolution')]);
//      }
//
//      if (!extraRequiredVal) {
//        if (finalMessage != '') finalMessage+='<br/>';
//        extraRequired.forEach(function(item) {
//          var field=dojo.byId(item);
//          if (field && (field.value.trim() == '' || field.value == 0)) {
//            var name=item[0].toUpperCase() + item.substring(1);
//            finalMessage+=i18n('messageMandatory',[i18n('col' + name)]);
//            finalMessage+='<br/>';
//          }
//        });
//      }
//
//      if (finalMessage != '') showAlert(finalMessage);
//      hideWait();
//    }
//  }
//}

//function plgAddColumnKanban(idKanban,idFrom,isStatut,typeD) {
//  var name="";
//  if (typeof (dijit.byId("kanbanName")) != 'undefined') name=dijit.byId("kanbanName").get("value");
//  var type='';
//  if (typeof (dijit.byId("kanbanTypeList")) != 'undefined') type=dijit.byId("kanbanTypeList").get("value");
//  if ((idFrom == -1 && ((name.trim() != '' && isStatut) || (!isStatut && type.trim() != ''))) || (idFrom != -1 && isStatut && name.trim() != '') || (idFrom != -1 && !isStatut)) {
//    showWait();
//    dojo.xhrPost({
//      url:"../tool/kanbanColumnAdd.php?name=" + name + "&type=" + type + "&idKanban=" + idKanban + '&idFrom=' + idFrom +addTokenIndexToUrl(),
//      form:"kanbanResultForm",
//      handleAs:"text",
//      load:function(data,args) {
//        formChangeInProgress=false;
//        loadContent("../view/kanbanView.php?idKanban=" + idKanban,"divKanbanContainer");
//        dijit.byId('dialogKanbanUpdate').hide();
//        // hideWait();
//      },
//      error:function() {
//        hideWait();
//      }
//    });
//  } else {
//    var finalMessage='';
//    if (name.trim() == '' && isStatut && idFrom == -1) {
//      finalMessage+=i18n('messageMandatory',[i18n('colName')]);
//    }
//
//    if (!isStatut && type.trim() == '' && idFrom == -1) {
//      var trad="colIdTargetProductVersion";
//      if (typeD == "Milestone") trad="colIdTargetMilestone";
//      if (typeD == "Activity") trad="colPlanningActivity";
//      if (typeD == "Status") trad="colIdStatus";
//      if (finalMessage != '') finalMessage+='<br/>';
//      finalMessage+=i18n('messageMandatory',[i18n(trad)]);
//    }
//
//    if (idFrom != -1 && isStatut && name.trim() == '') {
//      if (finalMessage != '') finalMessage+='<br/>';
//      finalMessage+=i18n('messageMandatory',[i18n('colName')]);
//    }
//    if (finalMessage != '') showAlert(finalMessage);
//  }
//}

//function kanbanSeeWork() {
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanSeeWork.php"+addTokenIndexToUrl('?'),
//    handleAs:"text",
//    load:function(data,args) {
//      loadContent("../view/kanbanView.php?idKanban=" + data,"divKanbanContainer");
//      // hideWait();
//    },
//    error:function() {
//      hideWait();
//    }
//  });
//}
//
//function kanbanModeColorTitle() {
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanModeColorTitle.php"+addTokenIndexToUrl('?'),
//    handleAs:"text",
//    load:function(data,args) {
//      loadContent("../view/kanbanView.php?idKanban=" + data,"divKanbanContainer");
//      //hideWait();
//    },
//    error:function() {
//      hideWait();
//    }
//  });
//}


//function kanbanShowIdle(idKanban) {
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanUpdateParameter.php?param=kanbanShowIdle"+addTokenIndexToUrl(),
//    handleAs:"text",
//    load:function(data,args) {
//      loadContent("../view/kanbanView.php?idKanban=" + idKanban,"divKanbanContainer");
//      // hideWait();
//    },
//    error:function() {
//      hideWait();
//    }
//  });
//}
//
//// kanbanFullWidthElement
//function kanbanFullWidthElement() {
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanUpdateParameter.php?param=kanbanFullWidthElement"+addTokenIndexToUrl(),
//    handleAs:"text",
//    load:function(data,args) {
//      loadContent("../view/kanbanView.php","divKanbanContainer");
//    },
//    error:function() {
//      hideWait();
//    }
//  });
//}
//
//function kanbanHideBacklog() {
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanUpdateParameter.php?param=kanbanHideBacklog"+addTokenIndexToUrl(),
//    handleAs:"text",
//    load:function(data,args) {
//      loadContent("../view/kanbanView.php","divKanbanContainer");
//    },
//    error:function() {
//      hideWait();
//    }
//  });
//}
//
//function kanbanHideColorTitle() {
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanUpdateParameter.php?param=kanbanHideColorTitle"+addTokenIndexToUrl(),
//    handleAs:"text",
//    load:function(data,args) {
//      loadContent("../view/kanbanView.php","divKanbanContainer");
//    },
//    error:function() {
//      hideWait();
//    }
//  });
//}
//
//function kanbanHideStatus() {
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanUpdateParameter.php?param=kanbanHideStatus"+addTokenIndexToUrl(),
//    handleAs:"text",
//    load:function(data,args) {
//      loadContent("../view/kanbanView.php","divKanbanContainer");
//    },
//    error:function() {
//      hideWait();
//    }
//  });
//}
//
//function kanbanHideProduct() {
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanUpdateParameter.php?param=kanbanHideProduct"+addTokenIndexToUrl(),
//    handleAs:"text",
//    load:function(data,args) {
//      loadContent("../view/kanbanView.php","divKanbanContainer");
//    },
//    error:function() {
//      hideWait();
//    }
//  });
//}
//
//function kanbanHideActivityPlanning() {
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanUpdateParameter.php?param=kanbanHideActivityPlanning"+addTokenIndexToUrl(),
//    handleAs:"text",
//    load:function(data,args) {
//      loadContent("../view/kanbanView.php","divKanbanContainer");
//    },
//    error:function() {
//      hideWait();
//    }
//  });
//}
//
//function kanbanHideResponsible() {
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanUpdateParameter.php?param=kanbanHideResponsible"+addTokenIndexToUrl(),
//    handleAs:"text",
//    load:function(data,args) {
//      loadContent("../view/kanbanView.php","divKanbanContainer");
//    },
//    error:function() {
//      hideWait();
//    }
//  });
//}
//
//function kanbanHidePriority() {
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanUpdateParameter.php?param=kanbanHidePriority"+addTokenIndexToUrl(),
//    handleAs:"text",
//    load:function(data,args) {
//      loadContent("../view/kanbanView.php","divKanbanContainer");
//    },
//    error:function() {
//      hideWait();
//    }
//  });
//}
//
//function kanbanHideCriticality() {
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanUpdateParameter.php?param=kanbanHideCriticality"+addTokenIndexToUrl(),
//    handleAs:"text",
//    load:function(data,args) {
//      loadContent("../view/kanbanView.php","divKanbanContainer");
//    },
//    error:function() {
//      hideWait();
//    }
//  });
//}
//
//function kanbanHidePlannedDate() {
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanUpdateParameter.php?param=kanbanHidePlannedDate"+addTokenIndexToUrl(),
//    handleAs:"text",
//    load:function(data,args) {
//      loadContent("../view/kanbanView.php","divKanbanContainer");
//    },
//    error:function() {
//      hideWait();
//    }
//  });
//}
//
//function kanbanHideType() {
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanUpdateParameter.php?param=kanbanHideType"+addTokenIndexToUrl(),
//    handleAs:"text",
//    load:function(data,args) {
//      loadContent("../view/kanbanView.php","divKanbanContainer");
//    },
//    error:function() {
//      hideWait();
//    }
//  });
//}
//
//function kanbanHideProjectName() {
//  showWait();
//  dojo.xhrGet({
//    url:"../tool/kanbanUpdateParameter.php?param=kanbanHideProjectName"+addTokenIndexToUrl(),
//    handleAs:"text",
//    load:function(data,args) {
//      loadContent("../view/kanbanView.php","divKanbanContainer");
//    },
//    error:function() {
//      hideWait();
//    }
//  });
//}

//function changeWorkNbTicket(idColumn,idTicket,factor) {
//  if (dojo.byId('plannedWorkC' + idColumn) != null) {
//    plannedTicket=parseFloat(dojo.byId('plannedWork' + idTicket).getAttribute("valueWork")) * factor;
//    realTicket=parseFloat(dojo.byId('realWork' + idTicket).getAttribute("valueWork")) * factor;
//    leftTicket=parseFloat(dojo.byId('leftWork' + idTicket).getAttribute("valueWork")) * factor;
//
//    dojo.byId('plannedWorkC' + idColumn).setAttribute("valueWork",(parseFloat(dojo.byId('plannedWorkC' + idColumn).getAttribute("valueWork")) + plannedTicket));
//    dojo.byId('plannedWorkC' + idColumn).innerHTML=workFormatter(dojo.byId('plannedWorkC' + idColumn).getAttribute("valueWork"));
//
//    dojo.byId('realWorkC' + idColumn).setAttribute("valueWork",(parseFloat(dojo.byId('realWorkC' + idColumn).getAttribute("valueWork")) + realTicket));
//    dojo.byId('realWorkC' + idColumn).innerHTML=workFormatter(dojo.byId('realWorkC' + idColumn).getAttribute("valueWork"));
//
//    dojo.byId('leftWorkC' + idColumn).setAttribute("valueWork",(parseFloat(dojo.byId('leftWorkC' + idColumn).getAttribute("valueWork")) + leftTicket));
//    dojo.byId('leftWorkC' + idColumn).innerHTML=workFormatter(dojo.byId('leftWorkC' + idColumn).getAttribute("valueWork"));
//  }
//
//  if (dojo.byId('plannedWorkC' + idColumn) != null) {
//
//    realTicket=parseFloat(dojo.byId('realWork' + idTicket).getAttribute("valueWork")) * factor;
//    leftTicket=parseFloat(dojo.byId('leftWork' + idTicket).getAttribute("valueWork")) * factor;
//
//  }
//  if (dojo.byId('numberTickets' + idColumn) != null) dojo.byId('numberTickets' + idColumn).innerHTML=parseFloat(dojo.byId('numberTickets' + idColumn).innerHTML) + factor;
//}

//function kanbanStart() {
//  if (dijit.byId('searchByName') == null) {
//    setTimeout(function() {
//      kanbanStart();
//    },20);
//  } else {
//    dojo.byId('kanbanContainer').scrollTop=kanbanScrollTop;
//    kanbanSearchBy();
//  }
//}


//function kanbanSearchBy() {
//  arrayVerify=[];
//  if (dojo.byId('searchByName') != null) {
//    searchValue=dijit.byId('searchByName').get('value').replace(/[*]/g,".*");
//    regex=new RegExp(kanbanEscapeRegExp(dijit.byId('searchByName').get('value')),'i');
//    arrayVerify.push({
//      "regex":regex,
//      "id":"name",
//      "val":dijit.byId('searchByName').get('value'),
//      "idSearch":"-1"
//    });
//  }
//
//  if (dojo.byId('searchByResponsible') != null) {
//    searchValue=dijit.byId('searchByResponsible').get('displayedValue').replace(/[*]/g,".*");
//    regex=new RegExp(kanbanEscapeRegExp(dijit.byId('searchByResponsible').get('displayedValue')),'i');
//    arrayVerify.push({
//      "regex":regex,
//      "id":"responsible",
//      "val":dijit.byId('searchByResponsible').get('displayedValue'),
//      "idSearch":dijit.byId('searchByResponsible').get('value')
//    });
//  }
//
//  if (dojo.byId('listStatus') != null) {
//    searchValue=dijit.byId('listStatus').get('displayedValue').replace(/[*]/g,".*");
//    regex=new RegExp(kanbanEscapeRegExp(dijit.byId('listStatus').get('displayedValue')),'i');
//    arrayVerify.push({
//      "regex":regex,
//      "id":"status",
//      "val":dijit.byId('listStatus').get('displayedValue'),
//      "idSearch":dijit.byId('listStatus').get('value')
//    });
//  }
//
//  if (dojo.byId('listTargetProductVersion') != null) {
//    searchValue=dijit.byId('listTargetProductVersion').get('displayedValue').replace(/[*]/g,".*");
//    regex=new RegExp(kanbanEscapeRegExp(dijit.byId('listTargetProductVersion').get('displayedValue')),'i');
//    arrayVerify.push({
//      "regex":regex,
//      "id":"targetProductVersion",
//      "val":dijit.byId('listTargetProductVersion').get('displayedValue'),
//      "idSearch":dijit.byId('listTargetProductVersion').get('value')
//    });
//  }
//
//  for ( var ite in arrayVerify)
//    kanbanSaveDataSession(arrayVerify[ite]['id'],arrayVerify[ite]['val'],arrayVerify[ite]['idSearch']);
//  listItem=dojo.query('.ticketKanBanColor');
//  for (var ite in listItem) {
//    if (listItem[ite] != null && dojo.byId(listItem[ite].id) != null) {
//      idTicket=listItem[ite].id.split('itemRow')[1].split('-')[0];
//      idColumn=listItem[ite].getAttribute('fromC');
//      controlePass=true;
//      for ( var ite2 in arrayVerify) {
//        if (arrayVerify[ite2]['val'] != '') {
//          var textToControl=null;
//          type=arrayVerify[ite2]['id'];
//          if (type != 'responsible' && dojo.byId(type + idTicket) != null) {
//            textToControl=dojo.byId(type + idTicket).innerHTML;
//          } else if (dojo.byId(type + idTicket) != null) {
//            textToControl=dojo.byId(type + idTicket).getAttribute('valueuser');
//          }
//          if (textToControl == null || textToControl.match(arrayVerify[ite2]['regex']) == null) controlePass=false;
//        }
//      }
//      if (controlePass) {
//        changeWorkNbTicket(idColumn,idTicket,changeTicketVisible(listItem[ite].id,1));
//      } else {
//        changeWorkNbTicket(idColumn,idTicket,changeTicketVisible(listItem[ite].id,-1));
//      }
//    }
//  }
//}
//
//function changeTicketVisible(idTicket,factorBase) {
//  oldVisible=dojo.style(dojo.byId(idTicket),'display');
//  if (factorBase == 1 && oldVisible == "none") {
//    dojo.byId(idTicket).style.setProperty('display',"inline-table","important");
//    return 1;
//  }
//  if (factorBase == -1 && oldVisible != "none") {
//    dojo.byId(idTicket).style.setProperty('display',"none","important");
//    return -1;
//  }
//  return 0;
//}
//
//function kanbanChangeOrderBy(val,idKanban) {
//  loadContent("../view/kanbanView.php?idKanban=" + idKanban + "&kanbanOrderBy=" + val,"divKanbanContainer");
//}

//function kanbanEscapeRegExp(str) {
//  return str.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g,"\\$&");
//}

//function divWidthKanban(idLine,typeKanban,numberColumn) {
//  var itemRow=dojo.byId("itemRow" + idLine + "-" + typeKanban);
//  if (numberColumn > '2' && numberColumn <= '4') {
//    itemRow.className="dojoDndItem dojoDndHandle ticketKanBanStyleFull ticketKanBanColor ticketKanbanCustomThree";
//  } else if (numberColumn == '2') {
//    itemRow.className="dojoDndItem dojoDndHandle ticketKanBanStyleFull ticketKanBanColor ticketKanbanCustomTwo";
//  } else if (numberColumn == '1') {
//    itemRow.className="dojoDndItem dojoDndHandle ticketKanBanStyleFull ticketKanBanColor ticketKanbanCustom";
//  } else if (numberColumn > '4') {
//    itemRow.className="dojoDndItem dojoDndHandle ticketKanBanStyleFull ticketKanBanColor ticketKanbanCustomMin";
//  }
//}

//function kanbanShowDescr(field,type,width,id) {
//  if (dojo.byId("descr_" + id).value == "full") {
//    return;
//  }
//  dojo.byId('descr_' + id).value="full";
//  url='../tool/kanbanGetDescription.php?dataType=defaultPriority&Type=' + type + "&id=" + id + "&field=" + field + "&width=" + width;
//  dojo.xhrGet({
//    url:url+addTokenIndexToUrl(),
//    handleAs:"text",
//    // mehdi #2516
//    load:function(data) {
//      dojo.byId('objectDescr' + id).innerHTML=data;
//    }
//  });
//}

//function activityStreamKanban(objectId,objectClass,type,placeholder) {
//  var param="&objectId=" + objectId + "&objectClass=" + objectClass + "&type=" + type;
//  // loadDialog(dialogDiv, callBack, autoShow, params, clearOnHide, closable,
//  // dialogTitle)
//  var callBack=function(){
//    dijit.byId("noteStreamKanban").set("placeholder", placeholder);
//  };
//  loadDialog('dialogKanbanGetObjectStream',callBack,true,param,true,true,'titleStream');
//}
//
//var saveNoteStreamKanbanTimeout=null;
//function saveNoteStreamKanban(event,line) {
//  var key=event.keyCode;
//  var type=dojo.byId('kanbanRefType').value;
//  var idKanban=dojo.byId('idKanban').value;
//  var id=dojo.byId('noteRefId').value;
//  var newStatut='';
//  if (key == 13 && !event.shiftKey) {
//    var noteEditor=dijit.byId("noteStreamKanban");
//    var noteEditorContent=noteEditor.get("value");
//    if (noteEditorContent.trim() == "") {
//      noteEditor.focus();
//      return;
//    }
//    var callBack=function() {
//      dojo.byId("resultKanbanStreamDiv").style.display="block";
//      if (saveNoteStreamKanbanTimeout) clearTimeout(saveNoteStreamKanbanTimeout);
//      saveNoteStreamKanbanTimeout=setTimeout('dojo.byId("resultKanbanStreamDiv").style.display="none";',3000);
//    };
//    // loadContent(page, destination, formName, isResultMessage, validationType,
//    // directAccess, silent, callBackFunction, noFading)
//    loadContent("../tool/saveNoteStreamKanban.php","activityStreamCenterKanban","noteFormStreamKanban",false,null,null,null,callBack);
//    var nodeTicket=dojo.byId('itemRow' + id + '-' + type);
//    dojo.removeClass(dojo.byId('itemRow' + id + '-' + type),'dojoDndHandle');
//    var oldColor=dojo.style(nodeTicket,"background-color");
//    dojo.style(nodeTicket,"background-color",'#999');
//    dojo.xhrGet({
//      url:"../tool/kanbanUpdate.php?idTicket=" + id + "&type=" + type + "&newStatut=" + newStatut + "&idKanban=" + idKanban +addTokenIndexToUrl(),
//      load:function(data) {
//        var callback=function() {
//          nodeTicket=dojo.byId('itemRow' + id + '-' + type);
//          dojo.addClass(nodeTicket,'dojoDndItemAnchor');
//          dojo.style(nodeTicket,"background-color",oldColor);
//          dojo.addClass(nodeTicket,'dojoDndHandle');
//          dojo.byId('itemRow' + id + '-' + type).setAttribute('fromC',newStatut);
//          hideWait();
//        };
//        loadDiv('../tool/kanbanRefreshTicket.php?id=' + id + '&type=' + type + '&idKanban=' + idKanban + '&from=' + newStatut,'itemRow' + id + '-' + type,null,callback);
//      },
//    });
//    noteEditor.set("value",null);
//    event.preventDefault();
//  }
//}

//function deleteOnKanbanFromContextMenu(refId, refType){
//  fromContextMenu = true;
//  if (refType=='Replan' || refType=='Construction' || refType=='Fixed') refType='Project';
//  var action=function(){
//    var resetContextMenuVariable=function(){
//      if(!(dojo.byId('confirmControl') && dojo.byId('confirmControl').value=='delete')){
//        fromContextMenu=false;
//      }
//      loadContent("../view/kanbanView.php?idKanban=" + dojo.byId('idKanban').value,"divKanbanContainer"); 
//    }
//    dojo.byId('objectClass').value = refType;
//    dojo.byId('objectId').value = refId;
//    loadContent('../tool/deleteObject.php?objectId=' + refId
//        + '&objectClassName='+refType+'&fromContextMenu='+fromContextMenu, 'resultDivMain', 'objectForm', true, null, null, null, resetContextMenuVariable);
//  };
//  showConfirm(i18n('confirmDelete', new Array(refType, refId)) ,action);
//}
//
//var hideKanbanContextMenuTimeout = null;
//function hideKanbanContextMenu(delay) {
//  var contextMenu = dijit.byId('kanbanContextMenu');
//  var contextMenuDiv = dojo.byId('dialogKanbanContextMenu');
//  if (contextMenu) {
//    var callback = function () {
//      if (dojo.byId('addFromKanban')) dojo.byId('addFromKanban').setAttribute('onClick', '');
//      if (dojo.byId('copyFromKanban')) dojo.byId('copyFromKanban').setAttribute('onClick', '');
//      if (dojo.byId('removeFromKanban')) dojo.byId('removeFromKanban').setAttribute('onClick', '');
//      if (dojo.byId('printFromKanban')) dojo.byId('printFromKanban').setAttribute('onClick', '');
//      if (dojo.byId('printPdfFromKanban')) dojo.byId('printPdfFromKanban').setAttribute('onClick', '');
//      if (dojo.byId('mailFromKanban')) dojo.byId('mailFromKanban').setAttribute('onClick', '');
//      if (dojo.byId('searchFromKanban')) dojo.byId('searchFromKanban').setAttribute('onClick', '');
//      if (dojo.byId('addCommentFromKanban')) dojo.byId('addCommentFromKanban').setAttribute('onClick', '');
//      if (dojo.byId('GotoFromKanban')) dojo.byId('GotoFromKanban').setAttribute('onClick', '');
//      contextMenu.closeDropDown();
//      contextMenuDiv.blur();
//    };
//    hideKanbanContextMenuTimeout = setTimeout(callback, delay);
//  }
//}
//
//function openKanbanContextMenu(vID, refId, refType, idProject, type){
//  var contextMenu = dijit.byId('kanbanContextMenu');
//  var contextMenuDiv = dojo.byId('dialogKanbanContextMenu');
//  event.preventDefault();
//  var divKanbanContainer = dojo.byId('divKanbanContainer');
//  var scrollX = divKanbanContainer.scrollLeft;
//  var mousePosition = {
//      x: event.clientX + scrollX, 
//      y: event.clientY -150
//    };
//  if(dojo.byId('isMenuLeftOpen').value == 'true'){
//    mousePosition.x -= 250;
//  }
//  dojo.query('.contextMenuClass').forEach(function(node){
//    node.style.cssText='position:absolute;width:0px;height:0px;overflow:hidden;top:'+mousePosition.y+'px;left:'+mousePosition.x+'px';
//  });
//  if (refType=='Replan' || refType=='Construction' || refType=='Fixed') refType='Project';
//  if(dojo.byId('contextMenuRefId'))dojo.byId('contextMenuRefId').value = refId;
//  if(dojo.byId('contextMenuRefType'))dojo.byId('contextMenuRefType').value = refType;
//  if(dojo.byId('objectClassRow'))dojo.byId('objectClassRow').value = refType;
//  if(dojo.byId('objectIdRow'))dojo.byId('objectIdRow').value = refId;
//  
//  var currentClass = null;
//  var currentId = null;
//  
//  if(dojo.byId('addFromKanban')){
//    dojo.byId('addFromKanban').style.display = '';
//    dojo.byId('addFromKanban').setAttribute('onClick', 'addItemFromKanban(\''+refType+'\')');
//  }
//  if(dojo.byId('copyFromKanban')){
//    dojo.byId('copyFromKanban').style.display = '';
//    dojo.byId('copyFromKanban').setAttribute('onClick', 'copyObjectFromContextMenu(\''+refId+'\', \''+refType+'\', null, '+idProject+', true)');
//  }
//  if(dojo.byId('editFromKanban')){
//    dojo.byId('editFromKanban').style.display = '';
//    dojo.byId('editFromKanban').setAttribute('onClick', 'showDetail(\'refreshActionAddItemKanban\',1,\''+refType+'\',false,'+refId+')');
//  }
//  if(dojo.byId('addCommentFromKanban')){
//    dojo.byId('addCommentFromKanban').style.display = '';
//    dojo.byId('addCommentFromKanban').setAttribute('onClick', 'activityStreamKanban(\''+vID+'\', '+refId+', \''+refType+'\', \''+i18n('textareaEnterText')+'\');');
//  }
//  if(dojo.byId('removeFromKanban')){
//    dojo.byId('removeFromKanban').style.display = '';
//    dojo.byId('removeFromKanban').setAttribute('onClick', 'deleteOnKanbanFromContextMenu(\''+refId+'\', \''+refType+'\', true)');
//  } 
//  if(dojo.byId('printFromKanban')){
//    dojo.byId('printFromKanban').style.display = '';
//    dojo.byId('printFromKanban').setAttribute('onClick', 'showPrint(\'objectDetail.php\', \'contextMenuObject\', null, null, \'P\')');
//  }   
//  if(dojo.byId('printPdfFromKanban')){
//    dojo.byId('printPdfFromKanban').style.display = '';
//    dojo.byId('printPdfFromKanban').setAttribute('onClick', 'showPrint(\'objectDetail.php\', \'contextMenuObject\', null, \'pdf\', \'P\')');
//  }
//  if(dojo.byId('mailFromKanban')){
//    dojo.byId('mailFromKanban').style.display = '';
//    dojo.byId('mailFromKanban').setAttribute('onClick', 'showMailOptions()');
//  }
//  if(dojo.byId('searchFromKanban')){
//    dojo.byId('searchFromKanban').style.display = '';
//    dojo.byId('searchFromKanban').setAttribute('onClick', 'noRefresh=true;gotoElement(\''+refType+'\', \''+refId+'\' ,false, false,\'planning\',false)');
//  }
//  if(dojo.byId('gotoFromKanban')){
//    dojo.byId('gotoFromKanban_label').innerHTML = i18n('kanbanGotoItem', new Array(refId,refId));
//    dojo.byId('gotoFromKanban').style.display = '';
//    dojo.byId('gotoFromKanban').setAttribute('onClick', 'gotoElement(\''+refType+'\','+refId+', true)');
//  }
//  
//  contextMenu.openDropDown();
//  contextMenuDiv.focus();
//}