<?php 
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

/* ============================================================================
 * Client is the owner of a project.
 */  
require_once('_securityCheck.php'); 
class InputMailboxTicket extends SqlElement {

  public $_sec_Description;
  public $id;
  public $name;
  public $idProject;
  public $serverImap;
  //public $_label_connectionMode;
  public $_spe_connectionMode;
  public $connectionMode;
  public $imapUserAccount;
  public $pwdImap;
  public $idOAuthClient;
  public $_spe_oauth2;
  public $securityConstraint;
  public $actionOK;
  public $actionKO; 
  public $_tab_4_1_4 = array('','','','','allowAttach');
  public $allowAttach;
  public $_label_sizeAttachment1;
  public $sizeAttachment;
  public $_label_sizeAttachment2;
  public $addToFollowUp;
  public $_lib_helpAddToFollowUp;
  public $addPseudoUsers;
  public $_lib_helpAddPseudoUsers;
  public $sortOrder=0;
  public $idle;
  public $_sec_treatment;
  public $idTicketType;
  public $idAffectable;
  public $idActivity;
  public $limitOfInputPerHour;
  public $lastInputDate;
  public $idTicket;
  public $totalInputTicket;
  public $failedRead;
  public $failedMessage;
  public $autoclosedReason;
  public $autoclosedDateTime;
  public $idStatus;
  public $reopenCondition;
  public $_sec_TicketHistory;
  public $limitOfHistory;
  public $_spe_ticketHistory;
  public $_nbColMax = 3;
  
  public $_noCopy;
  public $_dynamicHiddenFields=array('sizeAttachment','_label_sizeAttachment1','_label_sizeAttachment2','pwdImap','idOAuthClient');
  
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="8%"># ${id}</th>
    <th field="name" width="23%">${name}</th>
    <th field="nameProject" width="15%">${idProject}</th>
    <th field="serverImap" width="20%">${serverImap}</th>
    <th field="imapUserAccount" width="20%">${imapUserAccount}</th>
    <th field="limitOfInputPerHour" width="10%">${limitOfInputPerHour}</th>
    <th field="sortOrder" formatter="numericFormatter" width="5%">${sortOrderShort}</th> 
    <th field="idle" width="4%" formatter="booleanFormatter">${idle}</th>
    ';
  
  private static $_fieldsTooltip = array(
      "addToFollowUp"=> "tooltipAddToFollowUp",
      "addPseudoUsers"=> "tooltipAddPseudoUsers"
  );
  
  private static $_fieldsAttributes=array(
      'name'=>'required',
      'idProject'=>'required',
      'serverImap'=>'required',
      'imapUserAccount'=>'required',
      'pwdImap'=>'',
      'securityConstraint'=>'required',
      'idTicketType'=>'required',
      'lastInputDate'=>'readonly',
      'idTicket'=>'readonly',
      'totalInputTicket'=>'readonly',
      'failedRead'=>'hidden',
      'failedMessage'=>'hidden',
      'limitOfInputPerHour'=>'required',
      '_label_sizeAttachment2'=>'leftAlign',
      'addToFollowUp'=>'nobr',
      'addPseudoUsers'=>'nobr',
      'autoclosedReason'=>'hidden',
      'autoclosedDateTime'=>'hidden',
      '_label_sizeAttachment1'=>'longLabel',
      "connectionMode"=>"hidden"
  );
  
  private static $_colCaptionTransposition = array(
      'idAffectable' => 'responsible',
      'idActivity' => 'PlanningActivity',
      'idTicket' => 'lastInputTicket',
      'sizeAttachment'=>'sizeAttachment1',
      'idStatus'=>'noteOnTicketChangeStatus'
  );
  
  private static $_databaseColumnName = array();
  
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
    if (!$this->id) {
      $this->limitOfInputPerHour=10;
      $this->connectionMode='basic';
    }
  }

  
   /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }

  
  
  public function control(){
    if (property_exists($this, '_onlyResponse') and $this->_onlyResponse==true) return "OK"; 
    $result="";
    $defaultControl=parent::control();
    $old = $this->getOld();
    //unicity project/ticket type control
    $unicity = $this->countSqlElementsFromCriteria(array('idProject'=>$this->idProject,'idTicketType'=>$this->idTicketType));
    if($unicity > 0){
      if($this->id){
        if($old->idProject != $this->idProject)$result .= '<br/>' . i18n ( 'projectIsAlreadyUsed' );
      }else{
        $result .= '<br/>' . i18n ( 'projectIsAlreadyUsed' );
      }
    }
    //unicity global parameters
//     $emailHost=Parameter::getGlobalParameter('cronCheckEmailsHost'); // {imap.gmail.com:993/imap/ssl}INBOX';
//     $emailEmail=Parameter::getGlobalParameter('cronCheckEmailsUser');
//     if($emailHost and $emailEmail){
//       if($this->serverImap == $emailHost and $this->imapUserAccount == $emailEmail){
//         $result .= '<br/>' . i18n ( 'imapIsAlreadyUsed' );
//       }
//     }
    if ($defaultControl!='OK') {
      $result.=$defaultControl;
    }
    if ($result=="") {
      $result='OK';
    }
    return $result;
  }
  
  protected function getStaticFieldsTooltip() {
    return self::$_fieldsTooltip;
  }
  
  public function setAttributes() {
    self::$_fieldsAttributes['_spe_ticketHistory']='hidden';
    if($this->limitOfHistory > 0){
      self::$_fieldsAttributes['_spe_ticketHistory']='readonly';
    }
    if(!$this->id or $this->allowAttach == '0'){
      self::$_fieldsAttributes['sizeAttachment']='hidden';
      self::$_fieldsAttributes['_label_sizeAttachment1']='hidden,longLabel';
      self::$_fieldsAttributes['_label_sizeAttachment2']='hidden,leftAlign';
    }
    if(! $this->id or $this->connectionMode=='basic'){
      self::$_fieldsAttributes['idOAuthClient']='hidden';
      self::$_fieldsAttributes['pwdImap']='required';
    } else if ($this->connectionMode=='oauth') {
      self::$_fieldsAttributes['pwdImap']='hidden';
    }
  }
  
  /**=========================================================================
   * Overrides SqlElement::save() function to add specific treatments
  * @see persistence/SqlElement#save()
  * @return String the return message of persistence/SqlElement#save() method
  */
  public function save() {
    // This Class may be called for objet that is not stored : the definition is stored in the Global Parameter screen
    if (property_exists($this, '_onlyResponse') and $this->_onlyResponse==true) return; 
    
    $old = $this->getOld();
    if(!$this->id and !$this->limitOfHistory){
     $this->limitOfHistory = 10; 
    }
    if ($old->idle and !$this->idle) {
      $this->failedRead=0; // Reactivate closed mailbox
      $this->autoclosedReason=null;
      $this->autoclosedDateTime=null;
    }
    if($old->id){
      //if($this->pwdImap != decryptPwd($old->pwdImap) ){
      if($this->pwdImap!=$old->pwdImap and $this->pwdImap != decryptPwd($old->pwdImap) ){
        $this->pwdImap = encryptPwd($this->pwdImap);
      }else{
        $this->pwdImap = $old->pwdImap;
      }
    }
    if(!$this->id){
    	$this->pwdImap = encryptPwd($this->pwdImap);
    }
    $result = parent::save();
    if(!$old->id and $this->id == 1){
      $checkEmails=Parameter::getGlobalParameter('cronCheckEmails');
      if (!$checkEmails or intval($checkEmails)<=0) {
        Parameter::storeGlobalParameter('cronCheckEmails', 10);
      }
    }
    return $result;
  }
  
  public function delete() {
    if (property_exists($this, '_onlyResponse') and $this->_onlyResponse==true) return; 
    $result=parent::delete();
    return $result;
  }
  
  // ============================================================================**********
  // GET VALIDATION SCRIPT
  // ============================================================================**********
  
  /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo frameword)
   */
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript($colName);
    if ($colName=="allowAttach") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if(dojo.byId("allowAttach").checked){ ';
      $colScript .= '    dojo.query(".generalColClass.sizeAttachmentClass").style("display", "inline-block");';
      $colScript .= '    dojo.query("._label_sizeAttachment1Class").style("display", "inline-block");';
      $colScript .= '    dojo.query("._label_sizeAttachment2Class").style("display", "inline-block");';
      $colScript .= '  }else{';
      $colScript .= '    dojo.query(".generalColClass.sizeAttachmentClass").style("display", "none");';
      $colScript .= '    dojo.query("._label_sizeAttachment1Class").style("display", "none");';
      $colScript .= '    dojo.query("._label_sizeAttachment2Class").style("display", "none");';
      $colScript .= '  }';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    }
    if ($colName=="addToFollowUp") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';      
      $colScript .= '  if (dojo.byId("addToFollowUp").checked || dijit.byId("securityConstraint1").checked) {';
      $colScript .= '    dojo.query(".generalColClass.addPseudoUsersClass").style("display", "inline-block");';
      $colScript .= '    dojo.byId("_lib_helpAddPseudoUsers").style.display = "contents"';
      $colScript .= '  }else{';
      $colScript .= '    dojo.query(".generalColClass.addPseudoUsersClass").style("display", "none");';
      $colScript .= '    dojo.byId("_lib_helpAddPseudoUsers").style.display = "none";';
      $colScript .= '  }';
      $colScript .= '  terminateChange();';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    }
    
    
    return $colScript;
  }
  
// ============================================================================**********
// GET STATIC DATA FUNCTIONS
// ============================================================================**********
  
  /** ==========================================================================
   * Return the specific layout
   * @return String the layout
   */
  protected function getStaticLayout() {
    return self::$_layout;
  }
  
  /** ==========================================================================
   * Return the specific fieldsAttributes
   * @return Array the fieldsAttributes  
   */
  protected function getStaticFieldsAttributes() {
    return self::$_fieldsAttributes;
  }
  
  /** ============================================================================
   * Return the specific colCaptionTransposition
   * @return String the colCaptionTransposition
   */
  protected function getStaticColCaptionTransposition($fld=null) {
    return self::$_colCaptionTransposition;
  }
  
  /** ========================================================================
   * Return the specific databaseTableName
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseColumnName() {
    return self::$_databaseColumnName;
  }
  
  /** =========================================================================
   * Draw a specific item for the current class.
   * @param String $item the item. Correct values are : 
   *    - subprojects => presents sub-projects as a tree
   * @return String an html string able to display a specific item
   *  must be redefined in the inherited class
   */
  public function drawSpecificItem($item){
    global $print;
    $result = "";
    if($item=='ticketHistory'){
        $history = new InputMailboxHistory();
        $critArray=array('idInputMailbox'=>$this->id, 'refType'=>'ticket');
        $order = " date desc ";
        $historyList=$history->getSqlElementsFromCriteria($critArray, false,null,$order,false,false,$this->limitOfHistory);
        drawInputMailboxHistory($historyList,$this);
    }else if ($item=='connectionMode'){
      $result .= '<tr>';
      $result .= '<td>';
      $result .= '<label>'.i18n("connectionMode").'</label>';
      $result .= '</td>';
      $result .= '<td>';
      $result .= '<select id="connectionModeSelect"  dojoType="dijit.form.FilteringSelect" '.autoOpenFilteringSelect().' class="input" style="width:200px;" value="'.$this->connectionMode.'">';
      $result .= '  <option value="basic">'.i18n("basicAuth").'</option>';
      $result .= '  <option value="oauth">'.i18n("oAuth2").'</option>';
      $result .= '<script type="dojo/connect" event="onChange" >';
      $result .= ' var selectWidget = dijit.byId("connectionModeSelect");';
      $result .= ' var selectedValue = selectWidget.get("value");';
      $result .= '  dijit.byId("connectionMode").set("value",selectedValue);';
      $result .= '  if(selectedValue == "oauth"){ ';
      $result .= '    dojo.query(".pwdImapClass").forEach(function(node){node.style.display="none";});';
      $result .= '    dojo.query(".idOAuthClientClass").forEach(function(node){node.style.display="";});';
      //$result .= '    if (dijit.byId("idOAuthClient").get("value")==" ") dojo.query(".oauthUpdate").forEach(function(node){node.style.display="none";});';
      $result .= '  }else if(selectedValue == "basic"){ ';
      $result .= '    dojo.query(".pwdImapClass").forEach(function(node){node.style.display="";});';
      $result .= '    dojo.query(".idOAuthClientClass").forEach(function(node){node.style.display="none";});';
      $result .= '  }'; 
      $result .= '</script>';
      $result .= '</select>';
      $result .= '</td>';
      $result .= '</tr>';
    } else if ($item=='oauth2'){
      $result .= '<tr id="oauth2actions" class="idOAuthClientClass" style="display:'.(($this->isAttributeSetToField('idOAuthClient', 'hidden'))?'none':'').'">';
      $result .= '<td>';
      $result .= '<label>&nbsp;<label>';
      $result .= '</td>';
      $result .= '<td>';
      $result .= '<button class="dynamicTextButton" dojoType="dijit.form.Button" type="button" onclick="addNewOauthSource();">'.i18n("NEW").'</button>';
      $result .= '<button class="dynamicTextButton oauthUpdate" dojoType="dijit.form.Button" type="button" onclick="editOauthSource();">'.i18n("updating").'</button>';
      $result .= '<button class="dynamicTextButton" dojoType="dijit.form.Button" type="button" onclick="deleteOauthSource();">'.i18n("deleting").'</button>';
      $result .= '</td>';
      $result .= '</tr>';
    }
    
    return $result;
  }
  
  // ============================================================================**********
  // CRON FUNCTIONS
  // ============================================================================**********
  
  //use in Cron
  public static function checkEmailsTicket() {
    global $pathSeparator, $uploaddirMail, $uploaddirAttach, $imapFilterCriteria;
    //$afterMailTreatment = Parameter::getGlobalParameter('afterMailTreatment');
    $paramAttachDir=Parameter::getGlobalParameter('paramAttachmentDirectory');
    if (pq_substr($paramAttachDir,0,2)=='..') {
      $curdir=dirname(__FILE__);
      $paramAttachDir=pq_str_replace(array('/model','\model'),array('',''),$curdir).pq_substr($paramAttachDir,2);
    }
    $pathSeparator=Parameter::getGlobalParameter('paramPathSeparator');
    $paramAttachDir=pq_str_replace(array('/', '\\'),$pathSeparator,$paramAttachDir);
    if (pq_substr($paramAttachDir, -1)!=$pathSeparator and pq_substr($paramAttachDir, -1)!='/') $paramAttachDir.=$pathSeparator;
    $uploaddirMail = $paramAttachDir . "emails" . $pathSeparator;
    $uploaddirAttach = $paramAttachDir;
    if (pq_substr($uploaddirAttach, -1)!=$pathSeparator and pq_substr($uploaddirAttach, -1)!='/') $uploaddirAttach.=$pathSeparator;
    if (file_exists ( $uploaddirMail )) {
      purgeFiles ( $uploaddirMail, null );
    } else {
      mkdir($uploaddirMail,0777,true);
    }
    $imapFilterCriteria=Parameter::getGlobalParameter('imapFilterCriteria');
    if (! $imapFilterCriteria) { $imapFilterCriteria='UNSEEN UNDELETED'; }
    
    // Treat All Input Mailbox Tickets
    $where = "1=1";
    $inputMbT= new InputMailboxTicket();
    $lstIMb = $inputMbT->getSqlElementsFromCriteria(null,null,$where, 'sortOrder ASC');
    foreach ($lstIMb as $mb){ 
      $mb->treatInputMailbox(false);
    }
    
    // Treat Global Mailbox (for Response only)
//     $globalMb=new InputMailboxTicket();
//     $globalMb->name='GLOBAL';
//     $globalMb->idProject=null;
//     $globalMb->serverImap=Parameter::getGlobalParameter('cronCheckEmailsHost');
//     $globalMb->imapUserAccount=Parameter::getGlobalParameter('cronCheckEmailsUser');
//     $globalMb->pwdImap=Parameter::getGlobalParameter('cronCheckEmailsPassword');
//     $globalMb->securityConstraint=2;
//     $globalMb->actionOK=(Parameter::getGlobalParameter('afterMailTreatment')=='deleteMail')?'DELETE':'READ'; // NONE, READ, DELETE
//     $globalMb->actionKO=$globalMb->actionOK;
//     $globalMb->allowAttach=(Parameter::getGlobalParameter('allowAttachInputMails')=='YES')?1:0;
//     $globalMb->sizeAttachment=floatval(Parameter::getGlobalParameter('sizeAttachmentInputMails'));
//     $globalMb->addToFollowUp=false;
//     $globalMb->sortOrder=0;
//     $globalMb->idle=0;
//     $globalMb->limitOfInputPerHour=0;
//     $globalMb->_onlyResponse=true;
//     if ($globalMb->serverImap and $globalMb->imapUserAccount) {
//       $globalMb->treatInputMailbox();
//     }

    // Clean $emailAttachmentsDir
    purgeFiles ( $uploaddirMail, null );
    
  }
  
  public function treatInputMailbox() {
    global $pathSeparator, $uploaddirMail, $uploaddirAttach, $imapFilterCriteria;
    // Idle mailbox : do not treat (if idle because of connection, will retry)
    if($this->idle==1 and $this->autoclosedReason !="connexion") return;
    // Do no store history for cronned operation
    $this->_noHistory=true;
    
    // Check if idle because of connection, retry after 1h (3600s)
    if($this->autoclosedDateTime  and $this->autoclosedReason=="connexion" and $this->idle==1){
      //$now = date('Y-m-d H:i:s');
      $dateClosed = $this->autoclosedDateTime;
      $now=time();
      $oneHourAgo=$now-3600;
      $oneHourAgoDate=date("Y-m-d H:i:s",$oneHourAgo);
      if($this->idle==1 and $dateClosed < $oneHourAgoDate){
        $this->idle = 0;
        $this->autoclosedDateTime = null;
        $this->autoclosedReason = null;
        $this->failedRead=0;
        $this->save();
      }else{
        return;
      }
    }
    
    // Check if other mailbox exist for Import on same user (email)
    $inputMbI = new InputMailboxImport();
    $order = "";
    $inputMbiList=$inputMbI->getSqlElementsFromCriteria(null, false,"idle=0",$order,false,false);
    foreach ($inputMbiList as $id=>$val){
      $userImapI=$val->imapUserAccount;
      $idMbI=$val->id;
      if($userImapI == $this->imapUserAccount){
        // Same user as Import Mailbox : Close current Mailbox and continue
        $this->idle = 1;
        $this->autoclosedReason = "connexion";
        $this->autoclosedDateTime = date ( "Y-m-d H:i:s" );
        $this->save();        
        $error="import mailbox already exists with the same Imap user";
        InputMailboxHistory::storeHistory($this,"Cannot connect to mailbox",null,$error,true);
        return;
      } else {
        continue;
      }
    }
    
    // Read Mailbox
    $actionOK = $this->actionOK;
    $actionKO = $this->actionKO;
    $imapMailbox = new ImapMailbox($this->serverImap,
                                   $this->imapUserAccount,
                                   decryptPwd($this->pwdImap),
                                   $uploaddirMail,
                                   'utf-8',
                                   ($this->connectionMode=='oauth')?$this->idOAuthClient:null);
    enableCatchErrors();
    $mailsIds = null;
    try {
      $mailsIds = $imapMailbox->searchMailBox($imapFilterCriteria);
    }catch (Exception $e) {
      $this->failedRead += 1;
      debugTraceLog("=> Exception on ImapMailboxTicket::treatInputMailbox() for mailbox #$this->id | $this->name");
      $error="Cannot connect to ticket mailbox #$this->id | $this->name";
      if($this->failedRead >= 5) {
        $this->idle = 1;
        $this->autoclosedReason = "connexion";
        $this->autoclosedDateTime = date ( "Y-m-d H:i:s" );
        $resSaveIMT=$this->save();
        $receivers = array();
        $prof=new Profile();
        $user = new User();
        $crit=array('profileCode'=>'ADM');
        $lstProf=$prof->getSqlElementsFromCriteria($crit,false);
        foreach ($lstProf as $prof) {
          $crit=array('idProfile'=>$prof->id);
          $lstUsr=$user->getSqlElementsFromCriteria($crit,false);
          foreach($lstUsr as $usr) {
            $receivers[]=$usr;
          }
        }
        $title = "Cannot connect to ticket mailbox #$this->id";
        $content = imap_last_error().' - ticket mailbox closed, next try in 1 hour';
        sendNotification($receivers, $this, "ALERT", $title, $content, $error);
      } else {
        $resMb=$this->save();
      }
      InputMailboxHistory::storeHistory($this,"Cannot connect to mailbox",null,$error,true);
      return;
    }
    disableCatchErrors();
    if(!$mailsIds) {
      debugTraceLog("[IMBT#$this->id] Ticket mailbox #$this->id $this->serverImap for $this->imapUserAccount is empty (filter='$imapFilterCriteria')"); // Will be a debug level trace
      if ($this->failedRead>0) {
        $this->failedRead=0;
        $resMb=$this->save();
      }
      unset($imapMailbox);
      return;
    }
    // Read all mais in Mailbox
    $failMessageLimit = false;
    foreach ($mailsIds as $mailId){
      if($this->idle==1) break;
      $result = "";
      $resultTicket=null;
      $failMessage = false;
      $mail = $imapMailbox->getMail($mailId);
      $mailTo = array_merge_preserve_keys($mail->to,$mail->cc);
      $mailFrom = $mail->fromAddress;
      $limitOfInputPerHour = $this->limitOfInputPerHour;
      $inputHistory = new InputMailboxHistory();
      // Check if not too many email (limit per hour as defined)
      if ($this->id) {
        $now = date('Y-m-d H:i:s');
        $date = new DateTime($now);
        $date->sub(new DateInterval('PT1H'));
        $date = date_format($date, 'Y-m-d H:i:s');
        $where =  " idInputMailbox = ".$this->id." and date >='" . $date . "'" ;
        $nbInputHistory = $inputHistory->countSqlElementsFromCriteria(null,$where);
        if($limitOfInputPerHour and $nbInputHistory >= $limitOfInputPerHour){
          $this->idle=1;
          $result.= i18n('colLimitOfInputPerHour');
          $failMessage = true;
          $failMessageLimit = true;
          $this->autoclosedReason = "toomany";
          $this->autoclosedDateTime = date ( "Y-m-d H:i:s" );
          $this->save();
          //send notification
          $receivers = array();
          $prof=new Profile();
          $user = new User();
          $crit=array('profileCode'=>'ADM');
          $lstProf=$prof->getSqlElementsFromCriteria($crit,false);
          foreach ($lstProf as $prof) {
            $crit=array('idProfile'=>$prof->id);
            $lstUsr=$user->getSqlElementsFromCriteria($crit,false);
            foreach($lstUsr as $usr) {
              $receivers[]=$usr;
            }
          }
          $title = 'inputMailboxTicket #'.$this->id.' closed';
          $content = i18n('colLimitOfInputPerHour');
          $name = ' inputMailboxTicket #'.$this->id.' closed';
          sendNotification($receivers, $this, "WARNING", $title, $content, $name);
          InputMailboxHistory::storeHistory($this, $title, $name, $content);
          $imapMailbox->markMailAsUnread($mailId);
          return;
        }
      }
      // check security constraint : 2 = user must exist, 3 = user must be allocated to project 
      $securityConstraint = $this->securityConstraint;
      if($securityConstraint == '2' or $securityConstraint == '3'){
        $emailExist=Affectable::getAffectableFromEmail($mail->fromAddress);
        if(! $emailExist->id){
          $result= i18n('securityConstraint2');
        }
        if($securityConstraint == '3' and $emailExist->id){
          $aff= new Affectation();
          $affExist = $aff->countSqlElementsFromCriteria(array('idResource'=>$emailExist->id,'idProject'=>$this->idProject));
          if($affExist<1) $result=i18n('securityConstraint3');
        }
      }
      
      // Get subjet (and remove unexpected formating such as emojis or bad encoding)
      if(!$mail->subject) $result=i18n('noSubject');
      $bodyHtml=$mail->textHtml;
      $body=$mail->textPlain;
      $subject=$mail->subject;
      if ($bodyHtml) {
        $bodyHtmlTemp=self::replaceEmbededImages($bodyHtml);
        $toText=new Html2Text($bodyHtmlTemp);
        $body=$toText->getText();
        $body=self::replaceEmbededImagesEnd($body);
      }
      $encodings = [
          "UTF-8",
          "Windows-1252",
          "ISO-8859-15",
          "ISO-8859-1",
          "ASCII"
      ];
      $subjectEncoding=mb_detect_encoding($subject, $encodings, false);
      if ($subjectEncoding==false) {
        debugTraceLog("[IMBT#$this->id] Read Ticket Mailbox : cannot find encoding for message");
        debugTraceLog("[IMBT#$this->id] $subject");
      } else if ($subjectEncoding!='UTF-8') {
        $subject=mb_convert_encoding($subject,'UTF-8',$subjectEncoding);
      }
      $subject=InputMailboxTicket::convertEmojis($subject);
      
      // Search if email is a response to ProjeQtOr email
      $class=null;
      $id=null;
      $msg=null;
      $senderId=null;
      $obj=null;
      // Class and Id of object
      $headerClass=pq_substr($subject, pq_strpos($subject, '[')+1, (pq_strpos($subject, ']')-1)-pq_strpos($subject, '['));
      $posClass=pq_strpos($body,'directAccess=true&objectClass=');
      if (! $posClass) $posClass=pq_strpos($body,'directAccess=true&amp;objectClass=');
      $arrayHeader = pq_explode(' ', $headerClass);
      $class = (isset($arrayHeader[0]))?$arrayHeader[0]:'';
      $class=pq_ucfirst($class);
      $id = (isset($arrayHeader[1]))?pq_substr($arrayHeader[1], 1):'';
      if(SqlElement::class_exists($class) and is_numeric($id)) $obj=new $class($id);
      if(!SqlElement::class_exists($class) or !$obj){
        if ($posClass) { // It is a ProjeQtor mail
          $posId=pq_strpos($body,'&objectId=',$posClass);
          if (! $posId) $posId=pq_strpos($body,'&amp;objectId=',$posClass);
          if (! $posId) {
            debugTraceLog("[IMBT#$this->id] Message identified as response to Projeqtor email (but cannot find start of objectId)");
            self::markMail($imapMailbox,$mailId,$actionKO);
            continue;
          }
          $posEnd=pq_strpos($body,'"',$posId);
          if (!$posEnd or $posEnd-$posId>22) { $posEnd=pq_strpos($body,'>',$posId); }
          if (!$posEnd or $posEnd-$posId>22) { $posEnd=pq_strpos($body,']',$posId); }
          if (!$posEnd or $posEnd-$posId>22) { $posEnd=pq_strpos($body," ",$posId);	}
          if (!$posEnd or $posEnd-$posId>22) { $posEnd=pq_strpos($body,"\n",$posId); }
          if (!$posEnd or $posEnd-$posId>22) { $posEnd=pq_strpos($body,"\r",$posId); }
          if (!$posEnd or $posEnd-$posId>22) { $posEnd=pq_strpos($body,"_",$posId);	}
          if (!$posEnd or $posEnd-$posId>22) { $posEnd=pq_strpos($body,"&",$posId);	}
          if (!$posEnd or $posEnd-$posId>22) { $posEnd=pq_strpos($body,'"',$posId);	}
          if (!$posEnd or $posEnd-$posId>22) {
            if (pq_strlen($body)-$posId<20) {
              $posEnd=pq_strlen($body)-1;
              $testId=pq_substr($body,$posId+10);
              if (! is_int($testId)) {
                $posEnd=null;
              }
            }
          }
          if (! $posEnd or $posEnd-$posId>22) {
            debugTraceLog("[IMBT#$this->id] Message identified as response to Projeqtor email (but cannot find end of objectId)");
            self::markMail($imapMailbox,$mailId,$actionKO);
            continue;
          }
          $class=pq_substr($body,$posClass+30,$posId-$posClass-30);
          $id=pq_substr($body,$posId+10,$posEnd-$posId-10);
        }
      }
      
      $msgPlain=self::extractBodyPlain($body,$bodyHtml);
      $msgHtml=self::extractBodyHtml($bodyHtml);
      $msgTruncated=self::truncateBodyHtml($bodyHtml);
      
      // Sender
      $sender=$mail->fromAddress;
      $usr=Affectable::getAffectableFromEmail($sender);
      $senderId=$usr->id;
      debugTraceLog("[IMBT#$this->id] User corresponding to email address is #$senderId");
      if (! $senderId and $securityConstraint!='1') {
        traceLog("#$this->id - Email message received from '$sender', not recognized as resource or user or contact : message not stored as new ticket to avoid spamming");
        self::markMail($imapMailbox,$mailId,$actionKO);
        $result=i18n("errorMailSender",array($sender));
        if ($actionKO!='NONE') InputMailboxHistory::storeHistory($this,$mail->subject, $mailFrom,$result,true, "ticket");
        continue;
      }
      $arrayFrom=array("\n","\r"," ");
      $arrayTo=array("","","");
      $class=pq_str_replace($arrayFrom, $arrayTo, $class);
      $id=pq_str_replace($arrayFrom, $arrayTo, $id);
      $id=pq_str_replace(']','',$id);
      $obj=null;
      if (SqlElement::class_exists($class) and is_numeric($id)) {
        $obj=new $class($id);
        debugTraceLog("[IMBT#$this->id] Message identified as reply to message from $class #$id");
      }
      if (!pq_trim($msgPlain)) {
        if ($obj and $obj->id) traceLog("[IMBT#$this->id] Could not retreive response (empty response) from '$sender' mail concerning $class #$id");
        else traceLog("[IMBT#$this->id] Could not retreive message from '$sender' mail");
        self::markMail($imapMailbox,$mailId,$actionKO);
        $result=i18n("errorMailMessage",array($sender));
        if ($actionKO!='NONE') InputMailboxHistory::storeHistory($this,$mail->subject, $mailFrom,$result,true, "ticket");
        continue;
      }
      // Case 1 => answer to mail sent from projeqtor : add message as note to item
      if ($obj and $obj->id and $result) {
        debugTraceLog ("[IMBT#$this->id] note not stored : $result");
        self::markMail($imapMailbox,$mailId,$actionKO);
        if ($actionKO!='NONE') InputMailboxHistory::storeHistory($this,$mail->subject, $mailFrom,$result,true, "ticket");
        continue;
      }
      if ($obj and $obj->id and !$result) {
        if (!$senderId) $senderId=getCurrentUserId();
        if (substr_count($msgPlain,"\r\n")==2*substr_count($msgPlain,"\r\n\r\n")) {
          $msgPlain=pq_str_replace("\r\n\r\n","\r\n",$msgPlain); // Remove double lines as all are double
        }
        
        //---- Automatic reopening of the ticket ----
        $reopened = false;
        if ($class == 'Ticket' and $this->idStatus) {
          $reopen = self::checkReopenCondition($obj, $this->reopenCondition);
          if ($reopen) {
            $skipControls = SqlElement::$_skipAllControls;
            SqlElement::$_skipAllControls = true;
            $obj->idStatus = $this->idStatus;
            $obj->_noHistory = false;
            $obj->save();
            $reopened = true;
          }
        }

        $note=new Note();
        $note->refType=$class;
        $note->refId=$id;
        $note->idPrivacy=1;
        if ($msgHtml) $note->note=$msgHtml;
        else $note->note='<div>'.nl2brForPlainText($msgPlain).'</div>';
        $note->idUser=$senderId;
        $note->creationDate=date('Y-m-d H:i:s');
        $note->fromEmail=1;
        $resSaveNote=$note->save();
        $status=getLastOperationStatus($resSaveNote);
        if ($status=='OK') {
          //$objAtch=new $class($id);
          $sizeAttach = ($this->sizeAttachment)*1024*1024;
          $listAtt = $mail->getAttachments();
          foreach ($listAtt as $att){
            $attch = new Attachment();
            $attch->refType = $class;
            $attch->refId = $id;
            $attch->idPrivacy=1;
            $attch->type='file';
            $namefileWithPath = $att->filePath;
            $embededImg='src="cid:'.$att->id.'"';
            $attch->fileName = $att->name;
            $ext = pq_strtolower ( pathinfo ( $attch->fileName, PATHINFO_EXTENSION ) );
            // TODO EmbededImages
            if (pq_strpos($bodyHtml, $embededImg)!=0) { // The attacment is embeded (in the whole mail, before truncated)
              if (pq_substr($ext,0,3)=='php' or pq_substr($ext,0,3)=='pht' or pq_substr($ext,0,3)=='sht' or $ext=='phar' or $ext=='pgif') {
                continue; // Do not embed suspicious source
              }
              if (pq_strpos($msgHtml, $embededImg)!==false) continue; // Image is in the message but not after truncature (possibly after original message ?)
              if (! file_exists("../files/images/")) {
                mkdir("../files/images/",0777,true);
              }
              // This is an embeded image, do not save as attachment but as image embeded
              rename($att->filePath, "../files/images/".$att->id);
              $note->note=pq_str_replace($embededImg, 'src="../files/images/'.$att->id.'"', $note->note);
              $note->_noHistory=true;
              $note->save();
              continue; // Do not treat as attachment
            }
            if($this->allowAttach!=1) continue; 
            if (! $msgHtml and $msgTruncated and pq_strpos($bodyHtml, $embededImg)!=0 and pq_strpos($msgTruncated, $embededImg)===false) {
              // This is embedfed image for non html text but image is not before the original message or before the signature
              continue;
            }
//             if (pq_substr($ext,0,3)=='php' or pq_substr($ext,0,3)=='pht' or pq_substr($ext,0,3)=='sht' or $ext=='phar' or $ext=='pgif') {
//               $attch->fileName.='.projeqtor.txt';
//             }
            $attch->fileName=Security::checkValidFileName($attch->fileName,false, true);
            
            $attch->creationDate = date('Y-m-d H:i:s');
            $attch->fileSize = filesize($att->filePath);
            $attch->mimeType = mime_content_type($att->filePath);
            if($sizeAttach-$attch->fileSize > 0){
              $attch->save();
              $sizeAttach-=$attch->fileSize;
            } else {
              break;
            }
            $uploaddir = $uploaddirAttach . "attachment_" . $attch->id . $pathSeparator;
            if (! file_exists($uploaddir)) {
              mkdir($uploaddir,0777,true);
            }
            $paramFilenameCharset=Parameter::getGlobalParameter('filenameCharset');
            if ($paramFilenameCharset) {
              $uploadfile = $uploaddir . iconv("UTF-8", $paramFilenameCharset.'//TRANSLIT//IGNORE',$attch->fileName);
            } else {
              $uploadfile = $uploaddir . $attch->fileName;
            }
            if ( ! rename($namefileWithPath, $uploadfile)) {
              $error = htmlGetErrorMessage(i18n('errorUploadFile',array('hacking')));
              errorLog($error);
              $attch->delete();
            } else {
              //$attch->subDirectory = pq_str_replace(Parameter::getGlobalParameter('paramAttachmentDirectory'),'${attachmentDirectory}',$uploaddir);
              $attch->subDirectory = '${attachmentDirectory}'.$pathSeparator. "attachment_" . $attch->id . $pathSeparator;
              $otherResult=$attch->save();
            }
          }
          debugTraceLog("[IMBT#$this->id] Note from '$sender' added on $class #$id");
          if($this->addToFollowUp){
            $sender=$mail->fromAddress;
            $usrList=array();
            if ($mailFrom != $this->imapUserAccount) {
              $aff=Affectable::getAffectableFromEmail($mailFrom);
              if ($aff->id) $usrList[]=$aff;
              else if ($securityConstraint=='1' and $this->addPseudoUsers){
                $user = new User();
                $user->name = strstr($sender, "@", true);
                $user->email = $sender;
                $user->idProfile = 5;
                $user->idle = 1;
                $user->dummy = 1;
                $user->save();
                $senderId = $user->id;
                $usrList[]=$user;
              }
            }
            
            foreach ($mailTo as $key => $addressObj){
              $email = $addressObj->mail;
              $aff=Affectable::getAffectableFromEmail($email);
              if ($aff->id) $usrList[]=$aff;
              else if ($securityConstraint=='1' and $this->addPseudoUsers and $email != $this->imapUserAccount){
                $user = new User();
                $user->name = strstr($email, "@", true);
                $user->email = $email;
                $user->idProfile = 5;
                $user->idle = 1;
                $user->dummy = 1;
                $user->save();
                $usrList[]=$user;
              }
            }
            foreach ($usrList as $affectable){
              $sub = new Subscription();
              $sub->idAffectable=$affectable->id;
              $sub->refType=$class;
              $sub->refId=$id;
              $sub->idUser=$senderId;
              $sub->creationDateTime=date('Y-m-d H:i:s');
              //if ($affectable->dummy = 1 and $affectable->id != $senderId) $sub->inCopy = 1;
              if ($affectable->id != $senderId) $sub->inCopy = 1;
              $sub->save();
            }
          }
        } else {
          traceLog("ERROR saving note from '$sender' to item $class #$id : $resSaveNote");
          InputMailboxHistory::storeHistory($this,$mail->subject, $mailFrom,$resSaveNote);
        }
        if ($reopened) {
          SqlElement::$_skipAllControls = $skipControls;
        }
        $mailResult=$obj->sendMailIfMailable(false,false,false,false,true,false,false,false,false,false,false,true);
      }
      // if mailbox is Global Parameter mailbox, only treat case for Response to projeqtor emails 
      if (property_exists($this, '_onlyResponse') and $this->_onlyResponse==true) {
        self::markMail($imapMailbox,$mailId,$actionOK);
        continue;
      }
      
      // Case 2 => new mail received : add new ticket
      if (!SqlElement::class_exists($class) or !$obj) {
        $bodyHtml=$mail->textHtml;
        $body=$mail->textPlain;
        $encodings = [
            "UTF-8",
            "Windows-1252",
            "ISO-8859-15",
            "ISO-8859-1",
            "ASCII"
        ];
        $bodyEncoding=mb_detect_encoding($bodyHtml, $encodings, false);
        if ($bodyEncoding==false) {
          debugTraceLog("[IMBT#$this->id] Read Ticket mailbox : cannot find encoding for message");
          debugTraceLog("[IMBT#$this->id] $bodyHtml");
        } else if ($bodyEncoding!='UTF-8') {
          $bodyHtml=mb_convert_encoding($bodyHtml,'UTF-8',$bodyEncoding);
        }
        $bodyHtml=self::convertEmojis($bodyHtml);
        $bodyHtml=self::truncateSignature($bodyHtml);
        $ticket = new Ticket();
        if($result == ""){
          $ticket->name = pq_mb_substr($mail->subject,0,100);
          $ticket->idProject = $this->idProject;
          $ticket->idTicketType = $this->idTicketType;
          $ticket->idActivity = $this->idActivity;
          $ticket->idResource = $this->idAffectable;
          $ticket->externalReference = $mailFrom;
          if(pq_trim($bodyHtml)) $ticket->description = $bodyHtml;
          else $ticket->description = $body;
          $idStatus = SqlElement::getFirstSqlElementFromCriteria('Status', array('isCopyStatus'=>'1'));
          $ticket->idStatus = $idStatus->id;
          $knownUser=Affectable::getAffectableFromEmail($mailFrom);
          if($knownUser and $knownUser->id and $knownUser->isUser) $ticket->idUser = $knownUser->id;
          else if ($securityConstraint=='1' and $this->addPseudoUsers and $mailFrom != $this->imapUserAccount) {
            if (!$senderId){
              $user = new User();
              $user->name = strstr($sender, "@", true);
              $user->email = $sender;
              $user->idProfile = 5;
              $user->idle = 1;
              $user->dummy = 1;
              $user->save();
              $senderId = $user->id;
            }
            $ticket->idUser = $senderId;
          }
          if (Parameter::getGlobalParameter('requestorLimitToContact')=="YES"){
            if($knownUser and $knownUser->id and $knownUser->isContact) $ticket->idContact = $knownUser->id;
          }else {
            if($knownUser and $knownUser->id) $ticket->idContact = $knownUser->id;
            else if ($senderId) $ticket->idContact = $senderId;
          }
          // Transaction mode required for PostgreSql
          Sql::beginTransaction();
          $resultTicket=$ticket->save();
          if (getLastOperationStatus($resultTicket)=='OK') {
            Sql::commitTransaction();
          } else {
            Sql::rollbackTransaction();
          }
          if(getLastOperationStatus($resultTicket)=='OK' and $this->addToFollowUp){
            $sender=$mail->fromAddress;
            $usr=Affectable::getAffectableFromEmail($sender);
            $senderId=$usr->id;
            $usrList=array();
            if ($mailFrom != $this->imapUserAccount) {
              $aff=Affectable::getAffectableFromEmail($mailFrom);
              if ($aff->id) $usrList[]=$aff;
            }
            foreach ($mailTo as $key => $addressObj){
              $email = $addressObj->mail;
              $aff=Affectable::getAffectableFromEmail($email);
              if ($aff->id) $usrList[]=$aff;
              else if ($securityConstraint=='1' and $this->addPseudoUsers and $email != $this->imapUserAccount){
                $user = new User();
                $user->name = strstr($email, "@", true);
                $user->email = $email;
                $user->idProfile = 5;
                $user->idle = 1;
                $user->dummy = 1;
                $user->save();
                $usrList[]=$user;
              }
            }
            foreach ($usrList as $affectable){
              $sub = new Subscription();
              $sub->idAffectable=$affectable->id;
              $sub->refType='Ticket';
              $sub->refId=$ticket->id;
              $sub->idUser=$senderId;
              $sub->creationDateTime=date('Y-m-d H:i:s');
              //if ($affectable->dummy == 1 and $affectable->id != $senderId) $sub->inCopy = 1;
              if ($affectable->id != $senderId) $sub->inCopy = 1;
              $sub->save();
            }
          }
          if(getLastOperationStatus($resultTicket)=='OK') {
            // New set to status recorded
            $idStatus = SqlElement::getFirstSqlElementFromCriteria('Status', array('idle'=>'0'));
            $ticket->idStatus = $idStatus->id;
            SqlElement::$_skipAllControls=true;
            $ticket->save();
            SqlElement::$_skipAllControls=false;
          }
          
          if(getLastOperationStatus($resultTicket)=='OK'){
            $sizeAttach = ($this->sizeAttachment)*1024*1024;
            $listAtt = $mail->getAttachments();
            foreach ($listAtt as $att){
              $attch = new Attachment();
              $attch->refType = 'Ticket';
              $attch->refId = $ticket->id;
              $attch->idPrivacy=1;
              $attch->type='file';
              $namefileWithPath = $att->filePath;
              $embededImg='src="cid:'.$att->id.'"';
              $attch->fileName = $att->name;
              $ext = pq_strtolower ( pathinfo ( $attch->fileName, PATHINFO_EXTENSION ) );
              if (pq_strpos($ticket->description, $embededImg)!=0) {
                if (pq_substr($ext,0,3)=='php' or pq_substr($ext,0,3)=='pht' or pq_substr($ext,0,3)=='sht' or $ext=='phar' or $ext=='pgif') {
                  continue; // Do not embed suqpicious source
                }
                if (! file_exists("../files/images/")) {
                  mkdir("../files/images/",0777,true);
                }
                // This is an embeded image, do not save as attachment but as image embeded
                rename($att->filePath, "../files/images/".$att->id);
                $ticket->description=pq_str_replace($embededImg, 'src="../files/images/'.$att->id.'"', $ticket->description);
                $ticket->_noHistory=true;
                $ticket->save();
                continue; // Do not trat as attachment
              }
              if ($this->allowAttach!=1) continue;
//               if (pq_substr($ext,0,3)=='php' or pq_substr($ext,0,3)=='pht' or pq_substr($ext,0,3)=='sht' or $ext=='phar' or $ext=='pgif') {
//                 $attch->fileName.='.projeqtor.txt';
//               }
              $attch->fileName=Security::checkValidFileName($attch->fileName,false, true);
              $attch->creationDate = date('Y-m-d H:i:s');
              $attch->fileSize = filesize($att->filePath);
              $attch->mimeType = mime_content_type($att->filePath);
              if($sizeAttach-$attch->fileSize > 0){
                $attch->save();
                $sizeAttach-=$attch->fileSize;
              } else {
                break;
              }
              $uploaddir = $uploaddirAttach . "attachment_" . $attch->id . $pathSeparator;
              if (! file_exists($uploaddir)) {
                mkdir($uploaddir,0777,true);
              }
              $paramFilenameCharset=Parameter::getGlobalParameter('filenameCharset');
              if ($paramFilenameCharset) {
                $uploadfile = $uploaddir . iconv("UTF-8", $paramFilenameCharset.'//TRANSLIT//IGNORE',$attch->fileName);
              } else {
                $uploadfile = $uploaddir . $attch->fileName;
              }
              if ( ! rename($namefileWithPath, $uploadfile)) {
                $error = htmlGetErrorMessage(i18n('errorUploadFile',array('hacking')));
                errorLog($error);
                $attch->delete();
              } else {
                //$attch->subDirectory = pq_str_replace(Parameter::getGlobalParameter('paramAttachmentDirectory'),'${attachmentDirectory}',$uploaddir);
                $attch->subDirectory = '${attachmentDirectory}'.$pathSeparator. "attachment_" . $attch->id . $pathSeparator;
                $otherResult=$attch->save();
              }
            }
          }
        }
        $inputMailboxHistory = new InputMailboxHistory();
        $inputMailboxHistory->idInputMailbox = $this->id;
        $inputMailboxHistory->title = pq_mb_substr($mail->subject,0,200);
        $inputMailboxHistory->adress = $mailFrom;
        $inputMailboxHistory->date = date("Y-m-d H:i:s");
        if($result == "" and getLastOperationStatus($resultTicket)=='OK'){
          $result = i18n('ticketInserted').' : #'.$ticket->id;
        }else{
          $result = pq_mb_substr(i18n('ticketRejected').' : '.(($result!=='')?$result:strip_tags(getLastOperationMessage($resultTicket))),0,200);
          $failMessage=true;
        }
        $inputMailboxHistory->result = pq_mb_substr($result,0,200);
        $inputMailboxHistory->refType = "ticket";
        $saveHisto=$inputMailboxHistory->save();
        if (getLastOperationStatus($saveHisto)!='OK') debugTraceLog("[IMBT#$this->id] Error saving InputMailboxHistory : $saveHisto");
        if(! $failMessageLimit){
          $action=($failMessage)?$actionKO:$actionOK;
          self::markMail($imapMailbox,$mailId,$action);
          continue;
        } else {
          $imapMailbox->markMailAsUnread($mailId);
          continue;
        }
        if(!$failMessage){
          $this->lastInputDate = date("Y-m-d H:i:s");
          $this->idTicket = $ticket->id;
          $this->totalInputTicket += 1;
        }
        $this->failedRead=0;
        $resMb=$this->save();
      }else{
        $inputMailboxHistory = new InputMailboxHistory();
        $inputMailboxHistory->idInputMailbox = $this->id;
        $inputMailboxHistory->title = $mail->subject;
        $inputMailboxHistory->adress = $mailFrom;
        $inputMailboxHistory->date = date("Y-m-d H:i:s");
        if($result == "" and getLastOperationStatus($resultTicket)=='OK'){
          $result = i18n('noteAddFromMail', array($class, $id));
        }
        $inputMailboxHistory->result = $result;
        $inputMailboxHistory->refType = "ticket";
        $inputMailboxHistory->save();
      }
      self::markMail($imapMailbox,$mailId,$actionOK);
    }
    unset($imapMailbox);
  }
  
  public static function convertEmojis($data) {
    // Remove emojis
    return preg_replace('%(?:
          \xF0[\x90-\xBF][\x80-\xBF]{2}      # planes 1-3
        | [\xF1-\xF3][\x80-\xBF]{3}          # planes 4-15
        | \xF4[\x80-\x8F][\x80-\xBF]{2}      # plane 16
        )%xs', '', pq_nvl($data));
  }
  
  public static function truncateSignature($body) {
    $signIdent=Parameter::getGlobalParameter('paramSignatureAndTagToRemove');
    if(pq_trim($signIdent)!=''){
      $posRemoveMsg=pq_strpos($body,$signIdent);
      if($posRemoveMsg!==false){
        return pq_substr($body,0,$posRemoveMsg);
      }
    }
    return $body;
  }
  
  public static function markMail($imapMailbox,$mailId,$action) {
    if($action){
      switch ($action){
        case 'NONE':
          $imapMailbox->markMailAsUnread($mailId);
          break;
        case 'READ':
          $imapMailbox->markMailAsRead($mailId);
          break;
        case 'DELETE':
          $imapMailbox->deleteMail($mailId);
          break;
      }
    }
  }
  
  
  public static function replaceEmbededImages($bodyHtml) {
    // Replace images with simple text
    preg_match_all('/<img[^>]+src="(.*?)"[^>]*>/',$bodyHtml,$matches);
    foreach ($matches[0] as $match) {
      $repString = preg_replace('/(<[^>]+) style=".*?"/i', '$1', $match); // remove style in image as it sets the mess for SOGo emails
      $rep="###IMG_START###".pq_substr($repString,4,-1)."###IMG_END###";
      $bodyHtml=pq_str_replace($match, $rep, $bodyHtml);
    }
    return $bodyHtml;
  }
  public static function replaceEmbededImagesEnd($bodyHtml) {
    $bodyHtml=pq_str_replace(array("###IMG_START###","###IMG_END###"), array("<img",">"), $bodyHtml);
    return $bodyHtml;
  }
  
  /**
   * Get Body for notes in Plain test format :
   *  - truncate to remove original message
   *  - truncate to remove signature
   */  
  public static function extractBodyPlain($body, $bodyHtml) {
    if (! $body) return '';
    // Search end of Message (this is valid for text only, treatment of html messages would require other code)
      
    $posEndMsg=strrpos($body,"###PROJEQTOR###");
    if($posEndMsg){
      $checkThunderAndGmail=pq_strpos($body,"\r\n>");
      //$checkSeparator=pq_strpos($body,"____________________");
      if($checkThunderAndGmail and $checkThunderAndGmail<$posEndMsg){
        $posEndMsg=$checkThunderAndGmail;
        $posEndMsg=strrpos(pq_substr($body,0,$posEndMsg-20), "\r\n");// Search for Thunderbird and Gmail
      }else{
        $substrEndBody=pq_substr($body,0,$posEndMsg);
        $posStartTag=strrpos($substrEndBody,"\n");
        $substrRow=pq_substr($body,0,$posStartTag-2);
        $posEndMsg=strrpos($substrRow,"\n");
      }
    }
    if (! $posEndMsg and pq_strpos(pq_substr($body,0,pq_strlen($body)-20),"\r\n>")) {
      $posEndMsg=strrpos(pq_substr($body,0,pq_strlen($body)-20), "\r\n>");
    }
    if (! $posEndMsg) {
      $posEndMsg=pq_strpos($body,"\n>");
    }
    if (!$posEndMsg) { // Search for outlook
      preg_match('/<.*?@.*?> [\r\n]/',pq_nvl($body), $matches);
      if (count($matches)>0) {
        $posEndMsg=pq_strpos($body, $matches[0]);
        $posEndMsg=strrpos(pq_substr($body,0,$posEndMsg-2), "\r\n");
      }
    }
    if (!$posEndMsg) {
      $posEndMsg=pq_strpos($body,"\r\n\r\n\r\n");
      if (!$posEndMsg) {
        $posEndMsg=pq_strpos($body,"\n\n\n");
      }
    }
    if (!$posEndMsg) { // Message not received with previous methods, try another one
      $posClass=pq_strpos($body,'directAccess=true&objectClass=');
      if (! $posClass) $posClass=pq_strpos($body,'directAccess=true&amp;objectClass=');
      $posEndMsgDe=strrpos(pq_substr($body,0,$posClass), "\n");
      $posDe=strrpos(pq_substr($body,0,$posEndMsgDe), "De : ");
      if ($posDe>2) {
        $posEndMsg=$posDe-1;
      } else {
        $posDe=strrpos(pq_substr($body,0,$posEndMsgDe), "From : ");
        if ($posDe>2) {
          $posEndMsg=$posDe-1;
        }
      }
    }
    if ($posEndMsg) {
      $msg=pq_substr($body,0,$posEndMsg);
    } else {
      $msg=$body;
    }
    // Remove signature
    $msg=self::truncateSignature($msg);
    // Remove unexpected "tags" // Valid as long as we treat emails as text
    $msg=preg_replace('/<mailto.*?\>/','',pq_nvl($msg));
    $msg=preg_replace('/<http.*?\>/','',pq_nvl($msg));
    $msg=preg_replace('/<#[A-F0-9\-]*?\>/','',pq_nvl($msg));
    $msg=pq_str_replace(" \r\n","\r\n",$msg);
    $msg=pq_str_replace(" \r\n","\r\n",$msg);
    $msg=pq_str_replace(" \n","\n",$msg);
    $msg=pq_str_replace(" \n","\n",$msg);
    $msg=pq_str_replace("\n\n\n","\n\n",$msg);
    $msg=pq_str_replace("\n\n\n","\n\n",$msg);
    
    return $msg;
  }
  
  /** 
   * TODO : not working yet
   * Get Body for notes in Html format :
   *  - truncate to remove original message
   *  - does NOT truncate to remove signature
   */  
  public static function extractBodyHtml($body) {
    if (!$body) return null;
    // TODO 
    return null;
  }
  
  /**
   * TODO : not working yet
   * Get Body for notes in Html format : NOT TO BE STORED
   *  - truncate to remove original message
   *  - truncate to remove signature
   *  IMPORTANT : this format can not be stores as note has some tags opened are not closed
   *  Is usefull only to determine if embeded image is to be imported or not
   */ 
  public static function truncateBodyHtml($body) {
    if (!$body) return null;
    $posEndMsg=strrpos($body,"###PROJEQTOR###");
    if (!$posEndMsg) return null;
    $msg=pq_substr($body,0,$posEndMsg);
    $msg=self::truncateSignature($msg);
    return $msg;
  }
  
  private static function checkReopenCondition($obj, $condition) {
    if (!$condition) $condition = 'IDLE';
    switch ($condition) {
      case 'ALWAYS':
        return true;        
      case 'DONE':
        if (!$obj->idStatus) return false;
        $status = new Status($obj->idStatus);
        return ($status->setDoneStatus == 1 or $status->setIdleStatus == 1);      
      case 'IDLE':
      default:
        if (!$obj->idStatus) return false;
        $status = new Status($obj->idStatus);
        return ($status->setIdleStatus == 1);
    }
  }
}
?>
