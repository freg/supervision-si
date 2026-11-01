<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/
define('ANONYMOUS_ACCESS', true);
require_once "../tool/projeqtor.php";
scriptLog('resetPasswordChange');

Sql::beginTransaction();

$resetEnabled = (Parameter::getGlobalParameter('passwordResetEnabled','NO')=='YES');
if (! $resetEnabled) {
  exit;
}

$token = getSessionValue('passwordResetToken');
if (! $token) {
  $result = i18n('errorResetPasswordInvalidToken');
  $result.= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
  displayLastOperationStatus($result);
  exit;
}

$pwdR = PasswordResetRequest::getSingleSqlElementFromCriteria('PasswordResetRequest', array('token'=>$token));
if($pwdR->id){
  $oldUser = new User($pwdR->idUser);
}else{
  $oldUser = null;
}

$login = trim(RequestHandler::getValue('login'));
$password = RequestHandler::getValue('password');
$passwordLength = RequestHandler::getValue('passwordLength');
$userSalt = RequestHandler::getValue('userSalt');
$newPasswordWithOldSalt=RequestHandler::getValue('newPasswordWithOldSalt');

if (! $login || ! $password || ! $passwordLength || ! $userSalt) {
  $result = i18n('messageMandatory', array(i18n('colLogin') . '/' . i18n('colPassword')));
  $result.= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
  displayLastOperationStatus($result);
  exit;
}

$req = SqlElement::getSingleSqlElementFromCriteria('PasswordResetRequest', array('token' => $token));
if (! $req || ! $req->id) {
  traceLog("RESET_PASSWORD - invalid token [$token]");
  $result = i18n('errorResetPasswordInvalidToken');
  $result.= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
  displayLastOperationStatus($result);
  exit;
}

if ($req->used) {
  traceLog("RESET_PASSWORD - token already used #$req->id");
  $result = i18n('errorResetPasswordTokenUsed');
  $result.= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
  displayLastOperationStatus($result);
  exit;
}

// Expiration 10 minutes
$now = new DateTime();
$reqDate = new DateTime($req->requestDateTime);
$diffSec = $now->getTimestamp() - $reqDate->getTimestamp();
if ($diffSec > 10*60) {
  traceLog("RESET_PASSWORD - token expired #$req->id");
  $result = i18n('errorResetPasswordTokenExpired');
  $result.= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
  displayLastOperationStatus($result);
  exit;
}

$user = SqlElement::getSingleSqlElementFromCriteria('User', array('name'=>$login));
if (! $user || ! $user->id || $user->id != $req->idUser) {
  traceLog("RESET_PASSWORD - login mismatch with token #$req->id");
  $result = i18n('messageInvalidLoginOrEmail');
  $result.= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
  displayLastOperationStatus($result);
  exit;
}

// Verrou / LDAP
$paramLdap_allow_login=Parameter::getGlobalParameter('paramLdap_allow_login');
if ($user->idle!=0) {
  $result = i18n("errorResetPasswordLdapUser");
  $result.= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
  displayLastOperationStatus($result);
  exit;
}

if ($user->isLdap!=0 and isset($paramLdap_allow_login) and pq_strtolower($paramLdap_allow_login)=='true') {
  $result = i18n("colUser").' '.i18n("colIsLdap");
  $result.= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
  displayLastOperationStatus($result);
  exit;
}

// Password Min length
if ($passwordLength < Parameter::getGlobalParameter('paramPasswordMinLength')) {
  $result = i18n("pwdErrorLength", array(Parameter::getGlobalParameter('paramPasswordMinLength')));
  $result.= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
  displayLastOperationStatus($result);
  exit;
}

if (Parameter::getGlobalParameter('oldPasswordDifferentNew') == 'YES' and $oldUser->crypto == 'sha256' and $newPasswordWithOldSalt!='' and $newPasswordWithOldSalt==$oldUser->password) {
  $result = i18n('errorResetPasswordOldPassword');
  $result.= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
  displayLastOperationStatus($result);
  exit;
}

// ========== changePassword($user, $password, $userSalt, 'sha256') ==========
SqlElement::$_skipAllControls=true;
$user->password = $password;
$user->salt = $userSalt;
$user->crypto = 'sha256';
$user->passwordChangeDate = date('Y-m-d');
$user->mustChangePassword = 0;
$result = $user->save();

if (getLastOperationStatus($result)!='OK') {
  displayLastOperationStatus($result);
  exit;
}

$req->used = 1;
$req->save();
SqlElement::$_skipAllControls=false;

unsetSessionValue('passwordResetToken');

$res = i18n('messageResetPasswordDone');
$res.= '<div id="validated" name="validated" type="hidden" dojoType="dijit.form.TextBox">OK</div>';
$res.= '<input type="hidden" id="lastOperationStatus" value="OK" />';
displayLastOperationStatus($res);
