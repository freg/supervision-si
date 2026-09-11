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

// Header
include_once '../tool/projeqtor.php';
include_once('../tool/formatter.php');

$paramProject=pq_trim(RequestHandler::getId('idProject',false));
$paramClient=pq_trim(RequestHandler::getId('idClient',false));
$paramShowIdle = RequestHandler::getBoolean('showClosedItems');
$paramshowReference = RequestHandler::getBoolean('showReference');
// Header
$headerParameters="";
if ($paramProject!="") {
  $headerParameters.= i18n("colIdProject") . ' : ' . htmlEncode(SqlList::getNameFromId('Project', $paramProject)) . '<br/>';
}
if ($paramClient!="") {
  $headerParameters.= i18n("colIdClient") . ' : ' . htmlEncode(SqlList::getNameFromId('Client', $paramClient)) . '<br/>';
}

if (isset($outMode) and $outMode=='excel') {
  $headerParameters.=pq_str_replace('- ','<br/>',Work::displayWorkUnit()).'<br/>';
}
include "header.php";

//Request
$where=getAccesRestrictionClause('Command',false,false,true,true);
if ($paramProject!='') {
  $where.=  " and idProject in " . getVisibleProjectsList(true, $paramProject) ;
}
if( $paramClient !=''){
  $where.=  " and idClient = " . $paramClient ;
}
if(!$paramShowIdle){
  $where.=  " and idle = 0 " ;
}
$order=" idProject asc ";
$com = new Command();
$lstCmd = $com->getSqlElementsFromCriteria(null,false, $where, $order);
$tabCmd = array();
$tabIdCmd = array();
$tabBill = array();
$tabLink = array();

$link = new Link();
$whereLink = " ref1Type = 'Command' and ref2Type = 'Bill' or  ref1Type = 'Bill' and ref2Type = 'Command' ";
$lstLink = $link->getSqlElementsFromCriteria(null,false, $whereLink);

foreach ( $lstCmd as $cmd){
  $tabCmd[$cmd->idProject][$cmd->id] = $cmd ;
  $tabIdCmd[$cmd->id]=$cmd->id;
}

foreach ($lstLink as $lk){
  if($lk->ref2Type == 'Command' ){
    if(isset($tabIdCmd[$lk->ref2Id])){
      $tabBill[$lk->ref2Id][$lk->id]=$lk->ref1Id;
    }
  }
  if($lk->ref1Type == 'Command'){
    if(isset($tabIdCmd[$lk->ref1Id])){
      $tabBill[$lk->ref1Id][$lk->id]=$lk->ref2Id;
    }
  }
}
echo '<table  width="95%" align="center">';

$col1="11";
$col2="11";
$col3="6";
if($paramshowReference){
  $col1="10";
  $col2="10";
  $col3="5";
}

$tabProject = array();
$tabProjectWbs = array();
foreach ($tabCmd as $idProject=>$cm){
  $tabProject[$idProject]=$idProject;
}
foreach ($tabProject as $idProj){
  $wbsSortable = SqlElement::getSingleSqlElementFromCriteria('ProjectPlanningElement', array('idProject'=>$idProj,'refType'=>'Project','refId'=>$idProj));
  $tabProjectWbs[$idProj]=$wbsSortable->wbsSortable;
}
asort($tabProjectWbs);
$tabCmdOrder = $tabCmd;
foreach ($tabCmdOrder as $idProject=>$cm){
  $tabCmdOrder[$tabProjectWbs[$idProject]][$idProject]=$cm;
  unset($tabCmdOrder[$idProject]);
}
ksort($tabCmdOrder);
//title    
echo'<tr>';
echo' <td class="reportTableHeader"  style="width:'.$col1.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('colIdProject')).'</td>';
if($paramshowReference){
  echo' <td class="reportTableHeader"  style="width:'.$col2.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('colReference')).'</td>';
}
echo' <td class="reportTableHeader"  style="width:'.$col2.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('Command')).'</td>';
echo' <td class="reportTableHeader"  style="width:'.$col3.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('colDate')).'</td>';
echo' <td class="reportTableHeader"  style="width:'.$col2.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('Status')).'</td>';
echo' <td class="reportTableHeader"  style="width:'.$col3.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('commandAmount')).'</td>';
if($paramshowReference){
  echo' <td class="reportTableHeader"  style="width:'.$col2.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('colReference')).'</td>';
}
echo' <td class="reportTableHeader"  style="width:'.$col2.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('Invoice')).'</td>';
echo' <td class="reportTableHeader"  style="width:'.$col3.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('colDate')).'</td>';
echo' <td class="reportTableHeader"  style="width:'.$col2.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('Status')).'</td>';
echo' <td class="reportTableHeader"  style="width:'.$col3.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('colBillAmount')).'</td>';
echo' <td class="reportTableHeader"  style="width:'.$col2.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('restOfCommand')).'</td>';
echo'</tr>';
foreach ($tabCmdOrder as $wbs=>$objId){
  foreach ($objId as $obj){
    foreach ($obj as $val){
      $nbRowSpan = 1;
      $commandRest = $val->totalUntaxedAmount;
      if(isset($tabBill[$val->id])){
        $nbRowSpan = 0;
        foreach ($tabBill[$val->id] as $idTab=>$billId){
          $newBill = new Bill($billId);
          if($newBill->cancelled){
            unset($tabBill[$val->id][$idTab]);
            if(!$tabBill[$val->id])unset($tabBill[$val->id]);
            continue;
          }
          $nbRowSpan++;
          $commandRest -= $newBill->untaxedAmount;
        }
      }
      echo'<tr>';
      if($nbRowSpan==0)$nbRowSpan=1;
      echo' <td  rowspan="'.$nbRowSpan.'" class="reportTableData"  style="padding:4px;text-align:left;width:'.$col1.'%;" 
          '.excelFormatCell('data',null,null,null,null,'left').'>'.htmlEncode(SqlList::getNameFromId('Project', $val->idProject)).'</td>';
      if($paramshowReference){
        echo' <td  rowspan="'.$nbRowSpan.'" class="reportTableData"  style="padding:4px;text-align:left;width:'.$col2.'%;" 
            '.excelFormatCell('data',null,null,null,null,'left').'>'.htmlEncode($val->reference).'</td>';
      }
      echo' <td  rowspan="'.$nbRowSpan.'" class="reportTableData"  style="padding:4px;text-align:left;width:'.$col2.'%" 
          '.excelFormatCell('data',null,null,null,null,'left').'>'.htmlEncode($val->name).'</td>';
      
      echo' <td  rowspan="'.$nbRowSpan.'" class="reportTableData"  style="padding:4px;text-align:center;width:'.$col3.'%" 
          '.excelFormatCell('data').'>'.(($outMode=='excel')?$val->receptionDate:htmlFormatDate($val->receptionDate)).'</td>';
      
      if(($outMode=='excel')){
        $status=new Status($val->idStatus);
        $color=$status->color;
        $foreColor='#000000';
        if (pq_strlen($color)==7) {
          $red=pq_substr($color, 1, 2);
          $green=pq_substr($color, 3, 2);
          $blue=pq_substr($color, 5, 2);
          $light=(0.3)*base_convert($red, 16, 10)+(0.6)*base_convert($green, 16, 10)+(0.1)*base_convert($blue, 16, 10);
          if ($light<128) {
            $foreColor='#FFFFFF';
          }
        }
        echo' <td  rowspan="'.$nbRowSpan.'" class="reportTableData"  style="padding:4px;text-align:left;width:'.$col2.'%" '.excelFormatCell('data',20,$foreColor,$color).'>';
        echo $status->name.'</td>';
      }else{
        echo' <td  rowspan="'.$nbRowSpan.'" class="reportTableData"  style="padding:4px;text-align:left;width:'.$col2.'%" ><div>'.formatColor('Status', $val->idStatus).'</div></td>';
      }
      
      
      echo' <td  rowspan="'.$nbRowSpan.'" class="reportTableData"  style="padding:4px;width:'.$col3.'%;text-align:right;" 
          '.excelFormatCell('data',null,null,null,null,null,null,null,'work').'>'.(($outMode=='excel')?$val->totalUntaxedAmount:htmlDisplayCurrency($val->totalUntaxedAmount)).'</td>';
      if(isset($tabBill[$val->id])){
        $i=0;
        foreach ($tabBill[$val->id] as $billId){
          $newBill = new Bill($billId);
          if($i>0)echo' <tr> ';
          $i++;
          if($paramshowReference){
            echo' <td  class="reportTableData"  style="padding:4px;text-align:left;width:'.$col2.'%;" '.excelFormatCell('data',null,null,null,null,'left').'>'
                .$newBill->reference.'</td>';
          }
          echo' <td   class="reportTableData"  style="padding:4px;text-align:left;width:'.$col2.'%;" 
              '.excelFormatCell('data',null,null,null,null,'left').'>'.htmlEncode($newBill->name).'</td>';
          
          echo' <td  class="reportTableData"  style="padding:4px;text-align:center;width:'.$col3.'%" 
              '.excelFormatCell('data').'>'.(($outMode=='excel')?$newBill->date:htmlFormatDate($newBill->date)).'</td>';
          
          if(($outMode=='excel')){
            $status=new Status($newBill->idStatus);
            $color=$status->color;
            $foreColor='#000000';
            if (pq_strlen($color)==7) {
              $red=pq_substr($color, 1, 2);
              $green=pq_substr($color, 3, 2);
              $blue=pq_substr($color, 5, 2);
              $light=(0.3)*base_convert($red, 16, 10)+(0.6)*base_convert($green, 16, 10)+(0.1)*base_convert($blue, 16, 10);
              if ($light<128) {
                $foreColor='#FFFFFF';
              }
            }
            echo' <td class="reportTableData"  style="padding:4px;text-align:left;width:'.$col2.'%" '.excelFormatCell('data',20,$foreColor,$color).'>';
            echo $status->name.'</td>';
          }else{
            echo' <td class="reportTableData"  style="padding:4px;width:'.$col3.'%" ><div>'.formatColor('Status', $newBill->idStatus).'</div></td>';
          }
          
          echo' <td   class="reportTableData"  style="padding:4px;width:'.$col3.'%;text-align:right;" 
              '.excelFormatCell('data',null,null,null,null,null,null,null,'work').'>'.(($outMode=='excel')?$newBill->untaxedAmount:htmlDisplayCurrency($newBill->untaxedAmount)).'</td>';
          
          $backGround = "";
          if($commandRest < 0)$backGround = " background:#FFDDDD;" ;
          $backgroundExcel=($backGround!="")?"#FFDDDD":"";
          if($i==1){
            echo' <td  rowspan="'.$nbRowSpan.'" class="reportTableData"  style="padding:4px;width:'.$col2.'%;text-align:right;'.$backGround.'" 
                '.excelFormatCell('data',null,null,$backgroundExcel,null,null,null,null,'work').'>'.(($outMode=='excel')?$commandRest:htmlDisplayCurrency($commandRest)).'</td>';
          }
          echo'</tr>';
        }
      }else{
        if($paramshowReference){
          echo' <td  class="reportTableData"  style="width:'.$col2.'%"></td>';
        }
        echo' <td  rowspan="'.$nbRowSpan.'" class="reportTableData"  style="padding:4px;width:'.$col2.'%"></td>';
        echo' <td  rowspan="'.$nbRowSpan.'" class="reportTableData"  style="padding:4px;width:'.$col3.'%"></td>';
        echo' <td  rowspan="'.$nbRowSpan.'" class="reportTableData"  style="padding:4px;width:'.$col2.'%"></td>';
        echo' <td  rowspan="'.$nbRowSpan.'" class="reportTableData"  style="padding:4px;width:'.$col3.'%"></td>';
        $backGround = "";
        if($commandRest < 0)$backGround = " background:#FFDDDD;" ;
        $backgroundExcel=($backGround!="")?"#FFDDDD":"";
        echo' <td  rowspan="'.$nbRowSpan.'" class="reportTableData"  style="padding:4px;width:'.$col2.'%;text-align:right;'.$backGround.'" '.excelFormatCell('data',null,null,$backgroundExcel,null,null,null,null,'work').'>'
            .(($outMode=='excel')?$commandRest:htmlDisplayCurrency($commandRest)).'</td>';
        echo'</tr>';
      }
    }
  }
}


echo '</table>';

?>
