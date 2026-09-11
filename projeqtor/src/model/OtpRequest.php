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
 *** DO NOT REMOVE THIS NOTICE ************************************************/

require_once('_securityCheck.php');

#[AllowDynamicProperties]
class OtpRequest extends SqlElement {

  const CODE_LENGTH=6;
  const VALIDITY_MINUTES=10;
  const REQUEST_LIMIT=3;
  const REQUEST_LIMIT_MINUTES=60;
  const VALIDATION_TRY_LIMIT=3;
  const PARAM_ADMIN_USERS='otpForAdminUsers';
  const PARAM_NEW_USERS='otpForNewUsers';
  const PARAM_DIRECT_SSO='otpForDirectConnectionsWithSso';

  public $id;
  public $idUser;
  public $requestDateTime;
  public $codeHash;
  public $used;
  public $validationTry;

  private static $_fieldsAttributes=array(
      'id'=>'',
      'idUser'=>'required',
      'requestDateTime'=>'required',
      'codeHash'=>'required',
      'used'=>'',
      'validationTry'=>''
  );

  function __construct($id=NULL, $withoutDependentObjects=false) {
    parent::__construct($id, $withoutDependentObjects);
  }

  function __destruct() {
    parent::__destruct();
  }

  protected function getStaticFieldsAttributes() {
    return self::$_fieldsAttributes;
  }

  public static function isRequiredForUser($user) {
    if (!$user or !$user->id) return false;
    $newUserOtp=(Parameter::getGlobalParameter(self::PARAM_NEW_USERS)=='YES');
    if ($newUserOtp and $user->crypto===null) return true;
    $adminOtp=(Parameter::getGlobalParameter(self::PARAM_ADMIN_USERS)=='YES');
    if ($adminOtp) {
      $profile=new Profile($user->idProfile);
      if ($profile->profileCode=='ADM') return true;
    }
    $directSsoOtp=(Parameter::getGlobalParameter(self::PARAM_DIRECT_SSO)=='YES');
    $ssoEnabled=getBooleanValue(Parameter::getGlobalParameter('SAML_allow_login'));
    return ($directSsoOtp and $ssoEnabled and (SSO::issetAccessFromLoginScreen() or SSO::issetAvoidSSO()));
  }

  public static function getParameterCodes() {
    return array(self::PARAM_ADMIN_USERS, self::PARAM_NEW_USERS, self::PARAM_DIRECT_SSO);
  }

  public static function disableParameters() {
    $disabled=array();
    foreach (self::getParameterCodes() as $code) {
      if (Parameter::getGlobalParameter($code)=='YES') {
        Parameter::storeGlobalParameter($code, 'NO');
        $disabled[]=$code;
      }
    }
    Parameter::clearGlobalParameters();
    if (count($disabled)>0) traceLog('OTP - parameters disabled after mail failure: '.implode(', ', $disabled));
    return $disabled;
  }

  public static function testMailAvailability($user=null) {
    $recipient=($user and isset($user->email))?pq_trim($user->email):'';
    if ($user and isset($user->id) and $user->id and !$recipient) return false;
    if (!$recipient) $recipient=pq_trim(Parameter::getGlobalParameter('mailerTestDest'));
    if (!$recipient) $recipient=pq_trim(Parameter::getGlobalParameter('paramAdminMail'));
    if (!$recipient) return false;

    $dbName=Parameter::getGlobalParameter('paramDbDisplayName');
    $date=date('Y-m-d H:i:s');
    $title='['.$dbName.'] '.i18n('mailOtpTestSubject');
    $body=i18n('mailOtpTestBody', array($dbName, $date));
    $sender=Parameter::getGlobalParameter('paramMailSender');
    if (Parameter::getGlobalParameter('mailerTestSender')!='sender' and $user and isset($user->email) and $user->email) {
      $sender=$user->email;
    }
    return (bool)sendMail($recipient, $title, $body, null, null, $sender, null, null, null, false, false, false, false, false, true);
  }

  public static function requestCode($user) {
    if (!$user or !$user->id) return 'INVALID_USER';
    if (!$user->email) return 'NO_EMAIL';

    $now=new DateTime();
    $limitDate=clone $now;
    $limitDate->modify('-'.self::REQUEST_LIMIT_MINUTES.' minutes');
    $request=new OtpRequest();
    $table=$request->getDatabaseTableName();
    $connection=Sql::getConnection();
    Sql::beginTransaction();
    Sql::query('SELECT id FROM '.$user->getDatabaseTableName().' WHERE id='.Sql::fmtId($user->id).' FOR UPDATE', $connection);
    $query='SELECT COUNT(*) AS nb FROM '.$table
          .' WHERE idUser='.Sql::fmtId($user->id)
          .' AND requestDateTime>='.Sql::str($limitDate->format('Y-m-d H:i:s'));
    $result=Sql::query($query, $connection);
    $line=Sql::fetchLine($result);
    $requestCount=($line)?intval($line['nb']):0;
    if (self::REQUEST_LIMIT>0 and $requestCount>=self::REQUEST_LIMIT) {
      Sql::rollbackTransaction();
      traceLog('OTP - too many requests for user #'.$user->id);
      return 'LIMIT';
    }

    self::clearPendingRequest();
    $previousRequests=$request->getSqlElementsFromCriteria(array('idUser'=>$user->id, 'used'=>'0'));
    $validationTry=0;
    foreach ($previousRequests as $previousRequest) {
      $validationTry=max($validationTry, intval($previousRequest->validationTry));
      $previousRequest->used=1;
      $previousRequest->save();
    }

    $code='';
    for ($i=0; $i<self::CODE_LENGTH; $i++) {
      $code.=random_int(0, 9);
    }
    $request->idUser=$user->id;
    $request->requestDateTime=$now->format('Y-m-d H:i:s');
    $request->codeHash=password_hash($code, PASSWORD_DEFAULT);
    $request->used=0;
    $request->validationTry=$validationTry;
    $saveResult=$request->save();
    if (getLastOperationStatus($saveResult)!='OK') {
      Sql::rollbackTransaction();
      traceLog('OTP - cannot save request for user #'.$user->id);
      return 'SAVE_ERROR';
    }
    Sql::commitTransaction();

    $instance=Parameter::getGlobalParameter('paramDbDisplayName');
    $subjectLabel=i18n('mailOtpSubject');
    if ($subjectLabel=='[mailOtpSubject]') $subjectLabel=i18n('colCode');
    $subject='['.$instance.'] '.$subjectLabel;
    $body=i18n('mailOtpBody', array($user->name, $code, self::VALIDITY_MINUTES));
    if ($body=='[mailOtpBody]') {
      $body=i18n('colUser').' : '.htmlEncode($user->name).'<br/><br/>';
      $body.=i18n('colCode').' : <b>'.htmlEncode($code).'</b><br/><br/>';
      $body.=i18n('colDuration').' : '.self::VALIDITY_MINUTES.' '.i18n('minute');
    }
    if (!sendMail($user->email, $subject, $body, null, null, null, null, null, null, false, false, false, false, false, true)) {
      Sql::query('DELETE FROM '.$table.' WHERE id='.Sql::fmtId($request->id));
      self::clearPendingRequest();
      self::disableParameters();
      traceLog('OTP - mail not sent to user #'.$user->id);
      return 'MAIL_DISABLED';
    }

    setSessionValue('otpRequestId', $request->id);
    setSessionValue('otpRequestUserId', $user->id);
    traceLog('OTP - code sent to user #'.$user->id);
    return 'OK';
  }

  public static function validateCode($user, $code, &$remainingTry=null) {
    $remainingTry=null;
    $requestId=getSessionValue('otpRequestId');
    $requestUserId=getSessionValue('otpRequestUserId');
    if (!$user or !$user->id or !$requestId or $requestUserId!=$user->id) return 'MISSING';
    if (!is_string($code) or !preg_match('/^[0-9]{'.self::CODE_LENGTH.'}$/D', $code)) return 'INVALID_FORMAT';

    $requestProbe=new OtpRequest();
    $connection=Sql::getConnection();
    Sql::beginTransaction();
    Sql::query('SELECT id FROM '.$user->getDatabaseTableName().' WHERE id='.Sql::fmtId($user->id).' FOR UPDATE', $connection);
    Sql::query('SELECT id FROM '.$requestProbe->getDatabaseTableName().' WHERE id='.Sql::fmtId($requestId).' FOR UPDATE', $connection);
    $request=new OtpRequest($requestId);
    if (!$request->id or $request->idUser!=$user->id or $request->used) {
      Sql::rollbackTransaction();
      return 'MISSING';
    }

    $requestDate=new DateTime($request->requestDateTime);
    $age=(new DateTime())->getTimestamp()-$requestDate->getTimestamp();
    if ($age<0 or $age>self::VALIDITY_MINUTES*60) {
      $request->used=1;
      $request->save();
      Sql::commitTransaction();
      self::clearPendingRequest();
      traceLog('OTP - expired code for user #'.$user->id);
      return 'EXPIRED';
    }

    if (!password_verify($code, $request->codeHash)) {
      $request->validationTry=intval($request->validationTry)+1;
      $remainingTry=max(0, self::VALIDATION_TRY_LIMIT-$request->validationTry);
      if ($request->validationTry>=self::VALIDATION_TRY_LIMIT) {
        $request->used=1;
        $user->locked=1;
        $user->loginTry=max(intval($user->loginTry), self::VALIDATION_TRY_LIMIT);
        $user->save();
        self::clearPendingRequest();
      }
      $request->save();
      Sql::commitTransaction();
      traceLog('OTP - invalid code for user #'.$user->id);
      if ($request->used) {
        traceLog('OTP - user #'.$user->id.' locked after too many invalid codes');
        return 'LOCKED';
      }
      return 'INVALID';
    }

    $request->used=1;
    $request->save();
    Sql::query('DELETE FROM '.$requestProbe->getDatabaseTableName().' WHERE idUser='.Sql::fmtId($user->id), $connection);
    Sql::commitTransaction();
    self::clearPendingRequest();
    traceLog('OTP - code validated for user #'.$user->id);
    return 'OK';
  }

  public static function hasPendingRequestForUser($user) {
    return ($user and $user->id and getSessionValue('otpRequestId') and getSessionValue('otpRequestUserId')==$user->id);
  }

  public static function clearPendingRequest() {
    unsetSessionValue('otpRequestId');
    unsetSessionValue('otpRequestUserId');
  }
}
?>
