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
 * Save some information to session (remotely).
 */

require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/dynamicListTestCase.php');
$idProject=pq_trim($_REQUEST['idProject']);
Security::checkValidId($idProject);
$idProduct=pq_trim($_REQUEST['idProduct']);
Security::checkValidId($idProduct);

$selectedProject=getSessionValue('project');
if(pq_strpos($selectedProject, ",")){
	$selectedProject="*";
}

$selected="";
if (pq_array_key_exists('selected', $_REQUEST)) {
	$selected=$_REQUEST['selected'];
}
$selectedArray=pq_explode('_',$selected); // Note: elements are validated to be numeric in SqlElement base constructor
$obj=new TestCase();

$where = 'idle = 0';
if ($selectedProject != '*') {
	$where .= ' and idProject in (0, '.$selectedProject.') ';
}
if (pq_trim($idProduct)) {
  if (property_exists($obj,'idProduct')) $where .=' and (idProduct is Null  or idProduct = '.$idProduct.')';
  else if (property_exists($obj,'idProductOrComponent')) $where .=' and (idProductOrComponent is Null   or idProductOrComponent = '.$idProduct.')';
  else if (property_exists($obj,'idComponent')) $where .=' and (idProductOrComponent is Null   or idComponent = '.$idProduct.')';
}
$list=$obj->getSqlElementsFromCriteria(null,false,$where, null,true);//ne trouve rien -> regarder html.php
foreach ($selectedArray as $selected) {
  if ($selected and ! pq_array_key_exists("#" . $selected, $list)) {
	  $list["#".$selected]=new TestCase($selected);
  }
}

?>
<select xdojoType="dijit.form.MultiSelect" multiple
  id="testCaseRunTestCaseList" name="testCaseRunTestCaseList[]" 
  class="selectList" value="" required="required" size="10"
  onchange="enableWidget('dialogTestCaseRunSubmit');"  
  ondblclick="saveTestCaseRun();" >
 <?php
 foreach ($list as $lstObj) {
   echo "<option value='$lstObj->id'" . ((in_array($lstObj->id,$selectedArray))?' selected ':'') . ">#".htmlEncode($lstObj->id)." - ".htmlEncode($lstObj->name)."</option>";
 }
 ?>
</select>