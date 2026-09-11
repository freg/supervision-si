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
 * Save a checklistdefinition line : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */
require_once "../tool/projeqtor.php";

// if(!isset($checklistDefinitionId))$checklistDefinitionId=trim($_REQUEST['checklistDefinitionId']); // validated to be numeric value in SqlElement base constructor

// if(!isset($checklistObjectClass))$checklistObjectClass=$_REQUEST['checklistObjectClass'];
Security::checkValidClass($checklistObjectClass);

// if(!isset($checklistObjectId))$checklistObjectId=trim($_REQUEST['checklistObjectId']);
Security::checkValidId($checklistObjectId);

$checklistDefinition=new ChecklistDefinition($checklistDefinitionId);
// if(!isset($done)){
//   $done=(RequestHandler::isCodeSet('done'))?RequestHandler::getValue('done'):'false';
// }
// $statusLine='';
foreach($checklistDefinition->_ChecklistDefinitionLine as $line) {
//     if(isset($isMultiple)){
      $required = $line->required;
      $CheckList = Checklist::getSingleSqlElementFromCriteria('Checklist', array('refType'=>$checklistObjectClass, 'refId'=>$checklistObjectId));
      $lineValue = ChecklistLine::getSingleSqlElementFromCriteria('ChecklistLine', array('idCheckList'=>$CheckList->id ,'idCheckListDefinitionLine'=>$line->id));
//     }else{
//       $required=(RequestHandler::isCodeSet('isRequired_'.$line->id))?RequestHandler::getValue('isRequired_'.$line->id):0;
//     }
	$checkedCpt=0;
	for ($i=1; $i<=5; $i++) {
// 		if(isset($isMultiple)){
		  $valueName="value0".$i;
		  if ($lineValue->$valueName) {
		  	$checkedCpt++;
		  }
// 		}else{
// 		  $checkName="check_".$line->id."_".$i;
// 		  $valueName="value0".$i;
// 		  if (isset($_REQUEST[$checkName])) {
// 		  	$checkedCpt++;
// 		  }
// 		}
	}
	if($checkedCpt==0 and $required==1 and $done=='on'){
	  if(!isset($idStatus) and RequestHandler::getValue('idStatus')){
	    $idStatus=RequestHandler::getValue('idStatus');
	  }
	  if(!isset($idStatus)){
	    $idStatus='';
	  }
  	  $statusObj= new Status($idStatus);
  	  if(!isset($result))$result='<b>' . i18n('messageInvalidControls') . '</b><br/>';
      $result.='<br/>' . i18n('errorRequiredLine',array($line->name,$statusObj->name));
  	  $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
  	  $result .= '<input type="hidden" id="lastOperation" value="update" />';

// 	  if(isset($isMultiple)){
// 	   $lineName = $line->name;
// 	   $chechListResult = true;
// 	  }
	}
}


?>