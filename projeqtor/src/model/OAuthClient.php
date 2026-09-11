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

/** ============================================================================
 * The Diff implementation has been created by Stephen Morley
 * Source of the Diff class can be found at :
 *     http://code.stephenmorley.org/php/diff-implementation/
 * The current file just includes Stephen's Class file
 * to preserve Class management of ProjeQtOr
 * ============================================================================= */

require_once('_securityCheck.php'); 

class OAuthClient extends SqlElement {

  public $id;
  public $name;
  public $oauthSource;
  public $idUser;
  public $tenantId;
  public $clientId;
  public $clientSecret;
  public $scope;
  public $token;
  public $refreshToken;
  public $tokenDateTime;
  public $tokenExpires;
  const DEBUG=false;
  
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
  
  function getAccesUrl() {
    if ($this->oauthSource=='office365' or $this->oauthSource=='office' or $this->oauthSource=='graph') {
      $authUri = 'https://login.microsoftonline.com/'.$this->tenantId
               . '/oauth2/v2.0/authorize?client_id='.$this->clientId
               . '&scope='.$this->getScope()
               . '&redirect_uri=' .$this->getRedirectUri()
               . '&response_type=code'
               . '&approval_prompt=auto';
      return $authUri;
    }
  }
  function getTokenUrl() {
    if ($this->oauthSource=='office365' or $this->oauthSource=='office' or $this->oauthSource=='graph') {
      return "https://login.microsoftonline.com/$this->tenantId/oauth2/v2.0/token";
    }
  }
  
  public function getScope($forToken=false) {

    $scope="";
    if ($this->scope) $scope=$this->scope;
    else if ($this->oauthSource=='office365') $scope='https://outlook.office365.com/IMAP.AccessAsUser.All';
    else if ($this->oauthSource=='office') $scope='https://outlook.office.com/IMAP.AccessAsUser.All';
    else if ($this->oauthSource=='graph') $scope='https://graph.microsoft.com/IMAP.AccessAsUser.All';
    if ($forToken) {
      if ($this->oauthSource=='office365' or $this->oauthSource=='office' or $this->oauthSource=='graph') $scope.=' offline_access';
    }
    return $scope;
  }
  public function getRedirectUri() {
    return SqlElement::getBaseUrl()."/tool/getAccessTokenRedirect.php";
  }
  
  public function initializeToken() {
    $result='ERROR';
    $message="OAUTH2 RESULT ERROR<br/>Unknown OAUTH source $this->oauthSource";
    $this->scope=null; // Force refresh of scope - mandatory if oauthSource is changed
    if ($this->oauthSource=='office365' or $this->oauthSource=='office' or $this->oauthSource=='graph') {
      $code=RequestHandler::getValue('code');
      $session=RequestHandler::getValue('session_state');
      $url=$this->getTokenUrl();
      $param_post_curl = [
          'client_id'=>$this->clientId,
          'scope'=>$this->getScope(true),
          'code'=>$code,
          'session_state'=>$session,
          'client_secret'=>$this->getSecret(),
          'redirect_uri'=>$this->getRedirectUri(),
          'grant_type'=>'authorization_code' ];
      $ch=curl_init();
      curl_setopt($ch,CURLOPT_URL,$url);
      curl_setopt($ch,CURLOPT_POST, true);
      curl_setopt($ch,CURLOPT_POSTFIELDS, $param_post_curl);
      curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
      curl_setopt($ch,CURLOPT_RETURNTRANSFER, true);
      curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
      $oResult=curl_exec($ch);
      $http_code=curl_getinfo($ch, CURLINFO_HTTP_CODE);
      if (curl_errno($ch) or !$oResult) {
        errorLog("Error when callin curl $url");
        errorLog("http code : $http_code");
        errorLog(curl_error($ch));
        $message="OAUTH2 RESULT ERRORError received when calling $url";
      } else {
        $arrayJson=json_decode($oResult,true);
        $token=$arrayJson['access_token']??'';
        $refresh=$arrayJson['refresh_token']??'';
        $expires=$arrayJson['ext_expires_in']??'3600';
        if (! $token or ! $refresh) {
          errorLog("TOKEN='.$token");
          errorLog('REFRESH='.$refresh);
          errorLog('EXPIRES='.$expires);
          $message="OAUTH2 RESULT ERROR<br/>Incorrect result format";
          if (! $token) $message.="<br/> no token found";
          if (! $refresh) $message.="<br/> no refresh token found";
        } else {
          $this->setToken($token);
          $this->setRefreshToken($refresh);
          $this->tokenDateTime=date("Y-m-d H:i:s");
          $this->tokenExpires=time()+intval($expires);
          $resSave=$this->save();
          $message=i18n("treatmentEnded");
          $result='OK';
        }
      }
    }
    return array('result'=>$result, 'message'=>$message);
  }
  public function refreshToken() {
    $url= $this->getTokenUrl();
    $param_post_curl = [
        'client_id'=>$this->clientId,
        'client_secret'=>$this->getSecret(),
        'refresh_token'=>$this->getRefreshToken(),
        'grant_type'=>'refresh_token' ];
    $ch=curl_init();
    
    curl_setopt($ch,CURLOPT_URL,$url);
    curl_setopt($ch,CURLOPT_POST, true);
    curl_setopt($ch,CURLOPT_POSTFIELDS, $param_post_curl);
    curl_setopt($ch,CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch,CURLOPT_SSL_VERIFYPEER, false);
    
    $oResult=curl_exec($ch);
    $arrayJson=json_decode($oResult,true);
    $token=$arrayJson['access_token']??'';
    $expires=$arrayJson['ext_expires_in']??'3600';
    if (! $token) {
      errorLog("Cannot Refresh Token");
      errorLog("TOKEN='.$token");
      errorLog('EXPIRES='.$expires);
      errorLog("Result=".$oResult);
      $message="OAUTH2 RESULT ERROR<br/>Incorrect result format";
      if (! $token) $message.="<br/> no token found";
      return null;
    } else {
      $this->setToken($token);
      $this->tokenDateTime=date("Y-m-d H:i:s");
      $this->tokenExpires=time()+intval($expires);
      $resSave=$this->save();
      $message=i18n("treatmentEnded");
      $result='OK';
      debugTraceLog("Oauth - Token refreshed at $this->tokenDateTime for extended $expires seconds");
      return $token;
    }
  }
  public function getToken($forDisplayOnly=false) {
    $validity=$this->leftBeforeExpires();
    if ($validity>300 or $forDisplayOnly) $token=$this->token;
    else $token=$this->refreshToken();
    return decryptPwd($token);
  }
  public function setToken($token) {
    $this->token=encryptPwd($token);
  }
  public function getSecret() {
    return decryptPwd($this->clientSecret);
  }
  public function setSecret($secret) {
    $this->clientSecret=encryptPwd($secret);
  }
  public function getRefreshToken() {
    return decryptPwd($this->refreshToken);
  }
  public function setRefreshToken($refreshToken) {
    $this->refreshToken=encryptPwd($refreshToken);
  }
  
  public function save() {
    $old=$this->getOld();
    if (!$this->scope or $old->oauthSource!=$this->oauthSource) $this->scope=$this->getScope();
    return parent::save();
  }
  public function delete() {
    return parent::delete();
  }
  
  public function isExpired() {
    if (intval($this->tokenExpires)>time()) return false;
    else return true;
  }
  
  public function leftBeforeExpires() {
    if (intval($this->tokenExpires)>time()) return intval($this->tokenExpires)-time();
    else return 0;
  }
  public function getExpiresLabel() {
    if (!$this->tokenExpires) return 'not set';
    if ($this->isExpired()) return 'expired';
    $val=$this->leftBeforeExpires();
    if ($val<60*2) return $val.' seconds';
    if ($val<+60*60*2) return round($val/60,1).' minutes';
    if ($val<+24*60*60*2) return round($val/(60*60),1).' hours';
    return round($val/(24*60*60),1).' days';
  }
  public function getTokenLabel() {
    $token=$this->getToken(true); // True = for display value - will not call refresh
    if (!$token) return i18n('valueNotSet');
    if (! self::DEBUG) return i18n('valueCorrect');
    return $token;
  }
  public function getRefreshTokenLabel() {
    $refresh=$this->getRefreshToken();
    if (!$refresh) return i18n('valueNotSet');
    if (! self::DEBUG) return i18n('valueCorrect');
    return $refresh;
  }
}
?>