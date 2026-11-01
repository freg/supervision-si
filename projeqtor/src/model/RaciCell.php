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
class RaciCell extends SqlElement {

  // extends SqlElement, so has $id
  public $id;    // redefine $id to specify its visible place
  public $idRaciModel;
  public $idRaciFunction;
  public $idRaciRole;
  public $value; // one of R / A / C / I

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

  /** ==========================================================================
   * @see persistence/SqlElement#save()
   * @return String the return message
   */
  public function save($fromParameter=false) {
  	$result=parent::save($fromParameter);
  	if (pq_strpos($result,"OK")!==false and $this->value=='A' and $this->idRaciFunction) {
  	  // Only one Accountable per function : remove any other 'A' cell on the same row
  	  $crit="idRaciFunction=".Sql::fmtId($this->idRaciFunction)." and value='A' and id!=".Sql::fmtId($this->id);
  	  $others=$this->getSqlElementsFromCriteria(null,false,$crit);
  	  foreach ($others as $other) {
  	    $cell=new RaciCell($other->id);
  	    $cell->delete();
  	  }
  	}
  	return $result;
  }

}?>

