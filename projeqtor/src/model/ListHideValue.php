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
 * History reflects all changes to any object.
 */ 
require_once('_securityCheck.php');
class ListHideValue extends SqlElement {
  // extends SqlElement, so has $id
  public $id;    // redefine $id to specify its visible place 
  public $nameList;
  public $idProject;
  public $idValue;
  public $idUser;
  
  private static $_cachedRestrictedLists=array();
  private static $_cachedRestrictedValues=array();
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
  
  public static function getRestrictedLists($idProject=null) {
    if (isset(self::$_cachedRestrictedLists[$idProject??'*'])) return self::$_cachedRestrictedLists[$idProject??'*'];
    $list=array();
    $lhv=new ListHideValue();
    $tb=$lhv->getDatabaseTableName();
    $query="select distinct nameList from $tb ";
    $query.=($idProject)?" where idProject=$idProject":'';
    $query.=" order by nameList";
    $result=Sql::query($query);
    if (Sql::$lastQueryNbRows > 0) {
      $line = Sql::fetchLine($result);
      while ($line) {
        $list[]=$line['nameList'];
        $line = Sql::fetchLine($result);
      }
    }
    self::$_cachedRestrictedLists[$idProject??'*']=$list;
    return $list;
  }
  public static function isRestrictedList($list, $idProj=null) {
    if (Parameter::getGlobalParameter('allowListRestrictionOnProject')!='YES') return false;
    $restList=self::getRestrictedLists($idProj);
    if (in_array($list,$restList)) return true;
    else return false;
  }
  public static function getRestrictedValues($list, $idProject) {
    $result=array();
    if (! isset(self::$_cachedRestrictedValues[$list]) ) self::$_cachedRestrictedValues[$list]=array();
    if (isset(self::$_cachedRestrictedValues[$list][$idProject])) return self::$_cachedRestrictedValues[$list][$idProject];
    $lhv=new ListHideValue();
    $values=$lhv->getSqlElementsFromCriteria(array('nameList'=>$list,'idProject'=>$idProject));
    foreach ($values as $lhv) {
      $result[$lhv->idValue]=$lhv->idValue;
    }
    self::$_cachedRestrictedValues[$list][$idProject]=$result;
    return $result;
  }
  
  public static function getListOfValues() {
    $menu=new Menu();
    $result=array();
    $menuList=$menu->getSqlElementsFromCriteria(array("menuClass"=>"ListOfValues"));
    foreach ($menuList as $menu) {
      $class=pq_substr($menu->name,4);
      if (! class_exists($class)) continue;
      if ($class=='Status' or $class=='Role' or $class=='Language' or $class=='InterventionMode' or $class=='PokerComplexity' or $class=='MeasureUnit') continue;
      if (pq_substr($class,0,6)=='Budget') continue;
      if (pq_substr($class,0,8)=='Language') continue;
      if (pq_substr($class,0,7)=='Payment') continue;
      if (pq_substr($class,0,10)=='Predefined') continue;
      $result[$class]=i18n($menu->name);
    }
    if (Plugin::isPluginEnabled("screenCustomization")) {
      require_once "../plugin/screenCustomization/screenCustomizationFunctions.php";
      $lstCustom=screenCustomisationGetCustomClassList();
      foreach ($lstCustom as $key=>$val) {
        $result[$key]=$val.' *';
      }
    }
    asort($result);
    return $result;
  }
  public static function getValuesArray($idProject, $class) {
    $lhv=new ListHideValue();
    $hiddenList=$lhv->getSqlElementsFromCriteria(array('idProject'=>$idProject,'nameList'=>$class));
    $result=array();
    foreach ($hiddenList as $val) {
      $result[$val->idValue]=$val->idValue;
    }
    return $result;
  }

}
?>