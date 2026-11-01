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

require_once('_securityCheck.php');
class RaciFunction extends SqlElement {

  // extends SqlElement, so has $id
  public $id;    // redefine $id to specify its visible place
  public $idRaciModel;
  public $name;
  public $sortOrder;

  public $_noHistory=true; // Will never save history for this object

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

  /** ============================================================================
   * Control before save
   * @return String "OK" or the control message
   */
  public function control() {
  	$result="";
  	$name=pq_trim($this->name);
  	if ($this->idRaciModel and $name) {
  	  $crit="idRaciModel=".Sql::fmtId($this->idRaciModel)." and name=".Sql::str($name);
  	  if ($this->id) $crit.=" and id<>".Sql::fmtId($this->id);
  	  $dup=$this->getSqlElementsFromCriteria(null, false, $crit);
  	  if (count($dup)>0) {
  	    $result.='<br/>'.i18n('raciFunctionAlreadyInModel');
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
  /** ==========================================================================
   * Sort function on sortOrder then name.
   */
  public static function sort($a, $b) {
  	if ($a->sortOrder==$b->sortOrder) {
  	  return strcasecmp($a->name, $b->name);
  	}
  	return ($a->sortOrder < $b->sortOrder)?-1:1;
  }

}?>

