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
 * PasswordResetRequest
 */
require_once('_securityCheck.php');

#[AllowDynamicProperties]
class PasswordResetRequest extends SqlElement {
  public $id;
  public $idUser;
  public $email;
  public $requestDateTime;
  public $token;
  public $used;
  
  private static $_fieldsAttributes=array(
      "id"=>"",
      "idUser"=>"required",
      "email"=>"required",
      "requestDateTime"=>"required",
      "token"=>"required",
      "used"=>""
  );
  
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
  }
  function __destruct() {
    parent::__destruct();
  }
  
  protected function getStaticFieldsAttributes() {
    return self::$_fieldsAttributes;
  }
  
  public function control() {
    $result = parent::control();
    if ($result=="OK") $result="";
    if (! $this->idUser) {
      $result.= '<br/>' . i18n('messageMandatory', array(i18n('colIdUser')));
    }
    if (! $this->email) {
      $result.= '<br/>' . i18n('messageMandatory', array(i18n('colEmail')));
    }
    if (! $this->token) {
      $result.= '<br/>' . i18n('messageMandatory', array(i18n('colToken')));
    }
    if ($result=="") $result="OK";
    return $result;
  }
}
?>
