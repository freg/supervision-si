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

/** =========================================================================== 
 * Chek login/password entered in connection screen
 */
  require_once "../tool/projeqtor.php"; 
  require_once "../external/phpAES/aes.class.php";
  require_once "../external/phpAES/aesctr.class.php";
  scriptLog('   ->/tool/loginCheck.php');
  $isMobile = RequestHandler::getValue('isMobile');
  $login="";
  $password="";
  $dbVersion=Sql::getDbVersion();
  debugTraceLog("loginCheck : current db version = '$dbVersion'");
  if (pq_array_key_exists('login',$_POST)) {
    $login=$_POST['login'];
    $login=AesCtr::decrypt($login, getSessionValue('sessionSalt'), Parameter::getGlobalParameter('aesKeyLength'));
  }
  if (pq_array_key_exists('password',$_POST)) {
    $password=$_POST['password'];
  }
  $rememberMe=(isset($_REQUEST['rememberMe']) and $_REQUEST['rememberMe']=='on' and Parameter::getGlobalParameter('rememberMe')!='NO');
  $login=pq_trim($login);
  if ($login=="") {
    debugTraceLog("loginCheck : no login provided");
    loginError();
  }
  if ($password=="" or AesCtr::decrypt($password, getSessionValue('sessionSalt'), Parameter::getGlobalParameter('aesKeyLength'))=="") {
    debugTraceLog("loginCheck : no password or not encrypted / $password /".getSessionValue('sessionSalt'));
    loginError();
  }
  if (! $dbVersion or $dbVersion=='0.0.0') {
	  $password=AesCtr::decrypt($password, getSessionValue('sessionSalt'), Parameter::getGlobalParameter('aesKeyLength'));
	  debugTraceLog("login for maintenance with '$login' / '$password'");
    if ($login=="admin" and $password=="admin") {
      include "../db/maintenance.php";
      exit;
    }
    debugTraceLog("login for maintenance with other than 'admin' / 'admin'");
  }   
  if (Sql::getDbVersion() and Sql::getDbVersion()!=$version and version_compare(pq_substr(Sql::getDbVersion(),1), '3.0.0','<')) {
  	User::setOldUserStyle();
  }
  $obj=new User();
  $crit="lower(name)=".Sql::str(pq_strtolower($login));
  $users=$obj->getSqlElementsFromCriteria(null,true,$crit);
  if ( ! $users ) {
    debugTraceLog("loginCheck : no user with name '$login'");
  	loginError();
  	exit;
  } 
  if ( count($users)==1 ) {
  	$user=$users[0];
  } else if ( count($users)>1 ) {
  	debugTraceLog("User '" . $login . "' : too many rows in Database" );
    loginError();
   	exit;
  } else {
    $user=new User();
    $paramLdap_allow_login=Parameter::getGlobalParameter('paramLdap_allow_login'); // If ldap is enabled, look for username without case sensitive, as it will be stored this way.
    if (isset($paramLdap_allow_login) and pq_strtolower($paramLdap_allow_login)=='true') {
      $critWhere="lower(name)=".Sql::str(pq_strtolower($login));
      $users=$user->getSqlElementsFromCriteria(null,true,$critWhere);
      if ( count($users)==1 ) {
        $user=$users[0];
      }
    }
  }  
  if (!$user->crypto) {
  	$currVersion=Sql::getDbVersion();
  	if (version_compare(pq_substr($currVersion,1), '4.0.0','<')) {
  		traceLog("Migrating from version < V4.0.0 : previous errors are expected for Class 'User' on fields 'loginTry', 'salt' and 'crypto'");
  		$user->crypto='old';
  		//$user=SqlElement::getSingleSqlElementFromCriteria('UserOld', $crit);
  	}
  }
  enableCatchErrors();
  $authResult=$user->authenticate($login, $password, true);
  disableCatchErrors();    
  
// possible returns are 
// "OK"        login OK
// "login"     unknown login
// "password"  wrong password
// "ldap"      error connecting to Ldap  
// "plugin"    error triggered by plugin on Connect event

  if ( $authResult!="OK") {
  	if ($user->locked!=0) {
  	  debugTraceLog("loginCheck : user locked");
      loginErrorLocked();
  	} else if ($authResult=="ldap") {
  	  debugTraceLog("loginCheck : incorrect ldap authentification");
    	loginLdapError();
    } else if ($authResult=="plugin") {
      debugTraceLog("loginCheck : incorrect plugin authentification");
      loginErrorPlugin(); // Message is expected in the plugin
    } else {
      debugTraceLog("loginCheck : unidentified incorrect authentification");
  	  loginError();
    }
    exit;
 	} 
	
 	if ( ! $user->id) {
 	  debugTraceLog("loginCheck : no user retreived");
   	loginError();
   	exit;
 	} 
  if ( $user->idle!=0 or  $user->locked!=0) {
    debugTraceLog("loginCheck : user idle or locked");
    loginErrorLocked();
  } 

  if (Sql::getDbVersion()!=$version) {
    $prf=new Profile($user->idProfile);
    if ($prf->profileCode!='ADM') {
      debugTraceLog("loginCheck : not an Admin during maintenance");
      loginErrorMaintenance();
      exit;
    }
    include "../db/maintenance.php";
    exit;
  }
  if (Parameter::getGlobalParameter('applicationStatus')=='Closed') {
  	$prf=new Profile($user->idProfile);
    if ($prf->profileCode!='ADM') { 
      debugTraceLog("loginCheck : not an Admin and application is closed");
      loginErrorClosedApplication();
      exit;
    }                     
  }
  $otpRequired=OtpRequest::isRequiredForUser($user);
  if ($otpRequired) {
    $otpAction=RequestHandler::getValue('otpAction', false, '');
    if ($otpAction=='validate') {
      $otpCode=RequestHandler::getValue('otpCode', false, '');
      $remainingTry=null;
      $otpResult=OtpRequest::validateCode($user, $otpCode, $remainingTry);
      if ($otpResult!='OK') {
        setSessionUser(null);
        if ($otpResult=='EXPIRED') displayOtpChallenge('errorOtpCodeExpired', true, 'errorResetPasswordTokenExpired');
        else if ($otpResult=='LOCKED') displayOtpChallenge('errorOtpInvalidCodeAccountLocked', true, 'lockedUser');
        else if ($otpResult=='MISSING') displayOtpChallenge('errorOtpRequestMissing', true, 'invalidAccessAttempt');
        else if ($otpResult=='INVALID_FORMAT') displayOtpChallenge('errorOtpInvalidCode', true, 'invalidAccessAttempt');
        else displayOtpChallenge('errorOtpInvalidCodeRemainingTries', true, 'errorOtpInvalidCode', array($remainingTry));
      }
    } else {
      setSessionUser(null);
      $otpResult=OtpRequest::requestCode($user);
      if ($otpResult=='OK') {
        if ($otpAction=='request') displayOtpChallenge('messageOtpCodeResentAt', false, null, array(date('H:i:s')));
        else displayOtpChallenge(null, false);
      }
      else if ($otpResult=='LIMIT') displayOtpChallenge('messageTooManyOtpRequests', true, 'invalidAccessAttempt');
      else if ($otpResult=='NO_EMAIL') displayOtpError('errorOtpEmailMissing', 'noEmail');
      else if ($otpResult=='MAIL_DISABLED') displayOtpError('errorOtpSendDisabled', 'noMailSent', array($user->email, ''));
      else displayOtpError('errorOtpSend', 'noMailSent', array($user->email, ''));
    }
  } else {
    OtpRequest::clearPendingRequest();
  }
  if ($rememberMe and !$otpRequired) {
    $user->setCookieHash();
    $user->save();
  }
  $param = new Parameter();
  $paramCount = $param->countSqlElementsFromCriteria(array('idUser'=>$user->id));
  if($paramCount==0){
    Parameter::storeUserParameter('newGui', '1', $user->id);
  }
  $newGui = SqlElement::getSingleSqlElementFromCriteria('Parameter', array('idUser'=>$user->id, 'parameterCode'=>'newGui'));
  if($newGui->parameterValue == 1 or isIE()){
    $idMessageLegal = SqlList::getIdFromName('MessageLegal', 'newGui');
    if ($idMessageLegal) {
      $messageLegalFollow = SqlElement::getSingleSqlElementFromCriteria('MessageLegalFollowup', array('idUser'=>$user->id, 'name'=>'newGui', 'idMessageLegal'=>$idMessageLegal));
      if ($messageLegalFollow and $messageLegalFollow->id and $messageLegalFollow->accepted==0) {
        $messageLegalFollow->acceptedDate= date('Y-m-d H:i:s');
        $messageLegalFollow->accepted = 1;
        $res=$messageLegalFollow->saveForced();
      }
    }
  }
  //gautier #AttributionVote
  $voteAttr = new VotingAttribution();
  $today = date('Y-m-d');
  //For USER
  $listVoteAttrUser = $voteAttr->getSqlElementsFromCriteria(array('idUser'=>$user->id,'idClient'=>null));
  foreach ($listVoteAttrUser as $vote){
    VotingAttribution::votingAttributionPoints($vote->id,$today);
  }
  //FOR CLIENT
  $voteAttr = new VotingAttribution();
  $affectable = new Affectable($user->id);
  if($affectable->isContact){
    $contact = new Contact($affectable->id);
    if($contact->idClient){
      $listVoteAttrClient = $voteAttr->getSqlElementsFromCriteria(array('idClient'=>$contact->idClient));
      foreach ($listVoteAttrClient as $vote){
        VotingAttribution::votingAttributionPoints($vote->id,$today);
      }
    }
  }
  loginOk ($user);
  User::resetAllVisibleProjects();
  forcedLayout($user);
  
  /** ========================================================================
   * Display an error message because of invalid login
   * @return void
   */
  function loginError() {
    global $login;
    echo '<div class="messageERROR">';
    echo i18n('invalidLogin');
    echo '</div>';
    setSessionUser(null);
    traceLog("Login error for user '" . $login . "'");
    exit;
  }
  function loginErrorPlugin() {
    global $login;
    setSessionUser(null);
    traceLog("Login refused for user '" . $login . "'");
    exit;
  }
  
    /** ========================================================================
   * Display an error message because of invalid login
   * @return void
   */
  function loginLdapError() {
    global $login;
    echo '<div class="messageERROR">';
    echo i18n('ldapError');
    echo '</div>';
    setSessionUser(null);
    traceLog("Error contacting Ldap for user '" . $login . "'");
    exit;
  }
  
  /** ========================================================================
   * Display an error message because of bad password
   * @return void
   */
  function loginPasswordError() {
    global $login;
    echo '<div class="messageERROR">';
    echo i18n('invalidLoginPassword');
    echo '</div>';
    setSessionUser(null);
    traceLog("Login error for user '" . $login . "'");
    exit;
  }
  
   /** ========================================================================
   * Display an error message because of invalid login
   * @return void
   */
  function loginErrorLocked() {
    global $login;
    echo '<div class="messageERROR">';
    echo i18n('lockedUser');
    echo '</div>';
    setSessionUser(null);
    traceLog("Login locked for user '" . $login . "'");
    exit;
  }
  
     /** ========================================================================
   * Display an error message because of invalid login
   * @return void
   */
  function loginErrorMaintenance() {
    global $login;
    echo '<div style="position:absolute;float: left;left:30px;top : 120px;">';
    if (!isNewGui()) echo '<img src="../view/img/closedApplication.gif"  width="60px"/>';
    echo '</div>';
    echo '<div class="messageERROR">';
    echo i18n('wrongMaintenanceUser');
    echo '</div>';
    setSessionUser(null);
    traceLog("Login of non admin user during upgrade. User '" . $login . "'");
    exit;
  }
  
  function loginErrorClosedApplication() {
    echo '<div style="position:absolute;float: left;left:30px;top : 120px;">';
    if (!isNewGui()) echo '<img src="../view/img/closedApplication.gif"  width="60px" />';
    echo '</div>';
    echo '<div class="messageERROR" >';
    echo htmlEncode(Parameter::getGlobalParameter('msgClosedApplication'),'withBR');
    echo '</div>';
    exit;
  }

  function displayOtpChallenge($messageCode, $error=true, $fallbackCode=null, $parameters=null) {
    if ($messageCode) {
      $message=i18n($messageCode, $parameters);
      if ($messageCode=='errorOtpInvalidCodeRemainingTries' and $message=='['.$messageCode.']') {
        $legacyMessageCode=$messageCode.$messageCode;
        $legacyMessage=i18n($legacyMessageCode, $parameters);
        if ($legacyMessage!='['.$legacyMessageCode.']') $message=$legacyMessage;
      }
      if ($fallbackCode and $message=='['.$messageCode.']') {
        $message=i18n($fallbackCode, $parameters);
      }
      echo '<div class="message'.(($error)?'ERROR':'WARNING').'">'.$message.'</div>';
    }
    echo '<input type="hidden" id="otpRequired" value="1" />';
    exit;
  }

  function displayOtpError($messageCode, $fallbackCode=null, $parameters=null) {
    OtpRequest::clearPendingRequest();
    $message=i18n($messageCode, $parameters);
    if ($fallbackCode and $message=='['.$messageCode.']') $message=i18n($fallbackCode, $parameters);
    echo '<div class="messageERROR">'.$message.'</div>';
    exit;
  }
  
  function loginOK($user) {
    global $isMobile;
    $user->finalizeSuccessfullConnection(false);
    echo '<div class="messageOK">';
    echo i18n('loginOK');
    echo '<div id="validated" name="validated" type="hidden" dojoType="dijit.form.TextBox">OK';
    echo '</div>';
    echo '</div>';
// BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM
    if(!isNotificationSystemActiv() or !securityCheckDisplayMenu(null,'Notification') or $isMobile=='true') { return; }
    $notif = new Notification();
    $notificationCounts = $notif->countUnreadNotifications();
    
    if ($notificationCounts['total']>0) {
        echo '<br/><div class="messageNotificationTotal">';
        echo '<input type="hidden" id="notificationOnLogin" value="'.$notificationCounts['total'].'" />';
        echo '  <br/><br/>';
        echo '<div>';
        echo i18n("unreadNotifications", array($notificationCounts['total']));
        echo '</div>';
        if ($notificationCounts['ALERT']>0) {
            echo '<div class="messageNotificationAlert">';
            if ($notificationCounts['ALERT']>1) echo $notificationCounts['ALERT']. " ".pq_strtoupper(i18n("menuAlert"));
            else echo $notificationCounts['ALERT']. " ".pq_strtoupper(i18n("colAlert"));
            echo '</div>';
        }
        if ($notificationCounts['WARNING']>0) {
            echo '<div class="messageNotificationWarning">';           
            if ($notificationCounts['WARNING']>1) echo $notificationCounts['WARNING']. " ".pq_strtoupper(i18n("warnings"));
            else echo $notificationCounts['WARNING']. " ".pq_strtoupper(i18n("WARNING"));            
            echo '</div>';
        }
        if ($notificationCounts['INFO']>0) {
            echo '<div class="messageNotificationInfo">';
            if ($notificationCounts['INFO']>1) echo $notificationCounts['INFO']. " ".pq_strtoupper(i18n("informations"));
            else echo $notificationCounts['INFO']. " ".pq_strtoupper(i18n("INFO"));   
            echo '</div>';
        }
        echo '</div>';
    }    
    

  
// END - ADD BY TABARY - NOTIFICATION SYSTEM 
  }
  
  //GAUTIER #LAYOUT FORCED
function forcedLayout($user){
  $layoutForce = new LayoutForced();
  $lstForceLayout = $layoutForce->getSqlElementsFromCriteria(array('idUser'=>$user->id));
  foreach ($lstForceLayout as $lay){
    $user->setLayout($lay->idLayout);
  }
}
?>
