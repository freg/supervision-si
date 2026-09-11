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
class InputMailboxImport extends SqlElement {

  public $_sec_Description;
  public $id;
  public $name;
  public $serverImap;
  public $_spe_connectionMode;
  public $connectionMode;
  public $imapUserAccount;
  public $pwdImap;
  public $idOAuthClient;
  public $_spe_oauth2;
  public $actionOK;
  public $actionKO; 
  public $sortOrder=0;
  public $idle;
  public $_sec_treatment;
  public $limitOfInputPerHourImport;
  public $lastInputDate;
  public $failedRead;
  public $failedMessage;
  public $autoclosedReason;
  public $autoclosedDateTime;
  public $_sec_importHistory;
  public $limitOfHistory;
  public $_spe_importHistory;
  public $_nbColMax = 3;
  
  public $_noCopy;
  public $_dynamicHiddenFields=array('pwdImap','idOAuthClient');
  
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="8%"># ${id}</th>
    <th field="name" width="23%">${name}</th>
    <th field="serverImap" width="20%">${serverImap}</th>
    <th field="imapUserAccount" width="20%">${imapUserAccount}</th>
    <th field="limitOfInputPerHourImport" width="10%">${limitOfInputPerHourImport}</th>
    <th field="sortOrder" formatter="numericFormatter" width="5%">${sortOrderShort}</th> 
    <th field="idle" width="4%" formatter="booleanFormatter">${idle}</th>
    ';
  
   private static $_fieldsTooltip = array(
   );
  
  private static $_fieldsAttributes=array(
      'name'=>'required',
      'idProject'=>'required',
      'serverImap'=>'required',
      'imapUserAccount'=>'required',
      'pwdImap'=>'',
      'lastInputDate'=>'readonly',
      'failedRead'=>'hidden',
      'failedMessage'=>'hidden',
      'limitOfInputPerHourImport'=>'required',
      'autoclosedReason'=>'hidden',
      'autoclosedDateTime'=>'hidden',
      "connectionMode"=>"hidden"
  );
  
  private static $_colCaptionTransposition = array(
      'idAffectable' => 'responsible',
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
      $this->limitOfInputPerHourImport=10;
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
    $result="";
    $defaultControl=parent::control();
    $old = $this->getOld();
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
    self::$_fieldsAttributes['_spe_importHistory']='hidden';
    if($this->limitOfHistory > 0){
      self::$_fieldsAttributes['_spe_importHistory']='readonly';
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
    if($item=='importHistory'){
        $history = new InputMailboxHistory();
        $critArray=array('idInputMailbox'=>$this->id, 'refType'=>'import');
        $order = " date desc ";
        $historyList=$history->getSqlElementsFromCriteria($critArray, false,null,$order,false,false,$this->limitOfHistory);
        drawInputMailboxHistory($historyList,$this);
    } else if ($item=='connectionMode'){
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
  
  public static function convertEmojis($data) {

    // Remove emojis
    
      return preg_replace('%(?:
          \xF0[\x90-\xBF][\x80-\xBF]{2}      # planes 1-3
        | [\xF1-\xF3][\x80-\xBF]{3}          # planes 4-15
        | \xF4[\x80-\x8F][\x80-\xBF]{2}      # plane 16
        )%xs', '', pq_nvl($data));

  }
  
// -------------------------------------------------------------------checkIMPORT--------------------------------------------------------------------
  public static function checkEmailsImport() {
    global $pathSeparator, $uploaddirMail, $uploaddirAttach, $imapFilterCriteria;
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
    $uploaddirForImport = $paramAttachDir . "attachment_Import" . $pathSeparator;
    if (file_exists ( $uploaddirForImport )) {
      purgeFiles ( $uploaddirForImport, null );
    } else {
      mkdir($uploaddirForImport,0777,true);
    }
    $imapFilterCriteria=Parameter::getGlobalParameter('imapFilterCriteria');
    if (! $imapFilterCriteria) { $imapFilterCriteria='UNSEEN UNDELETED'; }
    
    $where = "1=1";
    $inputMbI= new InputMailboxImport();
    $lstIMbI = $inputMbI->getSqlElementsFromCriteria(null,null,$where, 'sortOrder ASC');

    foreach ($lstIMbI as $mbI){
      if($mbI->idle==1 and $mbI->autoclosedReason !="connexion")continue;
      $mbI->_noHistory=true; // Do no store history for cronned operation
      if($mbI->autoclosedDateTime  and $mbI->autoclosedReason=="connexion" and $mbI->idle==1){
        //$now = date('Y-m-d H:i:s');
        $dateClosed = $mbI->autoclosedDateTime;
        $now=time();
        $oneHourAgo=$now-3600;
        $oneHourAgoDate=date("Y-m-d H:i:s",$oneHourAgo);
        if($mbI->idle==1 and $dateClosed < $oneHourAgoDate){
          $mbI->idle = 0;
          $mbI->autoclosedDateTime = null;
          $mbI->autoclosedReason = null;
          $mbI->failedRead=0;
          $mbI->save();
        }else{
          continue;
        }
      }
      $actionOK = $mbI->actionOK;
      $actionKO = $mbI->actionKO;
      //$imapMailbox = new ImapMailbox($mbI->serverImap,$mbI->imapUserAccount,decryptPwd($mbI->pwdImap),$uploaddirMail,'utf-8');
      $imapMailbox = new ImapMailbox($mbI->serverImap,
          $mbI->imapUserAccount,
          decryptPwd($mbI->pwdImap),
          $uploaddirMail,
          'utf-8',
          ($mbI->connectionMode=='oauth')?$mbI->idOAuthClient:null);
      
      enableCatchErrors();
      $mailsIds = null;
      try {
        $mailsIds = $imapMailbox->searchMailBox($imapFilterCriteria);
      }catch (Exception $e) {
        $mbI->failedRead += 1;
        debugTraceLog("=> Exception on ImapMailboxImport::treatInputMailbox() for mailbox #$mbI->id | $mbI->name");
        $error="Cannot connect to import mailbox #$mbI->id | $mbI->name";
        if($mbI->failedRead >= 5) {
          $mbI->idle = 1;
          $mbI->autoclosedReason = "connexion";
          $mbI->autoclosedDateTime = date ( "Y-m-d H:i:s" );
          $resSaveIMI=$mbI->save();
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
          $title = "Cannot connect to Import mailbox";
          $content = pq_mb_substr(imap_last_error().(($mbI->idle)?' - Import mailbox closed':''),0,200).' ,next try in 1 hour.';
          $name = "Cannot connect to Import mailbox #".$mbI->id;
          sendNotification($receivers, $mbI, "ALERT", $title, $content, $name);
        } else {
          $resMbI=$mbI->save();
        }
        InputMailboxHistory::storeHistory($mbI,"Cannot connect to mailbox",null,$error,true,'import');        
        unset($imapMailbox);
        continue;
      }
      disableCatchErrors();
      if(!$mailsIds) {
        debugTraceLog("[IMBI#$mbI->id] Import mailbox #$mbI->id $mbI->serverImap for $mbI->imapUserAccount is empty (filter='$imapFilterCriteria')"); // Will be a debug level trace
        if ($mbI->failedRead>0) {
          $mbI->failedRead=0;
          $resMbI=$mbI->save();
        }
        unset($imapMailbox);
        continue;
      }
      $failMessageLimit = false;
      foreach ($mailsIds as $mailId){
        if($mbI->idle==1) break;
        $result = "";
        $failMessage = false;
        $mail = $imapMailbox->getMail($mailId);
        $mailTo = array_merge_preserve_keys($mail->to,$mail->cc);
        $mailFrom = $mail->fromAddress;
        $mailSubject = $mail->subject;
        $limitOfInputPerHourImport = $mbI->limitOfInputPerHourImport;
        $inputHistory = new InputMailboxHistory();
        $now = date('Y-m-d H:i:s');
        $date = new DateTime($now);
        $date->sub(new DateInterval('PT1H'));
        $date = date_format($date, 'Y-m-d H:i:s');
        $where =  " idInputMailbox = ".$mbI->id." and date >='" . $date . "'" ;
        $nbInputHistory = $inputHistory->countSqlElementsFromCriteria(null,$where);
        if($nbInputHistory >= $limitOfInputPerHourImport){
          $mbI->idle=1;
          $result.= i18n('colLimitOfInputPerHourImport');
          $failMessage = true;
          $failMessageLimit = true;
          $mbI->autoclosedReason = "toomany";
          $mbI->autoclosedDateTime = date ( "Y-m-d H:i:s" );
          $mbI->save();
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
          $title = 'inputMailboxImport #'.$mbI->id.' closed';
          $content = i18n('colLimitOfInputPerHour');
          $name = ' inputMailboxImport #'.$mbI->id.' closed';
          sendNotification($receivers, $mbI, "WARNING", $title, $content, $name);
          InputMailboxHistory::storeHistory($this, $title, $from, $content);
          $imapMailbox->markMailAsUnread($mailId);
          continue;
        }
        $securityConstraint = '2';
        $emailExist=Affectable::getAffectableFromEmail($mail->fromAddress);
        if(! $emailExist->id){
          $result= i18n('securityConstraint2');
        }  
        if(!$mail->subject) $result=i18n('noSubject');
        $bodyHtml=$mail->textHtml;
        $body=$mail->textPlain;
        $subject=$mail->subject;
        if ($bodyHtml) {
          $toText=new Html2Text($bodyHtml);
          $body=$toText->getText();
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
          debugTraceLog("[IMBI#$mbI->id] Read Import mailbox : cannot find encoding for message");
          debugTraceLog("[IMBI#$mbI->id] $subject");
        } else if ($subjectEncoding!='UTF-8') {
          $subject=mb_convert_encoding($subject,'UTF-8',$subjectEncoding);
        }
        $subject=InputMailboxTicket::convertEmojis($subject);
        // Sender
        $sender=$mail->fromAddress;
        $senderId=null;
        $resultImport="";
        $resultImportMail="";
        $usr=Affectable::getAffectableFromEmail($sender);
        if($usr->isUser == 1){
          $senderId=$usr->id;
          debugTraceLog("[IMBI#$mbI->id] User corresponding to email address is #$senderId");
        }
        if (! $senderId and $securityConstraint!='1') {
          traceLog("#$mbI->id - Email message received from '$sender', not recognized user Import cancel");
          self::markMail($imapMailbox,$mailId,$actionKO);
          $resultImportMail.=i18n("errorMailSenderImport",array($sender));
          if ($actionKO!='NONE') InputMailboxHistory::storeHistory($mbI,$mail->subject, $mailFrom,$result,true, "import");
          continue;
        }
        $listAtt = $mail->getAttachments();
        $fileExt="";
        foreach ($listAtt as $att){;
          $namefileWithPath = $att->filePath;
          $embededImg='src="cid:'.$att->id.'"';
          if (pq_strpos($bodyHtml, $embededImg)!=0) {
            continue; // embeded image, not import file
          }
          $fileName = $att->name;
          $fileId = $att->id;
          $fileExt = explode('.', $fileName)[1];
          $fileExt = pq_strtolower($fileExt);
          if($fileExt == "csv" || $fileExt== "xlsx"){
            if (count(explode("_", $fileName))>=2){
              $classFile = explode('_', $fileName)[0];
              $fileDate = explode('_', $fileName)[1];
              if(isset(explode('_', $fileName)[2])){
                $fileTime = explode('_', $fileName)[2];
                $fileDateTime = $fileDate.$fileTime;
                $fileDateTime = explode('.', $fileDateTime)[0];
              }
              if(SqlElement::class_exists($classFile)){
                $uploaddir = $uploaddirAttach . "attachment_Import" . $pathSeparator;
                if (! file_exists($uploaddir)) {
                  mkdir($uploaddir,0777,true);
                }
                $paramFilenameCharset=Parameter::getGlobalParameter('filenameCharset');
                if ($paramFilenameCharset) {
                  $uploadfile = $uploaddir . iconv("UTF-8", $paramFilenameCharset.'//TRANSLIT//IGNORE',$fileName);
                } else {
                  $uploadfile = $uploaddir. $fileName;
                }
                if ( ! rename($namefileWithPath, $uploadfile)) {
                  $error = htmlGetErrorMessage(i18n('errorUploadFile',array('hacking')));
                  errorLog($error);
                }
                $uploaddirForImport = $paramAttachDir . "attachment_Import" . $pathSeparator;
                setSessionValue("mailboxImportCronUserId",$senderId);
                global $cronnedScript;
                $cronnedScript=false; // To ensure controls use correct rights
                $tempUser = getSessionUser();
                SqlElement::$_skipAllControls=false; // Important to have correct rights applied ! 
                $userImport = new User($senderId);
                setSessionUser($userImport);
                debugTraceLog("Import with rights of User #$userImport->id | $userImport->name");
                $uploaddirForImportFile = $uploaddirForImport.$fileName;
                $resultImportMail = i18n("colResultImport");
                $resultImport = Importable::import($uploaddirForImportFile, $classFile);
                $resultImportMail .=" ".$resultImport;
                $resultImportHtml = Importable::$importResult;
                $cronnedScript=true; // To ensure Cron execution for other processes
                setSessionUser($tempUser);
                purgeFiles ( $uploaddirForImportFile, null );
                unsetSessionValue("mailboxImportCronUserId");
                $subjectBack = i18n('colResultImport')." : ".$mailSubject;
                $resultSendMail = sendMail($sender, $subjectBack, $resultImportHtml);
              } 
              if($resultImportMail==""){
                $resultImportMail=i18n('invalidClassName', array($classFile,''));
              }
            }
            if($resultImportMail==""){
              $resultImportMail=i18n('msgInvalidFileNameNomenclature', array($fileName));
            }
          }
          if($resultImportMail==""){
            $resultImportMail=i18n('msgInvalidFileFormat',array('csv,xlsx'));
          }
          if(sessionValueExists("mailboxImportCronUserId")){
            unsetSessionValue("mailboxImportCronUserId");
          }
          InputMailboxHistory::storeHistory($mbI,$subject,$mailFrom,$resultImportMail,($failMessage)?1:0, 'import');
        } // end foreach file
        if(! $failMessageLimit){
          $action=($failMessage)?$actionKO:$actionOK;
          self::markMail($imapMailbox,$mailId,$action);
        }
        if(!$failMessage){
          $mbI->lastInputDate = date("Y-m-d H:i:s");
        }
        $mbI->failedRead=0;
        $resMbI=$mbI->save();
      } // end forach mail
      unset($imapMailbox);
    } // end list of input mailboxes
    
    purgeFiles ( $uploaddirMail, null );
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
}