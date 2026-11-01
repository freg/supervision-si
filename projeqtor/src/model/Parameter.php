<?php 
/* ============================================================================
 * Parameter is a global kind of object for parametring.
 * It may be on user level, on project level or on global level.
 */ 
require_once('_securityCheck.php');

class Parameter extends SqlElement {

  // extends SqlElement, so has $id
  public $id;    // redefine $id to specify its visiblez place 
  public $idUser;
  public $idProject;
  public $parameterCode;
  public $parameterValue;
  
  public $_noHistory=true; // Will never save history for this object
  
  private static $planningColumnOrder=array();
  private static $planningColumnOrderAll=array();
  private static $planningColumnDescription=array();
  private static $planningColumnEditable=array();
  
  /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
  }

  
  /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }

// ============================================================================**********
// GET VALIDATION SCRIPT
// ============================================================================**********

  /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo frameword)
   */
  public function getValidationScript($colName) {
    global $type;
    //$colScript = parent::getValidationScript($colName);   
    $colScript="";
    if ($colName=="theme") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if (this.value!="random") changeTheme(this.value);';
      $colScript .= '</script>';
    } else if ($colName=="lang") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  changeLocale(this.value);';
      $colScript .= '</script>';
//     } else if ($colName=="scaytAutoStartup") {
//         $colScript .= '<script type="dojo/connect" event="onChange" >';
//         $colScript .= '  saveDataToSessionAndReload("scaytAutoStartup", this.value, null);';
//         $colScript .= '</script>';
    } else if ($colName=="timeZone") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  changeTimeZone(this.value);';
      $colScript .= '</script>';
    } else if ($colName=="startPage") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  saveUserParameter(\''.$colName.'\', this.value);';
      $colScript .= '</script>';
    } else if ($colName=="browserLocaleDateFormat") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  changeBrowserLocaleForDates(this.value);';
      $colScript .= '</script>';
      //gautier #2270
    } else if ($colName=="browserLocaleTimeFormat") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  changeBrowserLocaleTimeFormat(this.value);';
      $colScript .= '</script>';
    } else if ($colName=="paramConfirmQuit") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  paramConfirmQuit=this.value;';
      $colScript .= ' saveDataToSession(\''.$colName.'\', paramConfirmQuit);';
      $colScript .= '</script>';
    } else if ($colName=="paramTopIconSize" or $colName=="paramIconSize") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  newValue=this.value;';
      $colScript .= '  saveDataToSessionAndReload("'.$colName.'", newValue, false);';
      $colScript .= '</script>';      
// MTY - LEAVE SYSTEM        
    } else if ($colName=="leavesSystemAdmin") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  newValue=this.value;';
      $colScript .= '  if (newValue=='.getCurrentUserId().') {';
      $colScript .= '    saveDataToSessionAndReload("'.$colName.'", newValue, false);';
      $colScript .= '  } else {';
      $colScript .= '    saveDataToSession("'.$colName.'", newValue, false);';
      $colScript .= '  }';
      $colScript .= '</script>'; 
// MTY - LEAVE SYSTEM        
    } else if ($colName=="defaultProject") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  newValue=this.value;';
      $colScript .= '  saveDataToSession(\''.$colName.'\', newValue);';
      $colScript .= '</script>';             
    } else if ($colName=="hideMenu") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if (this.value=="NO") {';
      $colScript .= '    if (menuActualStatus!="visible") {hideShowMenu()}';
      $colScript .= '    menuHidden=false;';
      $colScript .= '  } else {';
      $colScript .= '    menuHidden=true;';
      $colScript .= '    menuShowMode=this.value; hideShowMenu()';
      $colScript .= '  }';
      $colScript .= '  newValue=this.value;';
      $colScript .= '  saveDataToSession(\''.$colName.'\', newValue);';
      $colScript .= '</script>';
    } else if ($colName=="switchedMode") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if (this.value=="NO") {';
      $colScript .= '    switchedMode=false;';
      $colScript .= '  } else {';
      $colScript .= '    switchedMode=true;';
      $colScript .= '    switchListMode=this.value;';
      $colScript .= '  }';
      $colScript .= '  newValue=this.value;';
      $colScript .= '  saveDataToSession(\''.$colName.'\', newValue); ';
      $colScript .= '</script>';    
    } else  if ($colName=="printInNewWindow"){
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  newValue=this.value;';
      $colScript .= '  if (newValue=="YES") {'; 
      $colScript .= '    printInNewWindow=true;';
      $colScript .= '  } else {';
      $colScript .= '    printInNewWindow=false;';
      $colScript .= '  }';
      $colScript .= '  saveDataToSession(\'' .$colName. '\', newValue); ';
      $colScript .= '</script>';
    } else  if ($colName=="pdfInNewWindow"){
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  newValue=this.value;';
      $colScript .= '  if (newValue=="YES") {'; 
      $colScript .= '    pdfInNewWindow=true;';
      $colScript .= '  } else {';
      $colScript .= '    pdfInNewWindow=false;';
      $colScript .= '  }';
      $colScript .= ' saveDataToSession(\''.$colName.'\', newValue);';
      $colScript .= '</script>';
    } else if ($colName=='versionNameAutoformat') {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  newValue=this.value;';
      $colScript .= '  var separator=dijit.byId("versionNameAutoformatSeparator");';
      $colScript .= '  if (newValue=="YES") {';
      $colScript .= '    if (! separator.get("value")) separator.set("value"," V");';
      $colScript .= '  } else {';
      $colScript .= '    separator.set("value",null);';
      $colScript .= '  }';
      $colScript .= ' saveDataToSession(\''.$colName.'\', newValue);';
      $colScript .= '</script>';
    } else if ($colName=='SAML_allow_login') {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  newValue=this.value;';
      $colScript .= '  if (newValue=="YES" || newValue=="true") {';
      $colScript .= '    dojo.addClass(dijit.byId("SAML_idpId").domNode, "required");';
      $colScript .= '    dojo.addClass(dijit.byId("SAML_idpCert").domNode, "required");';
      $colScript .= '    dojo.addClass(dijit.byId("SAML_SingleSignOnService").domNode, "required");';
      $colScript .= '    dojo.addClass(dijit.byId("SAML_SingleLogoutService").domNode, "required");';
      $colScript .= '    dojo.addClass(dijit.byId("SAML_attributeUid").domNode, "required");';
      $colScript .= '  } else {';
      $colScript .= '    dojo.removeClass(dijit.byId("SAML_idpId").domNode, "required");';
      $colScript .= '    dojo.removeClass(dijit.byId("SAML_idpCert").domNode, "required");';
      $colScript .= '    dojo.removeClass(dijit.byId("SAML_SingleSignOnService").domNode, "required");';
      $colScript .= '    dojo.removeClass(dijit.byId("SAML_SingleLogoutService").domNode, "required");';
      $colScript .= '    dojo.removeClass(dijit.byId("SAML_attributeUid").domNode, "required");';
      $colScript .= '  } ';
      $colScript .= '</script>';
      //Florent 
    } else if($colName=='paramAttachmentMaxSize'){
      $colScript .='<script type="dojo/connect" event="onChange">';
      $colScript .='var newValue=(this.value).trim();';
      $colScript .='if (newValue !=""){';
      $colScript .='var val=newValue.split("");';
      $colScript .='var lettre="";';
      $colScript .='var valLettre="0";';
      $colScript .='  val.forEach(function(element){';
      $colScript .='    if (isNaN(element)==true){';
      $colScript .='      lettre=lettre+element.toUpperCase();';
      $colScript .='    }';
      $colScript .='  });';
      $colScript .='  if(lettre.length==1 && (lettre=="K" || lettre=="M" || lettre=="G" || lettre=="T")){';
      $colScript .='    valLettre=lettre;';
      $colScript .='  }else if(lettre==""){';
       $colScript .='   valLettre="1";';
      $colScript .='  }else {newValue ="0"; }';
      $colScript .='dojo.byId("paramAttachmentNum").value=lettre;';
      $colScript .='dojo.byId("paramAttachmentMaxSize").value=newValue.toUpperCase();';
      $colScript .='}';
      $colScript .='</script>';
    }else if($colName=='paramAttachmentMaxSizeMail'){
      $colScript .='<script type="dojo/connect" event="onChange">';
      $colScript .='var newValue=(this.value).trim();';
      $colScript .='if (newValue !=""){';
      $colScript .='var val=newValue.split("");';
      $colScript .='var lettre="";';
      $colScript .='var valLettre="0";';
      $colScript .='  val.forEach(function(element){';
      $colScript .='    if (isNaN(element)==true){';
      $colScript .='      lettre=lettre+element.toUpperCase();';
      $colScript .='    }';
      $colScript .='  });';
      $colScript .='  if(lettre.length==1 && (lettre=="K" || lettre=="M" || lettre=="G" || lettre=="T")){';
      $colScript .='    valLettre=lettre;';
      $colScript .='  }else if(lettre==""){';
      $colScript .='    valLettre="1";';
      $colScript .='  }else {newValue ="null"; }';
      $colScript .='dojo.byId("paramAttachmentNumMail").value=lettre;';
      $colScript .='dojo.byId("paramAttachmentMaxSizeMail").value=newValue.toUpperCase();';
      $colScript .='}';
      $colScript .='</script>';
    } else if($colName=='paramMailerType') {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if (this.value=="phpmailer") {';
      $colScript .= '    if (dijit.byId("paramAttachmentMaxSizeMail") ){ enableWidget("paramAttachmentMaxSizeMail");dijit.byId("paramAttachmentMaxSizeMail").set("value","5M");}';
      $colScript .= '  } else {';
      $colScript .= '    if (dijit.byId("paramAttachmentMaxSizeMail") ){ disableWidget("paramAttachmentMaxSizeMail");dijit.byId("paramAttachmentMaxSizeMail").set("value",null); }';
      $colScript .= '  }';
      $colScript .= '</script>';           
    } else if ($colName=="newGui") {
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        if ($type=='userParameter') {
          $colScript .= '  saveDataToSessionAndReload("newGui", this.value, true);';
        } else {
          $colScript .= '  var callbackAfterSave=function(){loadContent("parameter.php?type=globalParameter","centerDiv");};';
          $colScript .= '  loadDiv("../tool/saveParameter.php","testEmailSaveResult", "parameterForm", callbackAfterSave);';
        }
        $colScript .= '</script>';
    } else if ($colName=="menuBarTopMode") {
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .='   saveDataToSession("menuBarTopMode", this.value, true);';
        $colScript .= '  menuNewGuiFilter("menuBarCustom", null);';
        $colScript .= '</script>';
    }else if ($colName=="menuLeftDisplayMode") {
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= '  showIconLeftMenu();';
        $colScript .= '</script>';
    }else if($colName=='colorBlindPlanning'){
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  saveDataToSessionAndReload(\''.$colName.'\', this.value, true);';
      $colScript .= '  isColorBlind = this.value;';
      $colScript .= '</script>';
    }else if($colName=='displayPoolsOnImputation'){
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if(this.get("value") == "NO"){';
      $colScript .= '   dijit.byId("showPoolLinesToUpdateLeftWork").setDisabled(false);';
      $colScript .= '  }else{';
      $colScript .= '   dijit.byId("showPoolLinesToUpdateLeftWork").setDisabled(true);';
      $colScript .= '  }';
      $colScript .= '</script>';
    }else if($colName=='autoUpdateLeftWorkOnPool'){
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  autoUpdateLeftWorkOnPool = (this.value == "YES")?1:0;';
      $colScript .= '</script>';
    }else if($colName=='paramMailSmtpUsername' && self::hostedSmtpDefault()) {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  newValue=this.value;';
      $colScript .= '  saveDataToSession("paramMailSmtpUsername", newValue);';
      //$colScript .= '  saveDataToSession("paramMailSmtpPassword", null);';
      $colScript .= '</script>';
    }else {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  newValue=this.value;';
      $colScript .= '  saveDataToSession(\''.$colName.'\', newValue);';
      $colScript .= '</script>';
    }
    return $colScript;
  }
  
// ============================================================================**********
// MISCELLANOUS FUNCTIONS
// ============================================================================**********
  
  /** ===========================================================================
   * Give the list of allows values for a parameter (to builmd a select)
   * @param String $parameter the name of the parameter
   * @return Array array of allowed values as code=>value
   */
  static function getList($parameter) {
    global $isAttachmentEnabled;
    $list=array();
    switch ($parameter) {
      case 'theme': case 'defaultTheme':
        $list=getThemesList(); // keep 'random' as last value to assure it is not selected via getTheme()
      break;
      case 'lang':case 'paramDefaultLocale':
        $list=self::getLangList();
        //sort($list);  // not a good idea : would push brazialian as defaut (first) language...   
        break;
      //gautier 
      case 'paramDefaultTimezone': case 'timeZone':
        $list=self::getTimezoneList();
        break;
      case 'cronDateFormat':
      case 'browserLocaleDateFormat':
        $list=array('DD/MM/YYYY'=>'DD/MM/YYYY',
            'MM/DD/YYYY'=>'MM/DD/YYYY',
            'YYYY-MM-DD'=>'YYYY-MM-DD');
        break;
      //gautier #2270
      case 'cronTimeFormat':
      case 'browserLocaleTimeFormat':
        $list=array('H:mm'=>'24h',
        'h:mm a'=>'AM/PM');
        break;
      case 'defaultProject':
        if (sessionUserExists()) {
          $user=getSessionUser();
          $listVisible=$user->getVisibleProjects();
        } else {
          $listVisible=SqlList::getList('Project');
        }  
        $list['**']=i18n('lastProject');      
        $list['*']=i18n('allProjects');
        foreach ($listVisible as $key=>$val) {
          $list[$key]=$val;
        }
        break;
      case 'displayHistory':
        $list=array('NO'=>i18n('displayNo'),
                    'YES'=>i18n('displayYes'),
                    'YESW'=>i18n('displayYesWithWork'),
                    'REQ'=>i18n('displayOnRequest') );
        break;
      case 'displaySubTask':
      case 'displayChecklist':
        $list=array('YES'=>i18n('displayYes'),
                    'REQ'=>i18n('displayOnRequest'));
        break;
      case 'typeOfCopyComponentVersion':
          $list=array('free'=>i18n('free'),
          'A'=>i18n('copyToCopyVersionStructureCopy'),
          'B'=>i18n('copyToCopyVersionStructureNoCopy'),
          'C'=>i18n('copyToCopyVersionStructureReplace'));
          break;
      case 'printHistory': 
      case 'allowTypeRestrictionOnProject' :
      case 'versionNameAutoformat' : 
      case 'directAccessToComponentList' :
      case 'printInNewWindow':
      case 'initializePassword': case 'setResponsibleIfNeeded': case 'requiredOldPassword': case 'oldPasswordDifferentNew':
      case 'autoSetAssignmentByResponsible':
      case 'autoSetUniqueComponentVersion': 
      case 'exportAssignmentsForXMLFormat':
      case 'cronArchiveCloseItems' :
      case 'directEditTestCaseRun' :
      case 'gestionInheritedEndDate' :
      case 'forceProjectPriority' :
      case 'manuallyChangePlannedDate' :
      case 'imputationTicketResponsible' :
      $list=array('YES'=>i18n('displayYes'),
                  'NO'=>i18n('displayNo'));
      break;
        //Florent
      case 'planningModeForParent':
        $list=array(
            'REGUL'=>i18n('parentPlanningModeREGUL'),
            'CDUR'=>i18n('parentPlanningModeCDUR'),
            'DDUR'=>i18n('parentPlanningModeDDUR'));
        break;
      case 'paramPasswordStrength':
        $lvl=1;
          $list=array('1'=>'[#1] '.i18n('passMinLength'),
          '2'=>'[#2] '.i18n('passMinLength').'+'.i18n('passMinMaj'),
          '3'=>'[#3] '.i18n('passMinLength').'+'.i18n('passMinMaj').'+'.i18n('passNum'),
          '4'=>'[#4] '.i18n('passMinLength').'+'.i18n('passMinMaj').'+'.i18n('passNum').'+'.i18n('passChar'));
          break;
         //End
      case 'setResponsibleIfSingle': case 'allocateResponsibleToProject':
      case 'realWorkOnlyForResponsible': case 'preserveUploadedFileName': case 'ganttPlanningPrintOldStyle':
      case 'displayOnlyHandled': case 'setHandledOnRealWork': case 'setDoneOnNoLeftWork':
      case 'limitPlanningActivity' :
      case 'autoUpdateActivityStatus':
      case 'dontStartBeforeValidatedDate':
      case 'lockDocumentDownload':
      case 'subscriptionAuto':
      case 'displayBusinessFeature':
      case 'displayListOfActivity':
      case 'filterByStatus':
      case 'globalNoteDiscussionMode'://damian
      case 'displayLanguage' :
      case 'displayContext' :
       case 'displayMilestonesStartDelivery' :
      case 'filterTicketReportPriority' :
      case 'projectRestriction' :
      case 'enablePredefinedActions' :
      case 'versionCompatibility' :
      case 'paramMailerSendAsCurrentUser' :
      case 'paramSignatureAndTagToRemove':
      case 'manageTicketCustomer' :  //ADD qCazelles - Manage ticket at customer level - Ticket #87
      case 'manageTicketVersion' :
      case 'productVersionOnDelivery' :
      case 'manageAccountable':
      case 'manageAccountable':
      case 'manageComponentOnRequirement' :   //ADD qCazelles - Add Component to Requirement - Ticket 171
      case 'manageComponentOnChangeRequest':
      case 'sortVersionComboboxNameDesc' : //ADD qCazelles - Sort versions in combobox - Ticket 89
      case 'sortCompositionStructure' : //ADD qCazelles - Sort version composition-structure - Ticket 142      
      //case 'manageMilestoneOnItems' :
      case 'autoLinkMilestone' :
      case 'milestoneFromVersion' :
      //case 'dontAddClosedDeliveredVersionToProject' : //ADD qCazelles - Dont add closed and delivered versions to Project - Ticket 181 
      case 'mailGroupActive' :
      case 'csvExportUTF8':  
      case 'isManualProgress':
      case 'selectFonction' :
      case 'listTagsPerProject' :
      case 'requestorLimitToContact' :
      case 'hideItemTypeRestrictionOnProject' : case 'SAML_isADFS' :
      //case 'activateSubtasksManagement':
      case 'skillsAlertResource' :
      case 'skillsAlertTeamManager' :
      case 'skillsAlertOrganismManager' :
      case 'automaticFeedingOfTheReal' : case 'showOnlyNotes'://florent
      case 'hideEmailsSent' :
      case 'colorBlindPlanning':
      case 'showColorTypeActivity' :
      case 'showHatchOnPlanningBar' :
      case 'autoHideMenuLeftDashboard' :
      case 'ExportBillInFormatFacturX' :
      case 'modeSurbookingDifferential' :
      case 'modeSurbookingComplete' :
      case 'checkedSurbookingDefault' :
      case 'startPageLocked' :
      case 'showPoolLinesToUpdateLeftWork' :
      case 'multiCurrency' :
      case 'multiCurrencyShowGlobal' :
      case 'hideHoursTicketDueDates':
      //case 'allowAttachInputMails':
      case 'versionsWithoutAttachments':
      case 'imputationHideDoneG':
      case 'imputationSearchOnName' : 
      case 'removeQuickPlanningFeature':
      case 'passwordResetEnabled' :
      case 'otpForAdminUsers' :
      case 'otpForNewUsers' :
      case 'otpForDirectConnectionsWithSso' :
      case 'automaticChangeTechnicalProgress':
      case 'mentionDetectionFollowup':
      case 'mentionDetectionMail':
      case 'mentionDetectionNotification':
        $list=array('NO'=>i18n('displayNo'),
                    'YES'=>i18n('displayYes')); 
        break;
      case 'paramMailSmtpUseUnsecureSsl':
        $list=array('YES'=>i18n('displayYes'),
                    'NO'=>i18n('displayNo'));
        break;
      case 'dontAddClosedDeliveredVersionToProject':
        $list=array('NO'=>i18n('displayYes'),
        'YES'=>i18n('displayNo'));
        break;
      case 'skillsAlertPeriodicity':
        $list=array('onlyOnce'=>i18n('onlyOnce'),
                    'everyDayUpToSkillEndDate'=>i18n('everyDayUpToSkillEndDate'),
                    'everyWeekUpToSkillEndDate'=>i18n('everyWeekUpToSkillEndDate'),
                    'everyWeek'=>i18n('everyWeek')); 
        break;
      case 'pdfInNewWindow': case "paramConfirmQuit": case "paramShowThumb" : case "paramShowThumbList":
      case 'dependencyStrictMode':
//       case 'notStartBeforeValidatedStartDate':
      //case 'technicalProgress':
      case 'activityOnRealTime':
      //case 'useOrganizationBudgetElement' :
      case 'notificationSystemActiv':
      case 'updateMilestoneResponsibleFromDeliverable': case 'updateMilestoneResponsibleFromIncoming':
      case 'updateDeliverableResponsibleFromMilestone': case 'updateIncomingResponsibleFromMilestone': 
      case 'scaytAutoStartup':
      case 'statusChangeAssignment':
      case 'changeReferenceOnTypeChange': case 'rememberMe':
      case 'getVersion':
      case 'displayPoolsOnImputation':
      case 'autoUpdateLeftWorkOnPool':
       // ELIOTT - LEAVE SYSTEM
       //case 'leavesSystemActiv'://For the addition of the parameter to activate/desactivate the leaves feature
       // ELIOTT - LEAVE SYSTEM
      case 'authorizeActivityOnDeliveredProduct' :
      case 'includeProductInProductStructure' :
      case 'planningPriorityByEndDate':
      case 'allowSendingStatistics':
      case 'filterByTags':
      case 'defaultSkipCopyStatus' :
        $list=array('YES'=>i18n('displayYes'),
                    'NO'=>i18n('displayNo'));
        break;
      case 'notStartBeforeValidatedStartDate' :
        $list=array('YES'=>i18n('displayNo'),
        'NO'=>i18n('displayYes'));
        break;
      case 'autoAffectationPool' :
        $list=array('NO'=>i18n('displayNo'),'IMPLICIT'=>i18n('displayImplicit'),
        'EXPLICIT'=>i18n('displayExplicit'));
        break;
      case 'submitAlertSendToProjectLeader': case 'submitAlertSendToTeamManager': 
      case 'submitAlertSendToOrganismManager':
        $list=array('NONE'=>i18n('displayNone'),
            'ALERT'=>i18n('displayAlert'),
            'MAIL'=>i18n('displayMail'),
            'ALERT&MAIL'=>i18n('displayAlertAndMail'));
        break;
      case 'displayNote':
        $list=array('YES_OPENED'=>i18n('displayYesOpened'),
                    'YES_CLOSED'=>i18n('displayYesClosed'));
        break;
      case 'displayAttachment':
        if ($isAttachmentEnabled) {
          $list=array('YES_OPENED'=>i18n('displayYesOpened'),
                      'YES_CLOSED'=>i18n('displayYesClosed'));
        } else {
          $list=array('NO'=>i18n('displayNo'));          
        }
        break;
      case 'hideMenu':
        $list=array('NO'=>i18n('displayNo'),
                    'AUTO'=>i18n('displayYesShowOnMouse'),
                    'CLICK'=>i18n('displayYesShowOnClick'));
        break;
      case 'switchedMode':
        $list=array('NO'=>i18n('displayNo'),
                    'AUTO'=>i18n('displayYesShowOnMouse'),
                    'CLICK'=>i18n('displayYesShowOnClick'));
        break;
      //gautier #financial
      case 'ExpenseLink':
        $list=array('false'=>i18n('displayNo'),
                    'true'=>i18n('displayYes'));
        break;
        
       case 'enableWorkCommandManagement':
          $list=array('false'=>i18n('displayNo'),
          'true'=>i18n('displayYes'));
          break;
      case 'allowListRestrictionOnProject':
      case 'CaReplaceValidCost':
        $list = array('NO'=>i18n('displayNo'),
                      'YES'=>i18n('displayYes'));
        break;
          
      case 'ImputOfAmountClient':
        $list=array('HT'=>i18n('imputHT'),
                    'TTC'=>i18n('imputTTC'));
        break;
        
      case 'ImputOfBillLineClient':
        $list=array('HT'=>i18n('imputHT'),
                    'TTC'=>i18n('imputTTC'));
        break;
      case 'ImputOfAmountProvider':
        $list=array('HT'=>i18n('imputHT'),
                    'TTC'=>i18n('imputTTC'));
        break;
        
      case 'ImputOfBillLineProvider':
        $list=array('HT'=>i18n('imputHT'),
                    'TTC'=>i18n('imputTTC'));
        break;
      //  
      case 'OpenDayMonday':
        $list=array('openDays'=>i18n('openDays'),
                    'offDays'=>i18n('offDays'));
        break;
        
       case 'OpenDayTuesday':
         $list=array('openDays'=>i18n('openDays'),
                     'offDays'=>i18n('offDays'));
         break;
         
       case 'OpenDayWednesday':
         $list=array('openDays'=>i18n('openDays'),
                     'offDays'=>i18n('offDays'));
         break;
         
       case 'OpenDayThursday':
         $list=array('openDays'=>i18n('openDays'),
                     'offDays'=>i18n('offDays'));
         break;
         
       case 'OpenDayFriday':
         $list=array('openDays'=>i18n('openDays'),
                     'offDays'=>i18n('offDays'));
         break;
         
       case 'OpenDaySaturday':
         $list=array('openDays'=>i18n('openDays'),
                     'offDays'=>i18n('offDays'));
         break;
         
       case 'OpenDaySunday':
         $list=array('openDays'=>i18n('openDays'),
                     'offDays'=>i18n('offDays'));
         break;
       
       case 'projectDailyHours':
         $list=array('false'=>i18n('displayNo'),
                    'true'=>i18n('displayYes'));
         break;
                 
      case 'imputationUnit':
        $list=array('days'=>i18n('days'),
                    'hours'=>i18n('hours'));
        break;
      case 'workUnit':
        $list=array('days'=>i18n('days'),
                    'hours'=>i18n('hours'));
        break;
      case 'paramLdap_allow_login':
      case 'SAML_allow_login':
      case 'paramFadeLoadingMode':
      case'ldapFormatUri':
      case'ldapSslOverTls':
        $list=array('false'=>i18n('displayNo'),
                    'true'=>i18n('displayYes'));
        break;
      case 'restrictProjectList':case 'showIdleDefault':
        $list=array('false'=>i18n('displayNo'),
                    'true'=>i18n('displayYes'));
        break;
      case 'userNoteDiscussionMode':
        $list = array('NO'=>i18n('displayNo'),
                      'YES'=>i18n('displayYes'));
        break;
      case 'clientElementList':
        $list = array('false'=>i18n('displayNo'),
                      'true'=>i18n('displayYes'));
        break;
      case 'paramLdap_version':
        $list=array('2'=>'2',
                    '3'=>'3');
        break;
      case 'ldapDefaultProfile': case 'SAML_defaultProfile' :
        $list=SqlList::getList('Profile');
        break;
      case 'defaultProfile': 
        $list=array_merge_preserve_keys( array(''=>''),SqlList::getList('Profile'));
        break;
      case 'paramTryToHackUserProfilList' :
        $list['']=' ';
        $listVisible=SqlList::getList('Profile');
        foreach ($listVisible as $key=>$val) {
          $list[$key]=$val;
        }
        break;
      case 'imputationOnlyIncompleteResourceWork': case 'imputationOnlyIncompleteProjectLeaderWork':
      case 'imputationOnlyIncompleteTeamManagerWork': case 'imputationOnlyIncompleteOrganismManagerWork':
        $list = array('false'=>i18n('fasleImputationIncomplete'),
                      'falseOnGlobalPeriod'=>i18n('falseOnGlobalPeriod'),
                      'true'=>i18n('trueImputationIncomplete'),
                      'trueOnGlobalPeriod'=>i18n('trueOnGlobalPeriod'));
      break;
      case 'ldapMsgOnUserCreation': case 'imputationAlertSendToResource': case 'SAML_msgOnUserCreation' :
      case 'imputationAlertSendToProjectLeader': case 'imputationAlertSendToTeamManager': 
      case 'imputationAlertSendToOrganismManager':
        $list=array('ALERT'=>i18n('displayAlert'),
                    'MAIL'=>i18n('displayMail'),
                    'ALERT&MAIL'=>i18n('displayAlertAndMail'));
        break;
      case 'imputationAlertInputByOther': case 'imputationAlertCancelByOther': case 'imputationAlertWorkTooSoon':
        $list=array('NONE'=>i18n('displayNone'),
                    'ALERT'=>i18n('displayAlert'),
                    'MAIL'=>i18n('displayMail'),
                    'ALERT&MAIL'=>i18n('displayAlertAndMail'));
       break;
      case 'imputationFormat':
        $list=array('WEEKORMONTH'=>pq_ucfirst(i18n('colWeek')).' | '.pq_ucfirst(i18n('colMonth')),
                    'WEEK'=>pq_ucfirst(i18n('colWeek')),
                    'MONTH'=>pq_ucfirst(i18n('colMonth'))
        );
        break;
      case 'hideRealAsPlanned':
          $list = array('NO'=>i18n('displayNo'),
          'YES'=>i18n('displayYes'));
          break;
      case 'csvSeparator':
        $list=array(';'=>';',','=>',');
        break;
      case 'displayResourcePlan':
        $list=array('name'=>i18n('colName'),
                    'initials'=>i18n('colInitials'),
                    'NO'=>i18n('displayNo'));
        break;  
      case 'cronImportLogDestination':
        $list=array('file'=>i18n('cronLogAsFile'),
                    'mail'=>i18n('cronLogAsMail'),
                    'mail+log'=>i18n('cronLogAsMailWithFile'));
        break; 
      case 'currencyPosition':
        $list=array('before'=>i18n('before'), 
                    'after'=>i18n('after'));
        break; 
      case 'paramIconSize': case 'paramTopIconSize':
        $list=array('16'=>i18n('iconSizeSmall'), 
                    '22'=>i18n('iconSizeMedium'), 
                    '32'=>i18n('iconSizeBig'));
        break;
      case 'MenuBarTop':
          $list=array('YES'=>i18n('Visible'),
          'NO'=>i18n('Hidden'));
          break;
      case 'MenuBarLeft':
        $list=array('false'=>i18n('singleIcon'),
        'true'=>i18n('wideMode'));
        break;   
      case 'paramMailEol':
         $list=array('CRLF'=>i18n('eolDefault'), 
                     'LF'=>i18n('eolPostfix'));
        break;
      case 'paramMailerType':
          $list=array('phpmailer'=>i18n('libraryPHPMailer'),
                      'mail'=>i18n('functionPHPMail'),
                      'socket'=>i18n('connexionSocket'));
        break; 
      case 'paramMailerHelo':
        $list = array('NO'=>i18n('displayNo'),
                      'YES'=>i18n('displayYes'));
        break;
      case 'paramAdditionImage':
        $list = array('NO'=>i18n('displayNo'),
                      'YES'=>i18n('displayYes'));
        
        break; 
      case 'logLevel':
         $list=array('0'=>i18n('debugLevel0'),
                     '1'=>i18n('debugLevel1'), 
                     '2'=>i18n('debugLevel2'),
                     '3'=>i18n('debugLevel3'),
                     '4'=>i18n('debugLevel4'));
        break; 
      case 'projectIndentChar':
         $list=array('_'=>'_','__'=>'__','___'=>'___',
                     '-'=>'-','--'=>'--','---'=>'---', 
                     '>'=>'>','>>'=>'>>','>>>'=>'>>>',
                     '|'=>'|', '|_'=>'|_','|__'=>'|__',
                     'no'=>i18n('paramNone'));
        break;
      case 'startPage':
        $list=array();
        $list['welcome.php']=i18n('paramNone');
        if (securityCheckDisplayMenu(null,'Today')) {$list['today.php']=i18n('menuToday');}
        if (securityCheckDisplayMenu(null,'ProjectDashboard')) {$list['projectDashboardMain.php']=i18n('menuProjectDashboard');}
        if (securityCheckDisplayMenu(null,'DashboardTicket')) {$list['dashboardTicketMain.php']=i18n('menuDashboardTicket');}
        if (securityCheckDisplayMenu(null,'Diary')) {$list['diaryMain.php']=i18n('menuDiary');}
        if (securityCheckDisplayMenu(null,'Imputation')) {$list['imputationMain.php']=i18n('menuImputation');}
        if (securityCheckDisplayMenu(null,'ImputationValidation')) {$list['ImputationValidation.php']=i18n('menuImputationValidation');}//damian
        if (securityCheckDisplayMenu(null,'Absence')) {$list['Absence.php']=i18n('menuAbsence');}
        if (securityCheckDisplayMenu(null,'Planning')) {$list['planningMain.php']=i18n('menuPlanning');}
        if (securityCheckDisplayMenu(null,'PortfolioPlanning')) {$list['portfolioPlanningMain.php']=i18n('menuPortfolioPlanning');}
        if (securityCheckDisplayMenu(null,'ResourcePlanning')) {$list['resourcePlanningMain.php']=i18n('menuResourcePlanning');}
        if (securityCheckDisplayMenu(null,'GlobalPlanning')) {$list['globalPlanningMain.php']=i18n('menuGlobalPlanning');}
        if (securityCheckDisplayMenu(null,'Kanban')) {$list['kanbanViewMain.php']=i18n('menuKanban');}
        if (securityCheckDisplayMenu(null,'PlannedWorkManual')) {$list['plannedWorkManualMain.php']=i18n('menuPlannedWorkManual');}
        $arrayItem=array('Project','Document','Ticket','TicketSimple','Activity','Action','Requirement','ProjectExpense','ProductVersion','ComponentVersion','GlobalView', 'UserStory');
        foreach  ($arrayItem as $item) {
          if (securityCheckDisplayMenu(null,$item)) {$list['objectMain.php?objectClass='.$item]=i18n('menu'.$item);}
        }
        $prf=new Profile(getSessionUser()->idProfile);
        if ($prf->profileCode=='ADM') {
          $list['startGuide.php']=i18n('startGuideTitle');
        }
        $welcome = $list['welcome.php'];
        unset($list['welcome.php']);       
        asort($list, SORT_NATURAL | SORT_FLAG_CASE);       
        $list = array('welcome.php' => $welcome) + $list;
        break; 
      case 'consolidateValidated' :
        $list=array('NO'=>i18n('consolidateNever'),
                     'ALWAYS'=>i18n('consolidateAlways'),
                    'IFSET'=>i18n('consolidateIfSet'));
        break;
      case 'editor' :
        $list=array('CK'=>i18n('CKEditor'),
                    'CKInline'=>i18n('CkEditorInline'),
                    // 'Dojo'=>i18n('DojoEditor'), // Removed because buggy
                    // 'DojoInline'=>i18n('DojoEditorInline'), // Removed because buggy
                    'text'=>i18n('plainTextEditor'));
        break;
      case 'maxColumns':
        $list=array('3'=>'3','2'=>'2','1'=>'1');
        break;
      case 'fontForPDF':
        $list=array('freesans'=>i18n('fontForPdfFreesans'),
            'helvetica'=>i18n('fontForPdfHelvetica'),
            'arial'=>i18n('fontForPdfArial'),
            'droidsansfallback'=>i18n('fontForPdfAsia'),
            'freeserif'=>i18n('fontForPdfArabic'));
        break;
      case 'ldapCreationAction' : case 'SAML_creationAction' :
        $list=array('createNothing'=>i18n('createNothingFromLdapUser'),
          'createResource'=>i18n('createResourceFromLdapUser'),
          'createContact'=>i18n('createContactFromLdapUser'),
          'createResourceAndContact'=>i18n('createResourceAndContactFromLdapUser'),
          'createReject'=>i18n('createReject'));
        break;
      case 'ldapDefaultProject': case 'SAML_defaultProject' :
        $list['']=' ';
        if (sessionUserExists()) {
          $user=getSessionUser();
          $listVisible=$user->getVisibleProjects();
        } else {
          $listVisible=SqlList::getList('Project');
        }
        foreach ($listVisible as $key=>$val) {
          $list[$key]=$val;
        }
        break;
      case 'responsibleFromProduct':
        $list=array('always'=>i18n('always'),
                    'ifempty'=>i18n('ifEmpty'),
                    'never'=>i18n('never'));
        break;
      case 'showTendersOnVersions':
        $list=array('NO'=>i18n('never'),
          '1#Product#'=>i18n("menuProduct"),
          '2#Product#ProductVersion#'=>i18n("menuProduct").', '.i18n("menuVersion"),
          '3#Product#Component#'=>i18n("menuProduct").', '.i18n("menuComponent"),
          '4#Product#Component#ProductVersion#ComponentVersion#'=>i18n("menuProduct").', '.i18n("menuComponent").', '.i18n("menuVersion")) ;
        break;    
      case 'displayHistory':
        $list=array('NO'=>i18n('displayNo'),
        'YES'=>i18n('displayYes'),
        'YESW'=>i18n('displayYesWithWork'),
        'REQ'=>i18n('displayOnRequest') );
        break;
        //END ADD qCazelles
      case 'imputationAlertGenerationDay': 
        $list=array(
          'NEVER'=>i18n('never'),
          1=>i18n("Monday"), 
          2=>i18n('Tuesday'),
          3=>i18n('Wednesday'),
          4=>i18n('Thursday'),
          5=>i18n('Friday'),
          6=>i18n('Saturday'),
          7=>i18n('Sunday'),
          '*'=>i18n('periodicityDaily')
        );
        break;
      case 'imputationAlertControlDayResource' :
       case 'imputationAlertControlDayProjectLeader' :
       case 'imputationAlertControlDayTeamManager' :
       case 'imputationAlertControlDayOrganismManager' :
          $list=array(
          'current'=>i18n('imputationControlCurrentDay'),
          'previous'=>i18n('imputationControlPreviousDay'),
          'next'=>i18n('imputationControlNextDay')
          );
          break;
      case 'mailerTestSender' :
        $list=array(
          'sender'=>i18n('paramParamMailSender'),
          'self'=>i18n('paramParamMailerSendAsCurrentUser')
        );
        break;
      case 'mailGroupDifferent' :
        $list=array(
            'ALL'=>i18n('paramMailGroupAll'),
            'LAST'=>i18n('paramMailGroupLast'),
            'MERGE'=>i18n('paramMailGroupMerge')
        );
        break;
      case 'automaticPlanningCompleteDate' :
      case 'automaticPlanningDifferentialDate' :
        $list=array(
          'W'=>i18n('firstDayOfWeek'),
          'M'=>i18n('firstDayOfMonth'),
          'J0'=>i18n('today'),
          'J-1'=>i18n('yesterday',array('1')),
          'J-2'=>i18n('daysBeforeToday',array('2')),
          'J-3'=>i18n('daysBeforeToday',array('3')),
          'J-7'=>i18n('daysBeforeToday',array('7')),
          'J-10'=>i18n('daysBeforeToday',array('10')),
          'J-15'=>i18n('daysBeforeToday',array('15')),
          'J-30'=>i18n('daysBeforeToday',array('30'))
        );
        break;
      case 'notApplicableValue' :
        $list=array(
          'null'=>'',
          "'N/A'"=>'N/A',
          "'-'"=>'-',
          "'[]'"=>'[]',
          "'Ø˜'"=>'Ø'
        );
        break;
      // MTY - LEAVE SYSTEM
      case 'leavesSystemAdmin':
        if (sessionUserExists()) {
          $user=getSessionUser();
          $listVisible= getUserVisibleResourcesList(true, "List",'',false, false,false,true,true);
        } else {
          $listVisible=SqlList::getList('User');
         }
         foreach ($listVisible as $key=>$val) {
           $list[$key]=$val;
         }
         // At least, one admin in the list
         if (empty($list)) {
           $crit = array("idProfile" => "1");
           $user = SqlElement::getFirstSqlElementFromCriteria("User", $crit);
           if (isset($user->id)) {
             $list[$user->id] = $user->name;
           }
         }
         break;
       // MTY - LEAVE SYSTEM
       // MTY - EXPORT EXCEL OR ODS
      case 'typeExportXLSorODS' :
         $list=array(
         'Excel2007'=>i18n('Excel'),
         'OpenDocument'=>i18n('OpenDocument')
         );
         break;
      case 'paramOrderNoteMail':
        $list = array('ASC'=>i18n('displayYes'),
            'DESC'=>i18n('displayNo'));
        break;
      case 'notReceiveHisOwnEmails':
         $list = array('NO'=>i18n('displayYes'),
         'YES'=>i18n('displayNo'));
         break;
       // MTY - EXPORT EXCEL OR ODS
      case 'plannedWorkManualType':
        $list = array('planned'=>i18n('colPlanned'),
            'real'=>i18n('colReal'));
        break;
      case 'manageCapacityForIntervention':
        $list = array('LIMIT'=>i18n('capacityForInterventionLIMIT'),
            'DURATION'=>i18n('capacityForInterventionDURATION'),
            'NO'=>i18n('capacityForInterventionNO'));
        break;
      case 'menuBarTopMode':
        $list = array('TXT'=>i18n('textual'),
                      'ICON'=>i18n('icon'),
                      'ICONTXT'=>i18n('iconTextual'));
        break;
      case 'menuLeftDisplayMode':
        $list = array('TXT'=>i18n('textual'),
                      'ICONTXT'=>i18n('iconTextual')) ;
        break;
      case 'newItemAccessMode':
        $list = array('direct'=>i18n('directAccess'),
        'dialog'=>i18n('dialogAccess')) ;
        break;
      case 'newGui':
        $list = array(true=>i18n('newGuiTrue'),
                      false=>i18n('newGuiFalse'));
      break;
      
//       case 'afterMailTreatment':
//         $list = array('markAsReadMail'=>i18n('markAsRead'),
//                       'deleteMail'=>i18n('deleteMail'));
    } 
    return $list;
  }
  
  static function getParamtersList($typeParameter) {
    $parameterList=array();
    switch ($typeParameter) {
      case ('userParameter'):
        $parameterList=array(
                     'tabDisplay'=>"tab",
                       'column_Dis_1'=>'newColumn',
                         'sectionDisplayParameter'=>"section",
                           //'newGui'=>'list',
                           'newGuiThemeColor'=>'color',
                           'newGuiThemeColorBis'=>'color',
                           'colorBlindPlanning'=>'list',
                           "theme"=>"list", 
                           "lang"=>"list",
                           "timeZone"=>"list",
                           "browserLocaleDateFormat"=>"list",
                           "browserLocaleTimeFormat"=>"list",
                           "paramIconSize"=>'list',
                           'menuBarTopMode'=>'list',
                           'menuLeftDisplayMode'=>'list',
                           //'newItemAccessMode'=>'list',
                           "paramShowThumb"=>"list",
                           "paramShowThumbList"=>"list",
                           "notApplicableValue"=>"list",
                           "projectIndentChar"=>'list',
                           "sizeDisplayProjectToday"=>'number',
                           'maxItemsInTodayLists'=>'number',
                       'column_Dis_2'=>'newColumn',
                         'sectionIHM'=>'section',
                           "displayHistory"=>"list",
                           "displaySubTask"=>"list",  
                           "displayChecklist"=>"list",  
                           "paramConfirmQuit"=>"list",
                           "startPage"=>"list",
                           "editor"=>'list',
                           //"scaytAutoStartup"=>'list',
                           "maxColumns"=>'list',
                           "showIdleDefault"=>'list',
                           "userNoteDiscussionMode"=>'list',
                           "showOnlyNotes"=>"list",
                           "hideEmailsSent"=>"list",
                           "clientElementList"=>'list',
                           "directEditTestCaseRun"=>'list',
                           "displayResourcePlan"=>'list',
                           'multiCurrencyShowGlobal'=>'list',
                           'autoHideMenuLeftDashboard'=>'list',
                     'tabExport'=>"tab",
                       'column_Exp_1'=>'newColumn',
                         'sectionPrintExport'=>'section',
                           'printHistory'=>'list',  
                           "printInNewWindow"=>"list",
                           "pdfInNewWindow"=>"list",
                           'typeExportXLSorODS'=>'list',
                           'exportAssignmentsForXMLFormat'=>'list',
                       'column_Exp_2'=>'newColumn',                         
                     'tabAutomation'=>"tab",
                       'column_Aut_1'=>'newColumn',
                         'sectionProjects'=>'section',
                           "defaultProject"=>"list",
                           "restrictProjectList"=>'list',
                         'sectionAction'=>'section',
                           'markAlertsAsRead'=>'specific',
                           'showSubscribedItems'=>'specific',
                         'sectionMail'=>'section',
                           'notReceiveHisOwnEmails'=>'list',
                           'paramOrderNoteMail'=>'list',
                         'sectionMentionDetection'=>'section',
                           'mentionDetectionFollowup'=>'list',
                           'mentionDetectionMail'=>'list',
                           'mentionDetectionNotification'=>'list',
                       'column_Aut_2'=>'newColumn',
                         'tabConfiguration'=>'section',
                           "directAccessToComponentList"=>'list',                        
                     'tabProfile'=>"tab",
                       'column_Pro_1'=>'newColumn',
                         'sectionOrganization'=>'section',
                           'team'=>'specific',
                           'organization'=>'specific',
                           'profile'=>'specific',                             
                       'column_Pro_2'=>'newColumn',
                         'sectionPhoto'=>'section',
                           'image'=>'photo'
                       
                         
        );
        $lockPassword=Parameter::getGlobalParameter('lockPassword');
        $paramLdap_allow_login=Parameter::getGlobalParameter('paramLdap_allow_login');
        if (! getBooleanValue($lockPassword) and ! (getSessionUser()->isLdap and isset($paramLdap_allow_login) and pq_strtolower($paramLdap_allow_login)=='true')) {
          $parameterList['sectionPassword']='section';
          $parameterList['password']='specific';
        }
        if (Parameter::getGlobalParameter('startPageLocked')=='YES') {
          unset($parameterList['startPage']);
        }
        if (Parameter::getGlobalParameter('doNotExportAssignmentsForXMLFormat')===true) {
          unset($parameterList['exportAssignmentsForXMLFormat']);
        }
        if(Parameter::getGlobalParameter('paramDbType')=='pgsql'){
          unset($parameterList['notApplicableValue']);
        }
        if(!isNewGui()){
          unset($parameterList['menuLeftDisplayMode']);
          unset($parameterList['menuBarTopMode']);
          unset($parameterList['newItemAccessMode']);
          unset($parameterList['newGuiThemeColor']);
          unset($parameterList['newGuiThemeColorBis']);     
        }else{
          unset($parameterList['theme']);
          unset($parameterList['menuBarTopMode']);
          unset($parameterList['menuLeftDisplayMode']);
        }
        if (isIE()) unset($parameterList['newGui']);
        break;
      case ('globalParameter'):
        $parameterList=array(
                        'tabWork'=>"tab",
                          'columnWorkLeft'=>'newColumn',
                            'sectionDailyHours'=>"section",
                              'startAM'=>'time',
                              'endAM'=>'time',
                              'startPM'=>'time',
                              'endPM'=>'time',
                              'projectDailyHours'=>'list',
                            'sectionOpenDays'=>'section',
                              'OpenDayMonday'=>'list',
                              'OpenDayTuesday'=>'list',
                              'OpenDayWednesday'=>'list',
                              'OpenDayThursday'=>'list',
                              'OpenDayFriday'=>'list',
                              'OpenDaySaturday'=>'list',
                              'OpenDaySunday'=>'list',
                            'sectionWorkUnit'=>'section',
                              'imputationUnit'=>'list',
                              'workUnit'=>'list',
                              'dayTime'=>'number',
                          'columnWorkRight'=>'newColumn',
                            'sectionImputation'=>'section',
                              'displayOnlyHandled'=>'list',
                              'setHandledOnRealWork'=>'list',
                              'setDoneOnNoLeftWork'=>'list',
                              'maxDaysToBookWork'=>'number',
                              'maxDaysToBookWorkBlocking'=>'number',
                              'dontStartBeforeValidatedDate'=>'list',
                              'imputationAlertInputByOther'=>'list',
                              'imputationAlertCancelByOther'=>'list',
                              'displayPoolsOnImputation'=>'list',
                              'showPoolLinesToUpdateLeftWork'=>'list',
                              'autoUpdateLeftWorkOnPool'=>'list',
                              'submitAlertSendToProjectLeader'=>'list',
                              'submitAlertSendToTeamManager'=>'list',
                              'submitAlertSendToOrganismManager'=>'list',
                              'imputationAlertWorkTooSoon'=>'list',
                              'imputationFormat'=>'list',
                              'hideRealAsPlanned'=>'list',
                              'imputationHideDoneG'=>'list',
                              'imputationSearchOnName'=>'list',
                              'imputationTicketResponsible'=>'list',
                        'tabPlanning'=>"tab",
                         'columnPlanningLeft'=>'newColumn',
                           'sectionTicket'=>'section',
                           'realWorkOnlyForResponsible'=>'list',
                           'responsibleFromProduct'=>'list',
                           'limitPlanningActivity'=>'list',
                           'filterTicketReportPriority'=>'list',
                           'manageTicketCustomer'=>'list', //ADD qCazelles - Manage ticket at customer level - Ticket #87
                           'manageTicketVersion'=>'list',
                          //'sectionAction'=>'section',
                          //    'enablePredefinedActions'=>'list',
                           'manageAccountable'=>'list',

                           //'sectionOrganization'=>'section',
                           //'useOrganizationBudgetElement'=>'list', // ADD BY TABARY Marc - 2017-06-06 - USE OR NOT ORGANIZATION BUDGETELEMENT
                           //'sectionToDoList'=>'section',
                           //'activateSubtasksManagement'=>'list',
                        'columnPlanningRight'=>'newColumn',
                          'sectionPlanningControl'=>'section',
                            'allowTypeRestrictionOnProject'=>'list',
                            'hideItemTypeRestrictionOnProject'=>'list',
                            'allowListRestrictionOnProject'=>'list',
                            'selectFonction'=>'list',
                            'listTagsPerProject'=>'list',
                            'requestorLimitToContact'=>'list',
                          'sectionLeaves'=>'section',
                            //  'leavesSystemActiv'=>'list',
                            'leavesSystemAdmin'=>'list',
                        'tabPlanPlanning'=>"tab",
                          'columnPlanPlanningLeft'=>'newColumn',
                            'sectionPlanning'=>'section',
                              'removeQuickPlanningFeature'=>'list',
                              'forceProjectPriority'=>'list',
                              'notStartBeforeValidatedStartDate'=>'list',
                              'planningPriorityByEndDate'=>'list',
                              'planningModeForParent'=>'list',
                              'displayResourcePlan'=>'list',
                              //'maxProjectsToDisplay'=>'number',    ticket #5659
                              'dependencyStrictMode'=>'list',
                              'isManualProgress'=>'list',
                              //'technicalProgress'=>'list',
                              'activityOnRealTime'=>'list',
                              'checkedSurbookingDefault'=>'list',
                              'gestionInheritedEndDate'=>'list',                             
                              'plannedWorkManualType'=>'list',
                              'manageCapacityForIntervention'=>'list',
                              'limitDisplayPlanning'=>'number',
                            'sectionAffectationAssignation'=>'section',
                              'autoAffectationPool'=>'list',
                              'statusChangeAssignment'=>'list',

                        'columnPlanPlanningRight'=>'newColumn',
                            //'sectionPool'=>'section',
                            'sectionPlanningAutomation'=>'section',
                              'consolidateValidated'=>'list',
                              'setResponsibleIfSingle'=>'list',
                              'allocateResponsibleToProject'=>'list',
                              'setResponsibleIfNeeded'=>'list',
                              'autoSetAssignmentByResponsible'=>'list',
                              'autoUpdateActivityStatus'=>'list',
                              'defaultSkipCopyStatus'=>'list',
                              'automaticChangeTechnicalProgress'=>'list',
                            'menuMilestone'=>'section',
                              //'manageMilestoneOnItems'=>'list',
                              'autoLinkMilestone'=>'list',
                              'milestoneFromVersion'=>'list',
                              'updateMilestoneResponsibleFromDeliverable'=>'list',
                              'updateMilestoneResponsibleFromIncoming'=>'list',
                              'updateDeliverableResponsibleFromMilestone'=>'list',
                              'updateIncomingResponsibleFromMilestone'=>'list',
                              'manuallyChangePlannedDate'=>'list',

// ELIOTT - LEAVE SYSTEM  
                          
                        'tabDisplay'=>"tab",
                          'columnDisplayLeft'=>'newColumn',
                            'sectionDisplay'=>'section',
                              'paramDbDisplayName'=>'text',
                              //'paramFadeLoadingMode'=>'list',
                              'sizeDisplayProjectToday'=>'number',
                              'maxItemsInTodayLists'=>'number',
                              'filterByStatus'=>'list', //ADD by qCazelles - Filter by Status
                              'filterByTags'=>'list',
                              "hideHoursTicketDueDates"=>'list',
                              //'projectRestriction'=>'list', // Babynus : feature disabled do to regressions                              
                          'columnDisplayRight'=>'newColumn',
                            'sectionDisplayDefault'=>'section',
                              'newGui'=>'list',
                              'newGuiThemeColor'=>'color',
                              'newGuiThemeColorBis'=>'color',
                              'paramDefaultLocale'=>'list',
                              'defaultTheme'=>'list',
                              'startPage'=>'list',
                              'startPageLocked'=>'list',
                              'paramIconSize'=>'list',
                              'menuBarTopMode'=>'list',
                              'menuLeftDisplayMode'=>'list',
                              'newItemAccessMode'=>'list',
                              'MenuBarTop'=>'list',
                              'MenuBarLeft'=>'list',
                              'displayHistory'=>'list',
                              "editor"=>'list',
                              //"scaytAutoStartup"=>'list',
                              "notApplicableValue"=>"list",
                              'restrictProjectList'=>'list',
                              // MTY - EXPORT XLS OR ODS
                              "typeExportXLSorODS"=>'list',
                              // MTY - EXPORT XLS OR ODS
                              "globalNoteDiscussionMode"=>'list',
                              "showOnlyNotes"=>"list",
                              "hideEmailsSent"=>"list",
                              "notReceiveHisOwnEmails"=>'list',
                              'paramOrderNoteMail'=>'list',
                              "clientElementList"=>'list',
                              "directEditTestCaseRun"=>'list',
                              "showColorTypeActivity"=>'list',
                              "showHatchOnPlanningBar"=>'list',
                              "autoHideMenuLeftDashboard"=>'list',
                        'tabMiscellaneous'=>"tab",
                          'columnMiscellanousLeft'=>'newColumn',
                             'sectionReferenceFormat'=>'section',
                               'referenceFormatPrefix'=>'text',
                               'referenceFormatNumber'=>'number',
                               'changeReferenceOnTypeChange'=>'list',
                             'sectionDocumentReferenceFormat'=>'section',
                               'documentReferenceFormat'=>'text',
                               'versionReferenceSuffix'=>'text',
                               'draftSeparator'=>'text',
                               'preserveUploadedFileName'=>'list',
                               'lockDocumentDownload'=>'list',
                               'versionsWithoutAttachments'=>'list',
                             'sectionBillReferenceFormat'=>'section',
                               'billReferenceFormat'=>'text',
                               'billNumSize'=>'number',
                               'ExportBillInFormatFacturX'=>'list',
                          'columnMiscellanousRight'=>'newColumn',
                      'tabConfiguration'=>'tab', //Add molives - ticket 178 - 26/04/2018
                          'columnConfigurationLeft'=>'newColumn',
                            'sectionProductAndComponent'=>'section',    // ADD by qCazelles
                            'displayBusinessFeature'=>'list',
                            'displayLanguage'=>'list',
                            'displayContext'=>'list',
                            'showTendersOnVersions'=>'list',
                            'includeProductInProductStructure'=>'list',
                          'columnConfigurationRight'=>'newColumn',
                            'sectionVersion'=>'section',
                            'displayMilestonesStartDelivery'=>'list',                           
                            'displayListOfActivity'=>'list',
                            'directAccessToComponentList'=>'list',
                            'versionNameAutoformat'=>'list',
                            'versionNameAutoformatSeparator'=>'text',
                            'subscriptionAuto'=>'list',
                            'typeOfCopyComponentVersion'=>'list',
                            'versionCompatibility'=>'list',
                            //'sectionDelivery'=>'section', //ADD qCazelles
                            'productVersionOnDelivery'=>'list',
                            'sortVersionComboboxNameDesc'=>'list', //ADD qCazelles - Sort versions in combobox - Ticket 89
                            'sortCompositionStructure'=>'list', //ADD qCazelles - Sort version composition-structure - Ticket 142
                            'manageComponentOnRequirement'=>'list',   //ADD qCazelles - Add Component to Requirement - Ticket 171
                            'manageComponentOnChangeRequest'=>'list',
                            'dontAddClosedDeliveredVersionToProject'=>'list', //ADD qCazelles - Dont add closed and delivered versions to Project - Ticket 181
                            'authorizeActivityOnDeliveredProduct'=>'list',
                            'autoSetUniqueComponentVersion'=>'list',
                        'tabFinancial'=>"tab",
                          'newColumnbFinancialLeft'=>'newColumn',
                            'sectionFinancialProvider'=>'section',
                              'ImputOfAmountProvider'=>'list',
                              'ImputOfBillLineProvider'=>'list',
                            'sectionFinancialClient'=>'section',
                              'ImputOfAmountClient'=>'list',
                              'ImputOfBillLineClient'=>'list',
                            'sectionFinancialAutomation'=>'section',
                              'ExpenseLink'=>'list',
                            'sectionFinancialWorkUnit'=>'section',
                              'ComplexitiesNumber'=>'number',
                              'CaReplaceValidCost'=>'list',
                              'enableWorkCommandManagement'=>'list',
                          'newColumnbFinancialRight'=>'newColumn',
                            'sectionLocalization'=>'section',
                              'currency'=>'text',
                              'currencyPosition'=>'list',
                            'sectionMultiCurrency'=>'section',
                              'multiCurrency'=>'list',
                              'multiCurrencyShowGlobal'=>'list',
                        'tabMail'=>"tab",   
                          'newColumnMailLeft'=>'newColumn',
                            'sectionMail'=>'section',
                              'paramAdminMail'=>'text',
                              'paramMailSender'=>'text',
                              'paramMailReplyTo'=>'text',
                              'paramMailReplyToName'=>'text',
                              'paramMailSmtpServer'=>'text',
                              'paramMailSmtpUseUnsecureSsl'=>'list',
                              'paramMailSmtpPort'=>'number',
                              'paramMailSmtpUsername'=>'text',
                              'paramMailSmtpPassword'=>'password',
                              'paramMailEol'=>'list',
                              'paramMailSendmailPath'=> 'text',
                              'paramMailerType'=>'list',
                              'paramMailerHelo'=>'list',
                              'paramMailerSendAsCurrentUser'=>'list',
                              'paramAttachmentMaxSizeMail'=>'text',
                              'paramAdditionImage'=>'list',
                              'paramAttachmentNumMail'=>'text',
                          'newColumnMailRight'=>'newColumn',
                            'sectionMailGrouping'=>'section',
                              'mailGroupActive'=>'list',
                              'mailGroupPeriod'=>'number',
                              'mailGroupDifferent'=>'list',
                            'sectionMailTest'=>'section',
                              'mailerTestDest'=>'text',
                              'mailerTestTitle'=>'text',
                              'mailerTestMessage'=>'display', 
                              'mailerTestSender'=>'list',
                              'mailerTest'=>'specific',
                          'newColumnMailBottom'=>'newColumnFull',
                            'sectionMailTitle'=>'section',  
                              'paramMailTitleNew'=>'longtext',
                              'paramMailTitleAnyChange'=>'longtext',
                              'paramMailTitleStatus'=>'longtext',
                              'paramMailTitleResponsible'=>'longtext',
                              'paramMailTitleDescription'=>'longtext',
                              'paramMailTitleResult'=>'longtext',
                              'paramMailTitleNote'=>'longtext',
                              'paramMailTitleNoteChange'=>'longtext',
                              'paramMailTitleAssignment'=>'longtext',
                              'paramMailTitleAssignmentChange'=>'longtext',
                              'paramMailTitlePriorityChanged'=>'longtext',
                              'paramMailTitleNewUserCreated'=>'longtext',
                              'paramMailTitleAttachment'=>'longtext',
                              'paramMailTitleDirect'=>'longtext',
                              'paramMailTitleUser'=>'longtext',
                              'paramMailBodyUser'=>'display',
                              'paramMailTitleApprover'=>'longtext',
                              'paramMailBodyApprover'=>'display',
                              'paramMailTitleAffectationAdd'=>'longtext',
                              'paramMailTitleAffectationChange'=>'longtext',
                              'paramMailTitleReport'=>'longtext',
                              'paramMailBodyReport'=>'longtext',
                        'tabAuthent'=>"tab",
                          'newColumnAuthentLeft'=>'newColumn',
                            'sectionUserAndPassword'=>'section',
                              'defaultProfile'=>'list',
                              //'paramDefaultPassword'=>'text',
                              'paramPasswordStrength'=>'list',
                              'paramPasswordMinLength'=>'number',
                              'paramLockAfterWrongTries'=>'number',
                              'passwordValidityDays'=>'number',
                              'rememberMe'=>'list',
                              'initializePassword'=>'list',
                              'requiredOldPassword'=>'list',   
                        'oldPasswordDifferentNew'=>'list',
                        'passwordResetEnabled'=>'list',
                        'otpForAdminUsers'=>'list',
                        'otpForNewUsers'=>'list',
                      'sectionLdap'=>'section',
                              'paramLdap_allow_login'=>'list',
                              'paramLdap_base_dn'=>'text',
                              'ldapFormatUri'=>'list',
                              'paramLdap_host'=>'text',
                              'paramLdap_port'=>'text',
                              'paramLdap_version'=>'list',
                              'ldapSslOverTls'=>'list',
                              'paramLdap_search_user'=>'text',
                              'paramLdap_search_pass'=>'password',
                              'paramLdap_user_filter'=>'text',
                              'ldapDefaultProfile'=>'list',
                              'ldapMsgOnUserCreation'=>'list',
                              'ldapCreationAction'=>'list',
                              'ldapDefaultProject'=>'list',
                          'newColumnAuthentRight'=>'newColumn',
                      'sectionSAML'=>'section',
                        'SAML_allow_login'=>'list',
                        'otpForDirectConnectionsWithSso'=>'list',
                        'SAML_ssoCommonName'=>'text',
                              'SAML_idpId'=>'text',
                              'SAML_SingleSignOnService'=>'text',
                              'SAML_SingleLogoutService'=>'text',
                              'SAML_idpCert'=>'text',
                              'SAML_attributeUid'=>'text',
                              'SAML_attributeMail'=>'text',
                              'SAML_attributeCommonName'=>'text',
                              'SAML_isADFS'=>'list',                              
                              'SAML_defaultProfile'=>'list',
                              'SAML_msgOnUserCreation'=>'list',
                              'SAML_creationAction'=>'list',
                              'SAML_defaultProject'=>'list',
                              'SAML_metadata'=>'specific',
                              'SAML_spCertMessage'=>'specific',
                        'tabAutomation'=>"tab",
                          'newColumnbAutomationLeft'=>'newColumn',
                            'sectionCron'=>'section',
                              //'cronDirectory'=>'text',
                              'cronSleepTime'=>'number',
                              'cronCheckDates'=>'number',                       
                              'alertCheckTime'=>'number',                              
// BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM
                              //'notificationSystemActiv'=>'list', // Now managed through module
                              'cronCheckNotifications'=>'number',
                              "cronDateFormat"=>'list',
                              "cronTimeFormat"=>'list',
                              'cronCheckEmails'=>'number',
                              'paramSignatureAndTagToRemove'=>'text',
// END - ADD BY TABARY - NOTIFICATION SYSTEM
                              'sectionCronArchiveHistory'=>'section',
                                'cronArchiveTime'=>'number',
                                'cronArchivePlannedDate'=>'time',
                                'cronArchiveCloseItems'=>'list',
                              'sectionCronImport'=>'section',
                                'cronImportDirectory'=>'text',
                                'cronCheckImport'=>'number',
                                'cronImportLogDestination'=>'list',
                                'cronImportMailList'=>'text',
                              'sectionCronInputMails'=>'section',
//                                 'cronCheckEmails'=>'number',
//                                 'cronCheckEmailsHost'=>'text',
//                                 'cronCheckEmailsUser'=>'text',
//                                 'cronCheckEmailsPassword'=>'password',
//                                 'paramSignatureAndTagToRemove'=>'text',
//                                 'afterMailTreatment'=>'list',
//                                 'allowAttachInputMails'=>'list',
//                                 'sizeAttachmentInputMails'=>'text',
                                '_lib_inputMailboxMessage'=>'label',
                              'sectionAutomaticPlanning'=>'section',
                                'automaticPlanningDifferential'=>'specific',
                                'automaticPlanningDifferentialDate'=>'list',
                                'modeSurbookingDifferential'=>'list',
                                'automaticPlanningComplete'=>'specific',
                                'automaticPlanningCompleteDate'=>'list',
                                'automaticFeedingOfTheReal'=>'list',
                                'modeSurbookingComplete'=>'list',
                                'cronBaseline' => 'section',
                                'automaticBaseline'=>'specific',
                            'newColumnbAutomationRight'=>'newColumn',
                              'sectionImputationAlert'=>'section',
                                'imputationAlertCronResource'=>'specific',
                                'imputationAlertControlDayResource'=>'list',
                                'imputationAlertControlNumberOfDaysResource'=>'number',
                                'imputationAlertSendToResource'=>'list',
                                'imputationOnlyIncompleteResourceWork'=>'list',
                                'imputationAlertCronProjectLeader'=>'specific',
                                'imputationAlertControlDayProjectLeader'=>'list',
                                'imputationAlertControlNumberOfDaysProjectLeader'=>'number',
                                'imputationAlertSendToProjectLeader'=>'list',
                                'imputationOnlyIncompleteProjectLeaderWork'=>'list',
                                'imputationAlertCronTeamManager'=>'specific',
                                'imputationAlertControlDayTeamManager'=>'list',
                                'imputationAlertControlNumberOfDaysTeamManager'=>'number',
                                'imputationAlertSendToTeamManager'=>'list',
                                'imputationOnlyIncompleteTeamManagerWork'=>'list',
                                'imputationAlertCronOrganismManager'=>'specific',
                                'imputationAlertControlDayOrganismManager'=>'list',
                                'imputationAlertControlNumberOfDaysOrganismManager'=>'number',
                                'imputationAlertSendToOrganismManager'=>'list',
                                'imputationOnlyIncompleteOrganismManagerWork'=>'list',
                              'sectionSkillsAlert'=>'section',
                                'skillsAlertCron'=>'specific',
                                'skillsAlertResource'=>'list',
                                'skillsAlertTeamManager'=>'list',
                                'skillsAlertOrganismManager'=>'list',
                                'skillsAlertLeadTimes'=>'number',
                                'skillsAlertPeriodicity'=>'list',
                              'sectionMentionDetection'=>'section',
                                'mentionDetectionFollowup'=>'list',
                                'mentionDetectionMail'=>'list',
                                'mentionDetectionNotification'=>'list',
                            /*'sectionImputationAlert'=>'section',
                              'imputationAlertGenerationDay'=>'list',
                              'imputationAlertGenerationHour'=>'time',
                              'imputationAlertControlDay'=>'list',
                              'imputationAlertControlNumberOfDays'=>'number',
                              'imputationAlertSendToResource'=>'list',
                              'imputationAlertSendToProjectLeader'=>'list',
                              'imputationAlertSendToTeamManager'=>'list',*/
                        'tabSystem'=>"tab",
                          'newColumnbSystemLeft'=>'newColumn',
                            'sectionFiles'=>'section',
                              'paramAttachmentMaxSize'=>'text',
                              'paramAttachmentNum'=>'text',
                              'paramAttachmentDirectory'=>'text',
//                              'paramReportTempDirectory'=>'text',
                              'documentRoot'=>'text',    
                            'sectionSystemLocalization'=>'section',
                              'filenameCharset'=>'text',
                              'paramDefaultTimezone'=>'list',
                              'csvSeparator'=>'list',
                              'csvExportUTF8'=>'list',
                            'sectionSecurity'=>'section',
                              'paramTryToHackUserProfilList'=>'list',
                              'paramTryToHackUserList'=>'longtext',
                              'paramTryToHackMailList'=>'longtext',
                              'paramTryToHackObjectMail'=>'text',
                         'newColumnbSystemRight'=>'newColumn',
                            'sectionMiscellaneous'=>'section',
                              'getVersion'=>'list',
                              'paramProxy'=>'text',
                              'paramProxyLogin'=>'text',
                              'paramProxyPassword'=>'password',
                              'allowSendingStatistics'=>'list',
                            'sectionPdfExport'=>"section",
                               'paramMemoryLimitForPDF'=>'number',
                               'fontForPDF'=>'list',
                            'connectionSslToBd'=>'section',
                              'SslKey'=>'text',
                              'SslCert'=>'text',
                              'SslCa'=>'text'
        );
    }
    global $hosted;
    if (isset($hosted) and $hosted) {
      if ($typeParameter=='globalParameter') {
        unset($parameterList['documentRoot']);
        //unset($parameterList['paramMailSender']);
        //unset($parameterList['paramMailReplyTo']);
        //unset($parameterList['paramMailSmtpServer']);
        //unset($parameterList['paramMailSmtpPort']);
        //unset($parameterList['paramMailSmtpPort']);
        unset($parameterList['paramMailSendmailPath']);
        unset($parameterList['cronImportDirectory']);
        unset($parameterList['paramMemoryLimitForPDF']);
        unset($parameterList['sectionFiles']);
        unset($parameterList['paramAttachmentDirectory']);
        unset($parameterList['paramAttachmentMaxSize']);
        unset($parameterList['paramAttachmentNum']);
//        unset($parameterList['paramReportTempDirectory']);
        unset($parameterList['paramMailEol']);
        unset($parameterList['cronDirectory']);
        if (self::hostedSmtpDefault()) {
          unset($parameterList['paramMailSmtpPassword']);
        }
      }
    }
   $ssoReject = Parameter::getGlobalParameter('SAML_creationAction');
    if($ssoReject == "createReject"){
      unset($parameterList['SAML_defaultProfile']);
      unset($parameterList['SAML_msgOnUserCreation']);
      unset($parameterList['SAML_defaultProject']);
    }
    
    if(!Module::isModuleActive('moduleTechnicalProgress')){
      unset($parameterList['automaticChangeTechnicalProgress']);
    }
    
    if(!Module::isModuleActive('moduleTargetMilestone')){
      unset($parameterList['menuMilestone']);
      unset($parameterList['autoLinkMilestone']);
      unset($parameterList['milestoneFromVersion']);
      unset($parameterList['updateMilestoneResponsibleFromDeliverable']);
      unset($parameterList['updateMilestoneResponsibleFromIncoming']);
      unset($parameterList['updateDeliverableResponsibleFromMilestone']);
      unset($parameterList['updateIncomingResponsibleFromMilestone']);
    }
    if(!Module::isModuleActive('moduleActivityStream')){
      unset($parameterList['showOnlyNotes']);
      unset($parameterList['hideEmailsSent']);
    }
    if(!Module::isModuleActive('moduleOrganization')){
      unset($parameterList['organization']);
    }
    if (Parameter::getGlobalParameter('paramMailerType')!='phpmailer' and Parameter::getGlobalParameter('paramAttachmentMaxSizeMail')==0) {
      unset($parameterList['paramAttachmentMaxSizeMail']);
    }
    Module::applyModuleRestrictionsOnParametersList($parameterList);
    $user=getSessionUser();
    $showChecklistAll=false;
    if(Module::isModuleActive('moduleChecklist')){
      foreach ($user->getAllProfiles() as $prf) {
        $showChecklist=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$prf,'scope'=>'checklist'));
        if ($showChecklist and $showChecklist->id and $showChecklist->rightAccess=='1') {
          $showChecklistAll=true;
        }
      }
    }
    $showSubTask=false;
    foreach ($user->getAllProfiles() as $prof) {
      $showSubTaskObj=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$prof,'scope'=>'subtask'));
      if ($showSubTaskObj and $showSubTaskObj->id and $showSubTaskObj->rightAccess=='1') {
        $showSubTask=true;
      }
    }
    if (! $showChecklistAll) {
      unset($parameterList['displayChecklist']);
    }
    if(!$showSubTask or !Module::isModuleActive('moduleTodoList') ){ //Parameter::getGlobalParameter('activateSubtasksManagement')!='YES'
      unset($parameterList['displaySubTask']);
    }
//     if(!Module::isMenuActive("menuViewAllSubTask")){
//       unset($parameterList['activateSubtasksManagement']);
//     }
    if(!isNewGui()){
      unset($parameterList['menuLeftDisplayMode']);
      unset($parameterList['menuBarTopMode']);
      unset($parameterList['newItemAccessMode']);
    }else{
      unset($parameterList['menuBarTop']);
      unset($parameterList['paramIconSize']);
      unset($parameterList['MenuBarLeft']);
      unset($parameterList['MenuBarTop']);
    }
    $newGui = Parameter::getGlobalParameter('newGui');
    if(!$newGui){
      unset($parameterList['newGuiThemeColor']);
      unset($parameterList['newGuiThemeColorBis']);
    }else{
      unset($parameterList['defaultTheme']);
    }
    if (isIE()) unset($parameterList['newGui']);
    return $parameterList;
  }
  
  static public function getGlobalParameter($code) {
    global $$code;
    if (isset($$code)) {
      if ($code=='paramDbPrefix') {
        $$code=pq_strtolower($$code);
      }
      return $$code;
    }
    if ($code=='paramDbHost' or $code=='paramDbPort' or $code=='paramDbType' or $code=='paramDbPrefix'
     or $code=='paramDbName' or $code=='paramDbUser' or $code=='paramDbPassword') {
      return '';
    }
    if ($code=='paramPathSeparator') {
      return DIRECTORY_SEPARATOR;
    }
    if ($code=='mailEol') {
      $nl=Parameter::getGlobalParameter('paramMailEol');
      if (isset($nl) and $nl) {
        if ($nl=='LF') {
          $nl="\n";
        } else if ($nl=='CRLF') {
          $nl="\r\n";
        } else {
          //$nl=$nl; 
        }
      } else {
        $nl="\r\n";
      }
      return $nl;
    }
    if (!sessionValueExists('globalParametersArray')) {
      setSessionValue('globalParametersArray', array());
      $p=new Parameter();
      $crit=" (idUser is null and idProject is null)";
      enableCatchErrors();
      enableSilentErrors();
      $lst=$p->getSqlElementsFromCriteria(null, false, $crit);
      foreach ($lst as $param) {
        setSessionTableValue('globalParametersArray', $param->parameterCode, $param->parameterValue);
      }
      disableCatchErrors();
      disableSilentErrors();
    }
    if (sessionTableValueExist('globalParametersArray', $code)) {
      return getSessionTableValue('globalParametersArray', $code);
    } else {
      if ($code=='paramReportTempDirectory') return '../files/report/';
      return '';
    }
  }

  static public function getUserParameter($code) {
    if (!sessionValueExists('userParamatersArray')) {
      setSessionValue('userParamatersArray', array());
    }
    if (sessionTableValueExist('userParamatersArray', $code)) {
      return getSessionTableValue('userParamatersArray', $code);
    } 
    // If user not set (no id) retreive global parameter
    $user=getSessionUser();
    if (!$user->id) {
      return self::getGlobalParameter($code);
    }
    // If user set : initialise list of all parameters if not already done
    //               NB : just do it only if array is empty, will avoid to retreive all list when user parameter is just not set yet
    //if (count(getSessionValue('userParamatersArray'))<10) {
    if (!sessionTableValueExist('userParamatersArray', 'newGui')) {
      $p=new Parameter();
      enableCatchErrors();
      enableSilentErrors();
      $crit=" idUser=" . Sql::fmtId($user->id) . " and idProject is null";
      $lst=$p->getSqlElementsFromCriteria(null, false, $crit, 'parameterCode');
      foreach ($lst as $param) {
        if ($param->parameterCode=='userParamatersArray') continue; // Issue found, possibly on DEV only : parameter stored with code userParamatersArray sets the mess
        setSessionTableValue('userParamatersArray', $param->parameterCode, $param->parameterValue);
      }
      disableCatchErrors();
      disableSilentErrors();
    }
    // If code is set in DB, return this value
    if (sessionTableValueExist('userParamatersArray', $code)) {
      return getSessionTableValue('userParamatersArray', $code);
    }
    if ($code=='favoriteProjectsArray' or $code=='idFavoriteProjectList') return ''; // #8625 : for favorites do not search for global parameter
    // If code is not set in DB, get global parameter with same code (is default value)
    $val=self::getGlobalParameter($code);
    if (!$val) $val='';
    // Store value (from global parameter or empty string)
    setSessionTableValue('userParamatersArray', $code, $val);
    return $val;
  }
  
  static function storeUserParameter($code,$value,$userId=null) {
    if (! $userId) {
      $userId=getSessionUser()->id;
    }
    if ($code=='userParamatersArray') return; // Issue found, possibly on DEV only : parameter stored woth code userParamatersArray sets the mess
    $param=SqlElement::getSingleSqlElementFromCriteria('Parameter', array('idUser'=>$userId,'parameterCode'=>$code));
    if (! $param->id) {
      $param->parameterCode=$code;
      $param->idUser=$userId;
      $param->idProject=null;
    }
    $param->parameterValue=$value;
    $res=$param->save();
    if ($userId==getSessionUser()->id) {
      if (!sessionValueExists('userParamatersArray')) {
        setSessionValue('userParamatersArray', array());
      }
      setSessionTableValue('userParamatersArray', $code, $value);
    }
  }
  static function storeGlobalParameter($code,$value) {
    $param=SqlElement::getSingleSqlElementFromCriteria('Parameter', array('idUser'=>null,'parameterCode'=>$code));
    if (! $param->id) {
        $param->parameterCode=$code;
        $param->idUser=null;
        $param->idProject=null;
    }
    $param->parameterValue=$value;
    $param->save();
    if (!sessionValueExists('globalParametersArray')) {
      setSessionValue('globalParametersArray', array());
    }
    setSessionTableValue('globalParametersArray', $code, $value);
// MTY - GENERIC DAY OFF
    if (pq_substr($code,0,7)=="OpenDay") {
        $weekDayNumWeekDayName = array("OpenDaySunday"=>"dayOfWeek0",
                                       "OpenDayMonday"=>"dayOfWeek1",
                                       "OpenDayTuesday"=>"dayOfWeek2",
                                       "OpenDayWednesday"=>"dayOfWeek3",
                                       "OpenDayThursday"=>"dayOfWeek4",
                                       "OpenDayFriday"=>"dayOfWeek5",
                                       "OpenDaySaturday"=>"dayOfWeek6");
        $calDef = new CalendarDefinition();
        $critCalDef = array("idle" => "0");
        $calDefList = $calDef->getSqlElementsFromCriteria($critCalDef);
        $field = $weekDayNumWeekDayName[$code];
        foreach($calDefList as $calDef) {
            $calDef->$field = ($value=="openDays"?0:1);
            $calDef->save();
  }
    }
// MTY - GENERIC DAY OFF
  
  }
  
  /* ==========================================================================
   * Columns of the document explorer.
   * ======================================================================= */
  static private $documentExplorerColumnDescription=array();
  static private $documentExplorerColumnOrder=array();

  static public function getDocumentExplorerColumnDescription($type='directory') {
    if (isset(self::$documentExplorerColumnDescription[$type])) {
      return self::$documentExplorerColumnDescription[$type];
    }
    if ($type=='document') {
      $objectClass='DocumentExplorerDocument';
      $arrayFields=array(
        'Name'                => array('width'=>260, 'minWidth'=>100, 'show'=>1),
        'Id'                  => array('width'=>60,  'minWidth'=>50,  'show'=>1),
        'IdProject'         => array('width'=>120, 'minWidth'=>50,  'show'=>1),
        'IdDocumentType'    => array('width'=>120, 'minWidth'=>50,  'show'=>1),
        'IdProduct'         => array('width'=>120, 'minWidth'=>50,  'show'=>1),
        'IdDocumentVersion' => array('width'=>120, 'minWidth'=>50,  'show'=>0),
        'DocumentReference'   => array('width'=>160, 'minWidth'=>50,  'show'=>1),
        'IdStatus'     => array('width'=>120, 'minWidth'=>50,  'show'=>1),
        'Idle'                => array('width'=>60,  'minWidth'=>50,  'show'=>0),
        'Locked'              => array('width'=>60,  'minWidth'=>50,  'show'=>0),
      );
    } else {
      $objectClass='DocumentExplorerDirectory';
      $arrayFields=array(
        'Name'        => array('width'=>300, 'minWidth'=>100, 'show'=>1),
        // Hideable, and hidden by default : the id brings nothing on the
        // directory tree. It stays forced on the document side.
        'Id'          => array('width'=>60,  'minWidth'=>50,  'show'=>0),
        'IdProject' => array('width'=>120, 'minWidth'=>50,  'show'=>0),
        'IdProduct' => array('width'=>120, 'minWidth'=>50,  'show'=>0),
        'Location'    => array('width'=>200, 'minWidth'=>50,  'show'=>0),
        'Idle'        => array('width'=>60,  'minWidth'=>50,  'show'=>0),
      );
    }

    // User settings, when there are any.
    $stored=array();
    $user=getSessionUser();
    if ($user and $user->id) {
      $cs=new ColumnSelector();
      $cols=$cs->getSqlElementsFromCriteria(array('idUser'=>$user->id,'objectClass'=>$objectClass));
      foreach ($cols as $c) {
        $stored[$c->field]=$c;
      }
    }

    // Header labels through the ProjeQtOr caption mechanism : getColCaption
    // applies the transposition of the object then returns i18n('col'.Field),
    // the very source the standard lists use.
    $captionObject = ($type=='document') ? new Document() : new DocumentDirectory();

    // Memorized order. sortOrder is written by the column selector when a
    // column is dragged.
    //
    // Each field gets a rank : its memorized sortOrder when that value is
    // usable, its declaration position otherwise. Usable means within the bounds
    // of the column count - a row created by the 'status' action may carry a
    // placeholder that is not a position. Equal ranks are settled by declaration
    // order.
    //
    // Ranking every field, rather than listing the memorized ones first, is what
    // keeps a column from jumping ahead of the columns that have no
    // ColumnSelector row yet.
    $nbFields=count($arrayFields);
    $ranked=array();
    $decl=0;
    foreach ($arrayFields as $field=>$attribute) {
      if ($field!='Name') {
        $pos=$decl;
        if (isset($stored[$field]) and $stored[$field]->sortOrder!==null
            and intval($stored[$field]->sortOrder)<$nbFields) {
          $pos=intval($stored[$field]->sortOrder);
        }
        $ranked[]=array('field'=>$field, 'pos'=>$pos, 'decl'=>$decl);
      }
      $decl++;
    }
    usort($ranked, function($a,$b) {
      if ($a['pos']==$b['pos']) return $a['decl']-$b['decl'];
      return ($a['pos']<$b['pos'])?-1:1;
    });
    // Name always holds position zero : it is the tree column, it carries the
    // fold handles and does not move.
    $reordered=array();
    if (isset($arrayFields['Name'])) $reordered['Name']=$arrayFields['Name'];
    foreach ($ranked as $entry) {
      $reordered[$entry['field']]=$arrayFields[$entry['field']];
    }
    $arrayFields=$reordered;

    $cpt=0;
    self::$documentExplorerColumnDescription[$type]=array();
    self::$documentExplorerColumnOrder[$type]=array();
    foreach ($arrayFields as $col=>$attribute) {
      $show=$attribute['show'];
      $width=$attribute['width'];
      if (isset($stored[$col])) {
        if ($stored[$col]->hidden=='1') $show=0;
        else                            $show=1;
        if (intval($stored[$col]->widthPct)) $width=intval($stored[$col]->widthPct);
      }
      // Name never hides : it is the tree column, its switch is locked in the
      // selector, and a memorized 'hidden' would put it out of reach for good.
      if ($col=='Name') $show=1;
      // Id stays forced on documents, for the same reason, and is hideable on
      // directories.
      if ($col=='Id' and $type=='document') $show=1;
      $label=$captionObject->getColCaption(pq_strtolower(pq_substr($col,0,1)).pq_substr($col,1));
      self::$documentExplorerColumnDescription[$type][$col]=array(
        'name'        => $col,
        'show'        => $show,
        'defaultShow' => $attribute['show'],
        'order'       => $cpt,
        'width'       => $width,
        'label'       => $label,
        'minWidth'    => $attribute['minWidth']);
      self::$documentExplorerColumnOrder[$type][$cpt]=$col;
      $cpt++;
    }
    return self::$documentExplorerColumnDescription[$type];
  }

  /**
   * Clears the static descriptor cache, for one type or for both.
   *
   * tool/documentExplorerColumnAction.php writes to ColumnSelector then reads
   * the descriptor back within the same request : without this purge it would
   * get the values from before its own write.
   */
  static public function resetDocumentExplorerColumnDescription($type=null) {
    if ($type===null) {
      self::$documentExplorerColumnDescription=array();
      self::$documentExplorerColumnOrder=array();
    } else {
      unset(self::$documentExplorerColumnDescription[$type]);
      unset(self::$documentExplorerColumnOrder[$type]);
    }
  }

  static public function getDocumentExplorerColumnOrder($type='directory') {
    if (! isset(self::$documentExplorerColumnOrder[$type])) {
      self::getDocumentExplorerColumnDescription($type);
    }
    return self::$documentExplorerColumnOrder[$type];
  }

  static public function getPlanningColumnOrder($planningType='planning', $all=false) {
    if (!isset(self::$planningColumnOrderAll[$planningType])) self::getPlanningColumnDescription($planningType);
    if ($all) {
      if (isset(self::$planningColumnOrderAll[$planningType]))return self::$planningColumnOrderAll[$planningType];
    } else {
      if (isset(self::$planningColumnOrder[$planningType]))return self::$planningColumnOrder[$planningType];
    }
  }
  
  static public function getPlanningColumnDescription($planningType='planning') {
    if (isset(self::$planningColumnDescription[$planningType])) return self::$planningColumnDescription[$planningType];
    $arrayFields=array(
        'Name'=>array('width'=>300, 'minWidth'=>100, 'show'=>1),
        'Id'=>array('width'=>50, 'minWidth'=>50, 'show'=>1),
        'Type'=>array('width'=>100, 'minWidth'=>50, 'show'=>1),
        'IdStatus'=>array('width'=>70, 'minWidth'=>50, 'show'=>1),
        'Priority'=>array('width'=>50, 'minWidth'=>50, 'show'=>1),
        'IdPlanningMode'=>array('width'=>100, 'minWidth'=>50, 'show'=>1),
        'ValidatedStartDate'=>array('width'=>80, 'minWidth'=>50, 'show'=>1),
        'ValidatedEndDate'=>array('width'=>80, 'minWidth'=>50, 'show'=>1),
        'ValidatedDuration'=>array('width'=>60, 'minWidth'=>50, 'show'=>1),
        'ValidatedCost'=>array('width'=>70, 'minWidth'=>50, 'show'=>1),
        'ValidatedWork'=>array('width'=>70, 'minWidth'=>50, 'show'=>1),
        'UnitProgress'=>array('width'=>50, 'minWidth'=>50, 'show'=>1),
        'AssignedWork'=>array('width'=>70, 'minWidth'=>50, 'show'=>1),
        'RealWork'=>array('width'=>70, 'minWidth'=>50, 'show'=>1),
        'LeftWork'=>array('width'=>70, 'minWidth'=>50, 'show'=>1),
        'Progress'=>array('width'=>50, 'minWidth'=>50, 'show'=>1),
        'Resource'=>array('width'=>90, 'minWidth'=>50, 'show'=>1),
        'Responsible'=>array('width'=>90, 'minWidth'=>50, 'show'=>1),
        'RespInitial'=>array('width'=>90, 'minWidth'=>50, 'show'=>0),
        'StartDate'=>array('width'=>80, 'minWidth'=>50, 'show'=>0),
        'EndDate'=>array('width'=>80, 'minWidth'=>50, 'show'=>0),
        'PlannedWork'=>array('width'=>70, 'minWidth'=>50, 'show'=>0),
        'Duration'=>array('width'=>60, 'minWidth'=>50, 'show'=>0),
        'AssignedCost'=>array('width'=>70, 'minWidth'=>50, 'show'=>0),
        'RealCost'=>array('width'=>70, 'minWidth'=>50, 'show'=>0),
        'LeftCost'=>array('width'=>70, 'minWidth'=>50, 'show'=>0),
        'PlannedCost'=>array('width'=>70, 'minWidth'=>50, 'show'=>0),
        'IdHealthStatus'=>array('width'=>70, 'minWidth'=>50, 'show'=>0),
        'QualityLevel'=>array('width'=>70, 'minWidth'=>50, 'show'=>0),
        'IdTrend'=>array('width'=>70, 'minWidth'=>50, 'show'=>0),
        'IdOverallProgress'=>array('width'=>90, 'minWidth'=>50, 'show'=>0),
        'ObjectType'=>array('width'=>150, 'minWidth'=>50, 'show'=>0),
        'ExterRes'=>array('width'=>90, 'minWidth'=>50, 'show'=>0),
        'Predecessor'=>array('width'=>90, 'minWidth'=>50, 'show'=>0),
        'Successor'=>array('width'=>90, 'minWidth'=>50, 'show'=>0),
        'Tags'=>array('width'=>120, 'minWidth'=>50, 'show'=>0)
    );
    if ($planningType === 'resource') {
      unset($arrayFields['Predecessor']);
      unset($arrayFields['Successor']);
    }
    if ($planningType=='planning') {
      $arrayFields['IdContact']=array('width'=>90, 'minWidth'=>50, 'show'=>0);
      $arrayFields['IdActivity']=array('width'=>120, 'minWidth'=>50, 'show'=>0);
      $arrayFields['UnitToRealise']=array('width'=>80, 'minWidth'=>50, 'show'=>0);
      $arrayFields['UnitWeight']=array('width'=>80, 'minWidth'=>50, 'show'=>0);
      $arrayFields['Origin']=array('width'=>90, 'minWidth'=>50, 'show'=>0);
    }
    $cpt=0;
    $project = new Project();
    $hiddenProjectField = $project->getExtraHiddenFields('*', null, getSessionUser()->getProfile(), true);
    $projectPE = new ProjectPlanningElement();
    $hiddenProjectPlanningElementField=$projectPE->getExtraHiddenFields('*', null, getSessionUser()->getProfile(), true);
    $hiddenProjectField=array_merge($hiddenProjectField,$hiddenProjectPlanningElementField);
    if(in_array('idHealth', $hiddenProjectField))$hiddenProjectField[array_search('idHealth', $hiddenProjectField)]='idHealthStatus';
    if(in_array('idQuality', $hiddenProjectField))$hiddenProjectField[array_search('idQuality', $hiddenProjectField)]='qualityLevel';
    
    $activity = new Activity();
    $hiddenActivityField = $activity->getExtraHiddenFields('*', null, getSessionUser()->getProfile(), true);
    $activityPE = new ActivityPlanningElement();
    $hiddenActivityPlanningElementField=$activityPE->getExtraHiddenFields('*', null, getSessionUser()->getProfile(), true);
    $hiddenActivityField=array_merge($hiddenActivityField,$hiddenActivityPlanningElementField);
    
    foreach($arrayFields as $col=>$attribute) {
      $cpt++;
      $field = pq_strtolower(pq_substr($col, 0, 1)).pq_substr($col, 1);
      if($col == 'IdHealthStatus')$field = 'idHealth';
      if($col == 'QualityLevel')$field = 'idQuality';
      if($project->isAttributeSetToField($field, 'hidden')){
        $field = pq_strtolower(pq_substr($col, 0, 1)).pq_substr($col, 1);
        if(!in_array($field, $hiddenProjectField))$hiddenProjectField[]=$field;
      }
      if($activity->isAttributeSetToField($field, 'hidden')){
        $field = pq_strtolower(pq_substr($col, 0, 1)).pq_substr($col, 1);
        if(!in_array($field, $hiddenActivityField))$hiddenActivityField[]=$field;
      }
      $show=($col=='Tags' or ($planningType=='planning' and in_array($col, array('IdContact','IdActivity','UnitToRealise','UnitWeight','Origin','Successor'))))?'0':'1';
      self::$planningColumnDescription[$planningType][$col]=array('name'=>$col,'show'=>$show,'defaultShow'=>$attribute['show'],'order'=>$cpt,'width'=>$attribute['width'], 'minWidth'=>$attribute['minWidth']);
    }
    
    $arrayProjectFields = array();
    if($planningType == 'portfolio'){
      $listProjectFields = $project->getFieldsArray(true);
      $cpt++;
      foreach ($listProjectFields as $field){
        $dataType = $project->getDataType($field);
        $dataLength = $project->getDataLength($field);
        if(pq_substr($field, 0, 1) == '_')continue;
        if($field == 'isUnderConstruction' or $field == 'idProjectType' or $field == 'fixPlanning' or $field == 'idQuality' or $field == 'idHealth' or $field == 'idTrend' or $field == 'idOverallProgress')continue;
        if($dataType == 'undefined' or ((($dataType == 'varchar' or $dataType == 'mediumtext') and $dataLength > 200) and $field!='tags'))continue;
        if(isset($arrayProjectFields[ucfirst($field)]) or isset($arrayFields[ucfirst($field)]))continue;
        $cpt++;
        $arrayProjectFields[ucfirst($field)]=array('width'=>90, 'minWidth'=>50, 'show'=>0);
        self::$planningColumnDescription[$planningType][ucfirst($field)]=array('name'=>ucfirst($field),'show'=>'1','defaultShow'=>0,'order'=>$cpt,'width'=>100, 'minWidth'=>50);
      }
    }
    
    $arrayActivityFields = array();
    if($planningType == 'planning'){
      $listActivityFields = $activity->getFieldsArray(true);
      $cpt++;
      foreach ($listActivityFields as $field){
        $dataType = $activity->getDataType($field);
        $dataLength = $activity->getDataLength($field);
        $lowField = pq_strtolower($field);
        if(pq_substr($field, 0, 1) == '_')continue;
        if(pq_strpos($lowField, "unit") !== false or $field == 'idWeightMode' or $field == 'idActivityType' or $field=='idActivityPlanningMode' or $field == 'originId'
            or $field == 'originType' or $field == 'targetValue' or $field == 'actualValue' or $field == 'nbVoted' or $field == 'pctRate')continue;
        if($dataType == 'undefined' or (($dataType == 'varchar' or $dataType == 'mediumtext') and $dataLength > 200))continue;
        if(isset($arrayActivityFields[ucfirst($field)]) or isset($arrayFields[ucfirst($field)]))continue;
        $arrayActivityFields[ucfirst($field)]=array('width'=>90, 'minWidth'=>50, 'show'=>0);
        $defaultWidth=($field=='idTargetProductVersion')?130:100;
        self::$planningColumnDescription[$planningType][ucfirst($field)]=array('name'=>ucfirst($field),'show'=>'1','defaultShow'=>0,'order'=>$cpt,'width'=>$defaultWidth, 'minWidth'=>50);
        $cpt++;
      }
    }
    
    $pe=new ProjectPlanningElement();
    $pe->setVisibility();
    $workVisibility=$pe->_workVisibility;
    $costVisibility=$pe->_costVisibility;
    $res=array();
    $resAll=array();
    // Default Values
    $planningClass = array('planning'=>'Planning','portfolio'=>'PortfolioPlanning','resource'=>'ResourcePlanning','global'=>'GlobalPlanning','version'=>'VersionPlanning','contract'=>'ContractGantt', 'workPlan'=>'WorkPlan');
    $user=getSessionUser();
    $columnSelector = new ColumnSelector();
    $list=$columnSelector->getSqlElementsFromCriteria(array('idUser'=>$user->id,'objectClass'=>$planningClass[$planningType]));
    //$hidden="||"; // double so that first is at 1, not zero
    $arrayFieldsSorted=array();
    $arrayFieldsSorted[0]='Name';
    foreach ($list as $col){
      //VISIBILITY
        if($col->hidden){
        //$hidden.=pq_substr($col->field,18).'|';
        self::$planningColumnDescription[$planningType][$col->field]['show']=0;
        } else {
          self::$planningColumnDescription[$planningType][$col->field]['show']=1;
        }
        if($col->objectClass == 'PortfolioPlanning'){
          $field = pq_strtolower(pq_substr($col->field, 0, 1)).pq_substr($col->field, 1);
          //if($col->field == 'IdHealthStatus')$field='idHealth';
          //if($col->field == 'QualityLevel')$field='idQuality';
          if(in_array($field, $hiddenProjectField)){
            self::$planningColumnDescription[$planningType][$col->field]['show']=0;
          }
        }
        if($col->objectClass == 'Planning'){
          $field = pq_strtolower(pq_substr($col->field, 0, 1)).pq_substr($col->field, 1);
          //if($col->field == 'IdHealthStatus')$field='idHealth';
          //if($col->field == 'QualityLevel')$field='idQuality';
          if(in_array($field, $hiddenActivityField)){
            self::$planningColumnDescription[$planningType][$col->field]['show']=0;
          }
        }
      //ORDER
        if (! in_array($col->field,$arrayFieldsSorted)) $arrayFieldsSorted[intval($col->sortOrder)+1]=$col->field;
        self::$planningColumnDescription[$planningType][$col->field]['order']=intval($col->sortOrder);
      //WIDTH 
        $width = intval($col->widthPct);
        if($width==0 and isset(self::$planningColumnDescription[$planningType][$col->field]['width'])){
          $width = self::$planningColumnDescription[$planningType][$col->field]['width'];
        }
        self::$planningColumnDescription[$planningType][$col->field]['width']=$width;
    }
    
    if ($workVisibility!='ALL') {
        if ($workVisibility!='VAL') {
          //$hidden.='ValidatedWork|';
          self::$planningColumnDescription[$planningType]['ValidatedWork']['show']=0;
        }
        //$hidden.='AssignedWork|RealWork|LeftWork|PlannedWork|';
        self::$planningColumnDescription[$planningType]['AssignedWork']['show']=0;
        self::$planningColumnDescription[$planningType]['RealWork']['show']=0;
        self::$planningColumnDescription[$planningType]['LeftWork']['show']=0;
        self::$planningColumnDescription[$planningType]['PlannedWork']['show']=0;
    }
    if ($costVisibility!='ALL') {
      if ($costVisibility!='VAL') {
        //$hidden.='ValidatedCost|';
        self::$planningColumnDescription[$planningType]['ValidatedCost']['show']=0;
      }
      //$hidden.='AssignedCost|RealCost|LeftCost|PlannedCost|';
      self::$planningColumnDescription[$planningType]['AssignedCost']['show']=0;
      self::$planningColumnDescription[$planningType]['RealCost']['show']=0;
      self::$planningColumnDescription[$planningType]['LeftCost']['show']=0;
      self::$planningColumnDescription[$planningType]['PlannedCost']['show']=0;
    }
    ksort($arrayFieldsSorted);
    foreach($arrayFields as $column=>$attribute) {
      if($planningType == 'portfolio'){
        $field = pq_strtolower(pq_substr($column, 0, 1)).pq_substr($column, 1);
        if(in_array($field, $hiddenProjectField)){
          continue;
        }
      }
      if($planningType == 'planning'){
        $field = pq_strtolower(pq_substr($column, 0, 1)).pq_substr($column, 1);
        if(in_array($field, $hiddenActivityField)){
          continue;
        }
      }
      if (! in_array($column,$arrayFieldsSorted)) {
        $arrayFieldsSorted[]=$column;
      }
    }
    if($planningType == 'portfolio'){
      foreach($arrayProjectFields as $column=>$attribute) {
        $field = pq_strtolower(pq_substr($column, 0, 1)).pq_substr($column, 1);
        if(in_array($field, $hiddenProjectField)){
          continue;
        }
        if (! in_array($column,$arrayFieldsSorted)) {
          $arrayFieldsSorted[]=$column;
          self::$planningColumnDescription[$planningType][$column]['show']=0;
        }
      }
    }
    if($planningType == 'planning'){
      foreach($arrayActivityFields as $column=>$attribute) {
        $field = pq_strtolower(pq_substr($column, 0, 1)).pq_substr($column, 1);
        if(in_array($field, $hiddenActivityField)){
          continue;
        }
        if (! in_array($column,$arrayFieldsSorted)) {
          $arrayFieldsSorted[]=$column;
          self::$planningColumnDescription[$planningType][$column]['show']=0;
        }
      }
    }
    $i=1;
    foreach($arrayFieldsSorted as $order=>$column) {
      if(isset(self::$planningColumnDescription[$planningType][$column]['name']) and self::$planningColumnDescription[$planningType][$column]['show']==1){
        $res[$i]=$column;
      }else{
        $res[$i]='Hidden'.$column;
      }
      $resAll[$i]=$column;
      $i++;
    }
    self::$planningColumnOrderAll[$planningType]=$resAll;
    self::$planningColumnOrder[$planningType]=$res;
    return self::$planningColumnDescription[$planningType];
  }
  
  static public function getPlanningColumnEditable($planningType='planning') {
    if (isset(self::$planningColumnEditable[$planningType])) return self::$planningColumnEditable[$planningType];
    $arrayFields=array(
        'Name'=>array('width'=>300, 'minWidth'=>100, 'show'=>1),
        'Id'=>array('width'=>50, 'minWidth'=>50, 'show'=>1),
        'Type'=>array('width'=>100, 'minWidth'=>50, 'show'=>1),
        'IdStatus'=>array('width'=>70, 'minWidth'=>50, 'show'=>1),
        'Priority'=>array('width'=>50, 'minWidth'=>50, 'show'=>1),
        'IdPlanningMode'=>array('width'=>100, 'minWidth'=>50, 'show'=>1),
        'ValidatedStartDate'=>array('width'=>80, 'minWidth'=>50, 'show'=>1),
        'ValidatedEndDate'=>array('width'=>80, 'minWidth'=>50, 'show'=>1),
        'ValidatedDuration'=>array('width'=>60, 'minWidth'=>50, 'show'=>1),
        'ValidatedCost'=>array('width'=>70, 'minWidth'=>50, 'show'=>1),
        'ValidatedWork'=>array('width'=>70, 'minWidth'=>50, 'show'=>1),
        'UnitProgress'=>array('width'=>50, 'minWidth'=>50, 'show'=>1),
        'Predecessor'=>array('width'=>50, 'minWidth'=>50, 'show'=>1)
    );
    $cpt=0;
    foreach($arrayFields as $col=>$attribute) {
      $cpt++;
      self::$planningColumnEditable[$planningType][$col]=array('name'=>$col,'show'=>'1','defaultShow'=>$attribute['show'],'order'=>$cpt,'width'=>$attribute['width'], 'minWidth'=>$attribute['minWidth']);
    }
    return self::$planningColumnEditable[$planningType];
  }
  
  static public function deleteLogLevelParamFile() {
    global $parametersLocation, $currVersion, $maintenanceDisableEnforceUTF8;
    $fileHandler = fopen($parametersLocation,"r");
    if (!$fileHandler) {
      throwError("Error opening file $parameterLocation");
      return;
    }
    $noLogLevel = true;
    $result='';
    while (!feof($fileHandler)) {
      $line = fgets($fileHandler);
      $findme   = '$logLevel';
      if (pq_strpos($line, $findme) !== false) {
        $noLogLevel = false;
      }else{
        $result.=$line;
      }
    }
    fclose($fileHandler);
    if(!$noLogLevel){
      $fileHandler = fopen($parametersLocation,"w");
      fwrite($fileHandler,$result);
      fclose($fileHandler);
    }
  }
  
  /** 
   * Regenerate pamareter.php file depending on new param location : 
   *  if param exists in database : do not write param to file
   *  else : write param to file 
   */
  static public function regenerateParamFile($echoResult=false) {
    global $parametersLocation, $currVersion, $maintenanceDisableEnforceUTF8;
    // Security : copy file (except for first installation
    if (!isset($currVersion) or $currVersion!='V0.0.0') {
      copy($parametersLocation, $parametersLocation.'.'.date('YmdHis'));
    }
    $fileHandler = fopen($parametersLocation,"r");
    if (!$fileHandler) {
      throwError("Error opening file $parameterLocation");
      return;
    }
    $cptLine=0;
    $cptVar=0;
    $cptVarDb=0;
    $cptVarFile=0;
    $var="";
    $arrayParams=array();
    while (!feof($fileHandler)) {
      $line = fgets($fileHandler);
      $cptLine++;
      if (pq_substr($line,0,2)!='//' and pq_strpos(pq_strtolower($line),'<?php')===false) { // exclude comments
        $var.=$line;
        $posSemi=strrpos($var,';');
        if ($posSemi>0) {
          $command=pq_trim(pq_substr($var,0,$posSemi));
          $posEq=pq_strpos($command,'=');
          if ($posEq>0) {
            $paramCode=pq_trim(pq_substr($command,0,$posEq));
            $paramValue=pq_trim(pq_substr($command,$posEq+1));            

            $arrayParam[$paramCode]=$paramValue;
            $cptVar+=1;
          }
          $var="";
        }
      }       
    }
    fclose($fileHandler);  
    $nl="\n";
    traceLog("=== REWRITE PARAMTERS.PHP FILE = START ====================");    
    $fileHandler = fopen($parametersLocation,"w");
    fwrite($fileHandler,'<?php'.$nl); 
    fwrite($fileHandler,'// ======================================================================================='.$nl);
    fwrite($fileHandler,'// Automatically generated parameter file'.$nl);
    fwrite($fileHandler,'// on '.date('Y-m-d H:i:s').$nl);
    fwrite($fileHandler,'// ======================================================================================='.$nl);
    if ($echoResult) echo "<table style=\"border: 1px solid black;\"><tr><th class=\"messageHeader\">Code</th><th class=\"messageHeader\">Value</th><th class=\"messageHeader\">Result</th></tr>";
    foreach ($arrayParam as $paramCode=>$paramValue) {
      $result='';
      $resultHtml='&nbsp;';
      $code=pq_substr($paramCode,1);
      if (self::isGlobalParameterInDB($code)) {
        $result="moved to database";
        $resultHtml="<span style=\"color:red\">$result</span>";   
        $cptVarDb+=1;     
      } else if ($paramCode=='$enforceUTF8' and $paramValue and isset($maintenanceDisableEnforceUTF8) and $maintenanceDisableEnforceUTF8) {
        $result="enforceUTF8 set to 0";
        fwrite($fileHandler,$paramCode."='0';".$nl);
        $msg="For compatibility reason, \$enforceUTF8 parameter has been set to '0' in your parameters.php file<br/>";
        $msg.="Check your data through ProjeQtOr : if non ASCCII characters (like accentuated characters) are not displayed correctly, revert to \$enforceUTF8='1';";
        echo "<div class='messageWARNING'><i>" . $msg . "</i></div><br/>"; 
      } else {
        fwrite($fileHandler,$paramCode.'='.$paramValue.';'.$nl);
        $result="$paramCode kept in parameter file";
        $resultHtml="<span style=\"color:green\">$result</span>";
        $cptVarFile+=1;           
      }
      if ($echoResult) echo "<tr><td class=\"messageData\">$code</td><td class=\"messageData\">$paramValue</td><td class=\"messageData\">$resultHtml</td></tr>";
      traceLog("$paramCode $result");
    }
    if ($echoResult) echo "</table>";
    if ($echoResult) echo "<br/>lines read from file = $cptLine<br/>parameters found = $cptVar";
    if ($echoResult) echo "<br/>parameters moved to database = $cptVarDb<br/>parameters kept in parameter file = $cptVarFile";
    traceLog("---> lines read from file = $cptLine");
    traceLog("---> parameters found = $cptVar");
    traceLog("---> parameters moved to database = $cptVarDb");
    traceLog("---> parameters kept in parameter file = $cptVarFile");
    fwrite($fileHandler,'//======= END');
    fclose($fileHandler);
    traceLog("REWRITE PARAMTERS.PHP FILE = END ======================");
  }
  
  static public function isGlobalParameterInDB($code) {
    global $hosted;
    if (isset($hosted) and $hosted==true) {
      $hostedParams=array('documentRoot','paramAttachmentDirectory','cronImportDirectory','logFile','logLevel');
      if (in_array($code, $hostedParams)) return false;
    }
    $p=new Parameter();
    $crit=" idUser is null and idProject is null and parameterCode='" . $code . "'";
    $lst=$p->getSqlElementsFromCriteria(null, false, $crit);
    if (count($lst)==1) {
      return true;
    } else {
      return false;
    }
  }
  
  static public function clearGlobalParameters() {
    // This function is call on most of admin functionalities or global parameters update, to force refresh of parameters
    unsetSessionValue('globalParametersArray');
    $aut=new Audit();
    $table=$aut->getDatabaseTableName();
    $sessionId=session_id();
    $query="update $table set requestRefreshParam=1 where idle=0 and sessionid!='$sessionId'";
    Sql::query($query);
  }
  
  static public function refreshParameters() {
    scriptLog('refreshParameters()');
    // This function is call when refresh of parameters is requested
    unsetSessionValue('globalParametersArray');
  }
  static public function getLangList() {
    $dir='../tool/i18n/nls';
    $handle = opendir($dir);
    $result=array();
    while ( ($file = readdir($handle)) !== false) {
      
      if ($file == '.' || $file == '..' || $file=='index.php' // exclude ., .. and index.php
      || ! is_dir($dir.'/'.$file) || pq_substr($file,0,1)=='.' ) {        // non directories or directories starting with . (.svn)
        continue;
      }
      $nls=$file;
      $lang=pq_str_replace('-',' ', $file);
      $lang=ucwords($lang);
      $lang=pq_str_replace(' ','', $lang);
      $result[$nls]=i18n('lang'.$lang);
    }
    closedir($handle);
    asort($result);
    return $result;
  } 
  
  // gautier ticket #2290 list of timezone
static public function getTimezoneList() {
  $zones_array = array('Africa/Abidjan'=>'Africa/Abidjan',
'Africa/Accra'=>'Africa/Accra',
'Africa/Addis_Ababa'=>'Africa/Addis_Ababa',
'Africa/Algiers'=>'Africa/Algiers',
'Africa/Asmara'=>'Africa/Asmara',
'Africa/Asmera'=>'Africa/Asmera',
'Africa/Bamako'=>'Africa/Bamako',
'Africa/Bangui'=>'Africa/Bangui',
'Africa/Banjul'=>'Africa/Banjul',
'Africa/Bissau'=>'Africa/Bissau',
'Africa/Blantyre'=>'Africa/Blantyre',
'Africa/Brazzaville'=>'Africa/Brazzaville',
'Africa/Bujumbura'=>'Africa/Bujumbura',
'Africa/Cairo'=>'Africa/Cairo',
'Africa/Casablanca'=>'Africa/Casablanca',
'Africa/Ceuta'=>'Africa/Ceuta',
'Africa/Conakry'=>'Africa/Conakry',
'Africa/Dakar'=>'Africa/Dakar',
'Africa/Dar_es_Salaam'=>'Africa/Dar_es_Salaam',
'Africa/Djibouti'=>'Africa/Djibouti',
'Africa/Douala'=>'Africa/Douala',
'Africa/El_Aaiun'=>'Africa/El_Aaiun',
'Africa/Freetown'=>'Africa/Freetown',
'Africa/Gaborone'=>'Africa/Gaborone',
'Africa/Harare'=>'Africa/Harare',
'Africa/Johannesburg'=>'Africa/Johannesburg',
'Africa/Juba'=>'Africa/Juba',
'Africa/Kampala'=>'Africa/Kampala',
'Africa/Khartoum'=>'Africa/Khartoum',
'Africa/Kigali'=>'Africa/Kigali',
'Africa/Kinshasa'=>'Africa/Kinshasa',
'Africa/Lagos'=>'Africa/Lagos',
'Africa/Libreville'=>'Africa/Libreville',
'Africa/Lome'=>'Africa/Lome',
'Africa/Luanda'=>'Africa/Luanda',
'Africa/Lubumbashi'=>'Africa/Lubumbashi',
'Africa/Lusaka'=>'Africa/Lusaka',
'Africa/Malabo'=>'Africa/Malabo',
'Africa/Maputo'=>'Africa/Maputo',
'Africa/Maseru'=>'Africa/Maseru',
'Africa/Mbabane'=>'Africa/Mbabane',
'Africa/Mogadishu'=>'Africa/Mogadishu',
'Africa/Monrovia'=>'Africa/Monrovia',
'Africa/Nairobi'=>'Africa/Nairobi',
'Africa/Ndjamena'=>'Africa/Ndjamena',
'Africa/Niamey'=>'Africa/Niamey',
'Africa/Nouakchott'=>'Africa/Nouakchott',
'Africa/Ouagadougou'=>'Africa/Ouagadougou',
'Africa/Porto-Novo'=>'Africa/Porto-Novo',
'Africa/Sao_Tome'=>'Africa/Sao_Tome',
'Africa/Timbuktu'=>'Africa/Timbuktu',
'Africa/Tripoli'=>'Africa/Tripoli',
'Africa/Tunis'=>'Africa/Tunis',
'Africa/Windhoek'=>'Africa/Windhoek',
      'America/Adak'=>'America/Adak',
      'America/Anchorage'=>'America/Anchorage',
      'America/Anguilla'=>'America/Anguilla',
      'America/Antigua'=>'America/Antigua',
      'America/Araguaina'=>'America/Araguaina',
      'America/Argentina/Buenos_Aires'=>'America/Argentina/Buenos_Aires',
      'America/Argentina/Catamarca'=>'America/Argentina/Catamarca',
      'America/Argentina/ComodRivadavia'=>'America/Argentina/ComodRivadavia',
      'America/Argentina/Cordoba'=>'America/Argentina/Cordoba',
      'America/Argentina/Jujuy'=>'America/Argentina/Jujuy',
      'America/Argentina/La_Rioja'=>'America/Argentina/La_Rioja',
      'America/Argentina/Mendoza'=>'America/Argentina/Mendoza',
      'America/Argentina/Rio_Gallegos'=>'America/Argentina/Rio_Gallegos',
      'America/Argentina/Salta'=>'America/Argentina/Salta',
      'America/Argentina/San_Juan'=>'America/Argentina/San_Juan',
      'America/Argentina/San_Luis'=>'America/Argentina/San_Luis',
      'America/Argentina/Tucuman'=>'America/Argentina/Tucuman',
      'America/Argentina/Ushuaia'=>'America/Argentina/Ushuaia',
      'America/Aruba'=>'America/Aruba',
      'America/Asuncion'=>'America/Asuncion',
      'America/Atikokan'=>'America/Atikokan',
      'America/Atka'=>'America/Atka',
      'America/Bahia'=>'America/Bahia',
      'America/Bahia_Banderas'=>'America/Bahia_Banderas',
      'America/Barbados'=>'America/Barbados',
      'America/Belem'=>'America/Belem',
      'America/Belize'=>'America/Belize',
      'America/Blanc-Sablon'=>'America/Blanc-Sablon',
      'America/Boa_Vista'=>'America/Boa_Vista',
      'America/Bogota'=>'America/Bogota',
      'America/Boise'=>'America/Boise',
      'America/Buenos_Aires'=>'America/Buenos_Aires',
      'America/Cambridge_Bay'=>'America/Cambridge_Bay',
      'America/Campo_Grande'=>'America/Campo_Grande',
      'America/Cancun'=>'America/Cancun',
      'America/Caracas'=>'America/Caracas',
      'America/Catamarca'=>'America/Catamarca',
      'America/Cayenne'=>'America/Cayenne',
      'America/Cayman'=>'America/Cayman',
      'America/Chicago'=>'America/Chicago',
      'America/Chihuahua'=>'America/Chihuahua',
      'America/Coral_Harbour'=>'America/Coral_Harbour',
      'America/Cordoba'=>'America/Cordoba',
      'America/Costa_Rica'=>'America/Costa_Rica',
      'America/Creston'=>'America/Creston',
      'America/Cuiaba'=>'America/Cuiaba',
      'America/Curacao'=>'America/Curacao',
      'America/Danmarkshavn'=>'America/Danmarkshavn',
      'America/Dawson'=>'America/Dawson',
      'America/Dawson_Creek'=>'America/Dawson_Creek',
      'America/Denver'=>'America/Denver',
      'America/Detroit'=>'America/Detroit',
      'America/Dominica'=>'America/Dominica',
      'America/Edmonton'=>'America/Edmonton',
      'America/Eirunepe'=>'America/Eirunepe',
      'America/El_Salvador'=>'America/El_Salvador',
      'America/Ensenada'=>'America/Ensenada',
      'America/Fort_Wayne'=>'America/Fort_Wayne',
      'America/Fortaleza'=>'America/Fortaleza',
      'America/Glace_Bay'=>'America/Glace_Bay',
      'America/Godthab'=>'America/GodthabAmerica/Goose_Bay',
      'America/Grand_Turk'=>'America/Grand_Turk',
      'America/Grenada'=>'America/Grenada',
      'America/Guadeloupe'=>'America/Guadeloupe',
      'America/Guatemala'=>'America/Guatemala',
      'America/Guayaquil'=>'America/Guayaquil',
      'America/Guyana'=>'America/Guyana',
      'America/Halifax'=>'America/Halifax',
      'America/Havana'=>'America/Havana',
      'America/Hermosillo'=>'America/Hermosillo',
      'America/Indiana/Indianapolis'=>'America/Indiana/Indianapolis',
      'America/Indiana/Knox'=>'America/Indiana/Knox',
      'America/Indiana/Marengo'=>'America/Indiana/Marengo',
      'America/Indiana/Petersburg'=>'America/Indiana/Petersburg',
      'America/Indiana/Tell_City'=>'America/Indiana/Tell_City',
      'America/Indiana/Vevay'=>'America/Indiana/Vevay',
      'America/Indiana/Vincennes'=>'America/Indiana/Vincennes',
      'America/Indiana/Winamac'=>'America/Indiana/Winamac',
      'America/Indianapolis'=>'America/Indianapolis',
      'America/Inuvik'=>'America/Inuvik',
      'America/Iqaluit'=>'America/Iqaluit',
      'America/Jamaica'=>'America/Jamaica',
      'America/Jujuy'=>'America/Jujuy',
      'America/Juneau'=>'America/Juneau',
      'America/Kentucky/Louisville'=>'America/Kentucky/Louisville',
      'America/Kentucky/Monticello'=>'America/Kentucky/Monticello',
      'America/Knox_IN'=>'America/Knox_IN',
      'America/Kralendijk'=>'America/Kralendijk',
      'America/La_Paz'=>'America/La_Paz',
      'America/Lima'=>'America/Lima',
      'America/Los_Angeles'=>'America/Los_Angeles',
      'America/Louisville'=>'America/Louisville',
      'America/Lower_Princes'=>'America/Lower_Princes',
      'America/Maceio'=>'America/Maceio',
      'America/Managua'=>'America/Managua',
      'America/Manaus'=>'America/Manaus',
      'America/Marigot'=>'America/Marigot',
      'America/Martinique'=>'America/Martinique',
      'America/Matamoros'=>'America/Matamoros',
      'America/Mazatlan'=>'America/Mazatlan',
      'America/Mendoza'=>'America/Mendoza',
      'America/Menominee'=>'America/Menominee',
      'America/Merida'=>'America/Merida',
      'America/Metlakatla'=>'America/Metlakatla',
      'America/Mexico_City'=>'America/Mexico_City',
      'America/Miquelon'=>'America/Miquelon',
      'America/Moncton'=>'America/Moncton',
      'America/Monterrey'=>'America/Monterrey',
      'America/Montevideo'=>'America/Montevideo',
      'America/Montreal'=>'America/Montreal',
      'America/Montserrat'=>'America/Montserrat',
      'America/Nassau'=>'America/Nassau',
      'America/New_York'=>'America/New_York',
      'America/Nipigon'=>'America/Nipigon',
      'America/Nome'=>'America/Nome',
      'America/Noronha'=>'America/Noronha',
      'America/North_Dakota/Beulah'=>'America/North_Dakota/Beulah',
      'America/North_Dakota/Center'=>'America/North_Dakota/Center',
      'America/North_Dakota/New_Salem'=>'America/North_Dakota/New_Salem',
      'America/Ojinaga'=>'America/Ojinaga',
      'America/Panama'=>'America/Panama',
      'America/Pangnirtung'=>'America/Pangnirtung',
      'America/Paramaribo'=>'America/Paramaribo',
      'America/Phoenix'=>'America/Phoenix',
      'America/Port-au-Prince'=>'America/Port-au-Prince',
      'America/Port_of_Spain'=>'America/Port_of_Spain',
      'America/Porto_Acre'=>'America/Porto_Acre',
      'America/Porto_Velho'=>'America/Porto_Velho',
      'America/Puerto_Rico'=>'America/Puerto_Rico',
      'America/Rainy_River'=>'America/Rainy_River',
      'America/Rankin_Inlet'=>'America/Rankin_Inlet',
      'America/Recife'=>'America/Recife',
      'America/Regina'=>'America/Regina',
      'America/Resolute'=>'America/Resolute',
      'America/Rio_Branco'=>'America/Rio_Branco',
      'America/Rosario'=>'America/Rosario',
      'America/Santa_Isabel'=>'America/Santa_Isabel',
      'America/Santarem'=>'America/Santarem',
      'America/Santiago'=>'America/Santiago',
      'America/Santo_Domingo'=>'America/Santo_Domingo',
      'America/Sao_Paulo'=>'America/Sao_Paulo',
      'America/Scoresbysund'=>'America/Scoresbysund',
      'America/Shiprock'=>'America/Shiprock',
      'America/Sitka'=>'America/Sitka',
      'America/St_Barthelemy'=>'America/St_Barthelemy',
      'America/St_Johns'=>'America/St_Johns',
      'America/St_Kitts'=>'America/St_Kitts',
      'America/St_Lucia'=>'America/St_Lucia',
      'America/St_Thomas'=>'America/St_Thomas',
      'America/St_Vincent'=>'America/St_Vincent',
      'America/Swift_Current'=>'America/Swift_Current',
      'America/Tegucigalpa'=>'America/Tegucigalpa',
      'America/Thule'=>'America/Thule',
      'America/Thunder_Bay'=>'America/Thunder_Bay',
      'America/Tijuana'=>'America/Tijuana',
      'America/Toronto'=>'America/Toronto',
      'America/Tortola'=>'America/Tortola',
      'America/Vancouver'=>'America/Vancouver',
      'America/Virgin'=>'America/Virgin',
      'America/Whitehorse'=>'America/Whitehorse',
      'America/Winnipeg'=>'America/Winnipeg',
      'America/Yakutat'=>'America/Yakutat',
      'America/Yellowknife'=>'America/Yellowknife',
      'Antarctica/Casey'=>'Antarctica/Casey',
      'Antarctica/Davis'=>'Antarctica/Davis',
      'Antarctica/DumontDUrville'=>'Antarctica/DumontDUrville',
      'Antarctica/Macquarie'=>'Antarctica/Macquarie',
      'Antarctica/Mawson'=>'Antarctica/Mawson',
      'Antarctica/McMurdo'=>'Antarctica/McMurdo',
      'Antarctica/Palmer'=>'Antarctica/Palmer',
      'Antarctica/Rothera'=>'Antarctica/Rothera',
      'Antarctica/South_Pole'=>'Antarctica/South_Pole',
      'Antarctica/Syowa'=>'Antarctica/Syowa',
      'Antarctica/Troll'=>'Antarctica/Troll',
      'Antarctica/Vostok'=>'Antarctica/Vostok',
      'Arctic/Longyearbyen'=>'Arctic/Longyearbyen',
      'Asia/Aden'=>'Asia/Aden',
      'Asia/Almaty'=>'Asia/Almaty',
      'Asia/Amman'=>'Asia/Amman',
      'Asia/Anadyr'=>'Asia/Anadyr',
      'Asia/Aqtau'=>'Asia/Aqtau',
      'Asia/Aqtobe'=>'Asia/Aqtobe',
      'Asia/Ashgabat'=>'Asia/Ashgabat',
      'Asia/Ashkhabad'=>'Asia/Ashkhabad',
      'Asia/Baghdad'=>'Asia/Baghdad',
      'Asia/Bahrain'=>'Asia/Bahrain',
      'Asia/Baku'=>'Asia/Baku',
      'Asia/Bangkok'=>'Asia/Bangkok',
      'Asia/Beirut'=>'Asia/Beirut',
      'Asia/Bishkek'=>'Asia/Bishkek',
      'Asia/Brunei'=>'Asia/Brunei',
      'Asia/Calcutta'=>'Asia/Calcutta',
      'Asia/Chita'=>'Asia/Chita',
      'Asia/Choibalsan'=>'Asia/Choibalsan',
      'Asia/Chongqing'=>'Asia/Chongqing',
      'Asia/Chungking'=>'Asia/Chungking',
      'Asia/Colombo'=>'Asia/Colombo',
      'Asia/Dacca'=>'Asia/Dacca',
      'Asia/Damascus'=>'Asia/Damascus',
      'Asia/Dhaka'=>'Asia/Dhaka',
      'Asia/Dili'=>'Asia/Dili',
      'Asia/Dubai'=>'Asia/Dubai',
      'Asia/Dushanbe'=>'Asia/Dushanbe',
      'Asia/Gaza'=>'Asia/Gaza',
      'Asia/Harbin'=>'Asia/Harbin',
      'Asia/Hebron'=>'Asia/Hebron',
      'Asia/Ho_Chi_Minh'=>'Asia/Ho_Chi_Minh',
      'Asia/Hong_Kong'=>'Asia/Hong_Kong',
      'Asia/Hovd'=>'Asia/Hovd',
      'Asia/Irkutsk'=>'Asia/Irkutsk',
      'Asia/Istanbul'=>'Asia/Istanbul',
      'Asia/Jakarta'=>'Asia/Jakarta',
      'Asia/Jayapura'=>'Asia/Jayapura',
      'Asia/Jerusalem'=>'Asia/Jerusalem',
      'Asia/Kabul'=>'Asia/Kabul',
      'Asia/Kamchatka'=>'Asia/Kamchatka',
      'Asia/Karachi'=>'Asia/Karachi',
      'Asia/Kashgar'=>'Asia/Kashgar',
      'Asia/Kathmandu'=>'Asia/Kathmandu',
      'Asia/Katmandu'=>'Asia/Katmandu',
      'Asia/Khandyga'=>'Asia/Khandyga',
      'Asia/Kolkata'=>'Asia/Kolkata',
      'Asia/Krasnoyarsk'=>'Asia/Krasnoyarsk',
      'Asia/Kuala_Lumpur'=>'Asia/Kuala_Lumpur',
      'Asia/Kuching'=>'Asia/Kuching',
      'Asia/Kuwait'=>'Asia/Kuwait',
      'Asia/Macao'=>'Asia/Macao',
      'Asia/Macau'=>'Asia/Macau',
      'Asia/Magadan'=>'Asia/Magadan',
      'Asia/Makassar'=>'Asia/Makassar',
      'Asia/Manila'=>'Asia/Manila',
      'Asia/Muscat'=>'Asia/Muscat',
      'Asia/Nicosia'=>'Asia/Nicosia',
      'Asia/Novokuznetsk'=>'Asia/Novokuznetsk',
      'Asia/Novosibirsk'=>'Asia/Novosibirsk',
      'Asia/Omsk'=>'Asia/Omsk',
      'Asia/Oral'=>'Asia/Oral',
      'Asia/Phnom_Penh'=>'Asia/Phnom_Penh',
      'Asia/Pontianak'=>'Asia/Pontianak',
      'Asia/Pyongyang'=>'Asia/Pyongyang',
      'Asia/Qatar'=>'Asia/Qatar',
      'Asia/Qyzylorda'=>'Asia/Qyzylorda',
      'Asia/Rangoon'=>'Asia/Rangoon',
      'Asia/Riyadh'=>'Asia/Riyadh',
      'Asia/Saigon'=>'Asia/Saigon',
      'Asia/Sakhalin'=>'Asia/Sakhalin',
      'Asia/Samarkand'=>'Asia/Samarkand',
      'Asia/Seoul'=>'Asia/Seoul',
      'Asia/Shanghai'=>'Asia/Shanghai',
      'Asia/Singapore'=>'Asia/Singapore',
      'Asia/Srednekolymsk'=>'Asia/Srednekolymsk',
      'Asia/Taipei'=>'Asia/Taipei',
      'Asia/Tashkent'=>'Asia/Tashkent',
      'Asia/Tbilisi'=>'Asia/Tbilisi',
      'Asia/Tehran'=>'Asia/Tehran',
      'Asia/Tel_Aviv'=>'Asia/Tel_Aviv',
      'Asia/Thimbu'=>'Asia/Thimbu',
      'Asia/Thimphu'=>'Asia/Thimphu',
      'Asia/Tokyo'=>'Asia/Tokyo',
      'Asia/Ujung_Pandang'=>'Asia/Ujung_Pandang',
      'Asia/Ulaanbaatar'=>'Asia/Ulaanbaatar',
      'Asia/Ulan_Bator'=>'Asia/Ulan_Bator',
      'Asia/Urumqi'=>'Asia/Urumqi',
      'Asia/Ust-Nera'=>'Asia/Ust-Nera',
      'Asia/Vientiane'=>'Asia/Vientiane',
      'Asia/Vladivostok'=>'Asia/Vladivostok',
      'Asia/Yakutsk'=>'Asia/Yakutsk',
      'Asia/Yekaterinburg'=>'Asia/Yekaterinburg',
      'Asia/Yerevan'=>'Asia/Yerevan',
      'Atlantic/Azores'=>'Atlantic/Azores',
      'Atlantic/Bermuda'=>'Atlantic/Bermuda',
      'Atlantic/Canary'=>'Atlantic/Canary',
      'Atlantic/Cape_Verde'=>'Atlantic/Cape_Verde',
      'Atlantic/Faeroe'=>'Atlantic/Faeroe',
      'Atlantic/Faroe'=>'Atlantic/Faroe',
      'Atlantic/Jan_Mayen'=>'Atlantic/Jan_Mayen',
      'Atlantic/Madeira'=>'Atlantic/Madeira',
      'Atlantic/Reykjavik'=>'Atlantic/Reykjavik',
      'Atlantic/South_Georgia'=>'Atlantic/South_Georgia',
      'Atlantic/St_Helena'=>'Atlantic/St_Helena',
      'Atlantic/Stanley'=>'Atlantic/Stanley',
      'Australia/ACT'=>'Australia/ACT',
      'Australia/Adelaide'=>'Australia/Adelaide',
      'Australia/Brisbane'=>'Australia/Brisbane',
      'Australia/Broken_Hill'=>'Australia/Broken_Hill',
      'Australia/Canberra'=>'Australia/Canberra',
      'Australia/Currie'=>'Australia/Currie',
      'Australia/Darwin'=>'Australia/Darwin',
      'Australia/Eucla'=>'Australia/Eucla',
      'Australia/Hobart'=>'Australia/Hobart',
      'Australia/LHI'=>'Australia/LHI',
      'Australia/Lindeman'=>'Australia/Lindeman',
      'Australia/Lord_Howe'=>'Australia/Lord_Howe',
      'Australia/Melbourne'=>'Australia/Melbourne',
      'Australia/North'=>'Australia/North',
      'Australia/NSW'=>'Australia/NSW',
      'Australia/Perth'=>'Australia/Perth',
      'Australia/Queensland'=>'Australia/Queensland',
      'Australia/South'=>'Australia/South',
      'Australia/Sydney'=>'Australia/Sydney',
      'Australia/Tasmania'=>'Australia/Tasmania',
      'Australia/Victoria'=>'Australia/Victoria',
      'Australia/West'=>'Australia/West',
      'Australia/Yancowinna'=>'Australia/Yancowinna',
  'Europe/Amsterdam'=>'Europe/Amsterdam', 
  'Europe/Andorra'=>'Europe/Andorra',
  'Europe/Athens'=>'Europe/Athens',
  'Europe/Belfast'=>'Europe/Belfast',
  'Europe/Belgrade'=>'Europe/Belgrade',
  'Europe/Berlin'=>'Europe/Berlin',
  'Europe/Bratislava'=>'Europe/Bratislava',
  'Europe/Brussels'=>'Europe/Brussels',
  'Europe/Bucharest'=>'Europe/Bucharest',
  'Europe/Budapest'  =>'Europe/Budapest',
  'Europe/Busingen'  =>'Europe/Busingen',
  'Europe/Chisinau'  =>'Europe/Chisinau',
  'Europe/Copenhagen'  =>'Europe/Copenhagen',
  'Europe/Dublin'   =>'Europe/Dublin',
  'Europe/Gibraltar'=>'Europe/Gibraltar',
  'Europe/Guernsey'  =>  'Europe/Guernsey',
  'Europe/Helsinki'  =>  'Europe/Helsinki',
  'Europe/Isle_of_Man'=> 'Europe/Isle_of_Man',
  'Europe/Istanbul'  =>  'Europe/Istanbul',
  'Europe/Jersey'  =>  'Europe/Jersey',
  'Europe/Kaliningrad'=>  'Europe/Kaliningrad',
  'Europe/Kiev'    =>  'Europe/Kiev',
  'Europe/Lisbon'  =>  'Europe/Lisbon',
  'Europe/Ljubljana'=>  'Europe/Ljubljana',
  'Europe/London'  =>  'Europe/London',
  'Europe/Luxembourg'=>  'Europe/Luxembourg',
  'Europe/Madrid'  =>  'Europe/Madrid',
  'Europe/Malta'  =>  'Europe/Malta',
  'Europe/Mariehamn'=>  'Europe/Mariehamn',
  'Europe/Minsk'  =>  'Europe/Minsk',
  'Europe/Monaco'  =>  'Europe/Monaco',
  'Europe/Moscow'  =>  'Europe/Moscow',
  'Europe/Nicosia'  =>  'Europe/Nicosia',
  'Europe/Oslo'    =>  'Europe/Oslo',
  'Europe/Paris'  =>  'Europe/Paris',
  'Europe/Podgorica'=>  'Europe/Podgorica',
  'Europe/Prague'  =>  'Europe/Prague',
  'Europe/Riga'    =>  'Europe/Riga',
  'Europe/Rome'    =>  'Europe/Rome',
  'Europe/Samara'  =>  'Europe/Samara',
  'Europe/San_Marino'  =>'Europe/San_Marino',
  'Europe/Sarajevo'  =>  'Europe/Sarajevo',
  'Europe/Simferopol'=>  'Europe/Simferopol',
  'Europe/Skopje'  =>  'Europe/Skopje',
  'Europe/Sofia'=>    'Europe/Sofia',
  'Europe/Stockholm'=>  'Europe/Stockholm',
  'Europe/Tallinn'  =>  'Europe/Tallinn',
  'Europe/Tirane'  =>  'Europe/Tirane',
  'Europe/Tiraspol'    =>'Europe/Tiraspol',
  'Europe/Uzhgorod'  =>  'Europe/Uzhgorod',
  'Europe/Vaduz'  =>  'Europe/Vaduz',
  'Europe/Vatican'=>    'Europe/Vatican',
  'Europe/Vienna'=>    'Europe/Vienna',
  'Europe/Vilnius'  =>  'Europe/Vilnius',
  'Europe/Volgograd'  =>'Europe/Volgograd',
  'Europe/Warsaw'  =>  'Europe/Warsaw',
  'Europe/Zagreb'  =>  'Europe/Zagreb',
  'Europe/Zaporozhye'=>'Europe/Zaporozhye',
  'Europe/Zurich'  =>  'Europe/Zurich',
  'Indian/Antananarivo'=>'Indian/Antananarivo',
'Indian/Chagos'=>'Indian/Chagos',
'Indian/Christmas'=>'Indian/Christmas',
'Indian/Cocos'=>'Indian/Cocos',
'Indian/Comoro'=>'Indian/Comoro',
'Indian/Kerguelen'=>'Indian/Kerguelen',
'Indian/Mahe'=>'Indian/Mahe',
'Indian/Maldives'=>'Indian/Maldives',
'Indian/Mauritius'=>'Indian/Mauritius',
'Indian/Mayotte'=>'Indian/Mayotte',
'Indian/Reunion'=>'Indian/Reunion',
'Pacific/Apia'=>'Pacific/Apia',
'Pacific/Auckland'=>'Pacific/Auckland',
'Pacific/Bougainville'=>'Pacific/Bougainville',
'Pacific/Chatham'=>'Pacific/Chatham',
'Pacific/Chuuk'=>'Pacific/Chuuk',
'Pacific/Easter'=>'Pacific/Easter',
'Pacific/Efate'=>'Pacific/Efate',
'Pacific/Enderbury'=>'Pacific/Enderbury',
'Pacific/Fakaofo'=>'Pacific/Fakaofo',
'Pacific/Fiji'=>'Pacific/Fiji',
'Pacific/Funafuti'=>'Pacific/Funafuti',
'Pacific/Galapagos'=>'Pacific/Galapagos',
'Pacific/Gambier'=>'Pacific/Gambier',
'Pacific/Guadalcanal'=>'Pacific/Guadalcanal',
'Pacific/Guam'=>'Pacific/Guam',
'Pacific/Honolulu'=>'Pacific/Honolulu',
'Pacific/Johnston'=>'Pacific/Johnston',
'Pacific/Kiritimati'=>'Pacific/Kiritimati',
'Pacific/Kosrae'=>'Pacific/Kosrae',
'Pacific/Kwajalein'=>'Pacific/Kwajalein',
'Pacific/Majuro'=>'Pacific/Majuro',
'Pacific/Marquesas'=>'Pacific/Marquesas',
'Pacific/Midway'=>'Pacific/Midway',
'Pacific/Nauru'=>'Pacific/Nauru',
'Pacific/Niue'=>'Pacific/Niue',
'Pacific/Norfolk'=>'Pacific/Norfolk',
'Pacific/Noumea'=>'Pacific/Noumea',
'Pacific/Pago_Pago'=>'Pacific/Pago_Pago',
'Pacific/Palau'=>'Pacific/Palau',
'Pacific/Pitcairn'=>'Pacific/Pitcairn',
'Pacific/Pohnpei'=>'Pacific/Pohnpei',
'Pacific/Ponape'=>'Pacific/Ponape',
'Pacific/Port_Moresby'=>'Pacific/Port_Moresby',
'Pacific/Rarotonga'=>'Pacific/Rarotonga',
'Pacific/Saipan'=>'Pacific/Saipan',
'Pacific/Samoa'=>'Pacific/Samoa',
'Pacific/Tahiti'=>'Pacific/Tahiti',
'Pacific/Tarawa'=>'Pacific/Tarawa',
'Pacific/Tongatapu'=>'Pacific/Tongatapu',
'Pacific/Truk'=>'Pacific/Truk',
'Pacific/Wake'=>'Pacific/Wake',
'Pacific/Wallis'=>'Pacific/Wallis',
'Pacific/Yap'=>'Pacific/Yap');
  return $zones_array;
 }
 public static function setDisplaySM() {
   if(Parameter::getGlobalParameter('subscriptionCodeStatus') != 'OK'){
     echo "setDisplaySM();";
   }
 }
 public function control(){
   $result="";
   if ($this->parameterCode=="SslKey" and pq_trim($this->parameterValue)!="" and !file_exists($this->parameterValue)) {
       $result.='<br/>' . i18n('msgNotaFile',array(i18n("paramSslKey"),$this->parameterValue));
   }
   if ($this->parameterCode=="SslCert" and pq_trim($this->parameterValue)!="" and !file_exists($this->parameterValue)) {
       $result.='<br/>' . i18n('msgNotaFile',array(i18n("paramSslCert"),$this->parameterValue));
   }
   if ($this->parameterCode=="SslCa" and pq_trim($this->parameterValue)!="" and !file_exists($this->parameterValue)) {
       $result.='<br/>' . i18n('msgNotaFile',array(i18n("paramSslCa"),$this->parameterValue));
   }
   if($this->parameterCode=="ComplexitiesNumber" and $this->parameterValue > 10){
     $result.='<br/>' . i18n('numberComplexityCanNotBeSuperiorOf10');
   }
   if(($this->parameterCode=="paramAttachmentMaxSize" and $this->parameterValue != "" ) or ($this->parameterCode=="paramAttachmentMaxSizeMail" and $this->parameterValue != "" )){
     $newVal=$this->parameterValue;
     $newValTab=str_split($newVal);
     $lettre="";
     $chiffre=null;
     $valLettre=1;
      for($i=0;$i<count($newValTab);$i++){
        if(is_numeric($newValTab[$i])==true){
          $chiffre=$chiffre.$newValTab[$i];
        }else{
          $lettre=$lettre.$newValTab[$i];
        }
      }
      if(pq_strlen($lettre)==1){
          switch (pq_strtoupper($lettre)) {
            case "K":
               $valLettre=1024;
             break;
             case "M":
               $valLettre=1024*1024;
             break;
            case "G":
              $valLettre=1024*1024*1024;
             break;
            case "T":
               $valLettre=1024*1024*1024*1024;
             break;
          }
      }
      $sumVal=$chiffre*$valLettre;
      $this->parameterValue=$sumVal;
   }
   if($this->parameterCode=="paramAttachmentNum" or $this->parameterCode=="paramAttachmentNumMail" ){
     $lettreN=pq_strtoupper($this->parameterValue);
     if(pq_strlen($this->parameterValue)==1 and ($lettreN=="K" or $lettreN=="M" or $lettreN=="G" or $lettreN=="T")){
         $this->parameterValue=$lettreN;
     }else{
      $this->parameterValue="";
     }
   }
   $defaultControl=parent::control();
   if ($defaultControl!='OK') {
     $result.=$defaultControl;
   }
   if ($result=="") {
     $result='OK';
   }
   return $result;
 }
 
 public static function getPlanningPageLineCount() {
   $param=Parameter::getGlobalParameter('planningPageLineCount');
   if ($param and intval($param>0)) return $param;
   else return 5000;
 }

 public static function hostedSmtpDefault() {
   global $hosted;
   if (! isset($hosted) or ! $hosted) return false;
   $smtpUser=Parameter::getGlobalParameter('paramMailSmtpUsername');
   $smtpPswd=Parameter::getGlobalParameter('paramMailSmtpPassword');
   $smtpHost=Parameter::getGlobalParameter('paramMailSmtpServer');
   //if ($smtpUser=='noreply@projeqtor.org' and $smtpHost=='smtp.projeqtor.org') return true;
   if ($smtpUser=='noreply@projeqtor.org') return true;
   return false;
 }
 
}
