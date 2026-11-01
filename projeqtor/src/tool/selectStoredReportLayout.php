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
 * Save a note : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */

require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/selectStoredReportLayout.php');
$user=getSessionUser();
$comboDetail=false;
if (pq_array_key_exists('comboDetail',$_REQUEST)) {
  $comboDetail=true;
}

if (! $comboDetail) {
  if (! $user->_arrayReportLayouts) {
    $user->_arrayReportLayouts=array();
  }
}

// Get the layout info
if (! pq_array_key_exists('idReportLayout',$_REQUEST)) {
  throwError('idReportLayout parameter not found in REQUEST');
}
$idReportLayout=$_REQUEST['idReportLayout'];
if (! pq_array_key_exists('reportLayoutObjectClass',$_REQUEST)) {
  throwError('reportLayoutObjectClass parameter not found in REQUEST');
}
$reportLayoutObjectClass=$_REQUEST['reportLayoutObjectClass'];

$reportLayout=new ReportLayout($idReportLayout);
$reportLayoutArray=array("id"=>$reportLayout->id,"comment"=>$reportLayout->comment,"name"=>$reportLayout->scope);

$user->_arrayReportLayouts[$reportLayoutObjectClass]=$reportLayoutArray;
$user->_arrayReportLayouts[$reportLayoutObjectClass . "ReportLayoutName"]=$reportLayout->scope;

$report = Report::getSingleSqlElementFromCriteria('Report', array('referTo'=>$reportLayoutObjectClass, 'name'=>$reportLayout->scope));
?>
<table width="100%" style="border: 1px solid grey;">
<tr>
  <td class='dialogLabel' style="white-space: nowrap;">
    <label for="reportLayoutNameDisplay" style="position:relative;top:5px;"><?php echo i18n("reportLayoutName").'&nbsp;&nbsp;'?></label>
    <div type="text" dojoType="dijit.form.ValidationTextBox" name="reportLayoutNameDisplay" id="reportLayoutNameDisplay"
      style="width:500px;" trim="true" maxlength="100" class="input" value="<?php echo $reportLayout->scope;?>">
  </td>
  <?php if($report->id){?>
  <td style="text-align:center">
    <button title="<?php echo i18n('showReport')?>"   
     dojoType="dijit.form.Button"  
     id="dialogReportLayoutShowReport" name="dialogReportLayoutShowReport" class="resetMargin roundedButton notButton" style="height:24px;width:32px;margin-top:-1px;"
     iconClass="dijitButtonIcon dijitButtonIconDisplay imageColorNewGui" showLabel="false"> 
     <script type="dojo/connect" event="onClick" args="evt">showPrint('../report/<?php echo $report->file; ?>','favorite',null,null,'<?php echo $report->orientation; ?>');</script>
    </button>
  </td>
  <?php }?>
  <td style="text-align:center">
    <button title="<?php echo i18n('saveReportLayout')?>"   
     dojoType="dijit.form.Button"  
     id="dialogReportLayoutSave" name="dialogReportLayoutSave" class="resetMargin roundedButton notButton" style="height:24px;width:32px;margin-top:-1px;"
     iconClass="dijitButtonIcon dijitButtonIconSave imageColorNewGui" showLabel="false"> 
     <script type="dojo/connect" event="onClick" args="evt">saveReportLayout();</script>
    </button>
  </td>
</tr>
<tr>
  <td class='dialogLabel' style="white-space: nowrap;">
    <label for="reportLayoutComment" style="position:relative;top:5px;"><?php echo i18n("colComment").'&nbsp;&nbsp;'?></label>
    <textarea dojoType="dijit.form.Textarea" 
    id="reportLayoutComment" name="reportLayoutComment"
    style="width: 512px;height:100px;"
    maxlength="4000"
    class="input"><?php echo $reportLayout->comment;?></textarea>   
  </td>
</tr>
</table>