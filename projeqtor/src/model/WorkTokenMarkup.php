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
class WorkTokenMarkup extends SqlElement {

  public $id;
  public $idWorkToken;
  public $name;
  public $coefficient;
  public $_isNameTranslatable = true;
  
  private static $_databaseTableName = 'worktokenmarkup';
  private static $_databaseCriteria = array();
  private static $_databaseColumnName = array(
  );
  /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
  */
  /** ========================================================================
   * Return the specific databaseTableName
   * @return String the databaseTableName
  */
  protected function getStaticDatabaseTableName() {
    $paramDbPrefix=Parameter::getGlobalParameter('paramDbPrefix');
    return $paramDbPrefix . self::$_databaseTableName;
  }
  
  /** ========================================================================
   * Return the specific database criteria
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseCriteria() {
    return self::$_databaseCriteria;
  }
  
  /** ==========================================================================
   * Construct
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
  
  protected function getStaticDatabaseColumnName() {
    return self::$_databaseColumnName;
  }
  
  
  public static function drawWorkTokenMarkup($obj,$print){
    $workTokenMarkup= new WorkTokenMarkup();
    $critArray= array("idWorkToken"=>$obj->id);
    $lstWorkTokenMarkup= $workTokenMarkup->getSqlElementsFromCriteria($critArray);
    $canDelete=securityGetAccessRightYesNo('menu'.get_class($obj), 'delete', $obj)=="YES";
    $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
    $canCreate=securityGetAccessRightYesNo('menu'.get_class($obj), 'create', $obj)=="YES";
    if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
      $canCreate=false;
      $canUpdate=false;
      $canDelete=false;
    }
    if ($obj->idle==1) {
      $canUpdate=false;
      $canCreate=false;
      $canDelete=false;
    }
    echo '<table style="width:90%;margin-left:50px;margin-top:15px;">';
    echo '<tr><td colspan=2 style="width:100%;"><table style="height:100%;width:100%;">';
    echo '<tr>';
    if (!$print) {
      echo '<td class="assignHeader" style="width:5%">';
      if ($obj->id!=null and !$print  and !$obj->idle) {
        echo '<a onClick="addWorkTokenMarkup(\''.$obj->id.'\');" title="'.i18n('addWorkTokenMarkup').'" /> '.formatSmallButton('Add').'</a>';
      }
      echo '</td>';
    }
    echo  '<td colspan="2" class="assignHeader" style="width:12%">'.i18n('colSurchargeSituation').'</td>';
    echo'</tr>';
    foreach ($lstWorkTokenMarkup as $val){
      $workTokenClientContractWork=SqlElement::getSingleSqlElementFromCriteria('WorkTokenClientContractWork', array('idWorkTokenMarkup'=>$val->id));
      $used=($workTokenClientContractWork->id)?1:0;
      echo '<tr  style="width:100%;height:100%;text-align:right;">';
      echo    '<td class="assignData" style="width:15%;white-space:nowrap;text-align:center;">';
      if ($canUpdate) {
        echo '<a onClick="editTokenMarkUp(\''.$val->id.'\','.$used.');" '.'title="'.i18n('editWorkTokenMarkup').'" > '.formatSmallButton('Edit').'</a>';
      }
      if ($canDelete and $used==0) {
        echo '<a onClick="removeTokenMarkUp(\''.$val->id.'\');" '.'title="'.i18n('removeWorkTokenMarkup').'" > '.formatSmallButton('Remove').'</a>';
      }
      echo  '</td>';
      echo  '<td class="assignData" style="width:50%;text-align:left;">'.$val->name.'</td>';
      echo  '<td class="assignData" style="width:35%;text-align:center;">'.htmlDisplayNumericWithoutTrailingZeros($val->coefficient,1).'</td>';
      echo '</tr>';
    }
    echo '</table></td></tr>';
  }
}
?>