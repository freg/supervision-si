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

include_once '../tool/projeqtor.php';

$idProject = pq_trim(RequestHandler::getId('idProject'));

if ($idProject == null){
  echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
  echo i18n('messageNoData',array(i18n('Project'))); 
  echo '</div>';
  return ;
} else {
  $projet = new Project($idProject);
}

$headerParameters= i18n("colIdProject") . ' : ' . htmlEncode(SqlList::getNameFromId('Project',$idProject)) . '<br/>';

if (!isset($outMode)) $outMode='html';
$print=false;

if ($outMode=='excel') {
  $headerParameters.=pq_str_replace('- ','<br/>',Work::displayWorkUnit()).'<br/>';
}
include "header.php";

$query= " idProject in " . transformListIntoInClause($projet->getRecursiveSubProjectsFlatList(false, true));

$action = new Action();
$listAction = $action->getSqlElementsFromCriteria(null, null, $query);

$decision = new Decision();
$listDecision = $decision->getSqlElementsFromCriteria(null, null, $query);

$question = new Question();
$listQuestion = $question->getSqlElementsFromCriteria(null, null, $query);

$finalArray = array();

foreach($listAction as $action) {
  $type = new Type($action->idActionType);
  $priority = new Priority($action->idPriority);
  $status = new Status($action->idStatus);
  $affectable = new Affectable($action->idContact);
  $resource= new Resource($action->idResource);

  $row['class'] = get_class($action);
  $row['nature'] = $action->getDatabaseTableName();
  $row['id'] = $action->id;
  $row['name'] = $action->name;
  $row['type'] = $type->name;
  $row['creationDate'] = $action->creationDate;
  $row['priority'] = $priority->name;
  $row['applicant'] = $affectable->name;
  $row['description'] = $action->description;
  $row['status'] = $status->name;
  $row['responsible'] = $resource->name;
  $row['initialDueDate'] = $action->initialDueDate;
  $row['actualDueDate'] = $action->actualDueDate;
  $row['handled'] = $action->handled;
  $row['done'] = $action->done;
  $row['idle'] = $action->idle;
  $row['cancelled'] = $action->cancelled ;

  array_push($finalArray, $row);
}
foreach($listDecision as $decision) {
  $type = new Type($decision->idDecisionType);
  $status = new Status($decision->idStatus);
  $resource= new Resource($decision->idResource);
  $user = new User($decision->idUser);

  $row['class'] = get_class($decision);
  $row['nature'] = $decision->getDatabaseTableName();
  $row['id'] = $decision->id;
  $row['name'] = $decision->name;
  $row['type'] = $type->name;
  $row['creationDate'] = isset($decision->creationDate)?$decision->creationDate:$decision->decisionDate;
  $row['priority'] = '';
  $row['applicant'] = $user->name;
  $row['description'] = $decision->description;
  $row['status'] = $status->name;
  $row['responsible'] = $resource->name;
  $row['initialDueDate'] = '';
  $row['actualDueDate'] = $decision->decisionDate;
  $row['handled'] = '';
  $row['done'] = $decision->done;
  $row['idle'] = $decision->idle;
  $row['cancelled'] = $decision->cancelled ;

  array_push($finalArray, $row);
}

foreach($listQuestion as $question) {
  $type = new Type($question->idQuestionType);
  $status = new Status($question->idStatus);
  $resource= new Resource($decision->idResource);
  $user = new User($decision->idUser);

  $row['class'] = get_class($question);
  $row['nature'] = $question->getDatabaseTableName();
  $row['id'] = $question->id;
  $row['name'] = $question->name;
  $row['type'] = $type->name;
  $row['creationDate'] = $question->creationDate;
  $row['priority'] = '';
  $row['applicant'] = $user->name;
  $des=pq_trim($question->description," \n\r\t\v\x00 ");
  $res=pq_trim($question->result," \n\r\t\v\x00 ");
  if ($outMode=='excel') $row['description'] = $des . (($des!='' and $res!='')?"\n\n":'') . $res;
  else $row['description'] = $des . (($des!='' and $res!='')?"<br><br>":'') . $res;
  $row['status'] = $status->name;
  $row['responsible'] = $resource->name;
  $row['initialDueDate'] = $question->initialDueDate;
  $row['actualDueDate'] = $question->actualDueDate;
  $row['handled'] = $question->handled;
  $row['done'] = $question->done;
  $row['idle'] = $question->idle;
  $row['cancelled'] = $question->cancelled ;

  array_push($finalArray, $row);
}

if (count($finalArray) > 0 ) {
  $pdfStyle=($outMode=='pdf')?'width:150px;max-width:200px;':'width:25%;';
  echo '<table id="reportRida" style="width:95%;margin:auto;" '.excelName().'>';
  echo '<TR>';
  echo '  <TD class="reportTableHeader" style="width:5%" '.excelFormatCell('header',10).'>' . i18n('colNature') . '</TD>';
  echo '  <TD class="reportTableHeader" style="width:2%" '.excelFormatCell('header',10).'>' . i18n('colId') . '</TD>';
  echo '  <TD class="reportTableHeader" style="width:2%" '.excelFormatCell('header',10).'>' . i18n('colIdRida') . '</TD>';
  echo '  <TD class="reportTableHeader" style="'.$pdfStyle.'" '.excelFormatCell('header',40).'>' . i18n('colName') . '</TD>';
  echo '  <TD class="reportTableHeader" style="width:5%" '.excelFormatCell('header',15).'>' . i18n('colType') . '</TD>';
  echo '  <TD class="reportTableHeader" style="width:5%" '.excelFormatCell('header',15).'>' . i18n('colCreationDate') . '</TD>';
  echo '  <TD class="reportTableHeader" style="width:5%" '.excelFormatCell('header',10).'>' . i18n('colPriority') . '</TD>';
  echo '  <TD class="reportTableHeader" style="width:5%" '.excelFormatCell('header',15).'>' . i18n('colOrigin') . '</TD>';
  echo '  <TD class="reportTableHeader" style="'.$pdfStyle.'" '.excelFormatCell('header',40).'>' . i18n('colDescription') . '/'.i18n('colResponse').'</TD>';
  echo '  <TD class="reportTableHeader" style="width:5%" '.excelFormatCell('header',10).'>' . i18n('colIdStatus') . '</TD>';
  echo '  <TD class="reportTableHeader" style="width:5%" '.excelFormatCell('header',20).'>' . i18n('colManager') . '</TD>';
  echo '  <TD class="reportTableHeader" style="width:5%" '.excelFormatCell('header',15).'>' . i18n('colInitialDueDate') . '</TD>';
  echo '  <TD class="reportTableHeader" style="width:5%" '.excelFormatCell('header',15).'>' . i18n('colActualDueDate') . '</TD>';
  echo '  <TD class="reportTableHeader" style="width:2%" '.excelFormatCell('header',10).'>' . i18n('handled') . '</TD>';
  echo '  <TD class="reportTableHeader" style="width:2%" '.excelFormatCell('header',10).'>' . i18n('colDone') . '</TD>';
  echo '  <TD class="reportTableHeader" style="width:2%" '.excelFormatCell('header',10).'>' . i18n('idle') . '</TD>';
  echo '  <TD class="reportTableHeader" style="width:2%" '.excelFormatCell('header',10).'>' . i18n('colCancelled') . '</TD>';
  echo '</TR>';
  
  
  usort($finalArray, 'sortByResourceCreationDate');
  $idRida = 1;
  foreach($finalArray as $row) {
    $lineStyle='vertical-align:top;';
    $bgcolor=null;
    $targetDate=$row['actualDueDate'];
    if ($row['cancelled']==1 or $row['idle']==1) {
      $lineStyle.='background-color: #cccccc;';
      $bgcolor='#cccccc';
    } else if ($row['done']==1) {
      $lineStyle.='background-color: #F0FFF0;';
      $bgcolor='#F0FCF0';
    } else if ($targetDate and $targetDate<date('Y-m-d')) {
      $lineStyle.='background-color: #FFF0F0;';
      $bgcolor='#FCF0F0';
    }
    
    echo '<TR style="vertical-align:top;">';
    echo '  <TD class="reportTableData classLinkName" style="'.$lineStyle.'" '.excelFormatCell('data',10,null,$bgcolor,false,'center','top').' onClick="gotoElement(\''.$row['class'].'\',\''.htmlEncode($row['id']).'\',true)">' . i18n(pq_ucfirst($row['nature'])) . '</TD>';
    echo '  <TD class="reportTableData classLinkName" style="'.$lineStyle.'" '.excelFormatCell('data',5,null,$bgcolor,false,'center','top').' onClick="gotoElement(\''.$row['class'].'\',\''.htmlEncode($row['id']).'\',true)">' . $row['id'] . '</TD>';
    echo '  <TD class="reportTableData" style="'.$lineStyle.'" '.excelFormatCell('data',5,null,$bgcolor,false,'center','top').'>' . $idRida . '</TD>';
    echo '  <TD class="reportTableData" style="'.$lineStyle.$pdfStyle.'text-align:left;padding-left: 5px" '.excelFormatCell('data',50,null,$bgcolor,false,'left','top').'>' . htmlEncode($row['name']) . '</TD>';
    echo '  <TD class="reportTableData" style="'.$lineStyle.'" '.excelFormatCell('data',15,null,$bgcolor,false,'center','top').'>' . $row['type'] . '</TD>';
    echo '  <TD class="reportTableData" style="'.$lineStyle.'" '.excelFormatCell('data',12,null,$bgcolor,false,'center','top').'>' . htmlFormatDate($row['creationDate']) . '</TD>';
    echo '  <TD class="reportTableData" style="'.$lineStyle.'" '.excelFormatCell('data',15,null,$bgcolor,false,'center','top').'>' . $row['priority'] . '</TD>';
    echo '  <TD class="reportTableData" style="'.$lineStyle.'" '.excelFormatCell('data',15,null,$bgcolor,false,'center','top').'>' . $row['applicant'] . '</TD>';
    if($outMode!='excel'){
      echo '  <TD class="reportTableData" style="'.$lineStyle.$pdfStyle.'text-align:left;padding-left: 5px;" '.excelFormatCell('data',50,null,$bgcolor,false,'left','top').'>' . $row['description'] . '</TD>';
    }else{
      echo '  <TD class="reportTableData" style="'.$lineStyle.$pdfStyle.'text-align:left;padding-left: 5px;" '.excelFormatCell('data',50,null,$bgcolor,false,'left','top').'>' . formatText($row['description']) . '</TD>';
    }
    echo '  <TD class="reportTableData" style="'.$lineStyle.'" '.excelFormatCell('data',15,null,$bgcolor,false,'center','top').'>' . $row['status'] . '</TD>';
    echo '  <TD class="reportTableData" style="'.$lineStyle.'" '.excelFormatCell('data',18,null,$bgcolor,false,'center','top').'>' . $row['responsible'] . '</TD>';
    echo '  <TD class="reportTableData" style="'.$lineStyle.'" '.excelFormatCell('data',12,null,$bgcolor,false,'center','top').'>' . htmlFormatDate($row['initialDueDate']) . '</TD>';
    echo '  <TD class="reportTableData" style="'.$lineStyle.'" '.excelFormatCell('data',12,null,$bgcolor,false,'center','top').'>' . htmlFormatDate($row['actualDueDate']) . '</TD>';
    echo '  <TD class="reportTableData" style="'.$lineStyle.'" '.excelFormatCell('data',7,null,$bgcolor,false,'center','top').'>' . $row['handled'] . '</TD>';
    echo '  <TD class="reportTableData" style="'.$lineStyle.'" '.excelFormatCell('data',7,null,$bgcolor,false,'center','top').'>' . $row['done'] . '</TD>';
    echo '  <TD class="reportTableData" style="'.$lineStyle.'" '.excelFormatCell('data',7,null,$bgcolor,false,'center','top').'>' . $row['idle'] . '</TD>';
    echo '  <TD class="reportTableData" style="'.$lineStyle.'" '.excelFormatCell('data',7,null,$bgcolor,false,'center','top').'>' . $row['cancelled'] . '</TD>';
    echo '</TR>';
    
    $idRida += 1;
  }
  echo '</table>';
} else {
    echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
    echo i18n ( 'noDataToDisplay');
    echo '</div>';
}

function sortByResourceCreationDate($a, $b) {
  return $a['creationDate'] <=> $b['creationDate'];
}

function formatText($val) {
    if (isTextFieldHtmlFormatted($val)) {
      $text=new Html2Text($val);
      $val=$text->getText();
      $val=nl2br($val);

    } 
    $val=pq_str_replace("<br />\n<br />", '<br />', $val);
    $val=pq_str_replace("<br />", '', $val);
    $val= htmlEncode($val);
    $val=pq_str_replace('"','""',$val);
  return $val;
}